"""Add append-only Independence Gain measurement and probe-control records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_03"
down_revision: str | None = "20261015_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_presentations_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("item_revision_id", sa.String(128), nullable=False),
        sa.Column("skill_id", sa.String(128), nullable=False),
        sa.Column("parallel_family_id", sa.String(128), nullable=False),
        sa.Column("equivalence_version", sa.String(128), nullable=False),
        sa.Column("measurement_role", sa.String(32), nullable=False),
        sa.Column("assistance_state", sa.String(32), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "measurement_role IN ('practice', 'unsupported_before', 'supported_practice', "
            "'unsupported_after', 'retention')",
            name="ck_item_presentations_v3_role",
        ),
        sa.CheckConstraint(
            "assistance_state IN ('none', 'scaffold_active', 'tutor_active', "
            "'adult_reported', 'unknown')",
            name="ck_item_presentations_v3_assistance",
        ),
        sa.CheckConstraint("sequence_no > 0", name="ck_item_presentations_v3_sequence"),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "sequence_no", name="uq_item_presentations_v3_sequence"),
    )
    op.create_table(
        "probe_reservations_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("item_revision_id", sa.String(128), nullable=False),
        sa.Column("parallel_family_id", sa.String(128), nullable=False),
        sa.Column("measurement_role", sa.String(32), nullable=False),
        sa.Column("reservation_version", sa.String(128), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contamination_sources_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("expires_at > reserved_at", name="ck_probe_reservations_v3_expiry"),
        sa.CheckConstraint(
            "measurement_role IN ('unsupported_before', 'unsupported_after')",
            name="ck_probe_reservations_v3_role",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_probe_reservations_v3_learner_item",
        "probe_reservations_v3",
        ["learner_id", "item_revision_id", "expires_at"],
    )
    op.create_table(
        "scaffold_exposure_records_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("scaffold_revision_id", sa.String(128), nullable=False),
        sa.Column("rendered_step_ids_json", sa.JSON(), nullable=False),
        sa.Column("answer_revealing", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "support_withdrawal_confirmations_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("exposure_id", sa.Uuid(), nullable=False),
        sa.Column("all_support_removed", sa.Boolean(), nullable=False),
        sa.Column("answer_revealing_state_cleared", sa.Boolean(), nullable=False),
        sa.Column("client_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "server_verified_at >= client_confirmed_at",
            name="ck_support_withdrawal_v3_order",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["exposure_id"], ["scaffold_exposure_records_v3.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_support_withdrawal_v3_episode"),
    )
    op.create_table(
        "authoritative_attempts_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("item_revision_id", sa.String(128), nullable=False),
        sa.Column("measurement_role", sa.String(32), nullable=False),
        sa.Column("assistance_state", sa.String(32), nullable=False),
        sa.Column("earned_score", sa.Numeric(18, 9), nullable=False),
        sa.Column("maximum_score", sa.Numeric(18, 9), nullable=False),
        sa.Column("rubric_version", sa.String(128), nullable=False),
        sa.Column("scoring_version", sa.String(128), nullable=False),
        sa.Column("server_authoritative", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "earned_score >= 0 AND maximum_score > 0 AND earned_score <= maximum_score",
            name="ck_authoritative_attempts_v3_scores",
        ),
        sa.CheckConstraint(
            "server_authoritative = true", name="ck_authoritative_attempts_v3_server"
        ),
        sa.ForeignKeyConstraint(["presentation_id"], ["item_presentations_v3.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_authoritative_attempts_v3_idempotency"),
    )
    op.create_table(
        "independence_measurements_v3",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("before_presentation_ids_json", sa.JSON(), nullable=False),
        sa.Column("after_presentation_ids_json", sa.JSON(), nullable=False),
        sa.Column("before_earned", sa.Numeric(18, 9), nullable=False),
        sa.Column("before_maximum", sa.Numeric(18, 9), nullable=False),
        sa.Column("after_earned", sa.Numeric(18, 9), nullable=False),
        sa.Column("after_maximum", sa.Numeric(18, 9), nullable=False),
        sa.Column("raw_independence_gain", sa.Numeric(18, 12), nullable=True),
        sa.Column("percentage_point_value", sa.Numeric(18, 9), nullable=True),
        sa.Column("formula_version", sa.String(128), nullable=False),
        sa.Column("scoring_versions_json", sa.JSON(), nullable=False),
        sa.Column("rubric_versions_json", sa.JSON(), nullable=False),
        sa.Column("equivalence_version", sa.String(128), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reasons_json", sa.JSON(), nullable=False),
        sa.Column("policy_update_status", sa.String(40), nullable=False),
        sa.Column("measurement_version", sa.String(128), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(valid = true AND raw_independence_gain IS NOT NULL AND "
            "percentage_point_value IS NOT NULL) OR "
            "(valid = false AND raw_independence_gain IS NULL AND "
            "percentage_point_value IS NULL)",
            name="ck_independence_measurements_v3_validity",
        ),
        sa.CheckConstraint(
            "policy_update_status IN ('authorized_delayed', 'not_authorized_baseline', "
            "'not_authorized_invalid')",
            name="ck_independence_measurements_v3_policy_status",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["support_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_independence_measurements_v3_episode"),
    )


def downgrade() -> None:
    op.drop_table("independence_measurements_v3")
    op.drop_table("authoritative_attempts_v3")
    op.drop_table("support_withdrawal_confirmations_v3")
    op.drop_table("scaffold_exposure_records_v3")
    op.drop_index("ix_probe_reservations_v3_learner_item", table_name="probe_reservations_v3")
    op.drop_table("probe_reservations_v3")
    op.drop_table("item_presentations_v3")
