"""Öğrenme uçları: profil, ana ekran özeti, seviyeler, dersler."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_content, get_user_session
from app.content import repository as repo
from app.services import progress

router = APIRouter(tags=["learning"])

LevelCode = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class LevelUpdate(BaseModel):
    level: LevelCode


class CompletionUpdate(BaseModel):
    completed: bool


def _profile_payload(profile) -> dict:  # noqa: ANN001
    return {"current_level": profile.current_level, "level_source": profile.level_source}


def _require_lesson(content: sqlite3.Connection, lesson_id: str) -> None:
    if not repo.lesson_exists(content, lesson_id):
        raise HTTPException(status_code=404, detail="Ders bulunamadı.")


@router.get("/profile")
def read_profile(session: Session = Depends(get_user_session)) -> dict:
    return _profile_payload(progress.get_profile(session))


@router.put("/profile/level")
def update_level(body: LevelUpdate, session: Session = Depends(get_user_session)) -> dict:
    return _profile_payload(progress.set_level(session, body.level))


@router.get("/dashboard")
def dashboard(
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    """Ana ekran özeti. Tüm sayılar gerçek kayıtlardan hesaplanır."""
    profile = progress.get_profile(session)
    statuses = progress.lesson_statuses(session)
    by_level = repo.lesson_ids_by_level(content)
    existing = {lesson_id for ids in by_level.values() for lesson_id in ids}

    continue_id = next(
        (lesson_id for lesson_id, status in progress.recently_opened(session)
         if status == "started" and lesson_id in existing),
        None,
    )
    level_progress = None
    next_id = None
    if profile.current_level:
        ordered = repo.ordered_lesson_ids(content, profile.current_level)
        completed = sum(1 for lesson_id in ordered if statuses.get(lesson_id) == "completed")
        level_progress = {"level": profile.current_level, "completed": completed, "total": len(ordered)}
        next_id = next((lesson_id for lesson_id in ordered if lesson_id not in statuses), None)

    briefs = repo.lesson_briefs(content, [i for i in (continue_id, next_id) if i])
    return {
        "profile": _profile_payload(profile),
        "totals": repo.totals(content),
        "completed_lessons": sum(1 for lesson_id, status in statuses.items() if status == "completed" and lesson_id in existing),
        "level_progress": level_progress,
        "continue_lesson": briefs.get(continue_id),
        "next_lesson": briefs.get(next_id),
        "word_list_count": progress.word_list_count(session),
    }


@router.get("/levels")
def list_levels(
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    statuses = progress.lesson_statuses(session)
    by_level = repo.lesson_ids_by_level(content)
    levels = repo.levels(content)
    for level in levels:
        level["completed_lessons"] = sum(
            1 for lesson_id in by_level.get(level["code"], []) if statuses.get(lesson_id) == "completed"
        )
    return {"levels": levels}


@router.get("/levels/{code}/units")
def list_units(
    code: LevelCode, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    statuses = progress.lesson_statuses(session)
    units = repo.units(content, code)
    for unit in units:
        for lesson in unit["lessons"]:
            lesson["status"] = statuses.get(lesson["id"], "not_started")
    return {"level": code, "units": units}


@router.get("/lessons/{lesson_id}")
def read_lesson(
    lesson_id: str, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    lesson = repo.lesson(content, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Ders bulunamadı.")
    statuses = progress.lesson_statuses(session)
    lesson["status"] = statuses.get(lesson_id, "not_started")
    for key in ("prerequisite_lessons", "next_lessons", "related_lessons"):
        for other in lesson[key]:
            other["status"] = statuses.get(other["id"], "not_started")
    saved = progress.in_word_list(session, [word["id"] for word in lesson["vocabulary"]])
    for word in lesson["vocabulary"]:
        word["in_word_list"] = word["id"] in saved
    return lesson


@router.post("/lessons/{lesson_id}/open")
def open_lesson(
    lesson_id: str, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    _require_lesson(content, lesson_id)
    return {"lesson_id": lesson_id, "status": progress.open_lesson(session, lesson_id)}


@router.put("/lessons/{lesson_id}/completion")
def set_lesson_completion(
    lesson_id: str,
    body: CompletionUpdate,
    session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    _require_lesson(content, lesson_id)
    return {"lesson_id": lesson_id, "status": progress.set_completion(session, lesson_id, body.completed)}
