import re
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid5

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)

FEATURE_DEFINITION_VERSION_V1 = "gamification-features-v1"
FEATURE_DEFINITION_VERSION = "gamification-features-v2"
SUPPORTED_FEATURE_VERSIONS = (FEATURE_DEFINITION_VERSION_V1, FEATURE_DEFINITION_VERSION)
MISCONCEPTION_CATALOGUE_VERSION = "provisional-misconceptions-v1"
SUPPORT_CATALOGUE_VERSION = "provisional-support-v1"
_SNAPSHOT_NAMESPACE = UUID("f551342b-d1ee-4ae1-8c1c-1ee69fd90914")
_SCAFFOLD_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_FORBIDDEN_TOKENS = (
    "verification",
    "post_decision",
    "outcome",
    "independence_gain",
    "future",
    "support_exposure",
    "support_delivery",
)


@dataclass(frozen=True, slots=True)
class DecisionFeatureInput:
    learner_id: UUID
    skill_id: SkillId
    captured_at: datetime
    protocol_version: ProtocolVersion
    skill_taxonomy_version: TaxonomyVersion
    misconception_catalogue_version: str
    support_catalogue_version: str
    current_score: float
    recent_correctness: tuple[bool, ...]
    attempt_count: int
    response_time_ms: int | None = None
    hint_requests: int | None = None
    answer_changes: int | None = None
    skipped: bool | None = None
    structured_error_code: str | None = None
    mastery_probability: float | None = None
    mastery_uncertainty: float | None = None
    learner_support_need: float | None = None
    learner_state_reliability: float | None = None
    prior_beliefs: Mapping[str, float] | None = None
    source_as_of: Mapping[str, datetime] | None = None
    selected_option_id: str | None = None
    distractor_misconception_code: str | None = None
    item_expected_time_ms: int | None = None
    response_time_ratio: float | None = None
    prior_skill_accuracy: float | None = None
    previous_scaffold_types: Mapping[str, int] | None = None
    previous_independence_gains: tuple[float, ...] | None = None
    support_dependency_index: float | None = None
    item_difficulty: int | None = None
    template_key: str | None = None
    prior_belief_age_ms: int | None = None

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must include a UTC offset")
        if not 0 <= self.current_score <= 1:
            raise ValueError("current_score must be between zero and one")
        if self.attempt_count < 1:
            raise ValueError("attempt_count must be positive")
        for name in (
            "mastery_probability",
            "mastery_uncertainty",
            "learner_support_need",
            "learner_state_reliability",
            "prior_skill_accuracy",
            "support_dependency_index",
        ):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.item_expected_time_ms is not None and self.item_expected_time_ms <= 0:
            raise ValueError("item_expected_time_ms must be positive")
        if self.response_time_ms is not None and self.response_time_ms < 0:
            raise ValueError("response_time_ms must be non-negative")
        if self.response_time_ratio is not None and self.response_time_ratio < 0:
            raise ValueError("response_time_ratio must be non-negative")
        if self.prior_belief_age_ms is not None and self.prior_belief_age_ms < 0:
            raise ValueError("prior_belief_age_ms must be non-negative")
        if self.previous_scaffold_types is not None:
            for key, count in self.previous_scaffold_types.items():
                if not _SCAFFOLD_KEY.fullmatch(key) or count < 0:
                    raise ValueError(
                        "scaffold counts need a lowercase key and a non-negative count"
                    )
        if self.previous_independence_gains is not None and any(
            not -1 <= gain <= 1 for gain in self.previous_independence_gains
        ):
            raise ValueError("previous independence gains must be between -1 and 1")
        object.__setattr__(self, "prior_beliefs", MappingProxyType(dict(self.prior_beliefs or {})))
        object.__setattr__(self, "source_as_of", MappingProxyType(dict(self.source_as_of or {})))
        object.__setattr__(
            self,
            "previous_scaffold_types",
            None
            if self.previous_scaffold_types is None
            else MappingProxyType(dict(self.previous_scaffold_types)),
        )


def reject_future_evidence(*, captured_at: datetime, source_as_of: Mapping[str, datetime]) -> None:
    """Reject future or post-decision evidence at the shared feature boundary."""

    for source, observed_at in source_as_of.items():
        normalized = source.lower().replace("-", "_")
        if any(token in normalized for token in _FORBIDDEN_TOKENS):
            raise ValueError(f"post-decision source is forbidden: {source}")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError(f"source timestamp must include a UTC offset: {source}")
        if observed_at > captured_at:
            raise ValueError(f"future evidence is forbidden: {source}")


