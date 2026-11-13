"""Kelime çalışması: oturum hazırlama, cevap kaydı, istatistikler."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.content import repository as repo
from app.learning import srs
from app.models.user import ReviewHistory, ReviewItem, utcnow
from app.services import progress

DIRECTIONS = ("en_tr", "tr_en")
SOURCES = ("level", "list", "due")


def _aware(value: datetime) -> datetime:
    """SQLite saat dilimi bilgisini saklamaz; okunan değerler UTC kabul edilir."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def pool_ids(session: Session, content: sqlite3.Connection, source: str, level: str | None) -> list[str]:
    """Çalışılacak kelime havuzu (içerikte hâlâ var olan kelimeler)."""
    if source == "level":
        return repo.word_ids_for_level(content, level) if level else []
    if source == "list":
        ids = progress.word_list_ids(session)
    else:  # due: daha önce çalışılmış tüm kelimeler
        ids = list(session.scalars(select(ReviewItem.word_id).distinct()))
    existing = repo.existing_word_ids(content, ids)
    return [word_id for word_id in ids if word_id in existing]


def _item_payload(item: ReviewItem | None, now: datetime) -> dict:
    if item is None:
        return {"status": "new", "interval_days": 0, "repetitions": 0, "lapses": 0, "due_at": None, "is_due": False}
    state = srs.CardState(item.ease, item.interval_days, item.repetitions, item.lapses)
    due = _aware(item.due_at)
    return {
        "status": srs.bucket(state),
        "interval_days": item.interval_days,
        "repetitions": item.repetitions,
        "lapses": item.lapses,
        "due_at": due.isoformat(),
        "is_due": due <= now,
    }


def build_session(
    session: Session, content: sqlite3.Connection, direction: str, source: str, level: str | None,
    size: int, new_limit: int, now: datetime | None = None,
) -> dict:
    """Önce tekrar zamanı gelen kartlar, sonra (sınırlı sayıda) yeni kelimeler."""
    now = now or utcnow()
    pool = pool_ids(session, content, source, level)
    pool_set = set(pool)
    items = {
        item.word_id: item
        for item in session.scalars(select(ReviewItem).where(ReviewItem.direction == direction))
    }
    due = sorted(
        (item for word_id, item in items.items() if word_id in pool_set and _aware(item.due_at) <= now),
        key=lambda item: item.due_at,
    )
    due_ids = [item.word_id for item in due[:size]]
    new_ids: list[str] = []
    if source != "due":
        room = min(new_limit, size - len(due_ids))
        new_ids = [word_id for word_id in pool if word_id not in items][: max(room, 0)]

    cards = repo.study_cards(content, due_ids + new_ids)
    for card in cards:
        card["review"] = _item_payload(items.get(card["id"]), now)
    return {
        "direction": direction,
        "cards": cards,
        "due_count": len(due),
        "new_available": sum(1 for word_id in pool if word_id not in items) if source != "due" else 0,
        "pool_size": len(pool),
    }


def record_review(session: Session, word_id: str, direction: str, grade: int, now: datetime | None = None) -> dict:
    """Kart cevabını kaydeder ve bir sonraki tekrar zamanını belirler."""
    now = now or utcnow()
    item = session.scalar(select(ReviewItem).where(ReviewItem.word_id == word_id, ReviewItem.direction == direction))
    before = srs.CardState(item.ease, item.interval_days, item.repetitions, item.lapses) if item else srs.CardState()
    after, due_at = srs.schedule(before, grade, now)
    if item is None:
        item = ReviewItem(word_id=word_id, direction=direction, created_at=now)
        session.add(item)
    item.ease, item.interval_days, item.repetitions, item.lapses = after.ease, after.interval_days, after.repetitions, after.lapses
    item.due_at = due_at
    item.last_reviewed_at = now
    session.add(ReviewHistory(
        word_id=word_id, direction=direction, activity="flashcard", grade=grade, correct=grade != srs.AGAIN,
        interval_before=before.interval_days, interval_after=after.interval_days, reviewed_at=now,
    ))
    session.commit()
    return _item_payload(item, now)


