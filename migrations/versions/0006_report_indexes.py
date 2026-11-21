"""Rapor sorguları için dizinler (yalnızca dizin eklenir, veri değişmez).

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # "En çok yanılınan kelimeler": correct = 0 süzgeci + word_id gruplaması dizinden karşılanır.
    op.create_index("ix_review_history_wrong", "review_history", ["correct", "word_id"])
    # Günlük etkinlik ve haftalık başarı: cevap zamanına göre tarama.
    op.create_index("ix_user_answers_time", "user_answers", ["answered_at", "result"])


def downgrade() -> None:
    op.drop_index("ix_user_answers_time", "user_answers")
    op.drop_index("ix_review_history_wrong", "review_history")
