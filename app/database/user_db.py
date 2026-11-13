"""Kullanıcı veri tabanı (user.db): ilerleme, cevaplar, ayarlar.

İçerikten ayrı bir dosyadır; içerik güncellemeleri kullanıcı geçmişini etkilemez.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class UserBase(DeclarativeBase):
    """user.db tablolarının ortak tabanı."""


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def create_user_engine(path: Path) -> Engine:
    engine = create_engine(sqlite_url(path), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")  # beklenmeyen kapanmada veri kaybını azaltır
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
