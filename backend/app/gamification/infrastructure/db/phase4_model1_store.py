"""Append-only persistence and reconstruction for Model 1."""

from __future__ import annotations

from datetime import UTC
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import (
    Model1BeliefProbabilityV4Model,
    Model1BeliefSnapshotV4Model,
    Model1FeatureSnapshotV4Model,
)
from app.gamification.modeling.misconception_inference.phase4 import (
    BeliefSnapshot,
    Model1Error,
    Model1FeatureSnapshot,
)
from app.gamification.modeling.shared.artifact_registry import canonical_json


def _aware(value):
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _feature_payload(value: Model1FeatureSnapshot) -> dict[str, object]:
    return {
        "id": str(value.snapshot_id),
        "learner_id": str(value.learner_id),
        "episode_id": str(value.episode_id),
        "presentation_id": str(value.presentation_id),
        "skill_id": value.skill_id,
        "skill_version": value.skill_version,
        "item_revision_id": value.item_revision_id,
        "inference_at": value.inference_at.isoformat(),
        "evidence_window_version": value.evidence_window_version,
        "feature_schema_version": value.feature_schema_version,
        "mapping_version": value.mapping_version,
        "model_version": value.model_version,
        "values": dict(value.values),
        "missingness": dict(value.missingness),
        "optional_freshness": dict(value.optional_freshness),
        "evidence_ids": [str(item) for item in value.evidence_ids],
        "evidence_event_ids": [str(item) for item in value.evidence_event_ids],
        "attempt_ids": [str(item) for item in value.attempt_ids],
    }


def _belief_payload(value: BeliefSnapshot) -> dict[str, object]:
    return {
        "id": str(value.belief_snapshot_id),
        "feature_snapshot_id": str(value.feature_snapshot_id),
        "probabilities": dict(value.probabilities),
        "top_hypothesis": value.top_hypothesis,
        "confidence": value.confidence,
        "entropy": value.entropy,
        "abstained": value.abstained,
        "low_confidence": value.low_confidence,
        "narrow_exploitation_allowed": value.narrow_exploitation_allowed,
        "reason_codes": list(value.reason_codes),
        "feature_schema_version": value.feature_schema_version,
        "mapping_version": value.mapping_version,
        "model_version": value.model_version,
        "artifact_sha256": value.artifact_sha256,
        "inference_at": value.inference_at.isoformat(),
    }


