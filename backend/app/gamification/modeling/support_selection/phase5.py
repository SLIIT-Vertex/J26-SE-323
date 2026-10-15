"""Contextual scaffold selection.

This boundary is development-only while the draft content and Model 1 beliefs lack human approval.
It preserves a conventional non-learning baseline, permits proposed scoring only offline or in
shadow mode, and consumes only valid raw Independence Gain as delayed reward.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Protocol
from uuid import UUID, uuid5

from app.gamification.domain.types import AssistanceState, ExperimentMode, MeasurementRole
from app.gamification.modeling.shared.artifact_registry import canonical_json
from app.gamification.modeling.support_selection.context import (
    CONTEXT_VERSION as LEGACY_CONTEXT_VERSION,
)
from app.gamification.modeling.support_selection.context import (
    BanditContext,
)
from app.gamification.modeling.support_selection.learned_policy import LinUCBPolicy

INTERFACE_VERSION = "model2-scaffold-selection-interface-v1"
CONTEXT_SCHEMA_VERSION = "model2-context-v1"
POLICY_VERSION = "model2-linucb-v1"
BASELINE_POLICY_VERSION = "model2-educator-baseline-v1"
REWARD_LINK_VERSION = "model2-raw-ig-reward-link-v1"
ARTIFACT_SCHEMA_VERSION = "model2-artifact-v1"
FORMULA_VERSION = "raw-independence-gain-v1"
MODEL1_FEATURE_VERSION = "model1-features-v1"
MODEL1_VERSION = "model1-authored-bayes-v1"
CATALOGUE_VERSION = "g5-mat-half-misconceptions-v1"
CATALOGUE_CODES = ("whole_set_as_half", "subtracts_two", "unknown_or_other")
SKILL_ID = "G5-MAT-C03-L01-O01"
SKILL_VERSION = "g5-mat-c03-l01-o01-v1"
CONTENT_VERSION = "g5-mat-half-items-v1"
SCAFFOLD_CATALOGUE_VERSION = "g5-mat-half-scaffolds-v1"
ACTION_TYPES = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
NEUTRAL_FALLBACK = "safe_neutral_support"
CONTEXT_NAMESPACE = UUID("0b0dd48c-28e7-4b9a-a810-da9351055e3b")
DECISION_NAMESPACE = UUID("1af7988b-b397-4098-bb2a-bdbb77e6d649")
REWARD_NAMESPACE = UUID("b2c17660-c970-4f0d-a60e-556c28146665")
FORBIDDEN_CONTEXT_TOKENS = (
    "supported_practice",
    "unsupported_after",
    "current_independence_gain",
    "scaffold_delivery_outcome",
    "policy_update",
    "answer_key",
    "probe_content",
    "name",
    "email",
    "phone",
    "contact",
    "camera",
)


class Model2Error(ValueError):
    pass


class BeliefSnapshotContract(Protocol):
    belief_snapshot_id: UUID
    learner_id: UUID
    skill_id: str
    probabilities: Mapping[str, float]
    confidence: float
    entropy: float
    abstained: bool
    feature_schema_version: str
    mapping_version: str
    model_version: str
    artifact_sha256: str
    inference_at: datetime


class OptionalEvidenceContract(Protocol):
    source: str
    source_version: str
    observed_at: datetime | None
    expires_at: datetime | None
    reliability: float | None
    consent_reference: str | None
    eligible: bool
    missing: bool
    values: Mapping[str, float | int | bool | str | None]


class IndependenceMeasurementContract(Protocol):
    measurement_id: UUID
    decision_id: UUID
    valid: bool
    raw_independence_gain: Decimal | None
    formula_version: str
    policy_update_status: object


class PolicyMode(StrEnum):
    DETERMINISTIC_BASELINE = "deterministic_baseline"
    PROPOSED_SHADOW = "proposed_shadow"
    PROPOSED_OFFLINE = "proposed_offline"
    LEARNED_DELIVERY = "learned_delivery"
    SAFE_FALLBACK = "safe_fallback"


class SelectionKind(StrEnum):
    BASELINE = "baseline"
    SHADOW = "shadow"
    EXPLORE = "explore"
    EXPLOIT = "exploit"
    FALLBACK = "fallback"


class PolicyStage(StrEnum):
    DETERMINISTIC_REFERENCE = "deterministic_reference"
    SHADOW = "shadow"
    CONSTRAINED_OFFLINE = "constrained_offline"
    LEARNED_CHILD_CONTROL = "learned_child_control"


@dataclass(frozen=True, slots=True)
class PolicyProgression:
    stage: PolicyStage = PolicyStage.DETERMINISTIC_REFERENCE

    def advance(
        self,
        target: PolicyStage,
        *,
        evidence_reference: str | None,
        human_authorization: object | None = None,
    ) -> PolicyProgression:
        order = tuple(PolicyStage)
        if order.index(target) != order.index(self.stage) + 1:
            raise Model2Error("policy stages must advance one reviewed step at a time")
        if not evidence_reference:
            raise Model2Error("policy stage transition requires immutable evidence")
        if target is PolicyStage.LEARNED_CHILD_CONTROL:
            del human_authorization
            raise PermissionError("learned child control requires exact-hash human approval")
        return PolicyProgression(target)


@dataclass(frozen=True, slots=True)
class UnsupportedEvidence:
    evidence_id: UUID
    presentation_id: UUID
    episode_id: UUID
    observed_at: datetime
    measurement_role: MeasurementRole
    assistance_state: AssistanceState
    earned_score: Decimal
    maximum_score: Decimal
    attempt_count: int
    error_persistence: int
    item_revision_id: str

    def __post_init__(self) -> None:
        _aware(self.observed_at, "unsupported evidence")
        if self.measurement_role is not MeasurementRole.UNSUPPORTED_BEFORE:
            raise Model2Error("policy context accepts unsupported_before evidence only")
        if self.assistance_state is not AssistanceState.NONE:
            raise Model2Error("unsupported evidence cannot contain assistance")
        if (
            self.maximum_score <= 0
            or self.earned_score < 0
            or self.earned_score > self.maximum_score
            or self.attempt_count < 1
            or self.error_persistence < 0
        ):
            raise Model2Error("unsupported score or attempt evidence is invalid")


@dataclass(frozen=True, slots=True)
class DifficultyEvidence:
    difficulty_event_id: UUID
    detected: bool
    severity: float
    trigger_version: str
    contributing_event_ids: tuple[UUID, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        _aware(self.observed_at, "difficulty evidence")
        if not 0 <= self.severity <= 1 or not self.trigger_version:
            raise Model2Error("difficulty evidence is invalid")


@dataclass(frozen=True, slots=True)
class PriorScaffoldOutcome:
    measurement_id: UUID
    decision_id: UUID
    scaffold_type: str
    raw_independence_gain: Decimal
    observed_at: datetime
    formula_version: str
    valid: bool

    def __post_init__(self) -> None:
        _aware(self.observed_at, "prior scaffold outcome")
        if self.scaffold_type not in ACTION_TYPES:
            raise Model2Error("prior outcome scaffold is outside the scaffold action set")
        if not self.valid or self.formula_version != FORMULA_VERSION:
            raise Model2Error("history accepts valid raw Independence Gain only")
        if not Decimal(-1) <= self.raw_independence_gain <= Decimal(1):
            raise Model2Error("raw Independence Gain is outside [-1, 1]")


@dataclass(frozen=True, slots=True)
class EpisodeMetadata:
    protocol_version: str
    experiment_mode: ExperimentMode
    sequence_at_decision: int
    session_support_count: int
    session_support_budget: int
    remaining_support_steps: int
    reserved_probe_revision_id: str
    reserved_probe_family_id: str

    def __post_init__(self) -> None:
        if (
            self.sequence_at_decision < 1
            or self.session_support_count < 0
            or self.session_support_budget < 0
            or self.remaining_support_steps < 0
        ):
            raise Model2Error("episode counters and budgets must be non-negative")
        if not self.protocol_version or not self.reserved_probe_revision_id:
            raise Model2Error("episode protocol and opaque probe revision reference are required")


@dataclass(frozen=True, slots=True)
class ItemMetadata:
    item_revision_id: str
    content_version: str
    difficulty: float
    response_format: str
    template_id: str
    parallel_family_id: str

    def __post_init__(self) -> None:
        if not 0 <= self.difficulty <= 1:
            raise Model2Error("item difficulty must be in [0, 1]")
        if not all(
            (
                self.item_revision_id,
                self.content_version,
                self.response_format,
                self.template_id,
                self.parallel_family_id,
            )
        ):
            raise Model2Error("versioned item metadata is incomplete")


@dataclass(frozen=True, slots=True)
class Model2ContextInput:
    learner_id: UUID
    pseudonymous: bool
    grade: int
    medium: str
    skill_id: str
    skill_version: str
    episode_id: UUID
    presentation_id: UUID
    decision_at: datetime
    current_unsupported: UnsupportedEvidence
    recent_unsupported: tuple[UnsupportedEvidence, ...]
    difficulty: DifficultyEvidence
    belief: BeliefSnapshotContract | None
    prior_outcomes: tuple[PriorScaffoldOutcome, ...]
    recent_support_count: int
    support_dependency_rate: float | None
    support_dependency_as_of: datetime | None
    item: ItemMetadata
    episode: EpisodeMetadata
    optional_evidence: tuple[OptionalEvidenceContract, ...]
    extra_metadata: Mapping[str, str | int | float | bool | None]
    development_mode: bool

    def __post_init__(self) -> None:
        if not self.pseudonymous:
            raise Model2Error("Model 2 accepts pseudonymous learners only")
        if self.grade != 5 or self.medium != "si":
            raise Model2Error("Model 2 is restricted to Grade 5 Sinhala medium")
        if self.skill_id != SKILL_ID or self.skill_version != SKILL_VERSION:
            raise Model2Error("skill/version is outside the Model 2 slice")
        if not self.development_mode:
            raise PermissionError("draft scaffolds require development_mode=True")
        _aware(self.decision_at, "decision")
        if self.current_unsupported.episode_id != self.episode_id:
            raise Model2Error("current unsupported evidence belongs to another episode")
        if self.recent_support_count < 0:
            raise Model2Error("recent support count cannot be negative")
        if self.support_dependency_rate is not None and not 0 <= self.support_dependency_rate <= 1:
            raise Model2Error("support dependency must be in [0, 1]")
        if (self.support_dependency_rate is None) != (self.support_dependency_as_of is None):
            raise Model2Error("support dependency value and timestamp must occur together")
        if self.support_dependency_as_of is not None:
            _aware(self.support_dependency_as_of, "support dependency")
        for key in self.extra_metadata:
            if any(token in key.lower() for token in FORBIDDEN_CONTEXT_TOKENS):
                raise Model2Error("forbidden personal or post-decision context field")
        object.__setattr__(self, "extra_metadata", MappingProxyType(dict(self.extra_metadata)))


@dataclass(frozen=True, slots=True)
class Model2ContextSnapshot:
    context_snapshot_id: UUID
    learner_id: UUID
    skill_id: str
    skill_version: str
    episode_id: UUID
    presentation_id: UUID
    decision_at: datetime
    schema_version: str
    values: Mapping[str, float]
    missingness: Mapping[str, bool]
    evidence_ids: tuple[UUID, ...]
    belief_snapshot_id: UUID | None
    belief_model_version: str | None
    belief_mapping_version: str | None
    belief_artifact_sha256: str | None
    optional_freshness: Mapping[str, str]
    feature_definitions: Mapping[str, str]
    provenance: Mapping[str, object]
    experiment_mode: ExperimentMode
    protocol_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "missingness", MappingProxyType(dict(self.missingness)))
        object.__setattr__(
            self, "optional_freshness", MappingProxyType(dict(self.optional_freshness))
        )
        object.__setattr__(
            self, "feature_definitions", MappingProxyType(dict(self.feature_definitions))
        )
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    def as_bandit_context(self, *, exclude_beliefs: bool = False) -> BanditContext:
        names = tuple(sorted(self.values))
        values = tuple(
            0.0 if exclude_beliefs and name.startswith("belief:") else self.values[name]
            for name in names
        )
        return BanditContext(LEGACY_CONTEXT_VERSION, names, values, self.missingness)


class Model2ContextBuilder:
    version = CONTEXT_SCHEMA_VERSION

    def build(
        self, data: Model2ContextInput, *, require_belief: bool = True
    ) -> Model2ContextSnapshot:
        evidence = (data.current_unsupported, *data.recent_unsupported)
        if any(row.observed_at > data.decision_at for row in evidence):
            raise Model2Error("future attempt evidence is forbidden")
        if data.difficulty.observed_at > data.decision_at:
            raise Model2Error("future difficulty evidence is forbidden")
        if (
            data.support_dependency_as_of is not None
            and data.support_dependency_as_of > data.decision_at
        ):
            raise Model2Error("future support-dependency summary is forbidden")
        if any(row.observed_at > data.decision_at for row in data.prior_outcomes):
            raise Model2Error("current or future Independence Gain is forbidden")
        belief = data.belief
        if require_belief and belief is None:
            raise Model2Error("proposed policy requires a complete Model 1 belief")
        if belief is not None:
            if belief.inference_at > data.decision_at:
                raise Model2Error("future Model 1 belief is forbidden")
            if set(belief.probabilities) != set(CATALOGUE_CODES):
                raise Model2Error("Model 1 belief catalogue is incomplete")
            if belief.mapping_version != CATALOGUE_VERSION:
                raise Model2Error("Model 1 mapping version mismatch")
            if belief.model_version != MODEL1_VERSION:
                raise Model2Error("Model 1 model version mismatch")
            if belief.feature_schema_version != MODEL1_FEATURE_VERSION:
                raise Model2Error("Model 1 feature version mismatch")
            if belief.learner_id != data.learner_id or belief.skill_id != data.skill_id:
                raise Model2Error("Model 1 belief identity mismatch")

        values: dict[str, float] = {
            "bias": 1.0,
            "unsupported_before_score": float(
                data.current_unsupported.earned_score / data.current_unsupported.maximum_score
            ),
            "recent_unsupported_mean": _mean(
                [float(row.earned_score / row.maximum_score) for row in data.recent_unsupported]
            ),
            "attempt_count": float(data.current_unsupported.attempt_count),
            "error_persistence": float(data.current_unsupported.error_persistence),
            "difficulty_detected": float(data.difficulty.detected),
            "difficulty_severity": data.difficulty.severity,
            "recent_support_count": float(data.recent_support_count),
            "support_dependency": data.support_dependency_rate or 0.0,
            "item_difficulty": data.item.difficulty,
            "format_single_choice": float(data.item.response_format == "single_choice"),
            "template_hash": _bounded_hash(data.item.template_id),
            "episode_sequence": float(data.episode.sequence_at_decision),
            "session_support_fraction": (
                data.episode.session_support_count / data.episode.session_support_budget
                if data.episode.session_support_budget
                else 1.0
            ),
            "belief_confidence": belief.confidence if belief else 0.0,
            "belief_entropy": belief.entropy if belief else 0.0,
            "belief_abstained": float(belief.abstained) if belief else 1.0,
        }
        for code in CATALOGUE_CODES:
            values[f"belief:{code}"] = belief.probabilities[code] if belief else 0.0
        for action in ACTION_TYPES:
            rows = [row for row in data.prior_outcomes if row.scaffold_type == action]
            values[f"prior_ig:{action}"] = _mean([float(row.raw_independence_gain) for row in rows])
            values[f"prior_ig_count:{action}"] = float(len(rows))

        missingness = {
            "recent_unsupported": not data.recent_unsupported,
            "support_dependency": data.support_dependency_rate is None,
            "model1_belief": belief is None,
        }
        optional_freshness: dict[str, str] = {}
        for row in data.optional_evidence:
            if row.source not in {"knowledge_tracing", "multimodal_learner_state"}:
                raise Model2Error("Model 2 optional context must use an approved ownership port")
            if row.missing:
                optional_freshness[row.source] = "missing"
                missingness[f"optional:{row.source}"] = True
                continue
            if row.observed_at is not None and row.observed_at > data.decision_at:
                raise Model2Error("future optional evidence is forbidden")
            if not row.eligible or not row.consent_reference:
                optional_freshness[row.source] = "ineligible"
                missingness[f"optional:{row.source}"] = True
                continue
            if row.expires_at is not None and row.expires_at <= data.decision_at:
                optional_freshness[row.source] = "stale"
                missingness[f"optional:{row.source}"] = True
                continue
            optional_freshness[row.source] = "fresh"
            missingness[f"optional:{row.source}"] = False
            values[f"optional:{row.source}:reliability"] = float(row.reliability or 0)
            for key, value in sorted(row.values.items()):
                if any(token in key.lower() for token in FORBIDDEN_CONTEXT_TOKENS):
                    raise Model2Error("post-decision or personal optional field is forbidden")
                if (
                    isinstance(value, bool)
                    or isinstance(value, (int, float))
                    and math.isfinite(float(value))
                ):
                    values[f"optional:{row.source}:{key}"] = float(value)
        for source in ("knowledge_tracing", "multimodal_learner_state"):
            missingness.setdefault(f"optional:{source}", True)
            optional_freshness.setdefault(source, "missing")
        for name, is_missing in missingness.items():
            values[f"missing:{name}"] = float(is_missing)

        feature_definitions = {name: _feature_definition(name) for name in sorted(values)}
        provenance: dict[str, object] = {
            "unsupported_evidence": {
                "source": "phase3_authoritative_attempts",
                "as_of": max(row.observed_at for row in evidence).isoformat(),
                "evidence_ids": [str(row.evidence_id) for row in evidence],
            },
            "difficulty": {
                "source": "phase1_difficulty_trigger",
                "source_version": data.difficulty.trigger_version,
                "as_of": data.difficulty.observed_at.isoformat(),
                "evidence_ids": [
                    str(data.difficulty.difficulty_event_id),
                    *[str(item) for item in data.difficulty.contributing_event_ids],
                ],
            },
            "model1": {
                "belief_snapshot_id": str(belief.belief_snapshot_id) if belief else None,
                "model_version": belief.model_version if belief else None,
                "mapping_version": belief.mapping_version if belief else None,
                "artifact_sha256": belief.artifact_sha256 if belief else None,
                "as_of": belief.inference_at.isoformat() if belief else None,
            },
            "prior_outcomes": {
                "source": "phase3_valid_raw_independence_gain",
                "formula_version": FORMULA_VERSION,
                "evidence_ids": [str(row.measurement_id) for row in data.prior_outcomes],
            },
            "optional": {
                row.source: {
                    "source_version": row.source_version,
                    "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    "consent_reference": row.consent_reference,
                    "eligible": row.eligible,
                    "missing": row.missing,
                    "reliability": row.reliability,
                    "freshness": optional_freshness[row.source],
                }
                for row in data.optional_evidence
            },
        }

        evidence_ids = tuple(row.evidence_id for row in evidence) + (
            data.difficulty.difficulty_event_id,
            *data.difficulty.contributing_event_ids,
            *(row.measurement_id for row in data.prior_outcomes),
        )
        identity = sha256(
            canonical_json(
                {
                    "learner": str(data.learner_id),
                    "episode": str(data.episode_id),
                    "presentation": str(data.presentation_id),
                    "decision_at": data.decision_at.isoformat(),
                    "schema": self.version,
                    "evidence": [str(value) for value in evidence_ids],
                    "belief": str(belief.belief_snapshot_id) if belief else None,
                    "values": values,
                    "feature_definitions": feature_definitions,
                    "provenance": provenance,
                }
            )
        ).hexdigest()
        return Model2ContextSnapshot(
            context_snapshot_id=uuid5(CONTEXT_NAMESPACE, identity),
            learner_id=data.learner_id,
            skill_id=data.skill_id,
            skill_version=data.skill_version,
            episode_id=data.episode_id,
            presentation_id=data.presentation_id,
            decision_at=data.decision_at,
            schema_version=self.version,
            values=values,
            missingness=missingness,
            evidence_ids=evidence_ids,
            belief_snapshot_id=belief.belief_snapshot_id if belief else None,
            belief_model_version=belief.model_version if belief else None,
            belief_mapping_version=belief.mapping_version if belief else None,
            belief_artifact_sha256=belief.artifact_sha256 if belief else None,
            optional_freshness=optional_freshness,
            feature_definitions=feature_definitions,
            provenance=provenance,
            experiment_mode=data.episode.experiment_mode,
            protocol_version=data.episode.protocol_version,
        )


@dataclass(frozen=True, slots=True)
class ScaffoldCandidate:
    scaffold_id: str
    revision_id: str
    scaffold_type: str
    skill_id: str
    medium: str
    mapping_version: str
    lifecycle_status: str
    child_delivery_approved: bool
    supported_accommodations: tuple[str, ...]
    maximum_steps: int
    answer_revealing: bool
    compatible_probe_family_ids: tuple[str, ...]
    compatible_protocol_versions: tuple[str, ...]
    required_asset_ids: tuple[str, ...]
    available_asset_ids: tuple[str, ...]
    disclosure_level: int
    disclosure_ceiling: int
    safety_status: str = "structurally_safe"

    def __post_init__(self) -> None:
        if self.scaffold_type not in ACTION_TYPES:
            raise Model2Error("action is outside the three scaffold types")
        if self.maximum_steps < 1 or self.disclosure_level < 0 or self.disclosure_ceiling < 0:
            raise Model2Error("scaffold limits are invalid")


@dataclass(frozen=True, slots=True)
class EligibilityInput:
    accommodations: tuple[str, ...]
    allow_draft: bool
    child_facing: bool


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    scaffold_id: str
    revision_id: str
    scaffold_type: str
    eligible: bool
    reason_codes: tuple[str, ...]
    predicted_raw_ig: float | None
    uncertainty: float | None
    rank: int | None
    propensity: float
    policy_version: str
    artifact_sha256: str
    context_schema_version: str


@dataclass(frozen=True, slots=True)
class ScaffoldDecision:
    decision_id: UUID
    learner_id: UUID
    skill_id: str
    episode_id: UUID
    presentation_id: UUID
    experiment_mode: ExperimentMode
    context_snapshot_id: UUID | None
    context_schema_version: str
    candidates: tuple[CandidateDecision, ...]
    selected_scaffold_id: str | None
    shadow_scaffold_id: str | None
    policy_version: str
    artifact_version: str
    artifact_sha256: str
    mode: PolicyMode
    selection_kind: SelectionKind
    random_seed: int
    assignment_token: str
    decided_at: datetime
    reason_codes: tuple[str, ...]
    reward_link_id: UUID | None = None


class Model2Selector(Protocol):
    interface_version: str

    def decide(
        self,
        *,
        mode: PolicyMode,
        context_input: Model2ContextInput,
        candidates: tuple[ScaffoldCandidate, ...],
        eligibility: EligibilityInput,
        seed: int,
        assignment_token: str,
    ) -> tuple[Model2ContextSnapshot | None, ScaffoldDecision]: ...


class ContextualScaffoldPolicy:
    interface_version = INTERFACE_VERSION

    def __init__(
        self,
        *,
        bandit: LinUCBPolicy | None = None,
        artifact_version: str = "model2-cold-start-v1",
        artifact_sha256: str = "0" * 64,
        baseline_scaffold_type: str = "visual_guidance",
        minimum_training_rewards: int = 3,
    ) -> None:
        if baseline_scaffold_type not in ACTION_TYPES:
            raise Model2Error("baseline scaffold must be in the scaffold action set")
        self.bandit = bandit or LinUCBPolicy(alpha=1.0, ridge=1.0, epsilon_min=0.05)
        self.artifact_version = artifact_version
        self.artifact_sha256 = artifact_sha256
        self.baseline_scaffold_type = baseline_scaffold_type
        self.minimum_training_rewards = minimum_training_rewards
        self.reward_count = 0

    def decide(
        self,
        *,
        mode: PolicyMode,
        context_input: Model2ContextInput,
        candidates: tuple[ScaffoldCandidate, ...],
        eligibility: EligibilityInput,
        seed: int,
        assignment_token: str,
    ) -> tuple[Model2ContextSnapshot | None, ScaffoldDecision]:
        if not candidates or {row.scaffold_type for row in candidates} != set(ACTION_TYPES):
            raise Model2Error("the complete three-action scaffold catalogue is required")
        if (
            mode is PolicyMode.DETERMINISTIC_BASELINE
            and context_input.episode.experiment_mode is not ExperimentMode.BASELINE
        ) or (
            mode
            in {
                PolicyMode.PROPOSED_SHADOW,
                PolicyMode.PROPOSED_OFFLINE,
                PolicyMode.LEARNED_DELIVERY,
            }
            and context_input.episode.experiment_mode is not ExperimentMode.PROPOSED
        ):
            raise Model2Error("policy mode and frozen experiment condition do not match")
        if not context_input.difficulty.detected:
            return None, self._fallback(
                context_input, candidates, seed, assignment_token, "DIFFICULTY_NOT_TRIGGERED"
            )
        require_belief = mode is not PolicyMode.DETERMINISTIC_BASELINE
        context = Model2ContextBuilder().build(context_input, require_belief=require_belief)
        assessed = _eligibility(context_input, candidates, eligibility)
        eligible = tuple(row for row, reasons in assessed if not reasons)
        if not eligible:
            return context, self._fallback(
                context_input,
                candidates,
                seed,
                assignment_token,
                "NO_ELIGIBLE_ACTION",
                assessed=assessed,
                context=context,
            )
        reference = next(
            (row for row in eligible if row.scaffold_type == self.baseline_scaffold_type),
            min(eligible, key=lambda row: row.scaffold_id),
        )
        if mode is PolicyMode.DETERMINISTIC_BASELINE:
            records = _baseline_records(
                assessed, reference, self.artifact_sha256, context.schema_version
            )
            return context, self._decision(
                context_input,
                context,
                records,
                reference.scaffold_id,
                None,
                PolicyMode.DETERMINISTIC_BASELINE,
                SelectionKind.BASELINE,
                seed,
                assignment_token,
                ("DIFFICULTY_TRIGGERED", "EDUCATOR_AUTHORED_FIXED", "NO_IG_UPDATE"),
            )

        arms = tuple(row.scaffold_type for row in eligible)
        bandit_context = context.as_bandit_context()
        predictions = self.bandit.predict(bandit_context, arms)
        sampled, propensities = self.bandit.sample_action(bandit_context, arms, seed=seed)
        cold_or_uncertain = (
            self.reward_count < self.minimum_training_rewards
            or context_input.belief is None
            or context_input.belief.abstained
            or context_input.belief.probabilities["unknown_or_other"] >= 0.5
        )
        reasons: tuple[str, ...]
        if cold_or_uncertain:
            sampled = reference.scaffold_type
            propensities = {
                action: 1.0 if action == reference.scaffold_type else 0.0 for action in arms
            }
            reasons = ("CONSERVATIVE_COLD_OR_UNCERTAIN_REFERENCE",)
        else:
            reasons = ("SEEDED_CONSTRAINED_EXPLORATION",)
        records = _proposed_records(
            assessed,
            predictions,
            propensities,
            self.artifact_sha256,
            context.schema_version,
        )
        would_select = next(row.scaffold_id for row in eligible if row.scaffold_type == sampled)
        if mode is PolicyMode.PROPOSED_SHADOW:
            selected = reference.scaffold_id
            shadow = would_select
            kind = SelectionKind.SHADOW
            reasons += ("SHADOW_REFERENCE_DELIVERY",)
        elif mode is PolicyMode.PROPOSED_OFFLINE:
            selected = would_select
            shadow = None
            kind = (
                SelectionKind.EXPLORE
                if len([value for value in propensities.values() if value > 0]) > 1
                else SelectionKind.EXPLOIT
            )
            reasons += ("OFFLINE_SIMULATION_ONLY",)
        elif mode is PolicyMode.LEARNED_DELIVERY:
            return context, self._fallback(
                context_input,
                candidates,
                seed,
                assignment_token,
                "LEARNED_CHILD_CONTROL_BLOCKED_PENDING_HUMAN_APPROVAL",
                assessed=assessed,
                context=context,
            )
        else:
            return context, self._fallback(
                context_input,
                candidates,
                seed,
                assignment_token,
                "SAFE_FALLBACK_REQUESTED",
                assessed=assessed,
                context=context,
            )
        return context, self._decision(
            context_input,
            context,
            records,
            selected,
            shadow,
            mode,
            kind,
            seed,
            assignment_token,
            reasons,
        )

    def update(self, context: Model2ContextSnapshot, scaffold_type: str, raw_ig: Decimal) -> None:
        if scaffold_type not in ACTION_TYPES or not Decimal(-1) <= raw_ig <= Decimal(1):
            raise Model2Error("policy update action or raw IG is invalid")
        self.bandit.update(context.as_bandit_context(), scaffold_type, float(raw_ig))
        self.reward_count += 1

    def _decision(
        self,
        data: Model2ContextInput,
        context: Model2ContextSnapshot,
        records: tuple[CandidateDecision, ...],
        selected: str | None,
        shadow: str | None,
        mode: PolicyMode,
        kind: SelectionKind,
        seed: int,
        token: str,
        reasons: tuple[str, ...],
    ) -> ScaffoldDecision:
        stable = f"{data.episode_id}|{context.context_snapshot_id}|{mode}|{seed}|{token}"
        return ScaffoldDecision(
            decision_id=uuid5(DECISION_NAMESPACE, stable),
            learner_id=data.learner_id,
            skill_id=data.skill_id,
            episode_id=data.episode_id,
            presentation_id=data.presentation_id,
            experiment_mode=data.episode.experiment_mode,
            context_snapshot_id=context.context_snapshot_id,
            context_schema_version=context.schema_version,
            candidates=records,
            selected_scaffold_id=selected,
            shadow_scaffold_id=shadow,
            policy_version=(
                BASELINE_POLICY_VERSION
                if mode is PolicyMode.DETERMINISTIC_BASELINE
                else POLICY_VERSION
            ),
            artifact_version=self.artifact_version,
            artifact_sha256=self.artifact_sha256,
            mode=mode,
            selection_kind=kind,
            random_seed=seed,
            assignment_token=token,
            decided_at=data.decision_at,
            reason_codes=reasons,
        )

    def _fallback(
        self,
        data: Model2ContextInput,
        candidates: tuple[ScaffoldCandidate, ...],
        seed: int,
        token: str,
        reason: str,
        *,
        assessed: tuple[tuple[ScaffoldCandidate, tuple[str, ...]], ...] | None = None,
        context: Model2ContextSnapshot | None = None,
    ) -> ScaffoldDecision:
        assessed = assessed or tuple((row, (reason,)) for row in candidates)
        records = tuple(
            CandidateDecision(
                row.scaffold_id,
                row.revision_id,
                row.scaffold_type,
                False,
                reasons or (reason,),
                None,
                None,
                None,
                0.0,
                POLICY_VERSION,
                self.artifact_sha256,
                CONTEXT_SCHEMA_VERSION,
            )
            for row, reasons in assessed
        )
        snapshot_id = context.context_snapshot_id if context else None
        stable = f"{data.episode_id}|{snapshot_id}|fallback|{seed}|{token}|{reason}"
        return ScaffoldDecision(
            decision_id=uuid5(DECISION_NAMESPACE, stable),
            learner_id=data.learner_id,
            skill_id=data.skill_id,
            episode_id=data.episode_id,
            presentation_id=data.presentation_id,
            experiment_mode=data.episode.experiment_mode,
            context_snapshot_id=snapshot_id,
            context_schema_version=CONTEXT_SCHEMA_VERSION,
            candidates=records,
            selected_scaffold_id=None,
            shadow_scaffold_id=None,
            policy_version=POLICY_VERSION,
            artifact_version=self.artifact_version,
            artifact_sha256=self.artifact_sha256,
            mode=PolicyMode.SAFE_FALLBACK,
            selection_kind=SelectionKind.FALLBACK,
            random_seed=seed,
            assignment_token=token,
            decided_at=data.decision_at,
            reason_codes=(reason, NEUTRAL_FALLBACK),
        )


def development_phase2_scaffolds(*, allow_draft: bool = False) -> tuple[ScaffoldCandidate, ...]:
    if not allow_draft:
        raise PermissionError("draft scaffolds require allow_draft=True")
    from app.gamification.content.phase2_registry import load_phase2_public_package

    package = load_phase2_public_package(allow_draft=True)
    if package.skill.skill_id != SKILL_ID:
        raise Model2Error("content skill does not match Model 2")
    rows = []
    for scaffold in package.scaffolds:
        rows.append(
            ScaffoldCandidate(
                scaffold_id=scaffold.scaffold_id,
                revision_id=scaffold.scaffold_revision_id,
                scaffold_type=scaffold.scaffold_type,
                skill_id=scaffold.skill_id,
                medium=scaffold.language,
                mapping_version=CATALOGUE_VERSION,
                lifecycle_status=scaffold.review_status,
                child_delivery_approved=False,
                supported_accommodations=("screen_reader", "reduced_motion", "keyboard"),
                maximum_steps=scaffold.maximum_steps,
                answer_revealing=False,
                compatible_probe_family_ids=(package.parallel_family.family_id,),
                compatible_protocol_versions=("adaptive-episode-v1",),
                required_asset_ids=(f"{scaffold.scaffold_id}:content",),
                available_asset_ids=(f"{scaffold.scaffold_id}:content",),
                disclosure_level=scaffold.maximum_steps,
                disclosure_ceiling=scaffold.maximum_steps,
                safety_status="structurally_safe",
            )
        )
    if {row.scaffold_type for row in rows} != set(ACTION_TYPES):
        raise Model2Error("scaffold catalogue has drifted")
    return tuple(rows)


def delivery_failure_fallback(
    decision: ScaffoldDecision, *, failed_at: datetime, reason_code: str
) -> ScaffoldDecision:
    """Record a delivery failure without silently trying an unlogged alternative action."""

    _aware(failed_at, "delivery failure")
    if not reason_code or decision.selected_scaffold_id is None:
        raise Model2Error("delivery fallback requires a selected action and reason")
    return replace(
        decision,
        selected_scaffold_id=None,
        shadow_scaffold_id=None,
        mode=PolicyMode.SAFE_FALLBACK,
        selection_kind=SelectionKind.FALLBACK,
        reason_codes=(*decision.reason_codes, f"DELIVERY_FAILURE:{reason_code}", NEUTRAL_FALLBACK),
    )


def _eligibility(
    data: Model2ContextInput,
    candidates: tuple[ScaffoldCandidate, ...],
    request: EligibilityInput,
) -> tuple[tuple[ScaffoldCandidate, tuple[str, ...]], ...]:
    results = []
    for row in candidates:
        reasons = []
        if row.lifecycle_status == "draft" and not request.allow_draft:
            reasons.append("DRAFT_OVERRIDE_REQUIRED")
        if request.child_facing:
            reasons.append("UNAPPROVED_FOR_CHILD_DELIVERY")
        if row.skill_id != data.skill_id:
            reasons.append("WRONG_SKILL")
        if row.medium != data.medium:
            reasons.append("WRONG_MEDIUM")
        if row.mapping_version != CATALOGUE_VERSION:
            reasons.append("MAPPING_VERSION_MISMATCH")
        if row.lifecycle_status == "retired":
            reasons.append("RETIRED_SCAFFOLD")
        if row.safety_status != "structurally_safe":
            reasons.append("UNSAFE_SCAFFOLD")
        if not row.revision_id.endswith("@v1"):
            reasons.append("WRONG_SCAFFOLD_VERSION")
        if not set(request.accommodations) <= set(row.supported_accommodations):
            reasons.append("ACCESSIBILITY_INCOMPATIBLE")
        if row.maximum_steps > data.episode.remaining_support_steps:
            reasons.append("ASSISTANCE_BUDGET_EXCEEDED")
        if data.episode.session_support_count >= data.episode.session_support_budget:
            reasons.append("SESSION_BUDGET_EXCEEDED")
        if row.answer_revealing:
            reasons.append("ANSWER_REVEALING")
        if data.item.parallel_family_id not in row.compatible_probe_family_ids:
            reasons.append("RESERVED_PROBE_INCOMPATIBLE")
        if data.episode.protocol_version not in row.compatible_protocol_versions:
            reasons.append("EPISODE_PROTOCOL_INCOMPATIBLE")
        if not set(row.required_asset_ids) <= set(row.available_asset_ids):
            reasons.append("REQUIRED_ASSET_UNAVAILABLE")
        if row.disclosure_level > row.disclosure_ceiling:
            reasons.append("DISCLOSURE_CEILING_EXCEEDED")
        results.append((row, tuple(reasons)))
    return tuple(results)


def _baseline_records(
    assessed: tuple[tuple[ScaffoldCandidate, tuple[str, ...]], ...],
    selected: ScaffoldCandidate,
    artifact_hash: str,
    context_version: str,
) -> tuple[CandidateDecision, ...]:
    return tuple(
        CandidateDecision(
            row.scaffold_id,
            row.revision_id,
            row.scaffold_type,
            not reasons,
            reasons or ("ELIGIBLE",),
            None,
            None,
            None,
            1.0 if row.scaffold_id == selected.scaffold_id else 0.0,
            BASELINE_POLICY_VERSION,
            artifact_hash,
            context_version,
        )
        for row, reasons in assessed
    )


def _proposed_records(
    assessed: tuple[tuple[ScaffoldCandidate, tuple[str, ...]], ...],
    predictions: Mapping[str, tuple[float, float]],
    propensities: Mapping[str, float],
    artifact_hash: str,
    context_version: str,
) -> tuple[CandidateDecision, ...]:
    ranked = sorted(predictions, key=lambda action: (-predictions[action][0], action))
    return tuple(
        CandidateDecision(
            row.scaffold_id,
            row.revision_id,
            row.scaffold_type,
            not reasons,
            reasons or ("ELIGIBLE",),
            predictions[row.scaffold_type][0] if not reasons else None,
            predictions[row.scaffold_type][1] if not reasons else None,
            ranked.index(row.scaffold_type) + 1 if not reasons else None,
            propensities.get(row.scaffold_type, 0.0) if not reasons else 0.0,
            POLICY_VERSION,
            artifact_hash,
            context_version,
        )
        for row, reasons in assessed
    )


@dataclass(frozen=True, slots=True)
class RewardLink:
    reward_link_id: UUID
    decision_id: UUID
    measurement_id: UUID
    raw_independence_gain: Decimal
    formula_version: str
    link_version: str
    linked_at: datetime


class RewardLinker:
    def __init__(self) -> None:
        self._links: dict[UUID, RewardLink] = {}

    def link(
        self,
        decision: ScaffoldDecision,
        measurement: IndependenceMeasurementContract,
        *,
        context: Model2ContextSnapshot,
        policy: ContextualScaffoldPolicy,
        linked_at: datetime,
        expected_policy_version: str = POLICY_VERSION,
        expected_context_version: str = CONTEXT_SCHEMA_VERSION,
        expected_artifact_sha256: str | None = None,
    ) -> RewardLink:
        _aware(linked_at, "reward link")
        if decision.decision_id in self._links:
            existing = self._links[decision.decision_id]
            if (
                existing.measurement_id != measurement.measurement_id
                or existing.raw_independence_gain != measurement.raw_independence_gain
                or existing.formula_version != measurement.formula_version
            ):
                raise Model2Error("DUPLICATE_REWARD_CONFLICT")
            return existing
        if (
            decision.context_snapshot_id != context.context_snapshot_id
            or decision.learner_id != context.learner_id
            or decision.episode_id != context.episode_id
        ):
            raise Model2Error("WRONG_CONTEXT_FOR_DECISION")
        if measurement.decision_id != decision.decision_id:
            raise Model2Error("WRONG_DECISION_REWARD")
        if decision.experiment_mode is not ExperimentMode.PROPOSED:
            raise Model2Error("BASELINE_REWARD_REJECTED")
        if decision.mode not in {PolicyMode.PROPOSED_SHADOW, PolicyMode.PROPOSED_OFFLINE}:
            raise Model2Error("decision mode cannot learn from reward")
        if (
            not measurement.valid
            or measurement.raw_independence_gain is None
            or getattr(measurement.policy_update_status, "value", None) != "authorized_delayed"
        ):
            raise Model2Error("INVALID_OR_UNAUTHORIZED_REWARD")
        if measurement.formula_version != FORMULA_VERSION:
            raise Model2Error("WRONG_REWARD_FORMULA_VERSION")
        if decision.policy_version != expected_policy_version:
            raise Model2Error("WRONG_POLICY_VERSION")
        if context.schema_version != expected_context_version:
            raise Model2Error("WRONG_CONTEXT_VERSION")
        if context.belief_mapping_version != CATALOGUE_VERSION:
            raise Model2Error("WRONG_CATALOGUE_VERSION")
        if (
            expected_artifact_sha256 is not None
            and decision.artifact_sha256 != expected_artifact_sha256
        ):
            raise Model2Error("WRONG_ARTIFACT_VERSION")
        selected = next(
            (
                row
                for row in decision.candidates
                if row.scaffold_id == decision.selected_scaffold_id
            ),
            None,
        )
        if selected is None:
            raise Model2Error("reward decision has no delivered eligible action")
        policy.update(context, selected.scaffold_type, measurement.raw_independence_gain)
        link = RewardLink(
            reward_link_id=uuid5(
                REWARD_NAMESPACE, f"{decision.decision_id}|{measurement.measurement_id}"
            ),
            decision_id=decision.decision_id,
            measurement_id=measurement.measurement_id,
            raw_independence_gain=measurement.raw_independence_gain,
            formula_version=measurement.formula_version,
            link_version=REWARD_LINK_VERSION,
            linked_at=linked_at,
        )
        self._links[decision.decision_id] = link
        return link


class ArtifactLifecycle(StrEnum):
    DRAFT = "draft"
    SHADOW = "shadow"
    APPROVED = "approved"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class Model2Artifact:
    artifact_version: str
    policy_version: str
    context_schema_version: str
    catalogue_version: str
    dataset_manifest_sha256: str
    evaluation_sha256: str
    seed: int
    parameters: Mapping[str, object]
    evidence_status: str
    data_authorization_reference: str | None
    lifecycle: ArtifactLifecycle
    artifact_sha256: str

    def __post_init__(self) -> None:
        if any(
            len(value) != 64
            for value in (
                self.dataset_manifest_sha256,
                self.evaluation_sha256,
                self.artifact_sha256,
            )
        ):
            raise Model2Error("artifact hashes must be complete SHA-256 digests")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))

    @classmethod
    def create(
        cls,
        *,
        artifact_version: str,
        dataset_manifest_sha256: str,
        evaluation_sha256: str,
        seed: int,
        parameters: Mapping[str, object],
        synthetic: bool,
        data_authorization_reference: str | None = None,
    ) -> Model2Artifact:
        if not synthetic and not data_authorization_reference:
            raise PermissionError(
                "non-synthetic artifacts require an exact data-authorization reference"
            )
        payload = {
            "artifact_version": artifact_version,
            "policy_version": POLICY_VERSION,
            "context_schema_version": CONTEXT_SCHEMA_VERSION,
            "catalogue_version": CATALOGUE_VERSION,
            "dataset_manifest_sha256": dataset_manifest_sha256,
            "evaluation_sha256": evaluation_sha256,
            "seed": seed,
            "parameters": dict(parameters),
            "evidence_status": "synthetic_engineering_only" if synthetic else "authorized_data",
            "data_authorization_reference": data_authorization_reference,
            "lifecycle": ArtifactLifecycle.DRAFT.value,
        }
        return cls(
            **{**payload, "lifecycle": ArtifactLifecycle.DRAFT},
            artifact_sha256=sha256(canonical_json(payload)).hexdigest(),
        )

    def verify(self) -> None:
        payload = {
            "artifact_version": self.artifact_version,
            "policy_version": self.policy_version,
            "context_schema_version": self.context_schema_version,
            "catalogue_version": self.catalogue_version,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "evaluation_sha256": self.evaluation_sha256,
            "seed": self.seed,
            "parameters": dict(self.parameters),
            "evidence_status": self.evidence_status,
            "data_authorization_reference": self.data_authorization_reference,
            "lifecycle": ArtifactLifecycle.DRAFT.value,
        }
        if sha256(canonical_json(payload)).hexdigest() != self.artifact_sha256:
            raise Model2Error("artifact hash mismatch")


class Model2ArtifactRegistry:
    def __init__(self) -> None:
        self._artifacts: dict[str, Model2Artifact] = {}
        self._active_shadow: str | None = None

    def register(self, artifact: Model2Artifact) -> None:
        artifact.verify()
        self._artifacts[artifact.artifact_sha256] = artifact

    def activate_shadow(self, artifact_sha256: str) -> None:
        artifact = self._artifacts[artifact_sha256]
        if artifact.lifecycle not in {ArtifactLifecycle.DRAFT, ArtifactLifecycle.SHADOW}:
            raise Model2Error("retired/approved artifact cannot enter draft shadow")
        self._active_shadow = artifact_sha256

    def activate_learned_delivery(self, artifact_sha256: str, authorization: object | None) -> None:
        del artifact_sha256, authorization
        raise PermissionError("exact-hash human authorization is absent")

    def retire(self, artifact_sha256: str) -> None:
        artifact = self._artifacts[artifact_sha256]
        self._artifacts[artifact_sha256] = _replace_lifecycle(artifact, ArtifactLifecycle.RETIRED)
        if self._active_shadow == artifact_sha256:
            self._active_shadow = None

    def rollback_shadow(self, artifact_sha256: str) -> None:
        artifact = self._artifacts[artifact_sha256]
        if artifact.lifecycle is ArtifactLifecycle.RETIRED:
            raise Model2Error("cannot rollback to a retired artifact")
        self._active_shadow = artifact_sha256

    @property
    def active_shadow(self) -> Model2Artifact | None:
        return self._artifacts.get(self._active_shadow) if self._active_shadow else None


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    episode_id: str
    action: str
    mode: str
    predicted_ig: float
    observed_raw_ig: float | None
    valid: bool
    propensity: float | None
    explored: bool
    fallback: bool
    support_dependency: float | None
    delivery_failed: bool
    ranking_group: str | None = None
    skill_version: str = SKILL_VERSION
    initial_ability_band: str = "not_available"
    approval_status: str = "draft_not_child_approved"
    safety_violation: bool = False
    decision_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Model2Evaluation:
    evidence_status: str
    valid_sample_count: int
    mean_valid_raw_ig_by_action: Mapping[str, float]
    mean_valid_raw_ig_by_mode: Mapping[str, float]
    mean_absolute_prediction_error: float
    calibration_bins: Mapping[str, Mapping[str, float | int]]
    action_coverage: float
    propensity_integrity: bool
    exploration_rate: float
    fallback_rate: float
    mean_support_dependency: float | None
    delivery_failure_rate: float
    pairwise_ranking_agreement: float | None
    mean_valid_raw_ig_by_skill: Mapping[str, float]
    mean_valid_raw_ig_by_initial_ability: Mapping[str, float]
    approval_statuses: tuple[str, ...]
    safety_violation_rate: float


def evaluate_model2(
    rows: Sequence[EvaluationRow],
    *,
    authorized_real_data: bool,
    authorization_reference: str | None = None,
) -> Model2Evaluation:
    if not rows:
        raise Model2Error("evaluation requires rows")
    if authorized_real_data and not authorization_reference:
        raise PermissionError("authorized real-data evaluation requires an authorization reference")
    valid = [row for row in rows if row.valid and row.observed_raw_ig is not None]
    by_action = _group_mean(valid, "action")
    by_mode = _group_mean(valid, "mode")
    errors = [abs(row.predicted_ig - float(row.observed_raw_ig)) for row in valid]
    calibration: dict[str, Mapping[str, float | int]] = {}
    for lower in (-1.0, -0.5, 0.0, 0.5):
        upper = lower + 0.5
        bucket = [
            row
            for row in valid
            if lower <= row.predicted_ig < upper or (upper == 1.0 and row.predicted_ig == 1.0)
        ]
        if bucket:
            calibration[f"{lower:.1f}:{upper:.1f}"] = MappingProxyType(
                {
                    "count": len(bucket),
                    "mean_predicted": _mean([row.predicted_ig for row in bucket]),
                    "mean_observed": _mean([float(row.observed_raw_ig) for row in bucket]),
                }
            )
    eligible_propensities = [row.propensity for row in rows if row.propensity is not None]
    return Model2Evaluation(
        evidence_status="authorized_real_data"
        if authorized_real_data
        else "synthetic_engineering_only",
        valid_sample_count=len(valid),
        mean_valid_raw_ig_by_action=MappingProxyType(by_action),
        mean_valid_raw_ig_by_mode=MappingProxyType(by_mode),
        mean_absolute_prediction_error=_mean(errors),
        calibration_bins=MappingProxyType(calibration),
        action_coverage=len({row.action for row in rows}) / len(ACTION_TYPES),
        propensity_integrity=all(
            value is not None and 0 <= value <= 1 for value in eligible_propensities
        ),
        exploration_rate=sum(row.explored for row in rows) / len(rows),
        fallback_rate=sum(row.fallback for row in rows) / len(rows),
        mean_support_dependency=(
            _mean([row.support_dependency for row in rows if row.support_dependency is not None])
            if any(row.support_dependency is not None for row in rows)
            else None
        ),
        delivery_failure_rate=sum(row.delivery_failed for row in rows) / len(rows),
        pairwise_ranking_agreement=_ranking_agreement(valid),
        mean_valid_raw_ig_by_skill=MappingProxyType(_group_mean(valid, "skill_version")),
        mean_valid_raw_ig_by_initial_ability=MappingProxyType(
            _group_mean(valid, "initial_ability_band")
        ),
        approval_statuses=tuple(sorted({row.approval_status for row in rows})),
        safety_violation_rate=sum(row.safety_violation for row in rows) / len(rows),
    )


@dataclass(frozen=True, slots=True)
class ContextAblation:
    full_predictions: Mapping[str, tuple[float, float]]
    without_model1_predictions: Mapping[str, tuple[float, float]]


def evaluate_context_ablation(
    policy: ContextualScaffoldPolicy,
    context: Model2ContextSnapshot,
    scaffold_types: Sequence[str] = ACTION_TYPES,
) -> ContextAblation:
    actions = tuple(scaffold_types)
    if not actions or any(action not in ACTION_TYPES for action in actions):
        raise Model2Error("ablation requires the Model 2 scaffold actions")
    return ContextAblation(
        full_predictions=MappingProxyType(
            policy.bandit.predict(context.as_bandit_context(), actions)
        ),
        without_model1_predictions=MappingProxyType(
            policy.bandit.predict(context.as_bandit_context(exclude_beliefs=True), actions)
        ),
    )


@dataclass(frozen=True, slots=True)
class OffPolicyEstimate:
    sample_count: int
    ips: float
    snips: float
    doubly_robust: float | None


@dataclass(frozen=True, slots=True)
class OfflineTimeSplit:
    cutoff: datetime
    training: tuple[EvaluationRow, ...]
    evaluation: tuple[EvaluationRow, ...]


def time_split_evaluation_rows(
    rows: Sequence[EvaluationRow], *, cutoff: datetime
) -> OfflineTimeSplit:
    _aware(cutoff, "offline evaluation cutoff")
    if not rows or any(row.decision_at is None for row in rows):
        raise Model2Error("time-split evaluation requires timestamped decisions")
    if any(
        row.decision_at is not None
        and (row.decision_at.tzinfo is None or row.decision_at.utcoffset() is None)
        for row in rows
    ):
        raise Model2Error("time-split decisions require UTC offsets")
    training = tuple(
        row for row in rows if row.decision_at is not None and row.decision_at < cutoff
    )
    evaluation = tuple(
        row for row in rows if row.decision_at is not None and row.decision_at >= cutoff
    )
    if not training or not evaluation:
        raise Model2Error("time split requires non-empty training and evaluation partitions")
    overlap = {row.episode_id for row in training} & {row.episode_id for row in evaluation}
    if overlap:
        raise Model2Error("episode leakage crosses the offline time split")
    return OfflineTimeSplit(cutoff, training, evaluation)


def evaluate_off_policy(
    rows: Sequence[EvaluationRow],
    target_probabilities: Mapping[tuple[str, str], float],
    reward_estimates: Mapping[tuple[str, str], float] | None = None,
) -> OffPolicyEstimate:
    usable = [row for row in rows if row.valid and row.observed_raw_ig is not None]
    if not usable or any(row.propensity is None or not 0 < row.propensity < 1 for row in usable):
        raise Model2Error(
            "IPS/SNIPS require valid outcomes and positive nondegenerate propensities"
        )
    for episode in {row.episode_id for row in usable}:
        probabilities = [
            value
            for (episode_id, _), value in target_probabilities.items()
            if episode_id == episode
        ]
        if not probabilities or abs(sum(probabilities) - 1.0) > 1e-12:
            raise Model2Error("off-policy target propensities must normalize for every episode")
    weights = [
        target_probabilities.get((row.episode_id, row.action), 0.0) / float(row.propensity)
        for row in usable
    ]
    if any(weight == 0 for weight in weights):
        raise Model2Error("off-policy support assumption is violated")
    weighted = [
        weight * float(row.observed_raw_ig) for weight, row in zip(weights, usable, strict=True)
    ]
    dr = None
    if reward_estimates is not None:
        values = []
        for row, weight in zip(usable, weights, strict=True):
            actions = [key for key in target_probabilities if key[0] == row.episode_id]
            if any(key not in reward_estimates for key in actions):
                raise Model2Error("doubly robust evaluation requires complete reward estimates")
            direct = sum(target_probabilities[key] * reward_estimates[key] for key in actions)
            logged = reward_estimates.get((row.episode_id, row.action))
            if logged is None:
                raise Model2Error("doubly robust logged-action estimate is missing")
            values.append(direct + weight * (float(row.observed_raw_ig) - logged))
        dr = _mean(values)
    return OffPolicyEstimate(
        sample_count=len(usable),
        ips=sum(weighted) / len(usable),
        snips=sum(weighted) / sum(weights),
        doubly_robust=dr,
    )


def run_phase5_simulation(*, seed: int = 31) -> Mapping[str, object]:
    """Deterministic synthetic scenarios; never learner or effectiveness evidence."""

    rng = random.Random(seed)
    effects = {
        "visual_guidance": (Decimal("0.50"), Decimal("0.00"), Decimal("-0.20")),
        "worked_parallel_example": (Decimal("0.00"), Decimal("0.50"), Decimal("-0.20")),
        "step_by_step_guidance": (Decimal("-0.10"), Decimal("0.00"), Decimal("0.50")),
    }
    scenarios = (
        "known_effects",
        "cold_start",
        "sparse_actions",
        "missing_model1",
        "model1_abstention",
        "positive_zero_negative_ig",
        "invalid_outcome",
        "action_imbalance",
    )
    draws = {
        action: [float(value) + rng.uniform(-0.01, 0.01) for value in values]
        for action, values in effects.items()
    }
    context_names = ("whole_set_error", "subtracts_two_error", "unknown_error")
    synthetic_policy = LinUCBPolicy(alpha=0.1, ridge=1.0, epsilon_min=0.05)
    contexts = tuple(
        BanditContext(
            LEGACY_CONTEXT_VERSION,
            ("bias", *context_names),
            (1.0, *(1.0 if index == position else 0.0 for index in range(3))),
            {},
        )
        for position in range(3)
    )
    for _ in range(40):
        for position, context in enumerate(contexts):
            for action in ACTION_TYPES:
                synthetic_policy.update(context, action, float(effects[action][position]))
    recovered = tuple(
        max(
            synthetic_policy.predict(context, ACTION_TYPES),
            key=lambda action: synthetic_policy.predict(context, ACTION_TYPES)[action][0],
        )
        for context in contexts
    )
    expected = tuple(
        max(ACTION_TYPES, key=lambda action: effects[action][position]) for position in range(3)
    )
    return MappingProxyType(
        {
            "generator_version": "model2-synthetic-simulation-v1",
            "seed": seed,
            "synthetic": True,
            "label": "engineering evidence only; not educational effectiveness",
            "scenarios": scenarios,
            "mean_raw_ig_by_action": {action: _mean(values) for action, values in draws.items()},
            "known_best_actions": dict(zip(context_names, expected, strict=True)),
            "recovered_best_actions": dict(zip(context_names, recovered, strict=True)),
            "best_action_recovery_rate": sum(
                actual == wanted for actual, wanted in zip(recovered, expected, strict=True)
            )
            / len(expected),
            "baselines": (
                "deterministic_educator_authored",
                "random_safe_simulation_only",
                "skill_only_authored",
                "proposed_without_model1_ablation",
            ),
        }
    )


def _replace_lifecycle(artifact: Model2Artifact, lifecycle: ArtifactLifecycle) -> Model2Artifact:
    return replace(artifact, lifecycle=lifecycle)


def _group_mean(rows: Sequence[EvaluationRow], attribute: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(getattr(row, attribute))].append(float(row.observed_raw_ig))
    return {key: _mean(values) for key, values in sorted(grouped.items())}


def _ranking_agreement(rows: Sequence[EvaluationRow]) -> float | None:
    """Compare predicted and observed order only within explicit comparable groups."""

    grouped: dict[str, list[EvaluationRow]] = defaultdict(list)
    for row in rows:
        if row.ranking_group is not None:
            grouped[row.ranking_group].append(row)
    outcomes: list[bool] = []
    for group in grouped.values():
        for left_index, left in enumerate(group):
            for right in group[left_index + 1 :]:
                predicted_delta = left.predicted_ig - right.predicted_ig
                observed_delta = float(left.observed_raw_ig) - float(right.observed_raw_ig)
                if predicted_delta and observed_delta:
                    outcomes.append((predicted_delta > 0) == (observed_delta > 0))
    return sum(outcomes) / len(outcomes) if outcomes else None


def _feature_definition(name: str) -> str:
    if name.startswith("belief:"):
        return "Model 1 posterior probability for the named reviewed misconception state."
    if name.startswith("prior_ig:"):
        return "Mean prior valid raw Independence Gain for the named scaffold type."
    if name.startswith("prior_ig_count:"):
        return "Count of prior valid Independence Gain outcomes for the named scaffold type."
    if name.startswith("missing:"):
        return "Explicit missingness indicator for the named pre-decision evidence source."
    if name.startswith("optional:"):
        return "Fresh, eligible, consent-referenced optional evidence from the named owner port."
    definitions = {
        "bias": "Constant intercept feature.",
        "unsupported_before_score": "Current unsupported-before earned/max score ratio.",
        "recent_unsupported_mean": "Mean prior unsupported score ratio in the supplied window.",
        "attempt_count": "Attempts observed for the current unsupported-before presentation.",
        "error_persistence": "Repeated-error count before the scaffold decision.",
        "difficulty_detected": "Whether the versioned difficulty trigger fired.",
        "difficulty_severity": "Normalized pre-decision difficulty-trigger severity.",
        "recent_support_count": "Count of prior support exposures in the supplied window.",
        "support_dependency": "Prior support-dependency summary, never the current outcome.",
        "item_difficulty": "Authored difficulty of the current immutable item revision.",
        "format_single_choice": "Indicator for the current item response format.",
        "template_hash": "Stable bounded encoding of the current game-template identifier.",
        "episode_sequence": "Event sequence number frozen at the decision boundary.",
        "session_support_fraction": "Support budget used before this decision.",
        "belief_confidence": "Confidence of the Model 1 belief snapshot.",
        "belief_entropy": "Entropy of the Model 1 belief distribution.",
        "belief_abstained": "Whether Model 1 abstained at this decision.",
    }
    return definitions.get(name, "Versioned pre-decision Model 2 feature.")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bounded_hash(value: str) -> float:
    return int.from_bytes(sha256(value.encode()).digest()[:4], "big") / (2**32 - 1)


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Model2Error(f"{label} timestamp must include a UTC offset")
