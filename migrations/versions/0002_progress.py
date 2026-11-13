"""Ders ilerlemesi ve kişisel kelime listesi.

İçerik kimlikleri (lesson_id, word_id) content.db'deki kararlı metin kimlikleridir;
iki veri tabanı arasında SQL yabancı anahtarı yoktur.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_progress",
        sa.Column("lesson_id", sa.String(120), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('started','completed')", name="ck_lesson_progress_status"),
    )
    op.create_index("ix_lesson_progress_last_opened", "lesson_progress", ["last_opened_at"])
    op.create_table(
        "personal_word_list",
        sa.Column("word_id", sa.String(120), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("personal_word_list")
    op.drop_index("ix_lesson_progress_last_opened", table_name="lesson_progress")
    op.drop_table("lesson_progress")
