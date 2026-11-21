"""Seviye tespit sınavı.

Yöntem (bilerek basit ve açıklanabilir tutuldu):
- Her seviye için 8 soruluk bir blok sorulur; en az 6 doğru o seviyenin "geçildiği" anlamına gelir.
- Geçilen seviyeden sonra bir üst seviye, kalınan seviyeden sonra (daha önce denenmediyse) bir alt
  seviye sınanır. Üst ve alt komşusu belirlenmiş olunca sınav biter.
- Tahmini seviye geçilen en yüksek seviyedir; önerilen çalışma seviyesi bunun bir üstüdür.

Yalnızca program tarafından kesin değerlendirilebilen soru tipleri kullanılır (serbest yazı, çeviri,
dinleme yoktur). Bu nedenle sonuç dil bilgisi, okuma ve sözcük bilgisine dayalı bir tahmindir;
konuşma, yazma ve dinleme becerilerini ölçmez.
"""

from __future__ import annotations

import json
import random
import sqlite3

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content import repository as repo
from app.models.user import PlacementResult, TestSession, UserAnswer, utcnow
from app.services import tests as tests_service

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
BLOCK_SIZE = 8
PASS_MARK = 6
TYPES = (
    "multiple_choice", "true_false", "error_spotting", "sentence_completion", "dialogue_completion",
    "reading_comprehension", "word_in_context", "paragraph_completion", "nuance", "fill_blank", "word_formation",
)
TRACKS = ("grammar", "reading", "expressions")
# Bir bloğun hedef dağılımı: çoğunluk dil bilgisi, birer okuma ve kalıp sorusu.
TARGET_MIX = {"reading": 1, "expressions": 1}

LIMITS_TR = (
    "Bu sınav dil bilgisi, okuma ve kelime bilgisine dayalı bir tahmindir. Konuşma, yazma ve dinleme "
    "becerilerinizi ölçmez. Sorular resmî bir CEFR sınavıyla eşleştirilmemiştir; sonucu bir başlangıç "
    "noktası olarak kullanın ve dersler size kolay ya da zor gelirse seviyenizi değiştirin."
)


class PlacementError(tests_service.TestError):
    pass


def _pick_block(session: Session, content: sqlite3.Connection, level: str, rng: random.Random,
                exclude: set[str]) -> list[str]:
    pool = [row for row in repo.placement_pool(content, level, TYPES, TRACKS) if row["id"] not in exclude]
    answered = set(session.scalars(select(UserAnswer.question_id)))
    rng.shuffle(pool)
    pool.sort(key=lambda row: row["id"] in answered)  # daha önce görülmemiş sorular önce (kararlı sıralama)
    chosen: list[str] = []
    used_lessons: set[str] = set()

    def take(rows, limit):  # noqa: ANN001
        for row in rows:
            if len(chosen) >= BLOCK_SIZE or limit <= 0:
                return
            if row["lesson_id"] in used_lessons or row["id"] in chosen:
                continue
            chosen.append(row["id"])
            used_lessons.add(row["lesson_id"])
            limit -= 1

    for track, count in TARGET_MIX.items():
        take([row for row in pool if row["track"] == track], count)
    take([row for row in pool if row["track"] == "grammar"], BLOCK_SIZE)
    # Ders başına bir soru yetmezse (küçük havuz) aynı dersten ikinci soruya izin verilir.
    if len(chosen) < BLOCK_SIZE:
        used_lessons.clear()
        take(pool, BLOCK_SIZE)
    rng.shuffle(chosen)
    return chosen


def _record(session: Session, session_id: int) -> tuple[TestSession, PlacementResult]:
    test = session.get(TestSession, session_id)
    result = session.scalar(select(PlacementResult).where(PlacementResult.session_id == session_id))
    if test is None or result is None or test.kind != "placement":
        raise PlacementError(404, "Seviye tespit sınavı bulunamadı.")
    return test, result


def _questions_payload(content: sqlite3.Connection, ids: list[str], rng: random.Random) -> list[dict]:
    return [tests_service._public_question(repo.question_for_grading(content, qid), rng) for qid in ids]  # noqa: SLF001


def _state(result: PlacementResult) -> dict:
    blocks = json.loads(result.blocks_json)
    return {
        "start_level": result.start_level,
        "current_level": result.current_level,
        "finished": result.finished_at is not None,
        "blocks": [{key: block[key] for key in ("level", "correct", "total", "passed") if key in block}
                   for block in blocks],
        "block_number": len(blocks),
        "block_size": BLOCK_SIZE,
        "pass_mark": PASS_MARK,
    }


def start(session: Session, content: sqlite3.Connection, start_level: str = "A1", seed: int | None = None) -> dict:
    if start_level not in LEVELS:
        raise PlacementError(422, "Geçersiz başlangıç seviyesi.")
    rng = random.Random(seed)  # noqa: S311 (güvenlik amaçlı değil)
    ids = _pick_block(session, content, start_level, rng, set())
    if len(ids) < BLOCK_SIZE:
        raise PlacementError(409, "Bu seviye için yeterli soru yok.")
    test = TestSession(kind="placement", level=start_level, question_ids=json.dumps(ids))
    session.add(test)
    session.flush()
    result = PlacementResult(
        session_id=test.id, start_level=start_level, current_level=start_level,
        blocks_json=json.dumps([{"level": start_level, "question_ids": ids}]),
    )
    session.add(result)
    session.commit()
    return {"session_id": test.id, **_state(result), "questions": _questions_payload(content, ids, rng),
            "limits_tr": LIMITS_TR}


