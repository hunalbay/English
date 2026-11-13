"""Test oturumları: soru seçimi, cevap kaydı, geri bildirim, geçmiş ve konu başarısı."""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment import grading
from app.content import repository as repo
from app.models.user import TestSession, UserAnswer, utcnow

SELF_RATINGS = {"correct": "self_correct", "partial": "self_partial", "incorrect": "self_incorrect"}
RIGHT = ("correct", "self_correct")
WRONG = ("incorrect", "self_incorrect")


class TestError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _public_question(question: dict, rng: random.Random) -> dict:
    """Soru verisi — cevap anahtarı olmadan."""
    payload: dict[str, Any] = {
        key: question[key]
        for key in ("id", "type", "evaluator", "level", "difficulty", "prompt", "context", "instruction_tr")
    }
    payload["lesson"] = question["lessons"][0] if question["lessons"] else None
    if question["evaluator"] == "choice":
        options = [{"position": o["position"], "text": o["text"]} for o in question["options"]]
        if question["type"] != "true_false":
            rng.shuffle(options)
        payload["options"] = options
    elif question["evaluator"] == "order":
        tokens = list(question["data"]["tokens"])
        for _ in range(5):  # doğru sırayla başlamasın
            rng.shuffle(tokens)
            if tokens != question["data"]["tokens"]:
                break
        payload["tokens"] = tokens
    elif question["evaluator"] == "matching":
        rights = [right for _, right in question["data"]["pairs"]]
        rng.shuffle(rights)
        payload["left"] = [left for left, _ in question["data"]["pairs"]]
        payload["right"] = rights
    elif question["evaluator"] == "text":
        payload["strict"] = question["grading"] == "strict"
    if question["data"].get("checklist"):
        payload["checklist"] = question["data"]["checklist"]
    return payload


def _pick_questions(session: Session, pool: list[str], size: int, rng: random.Random) -> list[str]:
    """Önce hiç çözülmemiş, sonra yanlış yapılmış, en son doğru yapılmış sorular."""
    last_result: dict[str, str] = {}
    rows = session.execute(
        select(UserAnswer.question_id, UserAnswer.result).order_by(UserAnswer.answered_at, UserAnswer.id)
    ).all()
    for question_id, result in rows:
        last_result[question_id] = result

    def priority(question_id: str) -> int:
        result = last_result.get(question_id)
        if result is None:
            return 0
        return 1 if result not in RIGHT else 2

    shuffled = rng.sample(pool, len(pool))
    return sorted(shuffled, key=priority)[:size]


def start(session: Session, content: sqlite3.Connection, lesson_id: str | None, level: str | None,
          types: list[str] | None, size: int, seed: int | None = None) -> dict:
    if lesson_id and not repo.lesson_exists(content, lesson_id):
        raise TestError(404, "Ders bulunamadı.")
    pool = repo.question_ids(content, lesson_id, level, types)
    if not pool:
        raise TestError(404, "Bu seçim için henüz soru yok.")
    rng = random.Random(seed)  # noqa: S311 (güvenlik amaçlı değil)
    chosen = _pick_questions(session, pool, size, rng)
    rng.shuffle(chosen)
    record = TestSession(
        kind="lesson" if lesson_id else "level" if level else "mixed",
        lesson_id=lesson_id, level=level, question_ids=json.dumps(chosen),
    )
    session.add(record)
    session.commit()
    questions = [_public_question(repo.question_for_grading(content, question_id), rng) for question_id in chosen]
    return {"session_id": record.id, "kind": record.kind, "lesson_id": lesson_id, "level": level,
            "questions": questions, "pool_size": len(pool)}


def _feedback(content: sqlite3.Connection, question: dict, answer: Any, outcome: dict) -> dict:
    feedback: dict[str, Any] = {
        "question_id": question["id"],
        "result": outcome["result"],
        "explanation_tr": question["explanation_tr"],
        "example": {"en": question["example_en"], "tr": question["example_tr"]} if question["example_en"] else None,
        "lessons": question["lessons"],
        "vocabulary": question["vocabulary"],
        "lesson_examples": repo.lesson_examples(content, question["lesson_id"]) if outcome["result"] != "correct" else [],
    }
    evaluator = question["evaluator"]
    if evaluator == "choice":
        feedback["chosen"] = answer
        feedback["options"] = question["options"]  # her seçeneğin doğruluğu ve açıklaması
    elif evaluator == "text":
        feedback["accepted_answers"] = question["accepted"]
        if outcome.get("near_miss"):
            feedback["note_tr"] = ("Cevabınız yalnızca büyük/küçük harf ya da noktalama yönünden farklı. "
                                   "Bu soruda yazım ve noktalama da değerlendiriliyor.")
        if outcome["result"] == "ungraded":
            feedback["note_tr"] = ("Cevabınız kabul edilen cevaplarla birebir eşleşmedi. Bir cümlenin birden çok doğru "
                                   "biçimi olabileceği için program bu cevabı kesin olarak değerlendiremez. "
                                   "Örnek cevaplarla karşılaştırıp kendinizi değerlendirin.")
    elif evaluator == "order":
        feedback["correct_order"] = question["data"]["tokens"]
        feedback["also"] = question["data"].get("also", [])
    elif evaluator == "matching":
        feedback["pairs"] = outcome["pairs"]
    else:
        feedback["model_answers"] = question["data"].get("model_answers", [])
        feedback["checklist"] = question["data"].get("checklist", [])
        feedback["note_tr"] = ("Serbest yazılı cevaplar program tarafından değerlendirilmez. Cevabınızı örnek "
                               "cevapla ve kontrol listesiyle karşılaştırıp kendinizi değerlendirin.")
    return feedback


