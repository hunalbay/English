"""İlerleme raporu ve güçlü / zayıf yön analizi.

Bütün sayılar kullanıcının kendi kayıtlarından (user.db) hesaplanır; tahmin ya da örnek veri yoktur.
Program çalışma süresini ölçmez; raporlar etkinlik sayılarına (cevaplanan soru, tekrar edilen kart,
tamamlanan ders) dayanır. Günler bilgisayarın yerel saat dilimine göre ayrılır.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content import repository as repo
from app.models.user import LessonProgress, ReviewHistory, TestSession, UserAnswer
from app.services import placement
from app.services import study as study_service
from app.services import tests as tests_service

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
MIN_ANSWERS = 3          # bir konu hakkında yargıya varmak için gereken en az kesin cevap
STRONG_FROM = 0.8
WEAK_BELOW = 0.6
ACTIVITY_DAYS = 30
TREND_WEEKS = 8


def _local_date(value: datetime, tz) -> date:  # noqa: ANN001
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).date()


def _graded_rows(session: Session) -> list[tuple[str, str, str, datetime]]:
    """(question_id, lesson_id, result, answered_at) — yalnızca kesin ya da öz değerlendirmeli sonuçlar."""
    rows = session.execute(
        select(UserAnswer.question_id, UserAnswer.lesson_id, UserAnswer.result, UserAnswer.answered_at)
    ).all()
    graded = (*tests_service.RIGHT, *tests_service.WRONG)
    return [tuple(row) for row in rows if row[2] in graded]


def _rate(correct: int, total: int) -> float | None:
    return round(correct / total, 3) if total else None


def analysis(session: Session, content: sqlite3.Connection) -> dict:
    """Konu, alan, seviye ve soru tipi bazında başarı; güçlü ve zayıf konular; öneriler."""
    rows = _graded_rows(session)
    lesson_ids = sorted({row[1] for row in rows})
    briefs = repo.lesson_briefs(content, lesson_ids)
    tracks = repo.lesson_tracks(content, lesson_ids)
    meta = repo.question_meta(content, sorted({row[0] for row in rows}))

    def bucket(store: dict, key: str, right: bool) -> None:
        entry = store.setdefault(key, {"correct": 0, "total": 0})
        entry["total"] += 1
        entry["correct"] += int(right)

    by_lesson: dict[str, dict] = {}
    by_track: dict[str, dict] = {}
    by_level: dict[str, dict] = {}
    by_type: dict[str, dict] = {}
    for question_id, lesson_id, result, _ in rows:
        if lesson_id not in briefs or question_id not in meta:
            continue  # içerik güncellemesiyle kaldırılmış soru ya da ders
        right = result in tests_service.RIGHT
        bucket(by_lesson, lesson_id, right)
        bucket(by_track, tracks.get(lesson_id, "grammar"), right)
        bucket(by_level, meta[question_id]["level"], right)
        bucket(by_type, meta[question_id]["type"], right)

    topics = [
        {**briefs[lesson_id], "track": tracks.get(lesson_id, "grammar"), **counts,
         "rate": _rate(counts["correct"], counts["total"])}
        for lesson_id, counts in by_lesson.items()
    ]
    judged = [topic for topic in topics if topic["total"] >= MIN_ANSWERS]
    strengths = sorted((t for t in judged if t["rate"] >= STRONG_FROM), key=lambda t: (-t["rate"], -t["total"], t["title_tr"]))
    weaknesses = sorted((t for t in judged if t["rate"] < WEAK_BELOW), key=lambda t: (t["rate"], -t["total"], t["title_tr"]))

    def table(store: dict, order: tuple[str, ...] | None = None) -> list[dict]:
        keys = [key for key in order if key in store] if order else sorted(store, key=lambda k: -store[k]["total"])
        return [{"key": key, **store[key], "rate": _rate(store[key]["correct"], store[key]["total"])} for key in keys]

    vocab = study_service.stats(session, content)
    difficult = vocab.get("most_missed", [])[:8]
    due = vocab["directions"]["en_tr"]["due"] + vocab["directions"]["tr_en"]["due"]

    recommendations = []
    for topic in weaknesses[:3]:
        recommendations.append({
            "kind": "review_lesson", "lesson": {k: topic[k] for k in ("id", "kind", "level", "title_tr", "title_en", "track")},
            "reason_tr": f"Bu konudaki {topic['total']} cevabınızın {topic['correct']} tanesi doğru (%{round(topic['rate'] * 100)}).",
        })
    if due:
        recommendations.append({"kind": "review_words", "count": due,
                                "reason_tr": f"Tekrar zamanı gelmiş {due} kelime kartınız var."})
    latest = placement.latest(session)
    if latest is None:
        recommendations.append({"kind": "placement",
                                "reason_tr": "Seviyenizi henüz ölçmediniz. Seviye tespit sınavı bir başlangıç noktası verir."})

    return {
        "graded_answers": len(rows),
        "min_answers": MIN_ANSWERS,
        "thresholds": {"strong_from": STRONG_FROM, "weak_below": WEAK_BELOW},
        "by_track": table(by_track, repo.TRACKS),
        "by_level": table(by_level, LEVELS),
        "by_type": table(by_type),
        "strengths": strengths[:8],
        "weaknesses": weaknesses[:8],
        "untested_topics": sum(1 for topic in topics if topic["total"] < MIN_ANSWERS),
        "difficult_words": difficult,
        "latest_placement": latest,
        "recommendations": recommendations,
    }


def _streaks(days: set[date], today: date) -> tuple[int, int]:
    """(güncel seri, en uzun seri). Bugün henüz etkinlik yoksa dünden geriye sayılır."""
    current = 0
    day = today if today in days else today - timedelta(days=1)
    while day in days:
        current += 1
        day -= timedelta(days=1)
    longest = run = 0
    previous = None
    for day in sorted(days):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return current, longest


def _day_counts(session: Session, column, *conditions) -> dict[date, int]:  # noqa: ANN001
    """Yerel güne göre kayıt sayıları. Gruplama SQLite'ta yapılır (büyük geçmişte de hızlı kalır).

    Zaman damgaları UTC saklanır; SQLite'ın 'localtime' dönüşümü işletim sisteminin saat dilimini kullanır.
    """
    day = func.date(column, "localtime")
    rows = session.execute(select(day, func.count()).where(*conditions).group_by(day)).all()
    return {date.fromisoformat(value): count for value, count in rows if value}


def progress(session: Session, content: sqlite3.Connection, now: datetime | None = None) -> dict:
    """Etkinlik geçmişi, seriler, haftalık başarı ve alanlara göre tamamlanan dersler."""
    now = now or datetime.now(timezone.utc)
    tz = now.astimezone().tzinfo
    today = _local_date(now, tz)
    first_day = today - timedelta(days=ACTIVITY_DAYS - 1)

    question_days = _day_counts(session, UserAnswer.answered_at)
    review_days = _day_counts(session, ReviewHistory.reviewed_at)
    lesson_days = _day_counts(session, LessonProgress.completed_at, LessonProgress.completed_at.is_not(None))
    activity_days = {day for counts in (question_days, review_days, lesson_days) for day, n in counts.items() if n}
    daily = {
        first_day + timedelta(days=i): {
            "questions": question_days.get(first_day + timedelta(days=i), 0),
            "reviews": review_days.get(first_day + timedelta(days=i), 0),
            "lessons": lesson_days.get(first_day + timedelta(days=i), 0),
        }
        for i in range(ACTIVITY_DAYS)
    }

    # Haftalık başarı (son 8 hafta, pazartesi başlangıçlı)
    week_start = today - timedelta(days=today.weekday())
    weeks = [week_start - timedelta(weeks=i) for i in range(TREND_WEEKS - 1, -1, -1)]
    weekly = {week: {"correct": 0, "total": 0} for week in weeks}
    graded = (*tests_service.RIGHT, *tests_service.WRONG)
    day_expr = func.date(UserAnswer.answered_at, "localtime")
    result_rows = session.execute(
        select(day_expr, UserAnswer.result, func.count()).group_by(day_expr, UserAnswer.result)
    ).all()
    graded_total = graded_right = 0
    for value, result, count in result_rows:
        if result not in graded:
            continue
        graded_total += count
        right = result in tests_service.RIGHT
        graded_right += count if right else 0
        day = date.fromisoformat(value)
        week = day - timedelta(days=day.weekday())
        if week in weekly:
            weekly[week]["total"] += count
            weekly[week]["correct"] += count if right else 0
    completions = session.execute(
        select(LessonProgress.completed_at, LessonProgress.lesson_id).where(LessonProgress.completed_at.is_not(None))
    ).all()
    answers_total = sum(question_days.values())
    reviews_total = sum(review_days.values())

    # Alanlara ve seviyelere göre tamamlanan dersler (yalnızca içerikte hâlâ bulunan dersler sayılır)
    completed_ids = {lesson_id for _, lesson_id in completions}
    track_levels = repo.track_counts(content)
    by_track_level = {track: {level: 0 for level in LEVELS} for track in repo.TRACKS}
    for track in repo.TRACKS:
        for level, ids in repo.lesson_ids_by_level(content, track).items():
            by_track_level[track][level] = sum(1 for lesson_id in ids if lesson_id in completed_ids)
    tracks = [
        {"track": track, "completed": sum(by_track_level[track].values()), "total": sum(track_levels[track].values()),
         "levels": [{"level": level, "completed": by_track_level[track][level], "total": track_levels[track].get(level, 0)}
                    for level in LEVELS if track_levels[track].get(level)]}
        for track in repo.TRACKS
    ]

    current_streak, longest_streak = _streaks(activity_days, today)
    finished_tests = session.scalar(
        select(TestSession.id).where(TestSession.finished_at.is_not(None)).limit(1)
    )
    vocab = study_service.stats(session, content)
    vocab_buckets = {
        key: vocab["directions"]["en_tr"][key] for key in ("learning", "learned", "long_term")
    }
    return {
        "today": today.isoformat(),
        "timezone_note_tr": "Günler bilgisayarınızın saat dilimine göre hesaplanır.",
        "measures_note_tr": "Program çalışma süresini ölçmez; rapor etkinlik sayılarına dayanır.",
        "streak": {"current": current_streak, "longest": longest_streak, "active_days": len(activity_days)},
        "daily": [{"date": day.isoformat(), **counts} for day, counts in daily.items()],
        "weekly_accuracy": [
            {"week_start": week.isoformat(), **counts, "rate": _rate(counts["correct"], counts["total"])}
            for week, counts in weekly.items()
        ],
        "totals": {
            "questions_answered": answers_total,
            "graded_answers": graded_total,
            "correct_answers": graded_right,
            "accuracy": _rate(graded_right, graded_total),
            "word_reviews": reviews_total,
            "lessons_completed": sum(track["completed"] for track in tracks),
            "has_finished_tests": finished_tests is not None,
        },
        "tracks": tracks,
        "vocabulary": {
            "studied_words": vocab["studied_words"],
            "total_words": vocab["total_words"],
            "buckets_en_tr": vocab_buckets,
            "due": vocab["directions"]["en_tr"]["due"] + vocab["directions"]["tr_en"]["due"],
        },
    }
