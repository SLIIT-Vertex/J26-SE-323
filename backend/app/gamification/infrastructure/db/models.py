from datetime import datetime
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
    hint_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
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
    revision: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
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
            "decision_mode IN ('deterministic_reference', 'shadow', 'learned', "
            "'conservative_fallback')",
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
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_support_exposures_duration"),
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

