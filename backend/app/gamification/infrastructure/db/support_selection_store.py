"""Append-only persistence for Model 2 decisions and delayed rewards."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session

from app.gamification.domain.types import ExperimentMode
from app.gamification.infrastructure.db.models import (
    Model2CandidateDecisionV5Model,
    Model2ContextSnapshotV5Model,
    Model2RewardLinkV5Model,
    Model2ScaffoldDecisionV5Model,
)
from app.gamification.modeling.shared.artifact_registry import canonical_json
from app.gamification.modeling.support_selection.selection import (
    CandidateDecision,
    Model2ContextSnapshot,
    Model2Error,
    PolicyMode,
    RewardLink,
    ScaffoldDecision,
    SelectionKind,
)


def _aware(value):
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _context_payload(value: Model2ContextSnapshot) -> dict[str, object]:
    return {
        "id": str(value.context_snapshot_id),
        "learner_id": str(value.learner_id),
        "skill_id": value.skill_id,
        "skill_version": value.skill_version,
        "episode_id": str(value.episode_id),
        "presentation_id": str(value.presentation_id),
        "decision_at": value.decision_at.isoformat(),
        "schema_version": value.schema_version,
        "values": dict(value.values),
        "missingness": dict(value.missingness),
        "evidence_ids": [str(item) for item in value.evidence_ids],
        "belief_snapshot_id": str(value.belief_snapshot_id) if value.belief_snapshot_id else None,
        "belief_model_version": value.belief_model_version,
        "belief_mapping_version": value.belief_mapping_version,
        "belief_artifact_sha256": value.belief_artifact_sha256,
        "optional_freshness": dict(value.optional_freshness),
        "feature_definitions": dict(value.feature_definitions),
        "provenance": dict(value.provenance),
        "experiment_mode": value.experiment_mode.value,
        "protocol_version": value.protocol_version,
    }


def _candidate_payload(value: CandidateDecision) -> dict[str, object]:
    return {
        "scaffold_id": value.scaffold_id,
        "revision_id": value.revision_id,
        "scaffold_type": value.scaffold_type,
        "eligible": value.eligible,
        "reason_codes": list(value.reason_codes),
        "predicted_raw_ig": value.predicted_raw_ig,
        "uncertainty": value.uncertainty,
        "rank": value.rank,
        "propensity": value.propensity,
        "policy_version": value.policy_version,
        "artifact_sha256": value.artifact_sha256,
        "context_schema_version": value.context_schema_version,
    }


def _decision_payload(value: ScaffoldDecision) -> dict[str, object]:
    return {
        "id": str(value.decision_id),
        "learner_id": str(value.learner_id),
        "skill_id": value.skill_id,
        "episode_id": str(value.episode_id),
        "presentation_id": str(value.presentation_id),
        "experiment_mode": value.experiment_mode.value,
        "context_snapshot_id": str(value.context_snapshot_id)
        if value.context_snapshot_id
        else None,
        "context_schema_version": value.context_schema_version,
        "candidates": [_candidate_payload(item) for item in value.candidates],
        "selected_scaffold_id": value.selected_scaffold_id,
        "shadow_scaffold_id": value.shadow_scaffold_id,
        "policy_version": value.policy_version,
        "artifact_version": value.artifact_version,
        "artifact_sha256": value.artifact_sha256,
        "mode": value.mode.value,
        "selection_kind": value.selection_kind.value,
        "random_seed": value.random_seed,
        "assignment_token": value.assignment_token,
        "decided_at": value.decided_at.isoformat(),
        "reason_codes": list(value.reason_codes),
    }


class SqlAlchemyModel2Store:
    """Writes exact retries once and rejects any changed context, decision, or reward."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_decision(
        self, context: Model2ContextSnapshot | None, decision: ScaffoldDecision
    ) -> ScaffoldDecision:
        if context is None and decision.context_snapshot_id is not None:
            raise Model2Error("decision references a missing context")
        if context is not None and decision.context_snapshot_id != context.context_snapshot_id:
            raise Model2Error("decision/context reference mismatch")
        context_hash = (
            sha256(canonical_json(_context_payload(context))).hexdigest() if context else None
        )
        decision_hash = sha256(canonical_json(_decision_payload(decision))).hexdigest()
        existing_context = (
            self._session.get(Model2ContextSnapshotV5Model, context.context_snapshot_id)
            if context
            else None
        )
        if existing_context is not None and existing_context.snapshot_sha256 != context_hash:
            raise Model2Error("CONTEXT_SNAPSHOT_IDEMPOTENCY_CONFLICT")
        existing_decision = self._session.get(Model2ScaffoldDecisionV5Model, decision.decision_id)
        if existing_decision is not None:
            if existing_decision.decision_sha256 != decision_hash:
                raise Model2Error("SCAFFOLD_DECISION_IDEMPOTENCY_CONFLICT")
            return decision
        if context is not None and existing_context is None:
            self._session.add(
                Model2ContextSnapshotV5Model(
                    id=context.context_snapshot_id,
                    learner_id=context.learner_id,
                    episode_id=context.episode_id,
                    presentation_id=context.presentation_id,
                    skill_id=context.skill_id,
                    skill_version=context.skill_version,
                    decision_at=context.decision_at,
                    schema_version=context.schema_version,
                    values_json=dict(context.values),
                    missingness_json=dict(context.missingness),
                    evidence_ids_json=[str(item) for item in context.evidence_ids],
                    belief_snapshot_id=context.belief_snapshot_id,
                    belief_model_version=context.belief_model_version,
                    belief_mapping_version=context.belief_mapping_version,
                    belief_artifact_sha256=context.belief_artifact_sha256,
                    optional_freshness_json=dict(context.optional_freshness),
                    feature_definitions_json=dict(context.feature_definitions),
                    provenance_json=dict(context.provenance),
                    experiment_mode=context.experiment_mode.value,
                    protocol_version=context.protocol_version,
                    snapshot_sha256=context_hash,
                )
            )
            self._session.flush()
        self._session.add(
            Model2ScaffoldDecisionV5Model(
                id=decision.decision_id,
                learner_id=decision.learner_id,
                episode_id=decision.episode_id,
                presentation_id=decision.presentation_id,
                skill_id=decision.skill_id,
                experiment_mode=decision.experiment_mode.value,
                context_snapshot_id=decision.context_snapshot_id,
                context_schema_version=decision.context_schema_version,
                selected_scaffold_id=decision.selected_scaffold_id,
                shadow_scaffold_id=decision.shadow_scaffold_id,
                policy_version=decision.policy_version,
                artifact_version=decision.artifact_version,
                artifact_sha256=decision.artifact_sha256,
                mode=decision.mode.value,
                selection_kind=decision.selection_kind.value,
                random_seed=decision.random_seed,
                assignment_token=decision.assignment_token,
                decided_at=decision.decided_at,
                reason_codes_json=list(decision.reason_codes),
                decision_sha256=decision_hash,
            )
        )
        self._session.flush()
        self._session.add_all(
            Model2CandidateDecisionV5Model(
                decision_id=decision.decision_id,
                scaffold_id=item.scaffold_id,
                candidate_order=position,
                revision_id=item.revision_id,
                scaffold_type=item.scaffold_type,
                eligible=item.eligible,
                reason_codes_json=list(item.reason_codes),
                predicted_raw_ig=item.predicted_raw_ig,
                uncertainty=item.uncertainty,
                rank=item.rank,
                propensity=item.propensity,
                policy_version=item.policy_version,
                artifact_sha256=item.artifact_sha256,
                context_schema_version=item.context_schema_version,
            )
            for position, item in enumerate(decision.candidates)
        )
        self._session.flush()
        return decision

    def add_reward_link(self, link: RewardLink) -> RewardLink:
        existing = self._session.get(Model2RewardLinkV5Model, link.reward_link_id)
        if existing is None:
            existing = (
                self._session.query(Model2RewardLinkV5Model)
                .filter(
                    (Model2RewardLinkV5Model.decision_id == link.decision_id)
                    | (Model2RewardLinkV5Model.measurement_id == link.measurement_id)
                )
                .one_or_none()
            )
        if existing is not None:
            reconstructed = self._reward(existing)
            if reconstructed != link:
                raise Model2Error("REWARD_LINK_IDEMPOTENCY_CONFLICT")
            return reconstructed
        self._session.add(
            Model2RewardLinkV5Model(
                id=link.reward_link_id,
                decision_id=link.decision_id,
                measurement_id=link.measurement_id,
                raw_independence_gain=link.raw_independence_gain,
                formula_version=link.formula_version,
                link_version=link.link_version,
                linked_at=link.linked_at,
            )
        )
        self._session.flush()
        return link

    def reconstruct(
        self, decision_id: UUID
    ) -> tuple[Model2ContextSnapshot | None, ScaffoldDecision] | None:
        row = self._session.get(Model2ScaffoldDecisionV5Model, decision_id)
        if row is None:
            return None
        context = None
        if row.context_snapshot_id is not None:
            saved = self._session.get(Model2ContextSnapshotV5Model, row.context_snapshot_id)
            if saved is None:
                raise Model2Error("persisted decision context is missing")
            context = Model2ContextSnapshot(
                context_snapshot_id=saved.id,
                learner_id=saved.learner_id,
                skill_id=saved.skill_id,
                skill_version=saved.skill_version,
                episode_id=saved.episode_id,
                presentation_id=saved.presentation_id,
                decision_at=_aware(saved.decision_at),
                schema_version=saved.schema_version,
                values=saved.values_json,
                missingness=saved.missingness_json,
                evidence_ids=tuple(UUID(item) for item in saved.evidence_ids_json),
                belief_snapshot_id=saved.belief_snapshot_id,
                belief_model_version=saved.belief_model_version,
                belief_mapping_version=saved.belief_mapping_version,
                belief_artifact_sha256=saved.belief_artifact_sha256,
                optional_freshness=saved.optional_freshness_json,
                feature_definitions=saved.feature_definitions_json,
                provenance=saved.provenance_json,
                experiment_mode=ExperimentMode(saved.experiment_mode),
                protocol_version=saved.protocol_version,
            )
            if (
                sha256(canonical_json(_context_payload(context))).hexdigest()
                != saved.snapshot_sha256
            ):
                raise Model2Error("persisted context hash mismatch")
        candidates = tuple(
            CandidateDecision(
                scaffold_id=item.scaffold_id,
                revision_id=item.revision_id,
                scaffold_type=item.scaffold_type,
                eligible=item.eligible,
                reason_codes=tuple(item.reason_codes_json),
                predicted_raw_ig=item.predicted_raw_ig,
                uncertainty=item.uncertainty,
                rank=item.rank,
                propensity=item.propensity,
                policy_version=item.policy_version,
                artifact_sha256=item.artifact_sha256,
                context_schema_version=item.context_schema_version,
            )
            for item in self._session.query(Model2CandidateDecisionV5Model)
            .filter_by(decision_id=decision_id)
            .order_by(Model2CandidateDecisionV5Model.candidate_order)
            .all()
        )
        decision = ScaffoldDecision(
            decision_id=row.id,
            learner_id=row.learner_id,
            skill_id=row.skill_id,
            episode_id=row.episode_id,
            presentation_id=row.presentation_id,
            experiment_mode=ExperimentMode(row.experiment_mode),
            context_snapshot_id=row.context_snapshot_id,
            context_schema_version=row.context_schema_version,
            candidates=candidates,
            selected_scaffold_id=row.selected_scaffold_id,
            shadow_scaffold_id=row.shadow_scaffold_id,
            policy_version=row.policy_version,
            artifact_version=row.artifact_version,
            artifact_sha256=row.artifact_sha256,
            mode=PolicyMode(row.mode),
            selection_kind=SelectionKind(row.selection_kind),
            random_seed=row.random_seed,
            assignment_token=row.assignment_token,
            decided_at=_aware(row.decided_at),
            reason_codes=tuple(row.reason_codes_json),
        )
        if sha256(canonical_json(_decision_payload(decision))).hexdigest() != row.decision_sha256:
            raise Model2Error("persisted decision hash mismatch")
        return context, decision

    @staticmethod
    def _reward(row: Model2RewardLinkV5Model) -> RewardLink:
        return RewardLink(
            reward_link_id=row.id,
            decision_id=row.decision_id,
            measurement_id=row.measurement_id,
            raw_independence_gain=Decimal(row.raw_independence_gain),
            formula_version=row.formula_version,
            link_version=row.link_version,
            linked_at=_aware(row.linked_at),
        )