def _session(session: Session, session_id: int) -> TestSession:
    record = session.get(TestSession, session_id)
    if record is None:
        raise TestError(404, "Test oturumu bulunamadı.")
    return record


def answer(session: Session, content: sqlite3.Connection, session_id: int, question_id: str, value: Any) -> dict:
    record = _session(session, session_id)
    if question_id not in json.loads(record.question_ids):
        raise TestError(404, "Bu soru bu teste ait değil.")
    question = repo.question_for_grading(content, question_id)
    if question is None:
        raise TestError(404, "Soru bulunamadı.")
    existing = session.scalar(
        select(UserAnswer).where(UserAnswer.session_id == session_id, UserAnswer.question_id == question_id))
    if existing is not None:
        raise TestError(409, "Bu soru zaten cevaplandı.")
    try:
        outcome = grading.grade(question, value)
    except ValueError as exc:
        raise TestError(422, str(exc)) from None
    session.add(UserAnswer(
        session_id=session_id, question_id=question_id, lesson_id=question["lesson_id"],
        answer_json=json.dumps(value, ensure_ascii=False), result=outcome["result"],
    ))
    session.commit()
    return _feedback(content, question, value, outcome)


def self_rate(session: Session, session_id: int, question_id: str, rating: str) -> dict:
    """Kesin değerlendirilemeyen cevap için kullanıcının öz değerlendirmesi."""
    _session(session, session_id)
    row = session.scalar(
        select(UserAnswer).where(UserAnswer.session_id == session_id, UserAnswer.question_id == question_id))
    if row is None:
        raise TestError(404, "Önce soruyu cevaplayın.")
    if row.result not in ("ungraded", *SELF_RATINGS.values()):
        raise TestError(409, "Bu cevap program tarafından değerlendirildi; öz değerlendirme yapılamaz.")
    row.result = SELF_RATINGS[rating]
    session.commit()
    return {"question_id": question_id, "result": row.result}


def _summary(session: Session, record: TestSession) -> dict:
    results = list(session.scalars(select(UserAnswer.result).where(UserAnswer.session_id == record.id)))
    total = len(json.loads(record.question_ids))
    return {
        "session_id": record.id, "kind": record.kind, "lesson_id": record.lesson_id, "level": record.level,
        "started_at": record.started_at.isoformat(), "finished": record.finished_at is not None,
        "total": total, "answered": len(results),
        "correct": sum(1 for r in results if r in RIGHT),
        "incorrect": sum(1 for r in results if r in WRONG),
        "partial": sum(1 for r in results if r == "self_partial"),
        "ungraded": sum(1 for r in results if r == "ungraded"),
        "self_assessed": sum(1 for r in results if r.startswith("self_")),
    }


def finish(session: Session, session_id: int) -> dict:
    record = _session(session, session_id)
    if record.finished_at is None:
        record.finished_at = utcnow()
        session.commit()
    return _summary(session, record)


def history(session: Session, content: sqlite3.Connection, limit: int = 20) -> list[dict]:
    records = session.scalars(select(TestSession).order_by(TestSession.started_at.desc(), TestSession.id.desc()).limit(limit))
    items = []
    for record in records:
        summary = _summary(session, record)
        if summary["answered"] == 0:
            continue  # hiç cevap verilmeden bırakılan oturumlar geçmişte gösterilmez
        if record.lesson_id:
            summary["lesson"] = repo.lesson_briefs(content, [record.lesson_id]).get(record.lesson_id)
        items.append(summary)
    return items


def topic_stats(session: Session, content: sqlite3.Connection) -> list[dict]:
    """Ders bazında başarı — yalnızca kesin ya da öz değerlendirmeyle sonuçlanmış cevaplardan."""
    rows = session.execute(
        select(UserAnswer.lesson_id, UserAnswer.result, func.count())
        .group_by(UserAnswer.lesson_id, UserAnswer.result)
    ).all()
    stats: dict[str, dict[str, int]] = {}
    for lesson_id, result, count in rows:
        entry = stats.setdefault(lesson_id, {"correct": 0, "incorrect": 0, "other": 0})
        entry["correct" if result in RIGHT else "incorrect" if result in WRONG else "other"] += count
    briefs = repo.lesson_briefs(content, list(stats))
    items = []
    for lesson_id, entry in stats.items():
        graded = entry["correct"] + entry["incorrect"]
        if lesson_id not in briefs or graded == 0:
            continue
        items.append({**briefs[lesson_id], "correct": entry["correct"], "incorrect": entry["incorrect"],
                      "accuracy": round(entry["correct"] / graded * 100)})
    return sorted(items, key=lambda item: (item["accuracy"], -item["incorrect"], item["id"]))
