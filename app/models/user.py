"""user.db modelleri. Şema değişiklikleri yalnızca Alembic migration ile yapılır."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.user_db import UserBase

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationSetting(UserBase):
    """Anahtar–değer biçiminde uygulama ayarı. Değer JSON olarak saklanır."""

    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UserProfile(UserBase):
    """Tek satırlık yerel kullanıcı profili (hesap/üyelik yoktur)."""

    __tablename__ = "user_profile"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_user_profile_single_row"),
        CheckConstraint(
            "current_level IS NULL OR current_level IN ('A1','A2','B1','B2','C1','C2')",
            name="ck_user_profile_level",
        ),
        CheckConstraint(
            "level_source IS NULL OR level_source IN ('self','placement')",
            name="ck_user_profile_level_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_level: Mapped[str | None] = mapped_column(String(2))
    level_source: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class LessonProgress(UserBase):
    """Bir dersin açılma ve tamamlanma durumu. lesson_id, content.db'deki kararlı kimliktir."""

    __tablename__ = "lesson_progress"
    __table_args__ = (
        CheckConstraint("status IN ('started','completed')", name="ck_lesson_progress_status"),
    )

    lesson_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    first_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PersonalWord(UserBase):
    """Kullanıcının tekrar listesine eklediği kelime."""

    __tablename__ = "personal_word_list"

    word_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReviewItem(UserBase):
    """Bir kelimenin bir yöndeki (EN→TR ya da TR→EN) aralıklı tekrar durumu."""

    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint("word_id", "direction", name="uq_review_items_word_direction"),
        CheckConstraint("direction IN ('en_tr','tr_en')", name="ck_review_items_direction"),
        CheckConstraint("interval_days >= 0 AND repetitions >= 0 AND lapses >= 0", name="ck_review_items_counts"),
        Index("ix_review_items_due", "direction", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    ease: Mapped[float] = mapped_column(Float, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ReviewHistory(UserBase):
    """Her kart cevabı ve alıştırma sonucu için bir kayıt."""

    __tablename__ = "review_history"
    __table_args__ = (
        Index("ix_review_history_word", "word_id", "reviewed_at"),
        Index("ix_review_history_time", "reviewed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(8))
    activity: Mapped[str] = mapped_column(String(24), nullable=False)
    grade: Mapped[int | None] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    interval_before: Mapped[int | None] = mapped_column(Integer)
    interval_after: Mapped[int | None] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
