from __future__ import annotations

from collections.abc import Iterator

import sqlite3

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.content_db import connect_readonly


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_user_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.user_sessions()
    try:
        yield session
    finally:
        session.close()


def get_content(request: Request) -> Iterator[sqlite3.Connection]:
    """İstek süresince salt okunur içerik bağlantısı."""
    path = request.app.state.settings.content_db_path
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Eğitim içeriği bulunamadı. Programı yeniden kurmayı deneyin.")
    conn = connect_readonly(path)
    try:
        conn.execute("SELECT value FROM content_meta LIMIT 1").fetchone()
    except sqlite3.DatabaseError:
        conn.close()
        raise HTTPException(
            status_code=503, detail="Eğitim içeriği dosyası bozuk ya da okunamıyor. Programı yeniden kurmayı deneyin."
        ) from None
    try:
        yield conn
    finally:
        conn.close()
