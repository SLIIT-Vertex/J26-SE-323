"""Add delivery jobs, learning-reward entries, exports, and consent references."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gam_20261015_02"
down_revision: str | None = "gam_20261014_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('ingestion', 'feature_construction', 'retention_check', 'evaluation', 'export')",
            name="ck_delivery_jobs_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'claimed', 'succeeded', 'failed')",
            name="ck_delivery_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_delivery_jobs_attempts"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_delivery_jobs_idempotency"),
    )
    op.create_table(
        "learning_reward_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("points >= 0", name="ck_learning_reward_entries_points"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("learner_id", "episode_id", name="uq_learning_reward_entries_episode"),
    )
    op.create_table(
        "research_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("consent_reference", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'succeeded', 'failed')", name="ck_research_exports_status"
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "consent_eligibility_references",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("consent_reference", sa.String(length=128), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("learner_id", "purpose"),
    )


def downgrade() -> None:
    op.drop_table("consent_eligibility_references")
    op.drop_table("research_exports")
    op.drop_table("learning_reward_entries")
    op.drop_table("delivery_jobs")
