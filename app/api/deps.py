from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_user_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.user_sessions()
    try:
        yield session
    finally:
        session.close()
