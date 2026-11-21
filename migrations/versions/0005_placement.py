"""Seviye tespit sınavı: oturum türü ve sonuç kaydı.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

OLD_KINDS = "kind IN ('lesson','level','mixed')"
NEW_KINDS = "kind IN ('lesson','level','mixed','placement')"


def upgrade() -> None:
    # SQLite CHECK kısıtını yerinde değiştiremez; tablo kopyalanarak yeniden kurulur (veri korunur).
    with op.batch_alter_table("test_sessions", recreate="always") as batch:
        batch.drop_constraint("ck_test_sessions_kind", type_="check")
        batch.create_check_constraint("ck_test_sessions_kind", NEW_KINDS)
    op.create_table(
        "placement_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("test_sessions.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("start_level", sa.String(2), nullable=False),
        sa.Column("current_level", sa.String(2), nullable=False),
        sa.Column("blocks_json", sa.Text, nullable=False),
        sa.Column("result_level", sa.String(8)),
        sa.Column("recommended_level", sa.String(2)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("start_level IN ('A1','A2','B1','B2','C1','C2')", name="ck_placement_start_level"),
        sa.CheckConstraint(
            "result_level IS NULL OR result_level IN ('below_A1','A1','A2','B1','B2','C1','C2')",
            name="ck_placement_result_level",
        ),
    )
    op.create_index("ix_placement_results_started", "placement_results", ["started_at"])


def downgrade() -> None:
    op.drop_table("placement_results")
    op.execute("DELETE FROM test_sessions WHERE kind = 'placement'")
    with op.batch_alter_table("test_sessions", recreate="always") as batch:
        batch.drop_constraint("ck_test_sessions_kind", type_="check")
        batch.create_check_constraint("ck_test_sessions_kind", OLD_KINDS)