def record_exercise(
    session: Session, activity: str, direction: str, results: list[dict], now: datetime | None = None
) -> None:
    """Alıştırma sonucunu geçmişe yazar.

    Doğru cevap tekrar planını ilerletmez (seçenekli sorular hatırlamaktan kolaydır).
    Yanlış cevapta, kelime daha önce kartlarla çalışılmışsa kart yeniden sorulmak üzere öne alınır.
    """
    now = now or utcnow()
    for result in results:
        item = None
        if not result["correct"]:
            item = session.scalar(select(ReviewItem).where(
                ReviewItem.word_id == result["word_id"], ReviewItem.direction == direction))
        before = after = None
        if item is not None:
            state = srs.CardState(item.ease, item.interval_days, item.repetitions, item.lapses)
            new_state, due_at = srs.schedule(state, srs.AGAIN, now)
            before, after = state.interval_days, new_state.interval_days
            item.ease, item.interval_days, item.repetitions, item.lapses = (
                new_state.ease, new_state.interval_days, new_state.repetitions, new_state.lapses)
            item.due_at = due_at
            item.last_reviewed_at = now
        session.add(ReviewHistory(
            word_id=result["word_id"], direction=direction, activity=activity, grade=None,
            correct=bool(result["correct"]), interval_before=before, interval_after=after, reviewed_at=now,
        ))
    session.commit()


def word_progress(session: Session, word_id: str, now: datetime | None = None) -> dict:
    now = now or utcnow()
    items = {
        item.direction: item
        for item in session.scalars(select(ReviewItem).where(ReviewItem.word_id == word_id))
    }
    history = session.scalars(
        select(ReviewHistory).where(ReviewHistory.word_id == word_id)
        .order_by(ReviewHistory.reviewed_at.desc(), ReviewHistory.id.desc()).limit(30)
    )
    return {
        "word_id": word_id,
        "directions": {direction: _item_payload(items.get(direction), now) for direction in DIRECTIONS},
        "history": [
            {"activity": h.activity, "direction": h.direction, "grade": h.grade, "correct": h.correct,
             "interval_after": h.interval_after, "reviewed_at": _aware(h.reviewed_at).isoformat()}
            for h in history
        ],
    }


def reset_word(session: Session, word_id: str) -> None:
    """Kelimenin tekrar planını sıfırlar. Cevap geçmişi silinmez."""
    session.execute(delete(ReviewItem).where(ReviewItem.word_id == word_id))
    session.commit()


def stats(session: Session, content: sqlite3.Connection, now: datetime | None = None) -> dict:
    """Kelime istatistikleri — tamamı gerçek kayıtlardan hesaplanır."""
    now = now or utcnow()
    items = list(session.scalars(select(ReviewItem)))
    existing = repo.existing_word_ids(content, sorted({item.word_id for item in items}))
    items = [item for item in items if item.word_id in existing]

    per_direction = {}
    for direction in DIRECTIONS:
        counts = {"learning": 0, "learned": 0, "long_term": 0, "due": 0}
        for item in items:
            if item.direction != direction:
                continue
            counts[srs.bucket(srs.CardState(item.ease, item.interval_days, item.repetitions, item.lapses))] += 1
            if _aware(item.due_at) <= now:
                counts["due"] += 1
        per_direction[direction] = counts

    week_ago = now - timedelta(days=7)
    started_this_week = len({item.word_id for item in items if _aware(item.created_at) >= week_ago})

    # Son 7 günün günlük cevap sayıları (UTC gününe göre)
    days = [(now - timedelta(days=offset)).date() for offset in range(6, -1, -1)]
    daily = {day: {"date": day.isoformat(), "answers": 0, "correct": 0} for day in days}
    rows = session.execute(
        select(ReviewHistory.reviewed_at, ReviewHistory.correct).where(ReviewHistory.reviewed_at >= now - timedelta(days=7))
    ).all()
    for reviewed_at, correct in rows:
        day = _aware(reviewed_at).date()
        if day in daily:
            daily[day]["answers"] += 1
            daily[day]["correct"] += int(correct)

    wrong_rows = session.execute(
        select(ReviewHistory.word_id, func.count().label("wrong"))
        .where(ReviewHistory.correct.is_(False))
        .group_by(ReviewHistory.word_id).order_by(func.count().desc(), ReviewHistory.word_id).limit(40)
    ).all()
    wrong_existing = repo.existing_word_ids(content, [row.word_id for row in wrong_rows])
    wrong = [(row.word_id, row.wrong) for row in wrong_rows if row.word_id in wrong_existing][:10]
    briefs = {word["id"]: word for word in repo.word_briefs(content, [word_id for word_id, _ in wrong])}

    total_answers = session.scalar(select(func.count()).select_from(ReviewHistory)) or 0
    total_correct = session.scalar(select(func.count()).select_from(ReviewHistory).where(ReviewHistory.correct.is_(True))) or 0
    return {
        "total_words": repo.totals(content)["words"],
        "studied_words": len({item.word_id for item in items}),
        "started_this_week": started_this_week,
        "directions": per_direction,
        "difficult_cards": sum(1 for item in items if item.lapses >= srs.DIFFICULT_LAPSES),
        "total_answers": total_answers,
        "total_correct": total_correct,
        "daily": list(daily.values()),
        "most_missed": [{**briefs[word_id], "wrong_count": count} for word_id, count in wrong if word_id in briefs],
    }
