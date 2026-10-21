"""Create append-only Adaptive Tutor interaction history.

Revision ID: tutor_20261018_01
Revises: 20261007_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "tutor_20261018_01"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = ("adaptive_tutor",)
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "tutor_interaction_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("interaction_id", sa.String(length=128), nullable=False),
        sa.Column("interaction_sequence", sa.Integer(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provenance", sa.String(length=128), nullable=False),
        sa.Column("assistance_level", sa.String(length=2), nullable=True),
        sa.Column("policy_version", sa.String(length=128), nullable=True),
        sa.Column("reason_codes", json_type, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("assessment_reference", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "interaction_sequence >= 1",
            name="ck_tutor_events_interaction_sequence",
        ),
        sa.CheckConstraint("event_sequence >= 1", name="ck_tutor_events_event_sequence"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_tutor_events_idempotency"),
        sa.UniqueConstraint(
            "session_id",
            "interaction_sequence",
            "event_sequence",
            name="uq_tutor_events_sequence",
        ),
        sa.UniqueConstraint(
            "decision_id",
            "event_type",
            "assessment_reference",
            name="uq_tutor_events_assessment_link",
        ),
    )
    op.create_index(
        "ix_tutor_events_decision_id",
        "tutor_interaction_events",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        "ix_tutor_events_history",
        "tutor_interaction_events",
        ["learner_id", "skill_id", "session_id", "interaction_sequence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tutor_events_history", table_name="tutor_interaction_events")
    op.drop_index("ix_tutor_events_decision_id", table_name="tutor_interaction_events")
    op.drop_table("tutor_interaction_events")
