"""Probabilistic misconception inference for the draft Sinhala skill.

The implementation is deliberately interpretable and development-only until human review records
authentic approvals.  It never consumes post-inference outcomes or exposes diagnosis data to a
child payload.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Protocol
from uuid import UUID, uuid5

from app.gamification.domain.types import AssistanceState, MeasurementRole
from app.gamification.modeling.shared.artifact_registry import canonical_json

FEATURE_SCHEMA_VERSION = "model1-features-v1"
MODEL1_INTERFACE_VERSION = "model1-inference-interface-v1"
MODEL_VERSION = "model1-authored-bayes-v1"
BASELINE_VERSION = "model1-authored-prior-v1"
CATALOGUE_VERSION = "g5-mat-half-misconceptions-v1"
SKILL_ID = "G5-MAT-C03-L01-O01"
SKILL_VERSION = "g5-mat-c03-l01-o01-v1"
CATALOGUE_CODES = ("whole_set_as_half", "subtracts_two", "unknown_or_other")
NORMALIZATION_TOLERANCE = 1e-12
ABSTAIN_THRESHOLD = 0.60
FEATURE_NAMESPACE = UUID("2427d6df-4b67-4676-9f03-6884dbbea1f0")
BELIEF_NAMESPACE = UUID("b417b12c-ed7a-4723-a05d-d3bfec6b39a0")
FORBIDDEN_FEATURE_TOKENS = (
    "unsupported_after",
    "independence_gain",
    "policy_reward",
    "policy_update",
    "scaffold_selection",
    "support_outcome",
)


class Model1Error(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class InteractionSummary:
    changes: int = 0
    moves: int = 0
    reversals: int = 0
    retries: int = 0

    def __post_init__(self) -> None:
        if any(value < 0 for value in asdict(self).values()):
            raise Model1Error("interaction summaries must be non-negative")


@dataclass(frozen=True, slots=True)
class InferenceEvidence:
    evidence_id: UUID
    event_ids: tuple[UUID, ...]
    attempt_id: UUID
    episode_id: UUID
    presentation_id: UUID
    item_revision_id: str
    content_version: str
    observed_at: datetime
    measurement_role: MeasurementRole
    assistance_state: AssistanceState
    earned_score: float | None
    maximum_score: float | None
    selected_response: str | None
    distractor_misconception_code: str | None
    structured_error_code: str | None
    attempt_number: int
    active_response_ms: int | None
    wall_clock_ms: int | None
    inactivity_ms: int | None
    interactions: InteractionSummary
    quality: str
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise Model1Error("evidence timestamp must include a UTC offset")
        if self.attempt_number < 1:
            raise Model1Error("attempt number must be positive")
        if self.quality not in {"high", "partial", "low", "malformed"}:
            raise Model1Error("unknown evidence quality")
        for value in (self.active_response_ms, self.wall_clock_ms, self.inactivity_ms):
            if value is not None and value < 0:
                raise Model1Error("timing evidence must be non-negative")
        if (self.earned_score is None) != (self.maximum_score is None):
            raise Model1Error("earned and maximum score must be present together")
        if self.maximum_score is not None and (
            not math.isfinite(self.maximum_score)
            or self.maximum_score <= 0
            or self.earned_score is None
            or not math.isfinite(self.earned_score)
            or not 0 <= self.earned_score <= self.maximum_score
        ):
            raise Model1Error("score evidence is malformed")


@dataclass(frozen=True, slots=True)
class OptionalEvidence:
    source: str
    source_version: str
    observed_at: datetime | None
    expires_at: datetime | None
    reliability: float | None
    consent_reference: str | None
    eligible: bool
    missing: bool
    values: Mapping[str, float | int | bool | str | None]

    @classmethod
    def from_ownership_port(cls, value: object) -> OptionalEvidence:
        """Copy an ownership-port envelope without reaching into another subsystem."""

        required = (
            "source",
            "source_version",
            "observed_at",
            "expires_at",
            "reliability",
            "consent_reference",
            "eligible",
            "missing",
            "values",
        )
        if any(not hasattr(value, name) for name in required):
            raise Model1Error("optional evidence does not satisfy the ownership-port envelope")
        payload = {name: getattr(value, name) for name in required}
        payload["values"] = payload["values"] or {}
        return cls(**payload)

    def __post_init__(self) -> None:
        if self.source not in {
            "knowledge_tracing",
            "multimodal_learner_state",
            "prerequisite_skill",
            "accessibility_accommodation",
        }:
            raise Model1Error("optional evidence must use an approved ownership port")
        if self.reliability is not None and (
            not math.isfinite(self.reliability) or not 0 <= self.reliability <= 1
        ):
            raise Model1Error("optional evidence reliability must be in [0, 1]")
        for timestamp in (self.observed_at, self.expires_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise Model1Error("optional evidence timestamps must include a UTC offset")
        if self.missing and (self.observed_at is not None or self.values):
            raise Model1Error("missing optional evidence cannot contain observations")
        if not self.missing and (
            self.observed_at is None
            or self.reliability is None
            or not self.source_version
            or not self.consent_reference
        ):
            raise Model1Error("available optional evidence needs provenance and consent")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class Model1InferenceInput:
    learner_id: UUID
    pseudonymous: bool
    grade: int
    medium: str
    skill_id: str
    skill_version: str
    episode_id: UUID
    presentation_id: UUID
    item_revision_id: str
    inference_at: datetime
    evidence_window_version: str
    evidence: tuple[InferenceEvidence, ...]
    recent_same_skill_errors: tuple[str, ...]
    recent_error_evidence_ids: tuple[UUID, ...]
    recent_errors_as_of: datetime | None
    previous_beliefs: Mapping[str, float]
    previous_belief_snapshot_id: UUID | None
    previous_belief_at: datetime | None
    optional_evidence: tuple[OptionalEvidence, ...]
    mapping_version: str
    model_version: str
    development_mode: bool

    def __post_init__(self) -> None:
        if not self.pseudonymous:
            raise Model1Error("Model 1 accepts pseudonymous learners only")
        if self.grade != 5:
            raise Model1Error("Model 1 is restricted to Grade 5")
        if self.medium != "si":
            raise Model1Error("Model 1 is restricted to Sinhala medium")
        if self.skill_id != SKILL_ID or self.skill_version != SKILL_VERSION:
            raise Model1Error("skill/version is outside the Model 1 slice")
        if not self.development_mode:
            raise PermissionError("draft catalogue requires development_mode=True")
        if self.inference_at.tzinfo is None or self.inference_at.utcoffset() is None:
            raise Model1Error("inference timestamp must include a UTC offset")
        if self.recent_same_skill_errors:
            if (
                self.recent_errors_as_of is None
                or len(self.recent_error_evidence_ids) != len(self.recent_same_skill_errors)
            ):
                raise Model1Error("recent errors require timestamped evidence provenance")
        elif self.recent_errors_as_of is not None or self.recent_error_evidence_ids:
            raise Model1Error("recent-error provenance cannot exist without recent errors")
        if self.previous_beliefs:
            if self.previous_belief_snapshot_id is None or self.previous_belief_at is None:
                raise Model1Error("previous beliefs require timestamped snapshot provenance")
        elif self.previous_belief_snapshot_id is not None or self.previous_belief_at is not None:
            raise Model1Error("previous-belief provenance cannot exist without beliefs")
        for timestamp in (self.recent_errors_as_of, self.previous_belief_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise Model1Error("summary provenance timestamps must include a UTC offset")
        object.__setattr__(self, "previous_beliefs", MappingProxyType(dict(self.previous_beliefs)))


@dataclass(frozen=True, slots=True)
class Model1FeatureSnapshot:
    snapshot_id: UUID
    learner_id: UUID
    skill_id: str
    skill_version: str
    episode_id: UUID
    presentation_id: UUID
    item_revision_id: str
    inference_at: datetime
    evidence_window_version: str
    feature_schema_version: str
    mapping_version: str
    model_version: str
    values: Mapping[str, float | int | bool | str | None]
    missingness: Mapping[str, bool]
    optional_freshness: Mapping[str, str]
    evidence_ids: tuple[UUID, ...]
    evidence_event_ids: tuple[UUID, ...]
    attempt_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "missingness", MappingProxyType(dict(self.missingness)))
        object.__setattr__(
            self, "optional_freshness", MappingProxyType(dict(self.optional_freshness))
        )


class Model1FeatureBuilder:
    version = FEATURE_SCHEMA_VERSION

    def build(self, data: Model1InferenceInput) -> Model1FeatureSnapshot:
        if data.mapping_version != CATALOGUE_VERSION:
            raise Model1Error("misconception mapping version mismatch")
        if data.model_version != MODEL_VERSION:
            raise Model1Error("model version mismatch")
        usable: list[InferenceEvidence] = []
        for row in data.evidence:
            if row.episode_id != data.episode_id or row.presentation_id != data.presentation_id:
                raise Model1Error("evidence identity does not match inference unit")
            if row.item_revision_id != data.item_revision_id:
                raise Model1Error("item revision mismatch")
            if row.observed_at > data.inference_at:
                raise Model1Error("future evidence is forbidden")
            if row.measurement_role is MeasurementRole.UNSUPPORTED_AFTER:
                raise Model1Error("current-episode unsupported_after evidence is forbidden")
            usable.append(row)
        for name in (*data.recent_same_skill_errors, *data.previous_beliefs):
            if any(token in name.lower() for token in FORBIDDEN_FEATURE_TOKENS):
                raise Model1Error("post-decision evidence is forbidden")
        if set(data.previous_beliefs) - set(CATALOGUE_CODES):
            raise Model1Error("previous belief contains a label outside the catalogue")
        if data.previous_beliefs:
            total = sum(data.previous_beliefs.values())
            if (
                any(not math.isfinite(value) or value < 0 for value in data.previous_beliefs.values())
                or abs(total - 1) > NORMALIZATION_TOLERANCE
            ):
                raise Model1Error("previous beliefs must be a normalized finite distribution")
        if data.recent_errors_as_of is not None and data.recent_errors_as_of > data.inference_at:
            raise Model1Error("future recent-error evidence is forbidden")
        if data.previous_belief_at is not None and data.previous_belief_at > data.inference_at:
            raise Model1Error("future previous-belief evidence is forbidden")

        latest = max(usable, key=lambda row: row.observed_at) if usable else None
        optional_freshness: dict[str, str] = {}
        optional_values: dict[str, float | int | bool | str | None] = {}
        for row in data.optional_evidence:
            if row.missing:
                optional_freshness[row.source] = "missing"
                continue
            if not row.eligible or not row.consent_reference:
                optional_freshness[row.source] = "ineligible"
                continue
            if row.observed_at is not None and row.observed_at > data.inference_at:
                raise Model1Error("future optional evidence is forbidden")
            if row.expires_at is not None and row.expires_at <= data.inference_at:
                optional_freshness[row.source] = "stale"
                continue
            optional_freshness[row.source] = "fresh"
            optional_values[f"optional:{row.source}:reliability"] = row.reliability
            for key, value in sorted(row.values.items()):
                if any(token in key.lower() for token in FORBIDDEN_FEATURE_TOKENS):
                    raise Model1Error("post-decision optional evidence is forbidden")
                optional_values[f"optional:{row.source}:{key}"] = value

        score_ratio = (
            latest.earned_score / latest.maximum_score
            if latest is not None
            and latest.earned_score is not None
            and latest.maximum_score is not None
            else None
        )
        interaction_total = (
            sum(asdict(latest.interactions).values()) if latest is not None else 0
        )
        values: dict[str, float | int | bool | str | None] = {
            "grade": data.grade,
            "medium": data.medium,
            "item_revision_id": data.item_revision_id,
            "content_version": latest.content_version if latest else None,
            "measurement_role": latest.measurement_role.value if latest else None,
            "assistance_state": latest.assistance_state.value if latest else None,
            "score_ratio": score_ratio,
            "selected_response": latest.selected_response if latest else None,
            "distractor_misconception_code": (
                latest.distractor_misconception_code if latest else None
            ),
            "structured_error_code": latest.structured_error_code if latest else None,
            "attempt_number": latest.attempt_number if latest else None,
            "active_response_ms": latest.active_response_ms if latest else None,
            "wall_clock_ms": latest.wall_clock_ms if latest else None,
            "inactivity_ms": latest.inactivity_ms if latest else None,
            "interaction_changes": latest.interactions.changes if latest else None,
            "interaction_moves": latest.interactions.moves if latest else None,
            "interaction_reversals": latest.interactions.reversals if latest else None,
            "interaction_retries": latest.interactions.retries if latest else None,
            "interaction_change_ratio": (
                latest.interactions.changes / interaction_total
                if latest is not None and interaction_total
                else None
            ),
            "interaction_move_ratio": (
                latest.interactions.moves / interaction_total
                if latest is not None and interaction_total
                else None
            ),
            "interaction_reversal_ratio": (
                latest.interactions.reversals / interaction_total
                if latest is not None and interaction_total
                else None
            ),
            "interaction_retry_ratio": (
                latest.interactions.retries / interaction_total
                if latest is not None and interaction_total
                else None
            ),
            "recent_error_count": len(data.recent_same_skill_errors),
            "recent_errors_as_of": (
                data.recent_errors_as_of.isoformat() if data.recent_errors_as_of else None
            ),
            "previous_belief_snapshot_id": (
                str(data.previous_belief_snapshot_id)
                if data.previous_belief_snapshot_id
                else None
            ),
            "previous_belief_at": (
                data.previous_belief_at.isoformat() if data.previous_belief_at else None
            ),
            "evidence_count": len(usable),
            "evidence_quality": latest.quality if latest else "low",
            **optional_values,
        }
        for code in CATALOGUE_CODES:
            values[f"previous_belief:{code}"] = data.previous_beliefs.get(code)
            values[f"recent_error_count:{code}"] = sum(
                (error if error in CATALOGUE_CODES else "unknown_or_other") == code
                for error in data.recent_same_skill_errors
            )
        missingness = {key: value is None for key, value in values.items()}
        for source in (
            "knowledge_tracing",
            "multimodal_learner_state",
            "prerequisite_skill",
            "accessibility_accommodation",
        ):
            missingness[f"optional:{source}"] = optional_freshness.get(source, "missing") != "fresh"
        stable = "|".join(
            (
                str(data.learner_id),
                str(data.episode_id),
                str(data.presentation_id),
                data.item_revision_id,
                data.inference_at.isoformat(),
                self.version,
                data.mapping_version,
                data.model_version,
                *(str(value) for value in data.recent_error_evidence_ids),
                str(data.previous_belief_snapshot_id or ""),
                *(str(row.evidence_id) for row in usable),
            )
        )
        return Model1FeatureSnapshot(
            snapshot_id=uuid5(FEATURE_NAMESPACE, stable),
            learner_id=data.learner_id,
            skill_id=data.skill_id,
            skill_version=data.skill_version,
            episode_id=data.episode_id,
            presentation_id=data.presentation_id,
            item_revision_id=data.item_revision_id,
            inference_at=data.inference_at,
            evidence_window_version=data.evidence_window_version,
            feature_schema_version=self.version,
            mapping_version=data.mapping_version,
            model_version=data.model_version,
            values=values,
            missingness=missingness,
            optional_freshness=optional_freshness,
            evidence_ids=tuple(row.evidence_id for row in usable)
            + data.recent_error_evidence_ids,
            evidence_event_ids=tuple(event for row in usable for event in row.event_ids),
            attempt_ids=tuple(row.attempt_id for row in usable),
        )


@dataclass(frozen=True, slots=True)
class BeliefSnapshot:
    belief_snapshot_id: UUID
    feature_snapshot_id: UUID
    learner_id: UUID
    skill_id: str
    skill_version: str
    episode_id: UUID
    presentation_id: UUID
    item_revision_id: str
    probabilities: Mapping[str, float]
    top_hypothesis: str
    confidence: float
    entropy: float
    abstained: bool
    low_confidence: bool
    narrow_exploitation_allowed: bool
    reason_codes: tuple[str, ...]
    evidence_event_ids: tuple[UUID, ...]
    attempt_ids: tuple[UUID, ...]
    feature_schema_version: str
    mapping_version: str
    model_version: str
    artifact_sha256: str
    inference_at: datetime
    optional_freshness: Mapping[str, str]

    def __post_init__(self) -> None:
        values = dict(self.probabilities)
        if set(values) != set(CATALOGUE_CODES):
            raise Model1Error("belief must represent every catalogue state exactly once")
        if any(not math.isfinite(value) or value < 0 for value in values.values()):
            raise Model1Error("belief probabilities must be finite and non-negative")
        if abs(sum(values.values()) - 1) > NORMALIZATION_TOLERANCE:
            raise Model1Error("belief probabilities must normalize to one")
        object.__setattr__(self, "probabilities", MappingProxyType(values))
        object.__setattr__(
            self, "optional_freshness", MappingProxyType(dict(self.optional_freshness))
        )

    def child_payload(self) -> Mapping[str, str]:
        """Technical labels and probabilities are intentionally absent."""

        return MappingProxyType(
            {
                "message_si": "අපි වෙනත් ආකාරයකින් උත්සාහ කරමු.",
                "next_step": "neutral_support_or_more_evidence",
            }
        )


class Model1Predictor(Protocol):
    """Versioned boundary implemented by Model 1 inference candidates."""

    version: str

    def predict(self, snapshot: Model1FeatureSnapshot) -> BeliefSnapshot: ...


class AuthoredPriorBaseline:
    version = BASELINE_VERSION

    def predict(self, snapshot: Model1FeatureSnapshot, *, artifact_sha256: str) -> BeliefSnapshot:
        return _belief(
            snapshot,
            {"whole_set_as_half": 0.25, "subtracts_two": 0.25, "unknown_or_other": 0.50},
            model_version=self.version,
            artifact_sha256=artifact_sha256,
            reasons=("AUTHORED_PRIOR_BASELINE", "DEVELOPMENT_ONLY"),
        )


class InterpretableBayesianCandidate:
    """Authored-prior categorical Bayes candidate; weights are provisional, not fitted claims."""

    version = MODEL_VERSION

    def __init__(
        self,
        *,
        artifact_sha256: str,
        mapping_version: str = CATALOGUE_VERSION,
        parameters: Mapping[str, object] | None = None,
    ) -> None:
        self.artifact_sha256 = artifact_sha256
        self.mapping_version = mapping_version
        self.parameters = MappingProxyType(dict(parameters or {}))

    def predict(self, snapshot: Model1FeatureSnapshot) -> BeliefSnapshot:
        if snapshot.mapping_version != self.mapping_version:
            return _fallback(snapshot, self.artifact_sha256, "CATALOGUE_VERSION_MISMATCH")
        quality = snapshot.values.get("evidence_quality")
        if not snapshot.evidence_ids or quality in {"low", "malformed"}:
            return _fallback(snapshot, self.artifact_sha256, "INSUFFICIENT_OR_LOW_QUALITY_EVIDENCE")
        prior = _prior(snapshot, self.parameters.get("class_prior"))
        likelihood = dict.fromkeys(CATALOGUE_CODES, 1.0)
        distractor = snapshot.values.get("distractor_misconception_code")
        error = snapshot.values.get("structured_error_code")
        supported_codes = {
            value for value in (distractor, error) if isinstance(value, str) and value in CATALOGUE_CODES
        }
        reasons: list[str] = ["PROVISIONAL_AUTHORED_LIKELIHOODS", "DEVELOPMENT_ONLY"]
        if len(supported_codes) > 1:
            likelihood["unknown_or_other"] *= 4.0
            reasons.append("CONTRADICTORY_EVIDENCE")
        elif supported_codes:
            code = next(iter(supported_codes))
            fitted = self.parameters.get("error_likelihoods")
            fitted_row = fitted.get(code) if isinstance(fitted, Mapping) else None
            if isinstance(fitted_row, Mapping) and set(fitted_row) == set(CATALOGUE_CODES):
                likelihood = {label: float(fitted_row[label]) for label in CATALOGUE_CODES}
                reasons.append("FITTED_PATTERN_SUPPORT")
            else:
                likelihood[code] *= 3.0
                likelihood["unknown_or_other"] *= 1.5
                reasons.append("AUTHORED_PATTERN_SUPPORT")
        else:
            likelihood["unknown_or_other"] *= 3.0
            reasons.append("UNMAPPED_OR_SPARSE_EVIDENCE")
        if snapshot.values.get("assistance_state") != AssistanceState.NONE.value:
            likelihood["unknown_or_other"] *= 2.0
            reasons.append("ASSISTED_EVIDENCE_PRESERVED")
        unnormalized = {code: prior[code] * likelihood[code] for code in CATALOGUE_CODES}
        return _belief(
            snapshot,
            _normalize(unnormalized),
            model_version=self.version,
            artifact_sha256=self.artifact_sha256,
            reasons=tuple(reasons),
        )


def development_curriculum_candidate(
    *, artifact_sha256: str, allow_draft: bool = False
) -> InterpretableBayesianCandidate:
    if not allow_draft:
        raise PermissionError("draft misconceptions require allow_draft=True")
    from app.gamification.content.curriculum_registry import load_curriculum_public_package

    package = load_curriculum_public_package(allow_draft=True)
    codes = tuple(row.misconception_id for row in package.misconceptions)
    versions = {row.mapping_version for row in package.misconceptions}
    if set(codes) != set(CATALOGUE_CODES) or versions != {CATALOGUE_VERSION}:
        raise Model1Error("catalogue/mapping no longer matches Model 1")
    return InterpretableBayesianCandidate(artifact_sha256=artifact_sha256)


@dataclass(frozen=True, slots=True)
class Model1DatasetRow:
    learner_id: str
    skill_id: str
    label: str
    score_ratio: float
    structured_error_code: str | None
    probabilities: Mapping[str, float]
    abstained: bool


@dataclass(frozen=True, slots=True)
class Model1DatasetManifest:
    dataset_id: str
    schema_version: str
    source_sha256: str
    split_seed: int
    learner_splits: Mapping[str, tuple[str, ...]]
    synthetic: bool
    authorized_expert_labels: bool
    catalogue_version: str

    @classmethod
    def build(
        cls,
        rows: Sequence[Model1DatasetRow],
        *,
        dataset_id: str,
        split_seed: int,
        synthetic: bool,
        authorized_expert_labels: bool,
    ) -> Model1DatasetManifest:
        if not synthetic and not authorized_expert_labels:
            raise PermissionError("non-synthetic labels require authorization")
        learners = sorted(
            {row.learner_id for row in rows},
            key=lambda value: sha256(f"{split_seed}:{value}".encode()).hexdigest(),
        )
        train_end = math.ceil(len(learners) * 0.6)
        validation_end = train_end + math.floor(len(learners) * 0.2)
        splits = {
            "train": tuple(learners[:train_end]),
            "validation": tuple(learners[train_end:validation_end]),
            "test": tuple(learners[validation_end:]),
        }
        manifest = cls(
            dataset_id=dataset_id,
            schema_version="model1-dataset-v1",
            source_sha256=sha256(canonical_json([asdict(row) for row in rows])).hexdigest(),
            split_seed=split_seed,
            learner_splits=MappingProxyType(splits),
            synthetic=synthetic,
            authorized_expert_labels=authorized_expert_labels,
            catalogue_version=CATALOGUE_VERSION,
        )
        manifest.assert_disjoint()
        return manifest

    def assert_disjoint(self) -> None:
        groups = [set(group) for group in self.learner_splits.values()]
        if any(left & right for index, left in enumerate(groups) for right in groups[index + 1 :]):
            raise Model1Error("learner splits overlap")

    @property
    def digest(self) -> str:
        payload = {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "source_sha256": self.source_sha256,
            "split_seed": self.split_seed,
            "learner_splits": dict(self.learner_splits),
            "synthetic": self.synthetic,
            "authorized_expert_labels": self.authorized_expert_labels,
            "catalogue_version": self.catalogue_version,
        }
        return sha256(canonical_json(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class Model1Artifact:
    model_version: str
    feature_schema_version: str
    mapping_version: str
    dataset_manifest_sha256: str
    seed: int
    parameters: Mapping[str, object]
    evidence_status: str
    lifecycle_status: str
    artifact_sha256: str

    @classmethod
    def create(
        cls, manifest: Model1DatasetManifest, *, seed: int, parameters: Mapping[str, object]
    ) -> Model1Artifact:
        payload = {
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "mapping_version": CATALOGUE_VERSION,
            "dataset_manifest_sha256": manifest.digest,
            "seed": seed,
            "parameters": dict(parameters),
            "evidence_status": (
                "authorized_expert_labelled" if manifest.authorized_expert_labels else "synthetic_development"
            ),
            "lifecycle_status": "draft_shadow",
        }
        return cls(**payload, artifact_sha256=sha256(canonical_json(payload)).hexdigest())

    def verify(self) -> None:
        payload = asdict(self)
        claimed = payload.pop("artifact_sha256")
        if sha256(canonical_json(payload)).hexdigest() != claimed:
            raise Model1Error("artifact hash mismatch")

    def model_card(self) -> str:
        return "\n".join(
            (
                f"# Model 1 card: {self.model_version}",
                "",
                f"- Artifact: `{self.artifact_sha256}`",
                f"- Dataset manifest: `{self.dataset_manifest_sha256}`",
                f"- Evidence status: {self.evidence_status}",
                "- Lifecycle: draft/shadow; not approved for child use",
                "- Candidate: interpretable authored categorical Bayes",
                "- Limitation: calibration and diagnostic validity require authorized expert labels",
            )
        )


def fit_model1_candidate(
    rows: Sequence[Model1DatasetRow], manifest: Model1DatasetManifest, *, seed: int
) -> Model1Artifact:
    """Fit transparent counts on the frozen learner-disjoint training split only."""

    manifest.assert_disjoint()
    expected_source = sha256(canonical_json([asdict(row) for row in rows])).hexdigest()
    if expected_source != manifest.source_sha256:
        raise Model1Error("dataset rows do not match the frozen manifest")
    train_learners = set(manifest.learner_splits["train"])
    train = [row for row in rows if row.learner_id in train_learners]
    if not train:
        raise Model1Error("training split is empty")
    if any(row.label not in CATALOGUE_CODES for row in train):
        raise Model1Error("training label is outside the versioned catalogue")
    label_counts = Counter(row.label for row in train)
    denominator = len(train) + len(CATALOGUE_CODES)
    prior = {code: (label_counts[code] + 1) / denominator for code in CATALOGUE_CODES}
    likelihoods: dict[str, dict[str, float]] = {}
    for error_code in CATALOGUE_CODES:
        matching = [row for row in train if row.structured_error_code == error_code]
        counts = Counter(row.label for row in matching)
        total = len(matching) + len(CATALOGUE_CODES)
        likelihoods[error_code] = {
            code: (counts[code] + 1) / total for code in CATALOGUE_CODES
        }
    return Model1Artifact.create(
        manifest,
        seed=seed,
        parameters={
            "fit_method": "laplace_categorical_counts_v1",
            "training_learner_count": len(train_learners),
            "training_row_count": len(train),
            "class_prior": prior,
            "error_likelihoods": likelihoods,
        },
    )


def candidate_from_artifact(
    artifact: Model1Artifact, *, allow_draft: bool = False
) -> InterpretableBayesianCandidate:
    if not allow_draft:
        raise PermissionError("draft Model 1 artifacts require allow_draft=True")
    artifact.verify()
    if (
        artifact.model_version != MODEL_VERSION
        or artifact.feature_schema_version != FEATURE_SCHEMA_VERSION
        or artifact.mapping_version != CATALOGUE_VERSION
        or artifact.lifecycle_status != "draft_shadow"
    ):
        raise Model1Error("artifact versions or lifecycle do not match Model 1")
    return InterpretableBayesianCandidate(
        artifact_sha256=artifact.artifact_sha256,
        mapping_version=artifact.mapping_version,
        parameters=artifact.parameters,
    )


class Model1ArtifactRegistry:
    def __init__(self) -> None:
        self._artifacts: dict[str, Model1Artifact] = {}
        self._active_shadow: str | None = None

    def register(self, artifact: Model1Artifact) -> None:
        artifact.verify()
        self._artifacts[artifact.artifact_sha256] = artifact

    def activate_shadow(self, artifact_sha256: str) -> None:
        artifact = self._artifacts[artifact_sha256]
        if artifact.lifecycle_status != "draft_shadow":
            raise Model1Error("unsupported artifact lifecycle")
        self._active_shadow = artifact_sha256

    def activate_for_child_delivery(self, artifact_sha256: str) -> None:
        del artifact_sha256
        raise PermissionError("human approval and release composition are required")

    def rollback_shadow(self, artifact_sha256: str) -> None:
        if artifact_sha256 not in self._artifacts:
            raise LookupError("rollback artifact is not registered")
        self._active_shadow = artifact_sha256

    @property
    def active_shadow(self) -> Model1Artifact | None:
        return self._artifacts.get(self._active_shadow) if self._active_shadow else None


@dataclass(frozen=True, slots=True)
class Model1Evaluation:
    evidence_status: str
    sample_count: int
    log_loss: float
    brier_score: float
    calibration_error: float
    reliability_bins: Mapping[str, Mapping[str, float | int]]
    top_k_agreement: float
    per_class_recall: Mapping[str, float]
    confusion_matrix: Mapping[str, Mapping[str, int]]
    results_by_skill: Mapping[str, Mapping[str, float | int | str]]
    unknown_recall: float
    abstention_coverage: float
    agreement_when_not_abstained: float
    baselines: Mapping[str, float]
    reviewer_agreement: float | None
    adjudication_evidence_present: bool


def evaluate_model1(
    rows: Sequence[Model1DatasetRow],
    *,
    authorized_expert_labels: bool,
    reviewer_agreement: float | None = None,
    adjudication_evidence_present: bool = False,
) -> Model1Evaluation:
    if not rows:
        raise Model1Error("evaluation requires labelled rows")
    if any(row.label not in CATALOGUE_CODES for row in rows):
        raise Model1Error("evaluation label is outside the versioned catalogue")
    if authorized_expert_labels and (
        reviewer_agreement is None or not adjudication_evidence_present
    ):
        raise Model1Error("authorized labels require reviewer agreement and adjudication evidence")
    if reviewer_agreement is not None and not 0 <= reviewer_agreement <= 1:
        raise Model1Error("reviewer agreement must be in [0, 1]")
    if authorized_expert_labels:
        evidence_status = "authorized_expert_labelled"
    else:
        evidence_status = "synthetic_development_only"
    log_loss = 0.0
    brier = 0.0
    hits = 0
    answered_hits = 0
    answered = 0
    labels = [row.label for row in rows]
    predictions: list[str] = []
    confidences: list[float] = []
    for row in rows:
        _validate_probabilities(row.probabilities)
        prediction = min(row.probabilities, key=lambda code: (-row.probabilities[code], code))
        predictions.append(prediction)
        confidences.append(row.probabilities[prediction])
        hits += row.label in sorted(row.probabilities, key=row.probabilities.get, reverse=True)[:2]
        if not row.abstained:
            answered += 1
            answered_hits += prediction == row.label
        log_loss -= math.log(max(row.probabilities.get(row.label, 0.0), 1e-15))
        brier += sum(
            (probability - (1.0 if code == row.label else 0.0)) ** 2
            for code, probability in row.probabilities.items()
        )
    counts = Counter(labels)
    recalls = {
        code: sum(label == code and prediction == code for label, prediction in zip(labels, predictions))
        / count
        for code, count in sorted(counts.items())
    }
    by_skill = Counter(labels).most_common(1)[0][0]
    authored = [
        row.structured_error_code if row.structured_error_code in CATALOGUE_CODES else "unknown_or_other"
        for row in rows
    ]
    performance = ["unknown_or_other" if row.score_ratio == 1 else by_skill for row in rows]
    confusion = {
        actual: {
            predicted: sum(
                left == actual and right == predicted
                for left, right in zip(labels, predictions, strict=True)
            )
            for predicted in CATALOGUE_CODES
        }
        for actual in CATALOGUE_CODES
    }
    reliability: dict[str, Mapping[str, float | int]] = {}
    calibration_error = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        upper = lower + 0.2
        indexes = [
            index
            for index, confidence in enumerate(confidences)
            if lower <= confidence < upper or (upper == 1.0 and confidence == 1.0)
        ]
        if not indexes:
            continue
        mean_confidence = sum(confidences[index] for index in indexes) / len(indexes)
        accuracy = sum(predictions[index] == labels[index] for index in indexes) / len(indexes)
        calibration_error += len(indexes) / len(rows) * abs(mean_confidence - accuracy)
        reliability[f"{lower:.1f}-{upper:.1f}"] = MappingProxyType(
            {"count": len(indexes), "mean_confidence": mean_confidence, "accuracy": accuracy}
        )
    skill_results = {
        skill_id: MappingProxyType(
            {
                "sample_count": len(indexes),
                "top_1_agreement": sum(predictions[index] == labels[index] for index in indexes)
                / len(indexes),
                "approval_status": evidence_status,
            }
        )
        for skill_id in sorted({row.skill_id for row in rows})
        if (indexes := [index for index, row in enumerate(rows) if row.skill_id == skill_id])
    }
    return Model1Evaluation(
        evidence_status=evidence_status,
        sample_count=len(rows),
        log_loss=log_loss / len(rows),
        brier_score=brier / len(rows),
        calibration_error=calibration_error,
        reliability_bins=MappingProxyType(reliability),
        top_k_agreement=hits / len(rows),
        per_class_recall=MappingProxyType(recalls),
        confusion_matrix=MappingProxyType(
            {key: MappingProxyType(value) for key, value in confusion.items()}
        ),
        results_by_skill=MappingProxyType(skill_results),
        unknown_recall=recalls.get("unknown_or_other", 0.0),
        abstention_coverage=sum(row.abstained for row in rows) / len(rows),
        agreement_when_not_abstained=answered_hits / answered if answered else 0.0,
        baselines=MappingProxyType(
            {
                "most_frequent_per_skill": _accuracy(labels, [by_skill] * len(rows)),
                "deterministic_authored_error_mapping": _accuracy(labels, authored),
                "performance_only": _accuracy(labels, performance),
            }
        ),
        reviewer_agreement=reviewer_agreement,
        adjudication_evidence_present=adjudication_evidence_present,
    )


def replay_inference(
    data: Model1InferenceInput, model: Model1Predictor
) -> tuple[Model1FeatureSnapshot, BeliefSnapshot]:
    snapshot = Model1FeatureBuilder().build(data)
    return snapshot, model.predict(snapshot)


def _prior(snapshot: Model1FeatureSnapshot, fitted: object = None) -> dict[str, float]:
    values = {
        code: snapshot.values.get(f"previous_belief:{code}") for code in CATALOGUE_CODES
    }
    if all(isinstance(value, (int, float)) for value in values.values()):
        return _normalize({code: float(value) for code, value in values.items()})
    if isinstance(fitted, Mapping) and set(fitted) == set(CATALOGUE_CODES):
        return _normalize({code: float(fitted[code]) for code in CATALOGUE_CODES})
    return {"whole_set_as_half": 0.25, "subtracts_two": 0.25, "unknown_or_other": 0.50}


def _fallback(
    snapshot: Model1FeatureSnapshot, artifact_sha256: str, reason: str
) -> BeliefSnapshot:
    return _belief(
        snapshot,
        {"whole_set_as_half": 0.10, "subtracts_two": 0.10, "unknown_or_other": 0.80},
        model_version=MODEL_VERSION,
        artifact_sha256=artifact_sha256,
        reasons=(reason, "SAFE_UNKNOWN_FALLBACK", "DEVELOPMENT_ONLY"),
    )


def _belief(
    snapshot: Model1FeatureSnapshot,
    probabilities: Mapping[str, float],
    *,
    model_version: str,
    artifact_sha256: str,
    reasons: tuple[str, ...],
) -> BeliefSnapshot:
    normalized = _normalize(probabilities)
    top = min(normalized, key=lambda code: (-normalized[code], code))
    confidence = normalized[top]
    abstained = confidence < ABSTAIN_THRESHOLD or top == "unknown_or_other"
    stable = f"{snapshot.snapshot_id}|{model_version}|{artifact_sha256}"
    return BeliefSnapshot(
        belief_snapshot_id=uuid5(BELIEF_NAMESPACE, stable),
        feature_snapshot_id=snapshot.snapshot_id,
        learner_id=snapshot.learner_id,
        skill_id=snapshot.skill_id,
        skill_version=snapshot.skill_version,
        episode_id=snapshot.episode_id,
        presentation_id=snapshot.presentation_id,
        item_revision_id=snapshot.item_revision_id,
        probabilities=normalized,
        top_hypothesis=top,
        confidence=confidence,
        entropy=-sum(value * math.log(value) for value in normalized.values() if value),
        abstained=abstained,
        low_confidence=abstained,
        narrow_exploitation_allowed=not abstained,
        reason_codes=reasons + (("ABSTAIN_LOW_CONFIDENCE",) if abstained else ()),
        evidence_event_ids=snapshot.evidence_event_ids,
        attempt_ids=snapshot.attempt_ids,
        feature_schema_version=snapshot.feature_schema_version,
        mapping_version=snapshot.mapping_version,
        model_version=model_version,
        artifact_sha256=artifact_sha256,
        inference_at=snapshot.inference_at,
        optional_freshness=snapshot.optional_freshness,
    )


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    complete = {code: float(values.get(code, 0.0)) for code in CATALOGUE_CODES}
    if any(not math.isfinite(value) or value < 0 for value in complete.values()):
        raise Model1Error("probability weight must be finite and non-negative")
    total = sum(complete.values())
    if total <= 0:
        raise Model1Error("probability weights cannot all be zero")
    return {code: complete[code] / total for code in CATALOGUE_CODES}


def _validate_probabilities(values: Mapping[str, float]) -> None:
    BeliefSnapshot(
        belief_snapshot_id=UUID(int=0),
        feature_snapshot_id=UUID(int=0),
        learner_id=UUID(int=0),
        skill_id=SKILL_ID,
        skill_version=SKILL_VERSION,
        episode_id=UUID(int=0),
        presentation_id=UUID(int=0),
        item_revision_id="validation-only",
        probabilities=values,
        top_hypothesis="unknown_or_other",
        confidence=max(values.values()),
        entropy=0,
        abstained=True,
        low_confidence=True,
        narrow_exploitation_allowed=False,
        reason_codes=("VALIDATION_ONLY",),
        evidence_event_ids=(),
        attempt_ids=(),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        mapping_version=CATALOGUE_VERSION,
        model_version=MODEL_VERSION,
        artifact_sha256="0" * 64,
        inference_at=datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo),
        optional_freshness={},
    )


def _accuracy(labels: Sequence[str], predictions: Sequence[str]) -> float:
    return sum(left == right for left, right in zip(labels, predictions)) / len(labels)
