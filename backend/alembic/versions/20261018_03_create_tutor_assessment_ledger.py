"""Create the Adaptive Tutor assessment correlation ledger.

Revision ID: tutor_20261018_02
Revises: tutor_20261018_01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tutor_20261018_02"
down_revision: str | None = "tutor_20261018_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tutor_assessment_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("interaction_sequence", sa.Integer(), nullable=False),
        sa.Column("source_component", sa.String(length=128), nullable=False),
        sa.Column("question_reference", sa.String(length=128), nullable=False),
        sa.Column("question_version", sa.String(length=128), nullable=False),
        sa.Column("authorization_reference", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "interaction_sequence >= 1",
            name="ck_tutor_assessment_interaction_sequence",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'INVALIDATED')",
            name="ck_tutor_assessment_interaction_status",
        ),
        sa.CheckConstraint(
            "(status = 'OPEN' AND closed_at IS NULL) OR "
            "(status <> 'OPEN' AND closed_at IS NOT NULL)",
            name="ck_tutor_assessment_interaction_lifecycle",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_tutor_assessment_interaction_idempotency",
        ),
        sa.UniqueConstraint(
            "session_id",
            "interaction_sequence",
            name="uq_tutor_assessment_interaction_sequence",
        ),
    )
    op.create_index(
        "ix_tutor_assessment_interaction_scope",
        "tutor_assessment_interactions",
        ["learner_id", "skill_id", "session_id"],
        unique=False,
    )

    op.create_table(
        "tutor_assessment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("attempt_sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_component", sa.String(length=128), nullable=False),
        sa.Column("source_score_reference", sa.String(length=128), nullable=False),
        sa.Column("scorer_authorized", sa.Boolean(), nullable=False),
        sa.Column("source_mapping_approved", sa.Boolean(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("partial_credit", sa.Float(), nullable=True),
        sa.Column("scoring_version", sa.String(length=128), nullable=True),
        sa.Column("item_rubric_version", sa.String(length=128), nullable=True),
        sa.Column("severity_category", sa.String(length=128), nullable=True),
        sa.Column("severity_value", sa.Float(), nullable=True),
        sa.Column("severity_policy_version", sa.String(length=128), nullable=True),
        sa.Column("severity_reviewed", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_sequence >= 1",
            name="ck_tutor_assessment_attempt_sequence",
        ),
        sa.CheckConstraint(
            "partial_credit IS NULL OR (partial_credit >= 0 AND partial_credit <= 1)",
            name="ck_tutor_assessment_partial_credit",
        ),
        sa.CheckConstraint(
            "severity_value IS NULL OR (severity_value >= 0 AND severity_value <= 1)",
            name="ck_tutor_assessment_severity",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED')",
            name="ck_tutor_assessment_attempt_status",
        ),
        sa.CheckConstraint(
            "(severity_category IS NULL AND severity_value IS NULL AND "
            "severity_policy_version IS NULL) OR "
            "(severity_category IS NOT NULL AND severity_value IS NOT NULL AND "
            "severity_policy_version IS NOT NULL)",
            name="ck_tutor_assessment_severity_shape",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND is_correct IS NULL AND accepted_at IS NULL AND "
            "observed_at IS NULL AND scoring_version IS NULL AND "
            "item_rubric_version IS NULL AND severity_value IS NULL AND "
            "NOT scorer_authorized AND NOT source_mapping_approved AND "
            "NOT severity_reviewed) OR "
            "(status = 'ACCEPTED' AND is_correct IS NOT NULL AND accepted_at IS NOT NULL "
            "AND observed_at IS NOT NULL AND scoring_version IS NOT NULL AND "
            "item_rubric_version IS NOT NULL)",
            name="ck_tutor_assessment_attempt_state",
        ),
        sa.CheckConstraint(
            "accepted_at IS NULL OR (recorded_at <= accepted_at AND observed_at <= accepted_at)",
            name="ck_tutor_assessment_attempt_times",
        ),
        sa.CheckConstraint(
            "is_correct IS NOT TRUE OR severity_value IS NULL OR severity_value = 0",
            name="ck_tutor_assessment_correct_severity",
        ),
        sa.ForeignKeyConstraint(["interaction_id"], ["tutor_assessment_interactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_tutor_assessment_attempt_idempotency"),
        sa.UniqueConstraint(
            "interaction_id",
            "attempt_sequence",
            name="uq_tutor_assessment_attempt_sequence",
        ),
        sa.UniqueConstraint(
            "source_component",
            "source_score_reference",
            name="uq_tutor_assessment_source_score",
        ),
    )
    op.create_index(
        "ix_tutor_assessment_attempt_snapshot",
        "tutor_assessment_attempts",
        ["interaction_id", "attempt_sequence", "accepted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tutor_assessment_attempt_snapshot",
        table_name="tutor_assessment_attempts",
    )
    op.drop_table("tutor_assessment_attempts")
    op.drop_index(
        "ix_tutor_assessment_interaction_scope",
        table_name="tutor_assessment_interactions",
    )
    op.drop_table("tutor_assessment_interactions")
