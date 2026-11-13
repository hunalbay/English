"""Aralıklı tekrar: kart durumları ve cevap geçmişi.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("word_id", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("ease", sa.Float, nullable=False),
        sa.Column("interval_days", sa.Integer, nullable=False),
        sa.Column("repetitions", sa.Integer, nullable=False),
        sa.Column("lapses", sa.Integer, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("word_id", "direction", name="uq_review_items_word_direction"),
        sa.CheckConstraint("direction IN ('en_tr','tr_en')", name="ck_review_items_direction"),
        sa.CheckConstraint("interval_days >= 0 AND repetitions >= 0 AND lapses >= 0", name="ck_review_items_counts"),
    )
    op.create_index("ix_review_items_due", "review_items", ["direction", "due_at"])
    op.create_table(
        "review_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("word_id", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(8)),
        sa.Column("activity", sa.String(24), nullable=False),
        sa.Column("grade", sa.Integer),
        sa.Column("correct", sa.Boolean, nullable=False),
        sa.Column("interval_before", sa.Integer),
        sa.Column("interval_after", sa.Integer),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_history_word", "review_history", ["word_id", "reviewed_at"])
    op.create_index("ix_review_history_time", "review_history", ["reviewed_at"])


def downgrade() -> None:
    op.drop_table("review_history")
    op.drop_table("review_items")
