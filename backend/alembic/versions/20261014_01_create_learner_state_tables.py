"""Create the learner-state table holding the latest state per learner and skill."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261014_01"
down_revision: str | None = "20261013_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_skill_states",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=16), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confusion_state", sa.String(length=40), nullable=False),
        sa.Column("confusion_support_need", sa.String(length=40), nullable=False),
        sa.Column("confusion_temporal_score", sa.Float(), nullable=False),
        sa.Column("disengagement_state", sa.String(length=40), nullable=False),
        sa.Column("disengagement_support_need", sa.String(length=40), nullable=False),
        sa.Column("recommended_action", sa.String(length=40), nullable=False),
        sa.Column("support_need", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "support_need IS NULL OR support_need BETWEEN 0 AND 1",
            name="ck_learner_skill_states_support_need",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("learner_id", "skill_id"),
    )


def downgrade() -> None:
    op.drop_table("learner_skill_states")
