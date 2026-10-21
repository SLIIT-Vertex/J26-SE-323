"""Add one durable row per delivered help type in a multi-help learning-flow episode."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gam_20261021_02"
down_revision: str | None = "gam_20261021_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "learning_flow_support_rounds"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("round_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey("learning_flow_episode_runs.episode_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("scaffold_type", sa.String(64), nullable=False),
        sa.Column("english_tag_key", sa.String(64), nullable=False),
        sa.Column("order_position", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(16)),
        sa.Column("supported_correct", sa.Boolean()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("episode_id", "round_number", name="uq_learning_flow_support_round"),
        sa.UniqueConstraint("episode_id", "scaffold_type", name="uq_learning_flow_support_type"),
        sa.CheckConstraint("round_number >= 1", name="ck_learning_flow_support_round_number"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded', 'failed')",
            name="ck_learning_flow_support_round_outcome",
        ),
    )
    op.create_index(
        "ix_learning_flow_support_rounds_episode", TABLE, ["episode_id", "round_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_learning_flow_support_rounds_episode", table_name=TABLE)
    op.drop_table(TABLE)
