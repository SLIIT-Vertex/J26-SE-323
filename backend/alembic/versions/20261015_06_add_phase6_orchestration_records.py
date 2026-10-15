"""Add durable orchestration projections, events, receipts, and audit records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_06"
down_revision: str | None = "20261015_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phase6_episode_runs",
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("content_package_version", sa.String(length=128), nullable=False),
        sa.Column("protocol_version", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("condition", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("state_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "environment IN ('development', 'test')", name="ck_phase6_runs_environment"
        ),
        sa.CheckConstraint(
            "condition IN ('baseline', 'proposed')", name="ck_phase6_runs_condition"
        ),
        sa.CheckConstraint(
            "status IN ('before_presented', 'support_active', 'support_complete', "
            "'support_withdrawn', 'after_presented', 'completed', 'invalidated')",
            name="ck_phase6_runs_status",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("episode_id"),
        sa.UniqueConstraint("session_id", name="uq_phase6_episode_runs_session"),
    )
    op.create_index(
        "ix_phase6_runs_learner_created",
        "phase6_episode_runs",
        ["learner_id", "created_at"],
    )
    op.create_table(
        "phase6_probe_reservations",
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("item_revision_id", sa.String(length=128), nullable=False),
        sa.Column("gateway_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contamination_source", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('reserved', 'used', 'contaminated')", name="ck_phase6_probe_status"
        ),
        sa.CheckConstraint("expires_at > reserved_at", name="ck_phase6_probe_expiry"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("reservation_id"),
        sa.UniqueConstraint(
            "learner_id", "item_revision_id", name="uq_phase6_probe_learner_revision"
        ),
    )
    op.create_index(
        "ix_phase6_probe_episode", "phase6_probe_reservations", ["episode_id", "status"]
    )
    op.create_table(
        "phase6_episode_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_phase6_events_sequence"),
        sa.CheckConstraint("length(payload_sha256) = 64", name="ck_phase6_events_hash"),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["phase6_episode_runs.episode_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "sequence", name="uq_phase6_events_sequence"),
        sa.UniqueConstraint("event_id", name="uq_phase6_events_event_id"),
    )
    op.create_index(
        "ix_phase6_events_episode_time",
        "phase6_episode_events",
        ["episode_id", "occurred_at"],
    )
    op.create_table(
        "phase6_idempotency_receipts",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(request_sha256) = 64", name="ck_phase6_receipts_request_hash"),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["phase6_episode_runs.episode_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("idempotency_key"),
    )
    op.create_table(
        "phase6_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["episode_id"], ["phase6_episode_runs.episode_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_phase6_audit_episode_time",
        "phase6_audit_events",
        ["episode_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_phase6_audit_episode_time", table_name="phase6_audit_events")
    op.drop_table("phase6_audit_events")
    op.drop_table("phase6_idempotency_receipts")
    op.drop_index("ix_phase6_events_episode_time", table_name="phase6_episode_events")
    op.drop_table("phase6_episode_events")
    op.drop_index("ix_phase6_probe_episode", table_name="phase6_probe_reservations")
    op.drop_table("phase6_probe_reservations")
    op.drop_index("ix_phase6_runs_learner_created", table_name="phase6_episode_runs")
    op.drop_table("phase6_episode_runs")
