"""Test uçları: oturum başlatma, cevaplama, öz değerlendirme, geçmiş, konu başarısı."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_content, get_user_session
from app.api.learning import LevelCode
from app.content import repository as repo
from app.content.source_models import QuestionType
from app.services import tests as service

router = APIRouter(tags=["tests"])


class StartBody(BaseModel):
    lesson_id: str | None = Field(default=None, max_length=120)
    level: LevelCode | None = None
    types: list[QuestionType] | None = Field(default=None, max_length=18)
    size: int = Field(default=10, ge=1, le=40)
    seed: int | None = Field(default=None, ge=0, le=2**31)


class AnswerBody(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    answer: Any


class SelfRatingBody(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    rating: Literal["correct", "partial", "incorrect"]


def _run(call, *args):  # noqa: ANN001, ANN002
    try:
        return call(*args)
    except service.TestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from None


@router.get("/tests/overview")
def overview(
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    """Seviyelere göre soru sayıları, ders bazında başarı ve son testler."""
    counts = repo.question_counts_by_lesson(content)
    stats = {item["id"]: item for item in service.topic_stats(session, content)}
    levels = []
    for level in repo.levels(content):
        lessons = []
        for unit in repo.units(content, level["code"]):
            for lesson in unit["lessons"]:
                if counts.get(lesson["id"]):
                    lessons.append({**lesson, "question_count": counts[lesson["id"]],
                                    "stats": stats.get(lesson["id"])})
        levels.append({"code": level["code"], "name_tr": level["name_tr"], "lessons": lessons,
                       "question_count": sum(item["question_count"] for item in lessons)})
    return {"levels": levels, "weak_topics": [item for item in stats.values() if item["accuracy"] < 70][:5],
            "history": service.history(session, content, limit=10)}


@router.post("/tests/sessions")
def start_session(
    body: StartBody, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    return _run(service.start, session, content, body.lesson_id, body.level, body.types, body.size, body.seed)


@router.post("/tests/sessions/{session_id}/answers")
def answer_question(
    session_id: int, body: AnswerBody, session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    return _run(service.answer, session, content, session_id, body.question_id, body.answer)


@router.post("/tests/sessions/{session_id}/self-rating")
def rate_own_answer(session_id: int, body: SelfRatingBody, session: Session = Depends(get_user_session)) -> dict:
    return _run(service.self_rate, session, session_id, body.question_id, body.rating)


@router.post("/tests/sessions/{session_id}/finish")
def finish_session(session_id: int, session: Session = Depends(get_user_session)) -> dict:
    return _run(service.finish, session, session_id)
