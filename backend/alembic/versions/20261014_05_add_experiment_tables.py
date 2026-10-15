"""Add experiment, arm, and learner-level assignment tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261014_05"
down_revision: str | None = "20261014_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version", sa.String(length=64), nullable=False),
        sa.Column("protocol_hash", sa.String(length=64), nullable=False),
        sa.Column("eligibility_rule", sa.String(length=128), nullable=False),
        sa.Column("allocation_rule", sa.String(length=128), nullable=False),
        sa.Column("assignment_unit", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(protocol_hash) = 64", name="ck_experiments_protocol_hash"),
        sa.CheckConstraint("assignment_unit = 'learner'", name="ck_experiments_assignment_unit"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "experiment_arms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("arm_key", sa.String(length=64), nullable=False),
        sa.Column("decision_mode", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "arm_key IN ('baseline_performance_triggered', 'proposed_misconception_ig_policy')",
            name="ck_experiment_arms_key",
        ),
        sa.CheckConstraint(
            "decision_mode IN ('performance_triggered_fixed', 'learned')",
            name="ck_experiment_arms_mode",
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "arm_key", name="uq_experiment_arms_key"),
    )
    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("arm_id", sa.Uuid(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["arm_id"], ["experiment_arms.id"]),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id", "learner_id", name="uq_experiment_assignments_learner"
        ),
    )


def downgrade() -> None:
    op.drop_table("experiment_assignments")
    op.drop_table("experiment_arms")
    op.drop_table("experiments")
