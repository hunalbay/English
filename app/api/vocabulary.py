"""Sözlük, kişisel kelime listesi ve genel arama uçları."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_content, get_user_session
from app.api.learning import LevelCode
from app.content import repository as repo
from app.services import progress

router = APIRouter(tags=["vocabulary"])


def _mark_saved(session: Session, words: list[dict]) -> list[dict]:
    saved = progress.in_word_list(session, [word["id"] for word in words])
    for word in words:
        word["in_word_list"] = word["id"] in saved
    return words


def _require_word(content: sqlite3.Connection, word_id: str) -> None:
    if not repo.word_exists(content, word_id):
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")


@router.get("/vocabulary")
def list_words(
    level: LevelCode | None = None,
    q: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    query = q.strip() if q else None
    items, total = repo.words(content, level, query or None, page_size, (page - 1) * page_size)
    return {"items": _mark_saved(session, items), "total": total, "page": page, "page_size": page_size}


@router.get("/vocabulary/lookup")
def lookup_word(form: str = Query(min_length=1, max_length=80), content: sqlite3.Connection = Depends(get_content)) -> dict:
    """Metin içindeki bir sözcüğün (çekimli de olabilir) sözlük kaydını bulur."""
    word_id = repo.lookup_form(content, form)
    if word_id is None:
        raise HTTPException(status_code=404, detail="Bu sözcük sözlükte yok.")
    return {"word_id": word_id}


@router.get("/vocabulary/{word_id}")
def read_word(
    word_id: str, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    word = repo.word(content, word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")
    word["in_word_list"] = bool(progress.in_word_list(session, [word_id]))
    for key in ("synonyms", "antonyms", "related_words"):
        _mark_saved(session, word[key])
    return word


@router.get("/word-list")
def read_word_list(
    session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    items = repo.word_briefs(content, progress.word_list_ids(session))
    for item in items:
        item["in_word_list"] = True
    return {"items": items, "total": len(items)}


@router.put("/word-list/{word_id}")
def add_to_word_list(
    word_id: str, session: Session = Depends(get_user_session), content: sqlite3.Connection = Depends(get_content)
) -> dict:
    _require_word(content, word_id)
    progress.add_word(session, word_id)
    return {"word_id": word_id, "in_word_list": True}


@router.delete("/word-list/{word_id}")
def remove_from_word_list(word_id: str, session: Session = Depends(get_user_session)) -> dict:
    progress.remove_word(session, word_id)
    return {"word_id": word_id, "in_word_list": False}


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=80),
    session: Session = Depends(get_user_session),
    content: sqlite3.Connection = Depends(get_content),
) -> dict:
    results = repo.search(content, q, limit=20)
    _mark_saved(session, results["words"])
    return {"query": q, **results}
