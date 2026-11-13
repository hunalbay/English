"""Test oturumları ve soru cevapları.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("lesson_id", sa.String(120)),
        sa.Column("level", sa.String(2)),
        sa.Column("question_ids", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('lesson','level','mixed')", name="ck_test_sessions_kind"),
    )
    op.create_index("ix_test_sessions_started", "test_sessions", ["started_at"])
    op.create_table(
        "user_answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(120), nullable=False),
        sa.Column("lesson_id", sa.String(120), nullable=False),
        sa.Column("answer_json", sa.Text, nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "question_id", name="uq_user_answers_session_question"),
        sa.CheckConstraint(
            "result IN ('correct','incorrect','ungraded','self_correct','self_partial','self_incorrect')",
            name="ck_user_answers_result",
        ),
    )
    op.create_index("ix_user_answers_question", "user_answers", ["question_id"])
    op.create_index("ix_user_answers_lesson", "user_answers", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("user_answers")
    op.drop_table("test_sessions")
