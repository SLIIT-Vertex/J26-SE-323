"""Create the adaptive gamification model-first evidence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "gam_20261013_02"
down_revision: str | None = "20261007_01"
branch_labels: str | Sequence[str] | None = ("gamification",)
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
big_int = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("client_session_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=False),
        sa.Column("device_class", sa.String(length=20), nullable=False),
        sa.Column("experiment_assignment_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_sequence", big_int, server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'abandoned', 'expired')",
            name="ck_game_sessions_status",
        ),
        sa.CheckConstraint("language IN ('si', 'ta', 'en')", name="ck_game_sessions_language"),
        sa.CheckConstraint("last_event_sequence >= 0", name="ck_game_sessions_event_sequence"),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ck_game_sessions_ended_at"
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("learner_id", "client_session_id", name="uq_game_sessions_client"),
        sa.UniqueConstraint("id", "learner_id", name="uq_game_sessions_id_learner"),
    )
    op.create_index(
        "ix_game_sessions_learner_started", "game_sessions", ["learner_id", "started_at"]
    )

    op.create_table(
        "item_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("item_version", sa.String(length=128), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("skill_taxonomy_version", sa.String(length=128), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("support_state", sa.String(length=20), nullable=False),
        sa.Column("answer_json", json_type, nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("active_time_ms", sa.Integer(), nullable=True),
        sa.Column("hint_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "phase IN ('baseline', 'supported', 'verification', 'retention')",
            name="ck_item_responses_phase",
        ),
        sa.CheckConstraint(
            "support_state IN ('unsupported', 'supported', 'unknown')",
            name="ck_item_responses_support_state",
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_item_responses_score"),
        sa.CheckConstraint("attempt_no >= 1", name="ck_item_responses_attempt_no"),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_item_responses_response_time",
        ),
        sa.CheckConstraint(
            "active_time_ms IS NULL OR active_time_ms >= 0",
            name="ck_item_responses_active_time",
        ),
        sa.CheckConstraint("hint_count >= 0", name="ck_item_responses_hint_count"),
        sa.ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_item_responses_session_learner",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_item_responses_idempotency"),
        sa.UniqueConstraint(
            "session_id",
            "item_id",
            "item_version",
            "attempt_no",
            "phase",
            name="uq_item_responses_attempt",
        ),
    )
    op.create_index(
        "ix_item_responses_learner_submitted", "item_responses", ["learner_id", "submitted_at"]
    )
    op.create_index(
        "ix_item_responses_session_phase", "item_responses", ["session_id", "phase"]
    )

    op.create_table(
        "adaptive_episodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("skill_taxonomy_version", sa.String(length=128), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("baseline_response_id", sa.Uuid(), nullable=True),
        sa.Column("verification_response_id", sa.Uuid(), nullable=True),
        sa.Column("retention_response_id", sa.Uuid(), nullable=True),
        sa.Column("episode_protocol_version", sa.String(length=128), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("support_withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_reason", sa.String(length=128), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "phase IN ('created', 'baseline_started', 'baseline_recorded', "
            "'struggle_assessed', 'misconception_recorded', 'support_decided', "
            "'support_delivered', 'support_withdrawn', 'verification_scheduled', "
            "'verification_started', 'verification_recorded', 'outcome_recorded', "
            "'completed', 'abandoned', 'invalidated')",
            name="ck_adaptive_episodes_phase",
        ),
        sa.CheckConstraint(
            "((phase IN ('abandoned', 'invalidated')) AND terminal_reason IS NOT NULL) OR "
            "((phase NOT IN ('abandoned', 'invalidated')) AND terminal_reason IS NULL)",
            name="ck_adaptive_episodes_terminal_reason",
        ),
        sa.CheckConstraint(
            "transitioned_at >= opened_at", name="ck_adaptive_episodes_transitioned_at"
        ),
        sa.ForeignKeyConstraint(["baseline_response_id"], ["item_responses.id"]),
        sa.ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_adaptive_episodes_session_learner",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.ForeignKeyConstraint(["retention_response_id"], ["item_responses.id"]),
        sa.ForeignKeyConstraint(["verification_response_id"], ["item_responses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_adaptive_episodes_learner_opened", "adaptive_episodes", ["learner_id", "opened_at"]
    )
    op.create_index(
        "ix_adaptive_episodes_skill_phase", "adaptive_episodes", ["skill_code", "phase"]
    )

    op.create_table(
        "interaction_events",
        sa.Column("id", big_int, autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_version", sa.SmallInteger(), nullable=False),
        sa.Column("sequence_no", big_int, nullable=False),
        sa.Column("client_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_tz_offset_min", sa.SmallInteger(), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("consent_scope_version", sa.String(length=128), nullable=False),
        sa.CheckConstraint("event_version >= 1", name="ck_interaction_events_version"),
        sa.CheckConstraint("sequence_no >= 1", name="ck_interaction_events_sequence"),
        sa.CheckConstraint(
            "client_tz_offset_min BETWEEN -840 AND 840", name="ck_interaction_events_tz_offset"
        ),
        sa.CheckConstraint("length(payload_hash) = 64", name="ck_interaction_events_payload_hash"),
        sa.ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_interaction_events_session_learner",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_interaction_events_sequence"),
    )
    op.create_index(
        "ix_interaction_events_episode_type", "interaction_events", ["episode_id", "event_type"]
    )
    op.create_index(
        "ix_interaction_events_learner_received",
        "interaction_events",
        ["learner_id", "server_received_at"],
    )

    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protocol_version", sa.String(length=128), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("features_json", json_type, nullable=False),
        sa.Column("missingness_json", json_type, nullable=False),
        sa.Column("source_as_of_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feature_snapshots_learner_skill",
        "feature_snapshots",
        ["learner_id", "skill_code", "captured_at"],
    )

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("model_role", sa.String(length=30), nullable=False),
        sa.Column("semantic_version", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.String(length=500), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("feature_definition_version", sa.String(length=128), nullable=False),
        sa.Column("training_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("metrics_json", json_type, nullable=False),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "model_role IN ('misconception', 'support_policy', 'independence_gain')",
            name="ck_model_versions_role",
        ),
        sa.CheckConstraint(
            "approval_status IN ('draft', 'validated', 'approved', 'retired')",
            name="ck_model_versions_approval",
        ),
        sa.CheckConstraint("length(artifact_sha256) = 64", name="ck_model_versions_sha256"),
        sa.CheckConstraint(
            "approval_status <> 'approved' OR "
            "(approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_model_versions_approved_metadata",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name", "semantic_version", name="uq_model_versions_name_version"),
    )
    op.create_index(
        "ix_model_versions_role_approval", "model_versions", ["model_role", "approval_status"]
    )

    op.create_table(
        "misconception_inferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("feature_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("misconception_catalogue_version", sa.String(length=128), nullable=False),
        sa.Column("top_misconception_code", sa.String(length=128), nullable=True),
        sa.Column("entropy", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("abstained", sa.Boolean(), nullable=False),
        sa.Column("reason_codes_json", json_type, nullable=False),
        sa.Column("inferred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entropy >= 0", name="ck_misconception_inferences_entropy"),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_misconception_inferences_confidence"
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], ["feature_snapshots.id"]),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_misconception_inferences_episode"),
    )
    op.create_index(
        "ix_misconception_inferences_model",
        "misconception_inferences",
        ["model_version_id", "inferred_at"],
    )

    op.create_table(
        "misconception_probabilities",
        sa.Column("inference_id", sa.Uuid(), nullable=False),
        sa.Column("misconception_code", sa.String(length=128), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "probability BETWEEN 0 AND 1", name="ck_misconception_probabilities_value"
        ),
        sa.CheckConstraint("rank >= 1", name="ck_misconception_probabilities_rank"),
        sa.ForeignKeyConstraint(["inference_id"], ["misconception_inferences.id"]),
        sa.PrimaryKeyConstraint("inference_id", "misconception_code"),
        sa.UniqueConstraint("inference_id", "rank", name="uq_misconception_probabilities_rank"),
    )

    op.create_table(
        "support_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("policy_model_version_id", sa.Uuid(), nullable=True),
        sa.Column("feature_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("selected_action_id", sa.String(length=128), nullable=False),
        sa.Column("selected_action_type", sa.String(length=40), nullable=False),
        sa.Column("selection_probability", sa.Float(), nullable=False),
        sa.Column("decision_mode", sa.String(length=30), nullable=False),
        sa.Column("policy_version", sa.String(length=128), nullable=False),
        sa.Column("support_catalogue_version", sa.String(length=128), nullable=False),
        sa.Column("reason_codes_json", json_type, nullable=False),
        sa.Column("random_seed", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision_mode IN ('deterministic_reference', 'shadow', 'learned', "
            "'conservative_fallback')",
            name="ck_support_decisions_mode",
        ),
        sa.CheckConstraint(
            "selection_probability BETWEEN 0 AND 1", name="ck_support_decisions_probability"
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["feature_snapshot_id"], ["feature_snapshots.id"]),
        sa.ForeignKeyConstraint(["policy_model_version_id"], ["model_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_support_decisions_episode"),
    )
    op.create_index(
        "ix_support_decisions_policy_time", "support_decisions", ["policy_version", "decided_at"]
    )

    op.create_table(
        "support_candidates",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("ineligibility_reasons_json", json_type, nullable=False),
        sa.Column("predicted_reward", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("propensity", sa.Float(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("propensity BETWEEN 0 AND 1", name="ck_support_candidates_propensity"),
        sa.CheckConstraint(
            "uncertainty IS NULL OR uncertainty BETWEEN 0 AND 1",
            name="ck_support_candidates_uncertainty",
        ),
        sa.CheckConstraint("rank >= 1", name="ck_support_candidates_rank"),
        sa.CheckConstraint(
            "eligible OR propensity = 0", name="ck_support_candidates_ineligible_propensity"
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["support_decisions.id"]),
        sa.PrimaryKeyConstraint("decision_id", "action_id"),
        sa.UniqueConstraint("decision_id", "rank", name="uq_support_candidates_rank"),
    )

    op.create_table(
        "support_exposures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.String(length=128), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("interaction_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("render_version", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "delivery_status IN ('scheduled', 'presented', 'interacted', 'dismissed', "
            "'completed', 'failed')",
            name="ck_support_exposures_status",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_support_exposures_duration"
        ),
        sa.CheckConstraint("interaction_count >= 0", name="ck_support_exposures_interactions"),
        sa.ForeignKeyConstraint(["decision_id"], ["support_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_support_exposures_decision_presented",
        "support_exposures",
        ["decision_id", "presented_at"],
    )

    op.create_table(
        "verification_pairs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_item_id", sa.String(length=128), nullable=False),
        sa.Column("baseline_item_version", sa.String(length=128), nullable=False),
        sa.Column("verification_item_id", sa.String(length=128), nullable=False),
        sa.Column("verification_item_version", sa.String(length=128), nullable=False),
        sa.Column("skill_code", sa.String(length=128), nullable=False),
        sa.Column("equivalence_version", sa.String(length=128), nullable=False),
        sa.Column("difficulty_delta", sa.Float(), nullable=False),
        sa.Column("surface_similarity", sa.Float(), nullable=False),
        sa.Column("answer_overlap", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "baseline_item_id <> verification_item_id OR "
            "baseline_item_version <> verification_item_version",
            name="ck_verification_pairs_distinct_items",
        ),
        sa.CheckConstraint(
            "surface_similarity BETWEEN 0 AND 1", name="ck_verification_pairs_similarity"
        ),
        sa.CheckConstraint("answer_overlap BETWEEN 0 AND 1", name="ck_verification_pairs_overlap"),
        sa.CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'approved', 'rejected')",
            name="ck_verification_pairs_review",
        ),
        sa.CheckConstraint(
            "review_status NOT IN ('reviewed', 'approved', 'rejected') OR "
            "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_verification_pairs_review_metadata",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_verification_pairs_episode"),
    )
    op.create_index(
        "ix_verification_pairs_skill_review",
        "verification_pairs",
        ["skill_code", "review_status"],
    )

    op.create_table(
        "independence_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("verification_pair_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("verification_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("raw_independence_gain", sa.Numeric(precision=6, scale=5), nullable=True),
        sa.Column("normalized_gain", sa.Float(), nullable=True),
        sa.Column("time_adjusted_gain", sa.Float(), nullable=True),
        sa.Column("misconception_resolution", sa.Float(), nullable=True),
        sa.Column("support_dependency_index", sa.Float(), nullable=True),
        sa.Column("validity", sa.String(length=20), nullable=False),
        sa.Column("baseline_support_state", sa.String(length=20), nullable=False),
        sa.Column("verification_support_state", sa.String(length=20), nullable=False),
        sa.Column("invalid_reason", sa.String(length=128), nullable=True),
        sa.Column("formula_version", sa.String(length=128), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("baseline_score BETWEEN 0 AND 1", name="ck_independence_outcomes_baseline"),
        sa.CheckConstraint(
            "verification_score BETWEEN 0 AND 1", name="ck_independence_outcomes_verification"
        ),
        sa.CheckConstraint(
            "raw_independence_gain BETWEEN -1 AND 1",
            name="ck_independence_outcomes_raw_gain",
        ),
        sa.CheckConstraint(
            "validity IN ('pending', 'valid', 'invalid')", name="ck_independence_outcomes_validity"
        ),
        sa.CheckConstraint(
            "baseline_support_state IN ('unsupported', 'supported', 'unknown') AND "
            "verification_support_state IN ('unsupported', 'supported', 'unknown')",
            name="ck_independence_outcomes_support_state",
        ),
        sa.CheckConstraint(
            "(validity = 'valid' AND baseline_support_state = 'unsupported' AND "
            "verification_support_state = 'unsupported' AND raw_independence_gain IS NOT NULL "
            "AND invalid_reason IS NULL) OR "
            "(validity = 'invalid' AND raw_independence_gain IS NULL AND invalid_reason IS NOT NULL) OR "
            "(validity = 'pending' AND raw_independence_gain IS NULL AND invalid_reason IS NULL)",
            name="ck_independence_outcomes_validity_fields",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["adaptive_episodes.id"]),
        sa.ForeignKeyConstraint(["verification_pair_id"], ["verification_pairs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", name="uq_independence_outcomes_episode"),
    )
    op.create_index(
        "ix_independence_outcomes_validity_time",
        "independence_outcomes",
        ["validity", "calculated_at"],
    )


def downgrade() -> None:
    op.drop_table("independence_outcomes")
    op.drop_table("verification_pairs")
    op.drop_table("support_exposures")
    op.drop_table("support_candidates")
    op.drop_table("support_decisions")
    op.drop_table("misconception_probabilities")
    op.drop_table("misconception_inferences")
    op.drop_table("model_versions")
    op.drop_table("feature_snapshots")
    op.drop_table("interaction_events")
    op.drop_table("adaptive_episodes")
    op.drop_table("item_responses")
    op.drop_table("game_sessions")

