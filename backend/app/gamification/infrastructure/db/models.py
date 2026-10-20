from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")
BigIntType = BigInteger().with_variant(Integer(), "sqlite")


class GameSessionModel(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        UniqueConstraint("learner_id", "client_session_id", name="uq_game_sessions_client"),
        UniqueConstraint("id", "learner_id", name="uq_game_sessions_id_learner"),
        CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'abandoned', 'expired')",
            name="ck_game_sessions_status",
        ),
        CheckConstraint("language IN ('si', 'ta', 'en')", name="ck_game_sessions_language"),
        CheckConstraint("last_event_sequence >= 0", name="ck_game_sessions_event_sequence"),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ck_game_sessions_ended_at"
        ),
        Index("ix_game_sessions_learner_started", "learner_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    client_session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    app_version: Mapped[str] = mapped_column(String(40), nullable=False)
    device_class: Mapped[str] = mapped_column(String(20), nullable=False)
    experiment_assignment_id: Mapped[UUID | None] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_sequence: Mapped[int] = mapped_column(
        BigIntType, server_default=text("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ItemResponseModel(Base):
    __tablename__ = "item_responses"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_item_responses_idempotency"),
        UniqueConstraint(
            "session_id",
            "item_id",
            "item_version",
            "attempt_no",
            "phase",
            name="uq_item_responses_attempt",
        ),
        ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_item_responses_session_learner",
        ),
        CheckConstraint(
            "phase IN ('baseline', 'supported', 'verification', 'retention')",
            name="ck_item_responses_phase",
        ),
        CheckConstraint(
            "support_state IN ('unsupported', 'supported', 'unknown')",
            name="ck_item_responses_support_state",
        ),
        CheckConstraint("score BETWEEN 0 AND 1", name="ck_item_responses_score"),
        CheckConstraint("attempt_no >= 1", name="ck_item_responses_attempt_no"),
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_item_responses_response_time",
        ),
        CheckConstraint(
            "active_time_ms IS NULL OR active_time_ms >= 0",
            name="ck_item_responses_active_time",
        ),
        CheckConstraint("hint_count >= 0", name="ck_item_responses_hint_count"),
        Index("ix_item_responses_learner_submitted", "learner_id", "submitted_at"),
        Index("ix_item_responses_session_phase", "session_id", "phase"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    item_version: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_code: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_taxonomy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    support_state: Mapped[str] = mapped_column(String(20), nullable=False)
    answer_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    active_time_ms: Mapped[int | None] = mapped_column(Integer)
    hint_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdaptiveEpisodeModel(Base):
    __tablename__ = "adaptive_episodes"
    __table_args__ = (
        CheckConstraint(
            "phase IN ('created', 'baseline_started', 'baseline_recorded', "
            "'struggle_assessed', 'misconception_recorded', 'support_decided', "
            "'support_delivered', 'support_withdrawn', 'verification_scheduled', "
            "'verification_started', 'verification_recorded', 'outcome_recorded', "
            "'completed', 'abandoned', 'invalidated')",
            name="ck_adaptive_episodes_phase",
        ),
        CheckConstraint(
            "((phase IN ('abandoned', 'invalidated')) AND terminal_reason IS NOT NULL) OR "
            "((phase NOT IN ('abandoned', 'invalidated')) AND terminal_reason IS NULL)",
            name="ck_adaptive_episodes_terminal_reason",
        ),
        CheckConstraint(
            "transitioned_at >= opened_at", name="ck_adaptive_episodes_transitioned_at"
        ),
        ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_adaptive_episodes_session_learner",
        ),
        Index("ix_adaptive_episodes_learner_opened", "learner_id", "opened_at"),
        Index("ix_adaptive_episodes_skill_phase", "skill_code", "phase"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    skill_code: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_taxonomy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False)
    trigger_reasons_json: Mapped[dict[str, object] | None] = mapped_column(JsonType)
    baseline_template: Mapped[str | None] = mapped_column(String(40))
    baseline_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("item_responses.id"))
    verification_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("item_responses.id"))
    retention_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("item_responses.id"))
    episode_protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    support_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_reason: Mapped[str | None] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InteractionEventModel(Base):
    __tablename__ = "interaction_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no", name="uq_interaction_events_sequence"),
        CheckConstraint("event_version >= 1", name="ck_interaction_events_version"),
        CheckConstraint("sequence_no >= 1", name="ck_interaction_events_sequence"),
        CheckConstraint(
            "client_tz_offset_min BETWEEN -840 AND 840",
            name="ck_interaction_events_tz_offset",
        ),
        CheckConstraint("length(payload_hash) = 64", name="ck_interaction_events_payload_hash"),
        ForeignKeyConstraint(
            ["session_id", "learner_id"],
            ["game_sessions.id", "game_sessions.learner_id"],
            name="fk_interaction_events_session_learner",
        ),
        Index("ix_interaction_events_learner_received", "learner_id", "server_received_at"),
        Index("ix_interaction_events_episode_type", "episode_id", "event_type"),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    episode_id: Mapped[UUID | None] = mapped_column(ForeignKey("adaptive_episodes.id"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sequence_no: Mapped[int] = mapped_column(BigIntType, nullable=False)
    client_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_tz_offset_min: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_scope_version: Mapped[str] = mapped_column(String(128), nullable=False)


class FeatureSnapshotModel(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (
        Index("ix_feature_snapshots_learner_skill", "learner_id", "skill_code", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    skill_code: Mapped[str] = mapped_column(String(128), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_version: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    features_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    missingness_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    source_as_of_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ModelVersionModel(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "semantic_version", name="uq_model_versions_name_version"),
        CheckConstraint(
            "model_role IN ('misconception', 'support_policy', 'independence_gain')",
            name="ck_model_versions_role",
        ),
        CheckConstraint(
            "approval_status IN ('draft', 'validated', 'approved', 'retired')",
            name="ck_model_versions_approval",
        ),
        CheckConstraint("length(artifact_sha256) = 64", name="ck_model_versions_sha256"),
        CheckConstraint(
            "approval_status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_model_versions_approved_metadata",
        ),
        Index("ix_model_versions_role_approval", "model_role", "approval_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_role: Mapped[str] = mapped_column(String(30), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_definition_version: Mapped[str] = mapped_column(String(128), nullable=False)
    training_dataset_id: Mapped[str | None] = mapped_column(String(128))
    metrics_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MisconceptionInferenceModel(Base):
    __tablename__ = "misconception_inferences"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_misconception_inferences_episode"),
        CheckConstraint("entropy >= 0", name="ck_misconception_inferences_entropy"),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1", name="ck_misconception_inferences_confidence"
        ),
        Index("ix_misconception_inferences_model", "model_version_id", "inferred_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    model_version_id: Mapped[UUID] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    feature_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_snapshots.id"), nullable=False
    )
    misconception_catalogue_version: Mapped[str] = mapped_column(String(128), nullable=False)
    top_misconception_code: Mapped[str | None] = mapped_column(String(128))
    entropy: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    inferred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MisconceptionProbabilityModel(Base):
    __tablename__ = "misconception_probabilities"
    __table_args__ = (
        CheckConstraint("probability BETWEEN 0 AND 1", name="ck_misconception_probabilities_value"),
        CheckConstraint("rank >= 1", name="ck_misconception_probabilities_rank"),
        UniqueConstraint("inference_id", "rank", name="uq_misconception_probabilities_rank"),
    )

    inference_id: Mapped[UUID] = mapped_column(
        ForeignKey("misconception_inferences.id"), primary_key=True
    )
    misconception_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class SupportDecisionModel(Base):
    __tablename__ = "support_decisions"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_support_decisions_episode"),
        CheckConstraint(
            "decision_mode IN ('performance_triggered_fixed', 'deterministic_reference', "
            "'shadow', 'learned', 'conservative_fallback')",
            name="ck_support_decisions_mode",
        ),
        CheckConstraint(
            "selection_probability BETWEEN 0 AND 1", name="ck_support_decisions_probability"
        ),
        Index("ix_support_decisions_policy_time", "policy_version", "decided_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    policy_model_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("model_versions.id"))
    feature_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_snapshots.id"), nullable=False
    )
    selected_action_id: Mapped[str] = mapped_column(String(128), nullable=False)
    selected_action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    selection_probability: Mapped[float] = mapped_column(Float, nullable=False)
    decision_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    support_catalogue_version: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    random_seed: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupportCandidateModel(Base):
    __tablename__ = "support_candidates"
    __table_args__ = (
        CheckConstraint("propensity BETWEEN 0 AND 1", name="ck_support_candidates_propensity"),
        CheckConstraint(
            "uncertainty IS NULL OR uncertainty BETWEEN 0 AND 1",
            name="ck_support_candidates_uncertainty",
        ),
        CheckConstraint("rank >= 1", name="ck_support_candidates_rank"),
        CheckConstraint(
            "eligible OR propensity = 0", name="ck_support_candidates_ineligible_propensity"
        ),
        UniqueConstraint("decision_id", "rank", name="uq_support_candidates_rank"),
    )

    decision_id: Mapped[UUID] = mapped_column(ForeignKey("support_decisions.id"), primary_key=True)
    action_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ineligibility_reasons_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    predicted_reward: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float)
    propensity: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class SupportExposureModel(Base):
    __tablename__ = "support_exposures"
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('scheduled', 'presented', 'interacted', 'dismissed', "
            "'completed', 'completed_over_budget', 'failed')",
            name="ck_support_exposures_status",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="ck_support_exposures_duration"
        ),
        CheckConstraint("interaction_count >= 0", name="ck_support_exposures_interactions"),
        Index("ix_support_exposures_decision_presented", "decision_id", "presented_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("support_decisions.id"), nullable=False)
    action_id: Mapped[str] = mapped_column(String(128), nullable=False)
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    interaction_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False)
    render_version: Mapped[str] = mapped_column(String(128), nullable=False)
    maximum_duration_ms: Mapped[int | None] = mapped_column(Integer)
    maximum_number_of_steps: Mapped[int | None] = mapped_column(Integer)


class VerificationPairModel(Base):
    __tablename__ = "verification_pairs"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_verification_pairs_episode"),
        CheckConstraint(
            "baseline_item_id <> verification_item_id OR "
            "baseline_item_version <> verification_item_version",
            name="ck_verification_pairs_distinct_items",
        ),
        CheckConstraint(
            "surface_similarity BETWEEN 0 AND 1", name="ck_verification_pairs_similarity"
        ),
        CheckConstraint("answer_overlap BETWEEN 0 AND 1", name="ck_verification_pairs_overlap"),
        CheckConstraint(
            "review_status IN ('draft', 'reviewed', 'approved', 'rejected')",
            name="ck_verification_pairs_review",
        ),
        CheckConstraint(
            "review_status NOT IN ('reviewed', 'approved', 'rejected') OR "
            "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_verification_pairs_review_metadata",
        ),
        Index("ix_verification_pairs_skill_review", "skill_code", "review_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    baseline_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_item_version: Mapped[str] = mapped_column(String(128), nullable=False)
    verification_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    verification_item_version: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_code: Mapped[str] = mapped_column(String(128), nullable=False)
    equivalence_version: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty_delta: Mapped[float] = mapped_column(Float, nullable=False)
    surface_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    answer_overlap: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IndependenceOutcomeModel(Base):
    __tablename__ = "independence_outcomes"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_independence_outcomes_episode"),
        CheckConstraint("baseline_score BETWEEN 0 AND 1", name="ck_independence_outcomes_baseline"),
        CheckConstraint(
            "verification_score BETWEEN 0 AND 1", name="ck_independence_outcomes_verification"
        ),
        CheckConstraint(
            "raw_independence_gain BETWEEN -1 AND 1",
            name="ck_independence_outcomes_raw_gain",
        ),
        CheckConstraint(
            "validity IN ('pending', 'valid', 'invalid')", name="ck_independence_outcomes_validity"
        ),
        CheckConstraint(
            "baseline_support_state IN ('unsupported', 'supported', 'unknown') AND "
            "verification_support_state IN ('unsupported', 'supported', 'unknown')",
            name="ck_independence_outcomes_support_state",
        ),
        CheckConstraint(
            "(validity = 'valid' AND baseline_support_state = 'unsupported' AND "
            "verification_support_state = 'unsupported' AND raw_independence_gain IS NOT NULL "
            "AND invalid_reason IS NULL) OR "
            "(validity = 'invalid' AND raw_independence_gain IS NULL AND invalid_reason IS NOT NULL) OR "
            "(validity = 'pending' AND raw_independence_gain IS NULL AND invalid_reason IS NULL)",
            name="ck_independence_outcomes_validity_fields",
        ),
        Index("ix_independence_outcomes_validity_time", "validity", "calculated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    verification_pair_id: Mapped[UUID] = mapped_column(
        ForeignKey("verification_pairs.id"), nullable=False
    )
    baseline_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    verification_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    raw_independence_gain: Mapped[float | None] = mapped_column(Numeric(6, 5))
    normalized_gain: Mapped[float | None] = mapped_column(Float)
    time_adjusted_gain: Mapped[float | None] = mapped_column(Float)
    misconception_resolution: Mapped[float | None] = mapped_column(Float)
    support_dependency_index: Mapped[float | None] = mapped_column(Float)
    validity: Mapped[str] = mapped_column(String(20), nullable=False)
    baseline_support_state: Mapped[str] = mapped_column(String(20), nullable=False)
    verification_support_state: Mapped[str] = mapped_column(String(20), nullable=False)
    invalid_reason: Mapped[str | None] = mapped_column(String(128))
    formula_version: Mapped[str] = mapped_column(String(128), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ItemPresentationV3Model(Base):
    __tablename__ = "item_presentations_v3"
    __table_args__ = (
        UniqueConstraint("episode_id", "sequence_no", name="uq_item_presentations_v3_sequence"),
        CheckConstraint(
            "measurement_role IN ('practice', 'unsupported_before', 'supported_practice', "
            "'unsupported_after', 'retention')",
            name="ck_item_presentations_v3_role",
        ),
        CheckConstraint(
            "assistance_state IN ('none', 'scaffold_active', 'tutor_active', "
            "'adult_reported', 'unknown')",
            name="ck_item_presentations_v3_assistance",
        ),
        CheckConstraint("sequence_no > 0", name="ck_item_presentations_v3_sequence"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    item_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    parallel_family_id: Mapped[str] = mapped_column(String(128), nullable=False)
    equivalence_version: Mapped[str] = mapped_column(String(128), nullable=False)
    measurement_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assistance_state: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProbeReservationV3Model(Base):
    __tablename__ = "probe_reservations_v3"
    __table_args__ = (
        CheckConstraint("expires_at > reserved_at", name="ck_probe_reservations_v3_expiry"),
        CheckConstraint(
            "measurement_role IN ('unsupported_before', 'unsupported_after')",
            name="ck_probe_reservations_v3_role",
        ),
        Index(
            "ix_probe_reservations_v3_learner_item",
            "learner_id",
            "item_revision_id",
            "expires_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    item_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    parallel_family_id: Mapped[str] = mapped_column(String(128), nullable=False)
    measurement_role: Mapped[str] = mapped_column(String(32), nullable=False)
    reservation_version: Mapped[str] = mapped_column(String(128), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contamination_sources_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)


class ScaffoldExposureRecordV3Model(Base):
    __tablename__ = "scaffold_exposure_records_v3"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    scaffold_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rendered_step_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    answer_revealing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportWithdrawalConfirmationV3Model(Base):
    __tablename__ = "support_withdrawal_confirmations_v3"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_support_withdrawal_v3_episode"),
        CheckConstraint(
            "server_verified_at >= client_confirmed_at", name="ck_support_withdrawal_v3_order"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    exposure_id: Mapped[UUID] = mapped_column(
        ForeignKey("scaffold_exposure_records_v3.id"), nullable=False
    )
    all_support_removed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answer_revealing_state_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False)
    client_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthoritativeAttemptV3Model(Base):
    __tablename__ = "authoritative_attempts_v3"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_authoritative_attempts_v3_idempotency"),
        CheckConstraint(
            "earned_score >= 0 AND maximum_score > 0 AND earned_score <= maximum_score",
            name="ck_authoritative_attempts_v3_scores",
        ),
        CheckConstraint("server_authoritative = true", name="ck_authoritative_attempts_v3_server"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    presentation_id: Mapped[UUID] = mapped_column(
        ForeignKey("item_presentations_v3.id"), nullable=False
    )
    item_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    measurement_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assistance_state: Mapped[str] = mapped_column(String(32), nullable=False)
    earned_score: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(128), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(128), nullable=False)
    server_authoritative: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IndependenceMeasurementV3Model(Base):
    """Append-only Independence Gain result; older independence_outcomes rows remain untouched."""

    __tablename__ = "independence_measurements_v3"
    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_independence_measurements_v3_episode"),
        CheckConstraint(
            "(valid = true AND raw_independence_gain IS NOT NULL AND "
            "percentage_point_value IS NOT NULL) OR "
            "(valid = false AND raw_independence_gain IS NULL AND "
            "percentage_point_value IS NULL)",
            name="ck_independence_measurements_v3_validity",
        ),
        CheckConstraint(
            "policy_update_status IN ('authorized_delayed', 'not_authorized_baseline', "
            "'not_authorized_invalid')",
            name="ck_independence_measurements_v3_policy_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    decision_id: Mapped[UUID] = mapped_column(ForeignKey("support_decisions.id"), nullable=False)
    before_presentation_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    after_presentation_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    before_earned: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    before_maximum: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    after_earned: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    after_maximum: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    raw_independence_gain: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    percentage_point_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 9))
    formula_version: Mapped[str] = mapped_column(String(128), nullable=False)
    scoring_versions_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    rubric_versions_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    equivalence_version: Mapped[str] = mapped_column(String(128), nullable=False)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exclusion_reasons_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    policy_update_status: Mapped[str] = mapped_column(String(40), nullable=False)
    measurement_version: Mapped[str] = mapped_column(String(128), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Model1FeatureSnapshotV4Model(Base):
    """Immutable, replayable pre-inference feature snapshot for Model 1."""

    __tablename__ = "model1_feature_snapshots_v4"
    __table_args__ = (
        CheckConstraint("length(snapshot_sha256) = 64", name="ck_model1_features_v4_hash"),
        UniqueConstraint("snapshot_sha256", name="uq_model1_features_v4_hash"),
        Index("ix_model1_features_v4_learner_time", "learner_id", "inference_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    presentation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(128), nullable=False)
    item_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_window_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    values_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    missingness_json: Mapped[dict[str, bool]] = mapped_column(JsonType, nullable=False)
    optional_freshness_json: Mapped[dict[str, str]] = mapped_column(JsonType, nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    evidence_event_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    attempt_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class Model1BeliefSnapshotV4Model(Base):
    """Immutable Model 1 posterior with provenance and safe-fallback state."""

    __tablename__ = "model1_belief_snapshots_v4"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_model1_beliefs_v4_confidence"
        ),
        CheckConstraint("entropy >= 0", name="ck_model1_beliefs_v4_entropy"),
        CheckConstraint("length(artifact_sha256) = 64", name="ck_model1_beliefs_v4_artifact_hash"),
        CheckConstraint("length(snapshot_sha256) = 64", name="ck_model1_beliefs_v4_snapshot_hash"),
        UniqueConstraint(
            "feature_snapshot_id",
            "model_version",
            "artifact_sha256",
            name="uq_model1_beliefs_v4_replay",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    feature_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("model1_feature_snapshots_v4.id"), nullable=False
    )
    probabilities_json: Mapped[dict[str, float]] = mapped_column(JsonType, nullable=False)
    top_hypothesis: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    entropy: Mapped[float] = mapped_column(Float, nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, nullable=False)
    low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    narrow_exploitation_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    inference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class Model1BeliefProbabilityV4Model(Base):
    """One immutable probability per catalogue state for auditable querying."""

    __tablename__ = "model1_belief_probabilities_v4"
    __table_args__ = (
        CheckConstraint(
            "probability >= 0 AND probability <= 1", name="ck_model1_probability_v4_range"
        ),
        CheckConstraint(
            "misconception_code IN ('whole_set_as_half', 'subtracts_two', 'unknown_or_other')",
            name="ck_model1_probability_v4_catalogue",
        ),
    )

    belief_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("model1_belief_snapshots_v4.id"), primary_key=True
    )
    misconception_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)


class Model2ContextSnapshotV5Model(Base):
    """Immutable, pre-decision-only context consumed by a Model 2 decision."""

    __tablename__ = "model2_context_snapshots_v5"
    __table_args__ = (
        CheckConstraint("length(snapshot_sha256) = 64", name="ck_model2_context_v5_hash"),
        CheckConstraint(
            "experiment_mode IN ('baseline', 'proposed')",
            name="ck_model2_context_v5_experiment",
        ),
        UniqueConstraint("snapshot_sha256", name="uq_model2_context_v5_hash"),
        Index("ix_model2_context_v5_learner_time", "learner_id", "decision_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    presentation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    values_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    missingness_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    belief_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model1_belief_snapshots_v4.id")
    )
    belief_model_version: Mapped[str | None] = mapped_column(String(128))
    belief_mapping_version: Mapped[str | None] = mapped_column(String(128))
    belief_artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    optional_freshness_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    feature_definitions_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    provenance_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    experiment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class Model2ScaffoldDecisionV5Model(Base):
    """One immutable policy decision, including fallback and shadow outcomes."""

    __tablename__ = "model2_scaffold_decisions_v5"
    __table_args__ = (
        CheckConstraint("length(artifact_sha256) = 64", name="ck_model2_decision_v5_artifact"),
        CheckConstraint("length(decision_sha256) = 64", name="ck_model2_decision_v5_hash"),
        CheckConstraint(
            "experiment_mode IN ('baseline', 'proposed')",
            name="ck_model2_decision_v5_experiment",
        ),
        CheckConstraint(
            "mode IN ('deterministic_baseline', 'proposed_shadow', 'proposed_offline', "
            "'learned_delivery', 'safe_fallback')",
            name="ck_model2_decision_v5_mode",
        ),
        UniqueConstraint("episode_id", name="uq_model2_decision_v5_episode"),
        UniqueConstraint("decision_sha256", name="uq_model2_decision_v5_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    episode_id: Mapped[UUID] = mapped_column(ForeignKey("adaptive_episodes.id"), nullable=False)
    presentation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    experiment_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    context_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model2_context_snapshots_v5.id")
    )
    context_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    selected_scaffold_id: Mapped[str | None] = mapped_column(String(128))
    shadow_scaffold_id: Mapped[str | None] = mapped_column(String(128))
    policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    selection_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_token: Mapped[str] = mapped_column(String(128), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    decision_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class Model2CandidateDecisionV5Model(Base):
    """Complete eligible and excluded action set at decision time."""

    __tablename__ = "model2_candidate_decisions_v5"
    __table_args__ = (
        CheckConstraint(
            "propensity >= 0 AND propensity <= 1", name="ck_model2_candidate_v5_propensity"
        ),
        CheckConstraint(
            "scaffold_type IN ('visual_guidance', 'worked_parallel_example', "
            "'step_by_step_guidance')",
            name="ck_model2_candidate_v5_action",
        ),
    )

    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("model2_scaffold_decisions_v5.id"), primary_key=True
    )
    scaffold_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_order: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scaffold_type: Mapped[str] = mapped_column(String(64), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    predicted_raw_ig: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    propensity: Mapped[float] = mapped_column(Float, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    context_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)


class Model2RewardLinkV5Model(Base):
    """Idempotent delayed reward link to an authoritative Independence Gain outcome."""

    __tablename__ = "model2_reward_links_v5"
    __table_args__ = (
        CheckConstraint(
            "raw_independence_gain >= -1 AND raw_independence_gain <= 1",
            name="ck_model2_reward_v5_raw_ig",
        ),
        UniqueConstraint("decision_id", name="uq_model2_reward_v5_decision"),
        UniqueConstraint("measurement_id", name="uq_model2_reward_v5_measurement"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("model2_scaffold_decisions_v5.id"), nullable=False
    )
    measurement_id: Mapped[UUID] = mapped_column(
        ForeignKey("independence_measurements_v3.id"), nullable=False
    )
    raw_independence_gain: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(128), nullable=False)
    link_version: Mapped[str] = mapped_column(String(128), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PolicyUpdateCursorModel(Base):
    __tablename__ = "policy_update_cursors"
    __table_args__ = (
        CheckConstraint(
            "artifact_sha256 IS NULL OR length(artifact_sha256) = 64",
            name="ck_policy_update_cursors_sha256",
        ),
    )

    episode_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("adaptive_episodes.id"), primary_key=True
    )
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearnerSkillSummaryModel(Base):
    __tablename__ = "learner_skill_summaries"
    __table_args__ = (
        CheckConstraint("unsupported_attempts >= 0", name="ck_learner_skill_summaries_unsupported"),
        CheckConstraint("supported_attempts >= 0", name="ck_learner_skill_summaries_supported"),
        CheckConstraint(
            "valid_outcome_count >= 0", name="ck_learner_skill_summaries_valid_outcomes"
        ),
        CheckConstraint(
            "independent_accuracy IS NULL OR "
            "(independent_accuracy >= 0 AND independent_accuracy <= 1)",
            name="ck_learner_skill_summaries_independent_accuracy",
        ),
        CheckConstraint(
            "supported_accuracy IS NULL OR (supported_accuracy >= 0 AND supported_accuracy <= 1)",
            name="ck_learner_skill_summaries_supported_accuracy",
        ),
        CheckConstraint(
            "support_dependency_index IS NULL OR "
            "(support_dependency_index >= 0 AND support_dependency_index <= 1)",
            name="ck_learner_skill_summaries_dependency",
        ),
    )

    learner_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("learners.id"), primary_key=True)
    skill_code: Mapped[str] = mapped_column(String(128), primary_key=True)
    unsupported_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    supported_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    independent_accuracy: Mapped[float | None] = mapped_column(Float)
    supported_accuracy: Mapped[float | None] = mapped_column(Float)
    mean_independence_gain: Mapped[float | None] = mapped_column(Float)
    support_dependency_index: Mapped[float | None] = mapped_column(Float)
    valid_outcome_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_version: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearnerEvidenceOutboxModel(Base):
    __tablename__ = "learner_evidence_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_learner_evidence_outbox_key"),
        CheckConstraint(
            "status IN ('pending', 'published')", name="ck_learner_evidence_outbox_status"
        ),
        CheckConstraint("attempt_count >= 1", name="ck_learner_evidence_outbox_attempts"),
        Index("ix_learner_evidence_outbox_learner", "learner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    skill_code: Mapped[str] = mapped_column(String(128), nullable=False)
    universal_skill_id: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentModel(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint("length(protocol_hash) = 64", name="ck_experiments_protocol_hash"),
        CheckConstraint("assignment_unit = 'learner'", name="ck_experiments_assignment_unit"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    protocol_version: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    eligibility_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    allocation_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    assignment_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExperimentArmModel(Base):
    __tablename__ = "experiment_arms"
    __table_args__ = (
        UniqueConstraint("experiment_id", "arm_key", name="uq_experiment_arms_key"),
        CheckConstraint(
            "arm_key IN ('baseline_performance_triggered', 'proposed_misconception_ig_policy')",
            name="ck_experiment_arms_key",
        ),
        CheckConstraint(
            "decision_mode IN ('performance_triggered_fixed', 'learned')",
            name="ck_experiment_arms_mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    arm_key: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_mode: Mapped[str] = mapped_column(String(64), nullable=False)


class DeliveryJobModel(Base):
    __tablename__ = "delivery_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_delivery_jobs_idempotency"),
        CheckConstraint(
            "kind IN ('ingestion', 'feature_construction', 'retention_check', 'evaluation', 'export')",
            name="ck_delivery_jobs_kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'claimed', 'succeeded', 'failed')",
            name="ck_delivery_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_delivery_jobs_attempts"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningRewardEntryModel(Base):
    __tablename__ = "learning_reward_entries"
    __table_args__ = (
        UniqueConstraint("learner_id", "episode_id", name="uq_learning_reward_entries_episode"),
        CheckConstraint("points >= 0", name="ck_learning_reward_entries_points"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    episode_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResearchExportModel(Base):
    __tablename__ = "research_exports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'succeeded', 'failed')", name="ck_research_exports_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    manifest_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConsentEligibilityReferenceModel(Base):
    __tablename__ = "consent_eligibility_references"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(64), primary_key=True)
    consent_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConsentDecisionModel(Base):
    """The current purpose-specific consent decision for a learner, for example camera use."""

    __tablename__ = "consent_decisions"

    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(64), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentAssignmentModel(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "learner_id", name="uq_experiment_assignments_learner"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    arm_id: Mapped[UUID] = mapped_column(ForeignKey("experiment_arms.id"), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningFlowEpisodeRunModel(Base):
    """Current durable projection for the development-only episode coordinator."""

    __tablename__ = "learning_flow_episode_runs"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_learning_flow_episode_runs_session"),
        CheckConstraint(
            "environment IN ('development', 'test', 'pilot')", name="ck_learning_flow_runs_environment"
        ),
        CheckConstraint(
            "condition IN ('baseline', 'proposed')", name="ck_learning_flow_runs_condition"
        ),
        CheckConstraint(
            "status IN ('before_presented', 'support_active', 'support_complete', "
            "'support_withdrawn', 'after_presented', 'completed', 'invalidated')",
            name="ck_learning_flow_runs_status",
        ),
        Index("ix_learning_flow_runs_learner_created", "learner_id", "created_at"),
    )

    episode_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    content_package_version: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    state_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningFlowProbeReservationModel(Base):
    __tablename__ = "learning_flow_probe_reservations"
    __table_args__ = (
        UniqueConstraint(
            "learner_id", "item_revision_id", name="uq_learning_flow_probe_learner_revision"
        ),
        CheckConstraint(
            "status IN ('reserved', 'used', 'contaminated')",
            name="ck_learning_flow_probe_status",
        ),
        CheckConstraint("expires_at > reserved_at", name="ck_learning_flow_probe_expiry"),
        Index("ix_learning_flow_probe_episode", "episode_id", "status"),
    )

    reservation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    item_revision_id: Mapped[str] = mapped_column(String(128), nullable=False)
    gateway_version: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contamination_source: Mapped[str | None] = mapped_column(String(64))


class LearningFlowEpisodeEventModel(Base):
    """Append-only normalized orchestration event used for replay and audit."""

    __tablename__ = "learning_flow_episode_events"
    __table_args__ = (
        UniqueConstraint("episode_id", "sequence", name="uq_learning_flow_events_sequence"),
        UniqueConstraint("event_id", name="uq_learning_flow_events_event_id"),
        CheckConstraint("sequence >= 1", name="ck_learning_flow_events_sequence"),
        CheckConstraint("length(payload_sha256) = 64", name="ck_learning_flow_events_hash"),
        Index("ix_learning_flow_events_episode_time", "episode_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_flow_episode_runs.episode_id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningFlowIdempotencyReceiptModel(Base):
    __tablename__ = "learning_flow_idempotency_receipts"
    __table_args__ = (
        CheckConstraint("length(request_sha256) = 64", name="ck_learning_flow_receipts_request_hash"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_flow_episode_runs.episode_id", ondelete="CASCADE"), nullable=False
    )
    response_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningFlowAuditEventModel(Base):
    __tablename__ = "learning_flow_audit_events"
    __table_args__ = (Index("ix_learning_flow_audit_episode_time", "episode_id", "occurred_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_flow_episode_runs.episode_id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JsonType, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
