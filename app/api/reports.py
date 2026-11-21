"""Seviye tespit sınavı, güçlü / zayıf yön analizi ve ilerleme raporu uçları."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_content, get_user_session
from app.api.learning import LevelCode
from app.services import placement, reports
from app.services import tests as tests_service

router = APIRouter(tags=["reports"])


class PlacementStart(BaseModel):
    start_level: LevelCode = "A1"
    seed: int | None = Field(default=None, ge=0, le=2**31)


class PlacementAdvance(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2**31)


def _run(call, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    try:
        return call(*args, **kwargs)
    except tests_service.TestError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from None


@router.get("/placement")
def placement_overview(session: Session = Depends(get_user_session)) -> dict:
    return {
        "block_size": placement.BLOCK_SIZE, "pass_mark": placement.PASS_MARK,
        "max_blocks": len(placement.LEVELS), "limits_tr": placement.LIMITS_TR,
        "history": placement.history(session),
    }


@router.post("/placement/sessions")
def placement_start(
    body: PlacementStart, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    return _run(placement.start, session, content, body.start_level, body.seed)


@router.post("/placement/sessions/{session_id}/next")
def placement_next(
    session_id: int, body: PlacementAdvance | None = None,
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content),
) -> dict:
    return _run(placement.advance, session, content, session_id, body.seed if body else None)


@router.get("/placement/sessions/{session_id}")
def placement_report(
    session_id: int, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    return _run(placement.report, session, content, session_id)


@router.get("/reports/analysis")
def analysis(session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)) -> dict:
    return reports.analysis(session, content)


@router.get("/reports/progress")
def progress(session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)) -> dict:
    return reports.progress(session, content)