def _decide(blocks: list[dict]) -> str | None:
    """Sınanacak sonraki seviye; sınav bittiyse None."""
    tested = {block["level"]: block["passed"] for block in blocks}
    last = blocks[-1]
    index = LEVELS.index(last["level"])
    if last["passed"]:
        if index == len(LEVELS) - 1 or LEVELS[index + 1] in tested:
            return None
        return LEVELS[index + 1]
    if index == 0 or LEVELS[index - 1] in tested:
        return None
    return LEVELS[index - 1]


def _outcome(blocks: list[dict]) -> tuple[str, str]:
    passed = [block["level"] for block in blocks if block["passed"]]
    if not passed:
        return "below_A1", "A1"
    best = max(passed, key=LEVELS.index)
    index = LEVELS.index(best)
    return best, LEVELS[min(index + 1, len(LEVELS) - 1)]


def advance(session: Session, content: sqlite3.Connection, session_id: int, seed: int | None = None) -> dict:
    """Mevcut bloğu değerlendirir; sonraki bloğu ya da sonucu döndürür."""
    test, result = _record(session, session_id)
    if result.finished_at is not None:
        return report(session, content, session_id)
    blocks = json.loads(result.blocks_json)
    current = blocks[-1]
    answers = dict(session.execute(
        select(UserAnswer.question_id, UserAnswer.result)
        .where(UserAnswer.session_id == session_id, UserAnswer.question_id.in_(current["question_ids"]))
    ).all())
    missing = [qid for qid in current["question_ids"] if qid not in answers]
    if missing:
        raise PlacementError(409, f"Devam etmeden önce bu bölümdeki bütün soruları cevaplayın ({len(missing)} soru kaldı).")
    correct = sum(1 for value in answers.values() if value in tests_service.RIGHT)
    current.update(correct=correct, total=len(current["question_ids"]), passed=correct >= PASS_MARK)

    next_level = _decide(blocks)
    if next_level is None:
        result.result_level, result.recommended_level = _outcome(blocks)
        result.finished_at = test.finished_at = utcnow()
        result.blocks_json = json.dumps(blocks)
        session.commit()
        return report(session, content, session_id)

    rng = random.Random(seed)  # noqa: S311
    asked = {qid for block in blocks for qid in block["question_ids"]}
    ids = _pick_block(session, content, next_level, rng, asked)
    blocks.append({"level": next_level, "question_ids": ids})
    result.blocks_json = json.dumps(blocks)
    result.current_level = next_level
    test.level = next_level
    test.question_ids = json.dumps([*json.loads(test.question_ids), *ids])
    session.commit()
    return {"session_id": session_id, **_state(result), "questions": _questions_payload(content, ids, rng)}


def report(session: Session, content: sqlite3.Connection, session_id: int) -> dict:
    test, result = _record(session, session_id)
    state = _state(result)
    if result.finished_at is None:
        return {"session_id": session_id, **state}
    rows = session.execute(
        select(UserAnswer.question_id, UserAnswer.lesson_id, UserAnswer.result).where(UserAnswer.session_id == session_id)
    ).all()
    wrong_lessons: dict[str, int] = {}
    for _qid, lesson_id, value in rows:
        if value in tests_service.WRONG:
            wrong_lessons[lesson_id] = wrong_lessons.get(lesson_id, 0) + 1
    briefs = repo.lesson_briefs(content, list(wrong_lessons))
    review = sorted(
        ({**briefs[lesson_id], "wrong": count} for lesson_id, count in wrong_lessons.items() if lesson_id in briefs),
        key=lambda item: (repo_level_index(item["level"]), -item["wrong"], item["title_tr"]),
    )
    return {
        "session_id": session_id, **state,
        "result_level": result.result_level,
        "recommended_level": result.recommended_level,
        "finished_at": result.finished_at.isoformat(),
        "answered": len(rows),
        "correct": sum(1 for _q, _l, value in rows if value in tests_service.RIGHT),
        "review_lessons": review[:8],
        "limits_tr": LIMITS_TR,
    }


def repo_level_index(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else len(LEVELS)


def history(session: Session, limit: int = 10) -> list[dict]:
    records = session.scalars(
        select(PlacementResult).where(PlacementResult.finished_at.is_not(None))
        .order_by(PlacementResult.finished_at.desc(), PlacementResult.id.desc()).limit(limit)
    )
    return [
        {"session_id": record.session_id, "result_level": record.result_level,
         "recommended_level": record.recommended_level, "finished_at": record.finished_at.isoformat(),
         "blocks": _state(record)["blocks"]}
        for record in records
    ]


def latest(session: Session) -> dict | None:
    items = history(session, 1)
    return items[0] if items else None
