"""Yerel kullanıcı ilerlemesi: seviye, ders durumu, kişisel kelime listesi."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import CEFR_LEVELS, LessonProgress, PersonalWord, UserProfile, utcnow


def get_profile(session: Session) -> UserProfile:
    profile = session.get(UserProfile, 1)
    if profile is None:
        profile = UserProfile(id=1)
        session.add(profile)
        session.commit()
    return profile


def set_level(session: Session, level: str, source: str = "self") -> UserProfile:
    """Seviyeyi değiştirir. Önceki ders ve kelime kayıtlarına dokunulmaz."""
    if level not in CEFR_LEVELS:
        raise ValueError(level)
    profile = get_profile(session)
    profile.current_level = level
    profile.level_source = source
    session.commit()
    return profile


def lesson_statuses(session: Session) -> dict[str, str]:
    return dict(session.execute(select(LessonProgress.lesson_id, LessonProgress.status)).all())


def lesson_status(session: Session, lesson_id: str) -> str:
    row = session.get(LessonProgress, lesson_id)
    return row.status if row else "not_started"


def open_lesson(session: Session, lesson_id: str) -> str:
    row = session.get(LessonProgress, lesson_id)
    if row is None:
        row = LessonProgress(lesson_id=lesson_id, status="started")
        session.add(row)
    else:
        row.last_opened_at = utcnow()
    session.commit()
    return row.status


def set_completion(session: Session, lesson_id: str, completed: bool) -> str:
    row = session.get(LessonProgress, lesson_id)
    if row is None:
        row = LessonProgress(lesson_id=lesson_id, status="started")
        session.add(row)
    row.status = "completed" if completed else "started"
    row.completed_at = utcnow() if completed else None
    session.commit()
    return row.status


def recently_opened(session: Session, limit: int = 20) -> list[tuple[str, str]]:
    """(lesson_id, status) — en son açılan önce."""
    return list(
        session.execute(
            select(LessonProgress.lesson_id, LessonProgress.status)
            .order_by(LessonProgress.last_opened_at.desc())
            .limit(limit)
        ).all()
    )


def word_list_ids(session: Session) -> list[str]:
    return list(session.scalars(select(PersonalWord.word_id).order_by(PersonalWord.added_at.desc(), PersonalWord.word_id)))


def word_list_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(PersonalWord)) or 0


def in_word_list(session: Session, word_ids: list[str]) -> set[str]:
    if not word_ids:
        return set()
    return set(session.scalars(select(PersonalWord.word_id).where(PersonalWord.word_id.in_(word_ids))))


def add_word(session: Session, word_id: str) -> None:
    if session.get(PersonalWord, word_id) is None:
        session.add(PersonalWord(word_id=word_id))
        session.commit()


def remove_word(session: Session, word_id: str) -> None:
    row = session.get(PersonalWord, word_id)
    if row is not None:
        session.delete(row)
        session.commit()
