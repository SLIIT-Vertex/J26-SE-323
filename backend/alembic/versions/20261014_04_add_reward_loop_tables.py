"""Add the policy cursor, learner-skill summary, and learner-evidence outbox."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261014_04"
down_revision: str | None = "20261014_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_update_cursors",
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "artifact_sha256 IS NULL OR length(artifact_sha256) = 64",
            name="ck_policy_update_cursors_sha256",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.PrimaryKeyConstraint("episode_id"),
    )
    op.create_table(
        "learner_skill_summaries",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("unsupported_attempts", sa.Integer(), nullable=False),
        sa.Column("supported_attempts", sa.Integer(), nullable=False),
        sa.Column("independent_accuracy", sa.Float(), nullable=True),
        sa.Column("supported_accuracy", sa.Float(), nullable=True),
        sa.Column("mean_independence_gain", sa.Float(), nullable=True),
        sa.Column("support_dependency_index", sa.Float(), nullable=True),
        sa.Column("valid_outcome_count", sa.Integer(), nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_version", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "unsupported_attempts >= 0", name="ck_learner_skill_summaries_unsupported"
        ),
        sa.CheckConstraint(
            "supported_attempts >= 0", name="ck_learner_skill_summaries_supported"
        ),
        sa.CheckConstraint(
            "valid_outcome_count >= 0", name="ck_learner_skill_summaries_valid_outcomes"
        ),
        sa.CheckConstraint(
            "independent_accuracy IS NULL OR "
            "(independent_accuracy >= 0 AND independent_accuracy <= 1)",
            name="ck_learner_skill_summaries_independent_accuracy",
        ),
        sa.CheckConstraint(
            "supported_accuracy IS NULL OR (supported_accuracy >= 0 AND supported_accuracy <= 1)",
            name="ck_learner_skill_summaries_supported_accuracy",
        ),
        sa.CheckConstraint(
            "support_dependency_index IS NULL OR "
            "(support_dependency_index >= 0 AND support_dependency_index <= 1)",
            name="ck_learner_skill_summaries_dependency",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("learner_id", "skill_code"),
    )
    op.create_table(
        "learner_evidence_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("universal_skill_id", sa.String(length=16), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'published')", name="ck_learner_evidence_outbox_status"
        ),
        sa.CheckConstraint("attempt_count >= 1", name="ck_learner_evidence_outbox_attempts"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_learner_evidence_outbox_key"),
    )
    op.create_index(
        "ix_learner_evidence_outbox_learner",
        "learner_evidence_outbox",
        ["learner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learner_evidence_outbox_learner", table_name="learner_evidence_outbox")
    op.drop_table("learner_evidence_outbox")
    op.drop_table("learner_skill_summaries")
    op.drop_table("policy_update_cursors")