class SqlAlchemyModel1Store:
    """Writes once, accepts exact retries, and rejects conflicting replacements."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, feature: Model1FeatureSnapshot, belief: BeliefSnapshot) -> BeliefSnapshot:
        if belief.feature_snapshot_id != feature.snapshot_id:
            raise Model1Error("belief does not reference the supplied feature snapshot")
        feature_hash = sha256(canonical_json(_feature_payload(feature))).hexdigest()
        belief_hash = sha256(canonical_json(_belief_payload(belief))).hexdigest()
        existing_feature = self._session.get(Model1FeatureSnapshotV4Model, feature.snapshot_id)
        if existing_feature is not None and existing_feature.snapshot_sha256 != feature_hash:
            raise Model1Error("FEATURE_SNAPSHOT_IDEMPOTENCY_CONFLICT")
        existing_belief = self._session.get(Model1BeliefSnapshotV4Model, belief.belief_snapshot_id)
        if existing_belief is not None and existing_belief.snapshot_sha256 != belief_hash:
            raise Model1Error("BELIEF_SNAPSHOT_IDEMPOTENCY_CONFLICT")
        if existing_feature is None:
            self._session.add(
                Model1FeatureSnapshotV4Model(
                    id=feature.snapshot_id,
                    learner_id=feature.learner_id,
                    episode_id=feature.episode_id,
                    presentation_id=feature.presentation_id,
                    skill_id=feature.skill_id,
                    skill_version=feature.skill_version,
                    item_revision_id=feature.item_revision_id,
                    inference_at=feature.inference_at,
                    evidence_window_version=feature.evidence_window_version,
                    feature_schema_version=feature.feature_schema_version,
                    mapping_version=feature.mapping_version,
                    model_version=feature.model_version,
                    values_json=dict(feature.values),
                    missingness_json=dict(feature.missingness),
                    optional_freshness_json=dict(feature.optional_freshness),
                    evidence_ids_json=[str(item) for item in feature.evidence_ids],
                    evidence_event_ids_json=[str(item) for item in feature.evidence_event_ids],
                    attempt_ids_json=[str(item) for item in feature.attempt_ids],
                    snapshot_sha256=feature_hash,
                )
            )
            self._session.flush()
        if existing_belief is None:
            self._session.add(
                Model1BeliefSnapshotV4Model(
                    id=belief.belief_snapshot_id,
                    feature_snapshot_id=belief.feature_snapshot_id,
                    probabilities_json=dict(belief.probabilities),
                    top_hypothesis=belief.top_hypothesis,
                    confidence=belief.confidence,
                    entropy=belief.entropy,
                    abstained=belief.abstained,
                    low_confidence=belief.low_confidence,
                    narrow_exploitation_allowed=belief.narrow_exploitation_allowed,
                    reason_codes_json=list(belief.reason_codes),
                    feature_schema_version=belief.feature_schema_version,
                    mapping_version=belief.mapping_version,
                    model_version=belief.model_version,
                    artifact_sha256=belief.artifact_sha256,
                    inference_at=belief.inference_at,
                    snapshot_sha256=belief_hash,
                )
            )
            self._session.flush()
            ranking = sorted(
                belief.probabilities,
                key=lambda code: (-belief.probabilities[code], code),
            )
            self._session.add_all(
                Model1BeliefProbabilityV4Model(
                    belief_snapshot_id=belief.belief_snapshot_id,
                    misconception_code=code,
                    probability=belief.probabilities[code],
                    rank=ranking.index(code) + 1,
                )
                for code in belief.probabilities
            )
            self._session.flush()
        return belief

    def reconstruct(self, belief_id: UUID) -> tuple[Model1FeatureSnapshot, BeliefSnapshot] | None:
        belief_row = self._session.get(Model1BeliefSnapshotV4Model, belief_id)
        if belief_row is None:
            return None
        feature_row = self._session.get(
            Model1FeatureSnapshotV4Model, belief_row.feature_snapshot_id
        )
        if feature_row is None:
            raise Model1Error("belief feature snapshot is missing")
        feature = Model1FeatureSnapshot(
            snapshot_id=feature_row.id,
            learner_id=feature_row.learner_id,
            skill_id=feature_row.skill_id,
            skill_version=feature_row.skill_version,
            episode_id=feature_row.episode_id,
            presentation_id=feature_row.presentation_id,
            item_revision_id=feature_row.item_revision_id,
            inference_at=_aware(feature_row.inference_at),
            evidence_window_version=feature_row.evidence_window_version,
            feature_schema_version=feature_row.feature_schema_version,
            mapping_version=feature_row.mapping_version,
            model_version=feature_row.model_version,
            values=feature_row.values_json,
            missingness=feature_row.missingness_json,
            optional_freshness=feature_row.optional_freshness_json,
            evidence_ids=tuple(UUID(item) for item in feature_row.evidence_ids_json),
            evidence_event_ids=tuple(UUID(item) for item in feature_row.evidence_event_ids_json),
            attempt_ids=tuple(UUID(item) for item in feature_row.attempt_ids_json),
        )
        probability_rows = self._session.query(Model1BeliefProbabilityV4Model).filter_by(
            belief_snapshot_id=belief_id
        ).all()
        probabilities = {row.misconception_code: row.probability for row in probability_rows}
        if probabilities != belief_row.probabilities_json:
            raise Model1Error("belief probability records conflict with snapshot")
        belief = BeliefSnapshot(
            belief_snapshot_id=belief_row.id,
            feature_snapshot_id=feature.snapshot_id,
            learner_id=feature.learner_id,
            skill_id=feature.skill_id,
            skill_version=feature.skill_version,
            episode_id=feature.episode_id,
            presentation_id=feature.presentation_id,
            item_revision_id=feature.item_revision_id,
            probabilities=probabilities,
            top_hypothesis=belief_row.top_hypothesis,
            confidence=belief_row.confidence,
            entropy=belief_row.entropy,
            abstained=belief_row.abstained,
            low_confidence=belief_row.low_confidence,
            narrow_exploitation_allowed=belief_row.narrow_exploitation_allowed,
            reason_codes=tuple(belief_row.reason_codes_json),
            evidence_event_ids=feature.evidence_event_ids,
            attempt_ids=feature.attempt_ids,
            feature_schema_version=belief_row.feature_schema_version,
            mapping_version=belief_row.mapping_version,
            model_version=belief_row.model_version,
            artifact_sha256=belief_row.artifact_sha256,
            inference_at=_aware(belief_row.inference_at),
            optional_freshness=feature.optional_freshness,
        )
        return feature, belief