def _response_time_ratio(data: DecisionFeatureInput) -> float | None:
    if data.response_time_ratio is not None:
        return data.response_time_ratio
    if data.response_time_ms is not None and data.item_expected_time_ms:
        return data.response_time_ms / data.item_expected_time_ms
    return None


class FeatureBuilder:
    """Create immutable pre-decision snapshots with explicit optional missingness.

    Version 2 writes the Model 1 inputs added in correction C2. Version 1 snapshots stay
    readable: every new field is optional, and a missing key means that modality was absent.
    """

    version = FEATURE_DEFINITION_VERSION

    def build(self, data: DecisionFeatureInput) -> FeatureSnapshotRecord:
        reject_future_evidence(captured_at=data.captured_at, source_as_of=data.source_as_of)
        ratio = _response_time_ratio(data)
        gains = data.previous_independence_gains
        optional = {
            "response_time_ms": data.response_time_ms,
            "hint_requests": data.hint_requests,
            "answer_changes": data.answer_changes,
            "skipped": data.skipped,
            "structured_error_code": data.structured_error_code,
            "mastery_probability": data.mastery_probability,
            "mastery_uncertainty": data.mastery_uncertainty,
            "learner_support_need": data.learner_support_need,
            "learner_state_reliability": data.learner_state_reliability,
            "selected_option_id": data.selected_option_id,
            "distractor_misconception_code": data.distractor_misconception_code,
            "item_expected_time_ms": data.item_expected_time_ms,
            "response_time_ratio": ratio,
            "prior_skill_accuracy": data.prior_skill_accuracy,
            "support_dependency_index": data.support_dependency_index,
            "item_difficulty": data.item_difficulty,
            "template_key": data.template_key,
            "prior_belief_age_ms": data.prior_belief_age_ms,
        }
        values: dict[str, float | int | bool | str | None] = {
            "skill_id": str(data.skill_id),
            "skill_taxonomy_version": str(data.skill_taxonomy_version),
            "misconception_catalogue_version": data.misconception_catalogue_version,
            "support_catalogue_version": data.support_catalogue_version,
            "current_score": data.current_score,
            "recent_accuracy": (
                sum(data.recent_correctness) / len(data.recent_correctness)
                if data.recent_correctness
                else None
            ),
            "attempt_count": data.attempt_count,
            **optional,
        }
        missingness = {name: value is None for name, value in optional.items()}
        missingness["recent_correctness"] = not data.recent_correctness
        missingness["prior_beliefs"] = not data.prior_beliefs
        missingness["previous_scaffold_types"] = data.previous_scaffold_types is None
        missingness["previous_independence_gains"] = gains is None
        for code, probability in sorted(data.prior_beliefs.items()):
            if not 0 <= probability <= 1:
                raise ValueError("prior misconception probabilities must be in [0, 1]")
            values[f"prior_belief:{code}"] = probability
        if data.previous_scaffold_types is not None:
            for name, count in sorted(data.previous_scaffold_types.items()):
                values[f"previous_scaffold_count:{name}"] = count
        if gains is not None:
            values["previous_ig_count"] = len(gains)
            if gains:
                values["previous_ig_mean"] = sum(gains) / len(gains)
                values["previous_ig_min"] = min(gains)
                values["previous_ig_max"] = max(gains)
        stable_key = "|".join(
            (str(data.learner_id), str(data.skill_id), data.captured_at.isoformat(), self.version)
        )
        return FeatureSnapshotRecord(
            snapshot_id=FeatureSnapshotId(uuid5(_SNAPSHOT_NAMESPACE, stable_key)),
            learner_id=data.learner_id,
            skill_id=data.skill_id,
            captured_at=data.captured_at,
            protocol_version=data.protocol_version,
            taxonomy_version=data.skill_taxonomy_version,
            feature_definition_version=self.version,
            values=values,
            missingness=missingness,
            source_as_of={
                name: observed_at.isoformat()
                for name, observed_at in sorted(data.source_as_of.items())
            },
            purpose="model_decision",
        )
