"""Kelime çalışması uçları: kart oturumu, alıştırmalar, istatistikler."""

from __future__ import annotations

import random
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_content, get_user_session
from app.api.learning import LevelCode
from app.content import repository as repo
from app.learning import exercises
from app.services import progress, study

router = APIRouter(tags=["study"])

Direction = Literal["en_tr", "tr_en"]
Source = Literal["level", "list", "due"]
ExerciseType = Literal["mc_en_tr", "mc_tr_en", "typing", "cloze", "antonym", "matching"]


class ReviewBody(BaseModel):
    word_id: str = Field(min_length=1, max_length=120)
    direction: Direction
    grade: Literal[0, 1, 2, 3]


class AnswerBody(BaseModel):
    type: ExerciseType
    word_id: str = Field(min_length=1, max_length=120)
    answer: Any


def _level(session: Session, source: str, level: str | None) -> str | None:
    if source != "level":
        return None
    resolved = level or progress.get_profile(session).current_level
    if resolved is None:
        raise HTTPException(status_code=422, detail="Önce seviyenizi seçin.")
    return resolved


@router.get("/study/session")
def study_session(
    direction: Direction,
    source: Source = "level",
    level: LevelCode | None = None,
    size: int = Query(default=20, ge=1, le=50),
    new_limit: int = Query(default=10, ge=0, le=50),
    session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    return study.build_session(session, content, direction, source, _level(session, source, level), size, new_limit)


@router.post("/study/review")
def review(
    body: ReviewBody, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    if not repo.word_exists(content, body.word_id):
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")
    return {"word_id": body.word_id, "direction": body.direction,
            "review": study.record_review(session, body.word_id, body.direction, body.grade)}


@router.get("/study/exercises")
def list_exercises(
    type: ExerciseType,  # noqa: A002
    source: Source = "level",
    level: LevelCode | None = None,
    size: int = Query(default=10, ge=1, le=30),
    seed: int | None = Query(default=None, ge=0, le=2**31),
    session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    pool = study.pool_ids(session, content, source, _level(session, source, level))
    rng = random.Random(seed)  # noqa: S311 (güvenlik amaçlı değil; soru karıştırma)
    return {"type": type, "questions": exercises.build(content, type, pool, size, rng), "pool_size": len(pool)}


@router.post("/study/answer")
def answer(
    body: AnswerBody, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    try:
        feedback = exercises.grade(content, body.type, body.word_id, body.answer)
    except LookupError:
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    study.record_exercise(session, body.type, exercises.DIRECTION[body.type], feedback["results"])
    return feedback


@router.get("/study/stats")
def study_stats(
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    return study.stats(session, content)


@router.get("/study/words/{word_id}")
def word_progress(
    word_id: str, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    if not repo.word_exists(content, word_id):
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")
    return study.word_progress(session, word_id)


@router.delete("/study/words/{word_id}")
def reset_word(word_id: str, session: Session = Depends(get_user_session)) -> dict:
    study.reset_word(session, word_id)
    return {"word_id": word_id, "reset": True}
