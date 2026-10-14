"""Versioned numeric context for the support-selection bandit.

The vector order is part of ``bandit-context-v1``. A null mastery gateway stands in until
C5 supplies Knowledge Tracing evidence for the Universal parent skill. This module does
not import Knowledge Tracing.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol
from uuid import UUID, uuid5

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.domain.types import FeatureSnapshotId, SupportActionType
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

CONTEXT_VERSION = "bandit-context-v1"
TEMPLATE_BINS = 4
_SNAPSHOT_NAMESPACE = UUID("c4a11c04-4b21-4c4a-8f4e-0b1c4d4e4f40")
HISTORY_TYPES = tuple(action.value for action in SupportActionType)
PILOT_RESPONSE_FORMATS = ("single_choice", "binary_sort", "numeric_construction")


class MasteryEvidenceGateway(Protocol):
    """C5 supplies parent-skill mastery. Until then a null gateway reports missingness."""

    def parent_skill_mastery(self, *, learner_id: UUID, skill_id: str) -> float | None: ...


class NullMasteryGateway:
    def parent_skill_mastery(self, *, learner_id: UUID, skill_id: str) -> float | None:
        return None


@dataclass(frozen=True, slots=True)
class QuestionContext:
    skill_id: str
    difficulty: int | None
    response_format: str | None
    template_key: str | None


@dataclass(frozen=True, slots=True)
class SupportHistory:
    mean_valid_ig: Mapping[str, float] = field(default_factory=dict)
    counts: Mapping[str, int] = field(default_factory=dict)
    support_dependency_index: float | None = None

    @classmethod
    def from_snapshot(cls, snapshot: FeatureSnapshotRecord) -> "SupportHistory":
        counts: dict[str, int] = {}
        prefix = "previous_scaffold_count:"
        for key, value in snapshot.values.items():
            number = _number(value)
            if key.startswith(prefix) and number is not None:
                counts[key.removeprefix(prefix)] = int(number)
        dependency = _number(snapshot.values.get("support_dependency_index"))
        return cls(counts=counts, support_dependency_index=dependency)


@dataclass(frozen=True, slots=True)
class BanditContext:
    version: str
    names: tuple[str, ...]
    values: tuple[float, ...]
    missingness: Mapping[str, bool]

    def __post_init__(self) -> None:
        if len(self.names) != len(self.values):
            raise ValueError("context names and values must have the same length")
        if self.version != CONTEXT_VERSION:
            raise ValueError("unsupported bandit context version")

    def without_belief_block(self) -> "BanditContext":
        """Zero misconception probabilities. Used only by the synthetic ablation."""

        values = tuple(
            0.0 if name.startswith("belief:") else value
            for name, value in zip(self.names, self.values, strict=True)
        )
        return BanditContext(self.version, self.names, values, self.missingness)

    def to_feature_values(self) -> dict[str, str]:
        payload = {
            "version": self.version,
            "names": list(self.names),
            "values": list(self.values),
        }
        return {
            "bandit_context_version": self.version,
            "bandit_context": json.dumps(payload, separators=(",", ":")),
        }


def policy_context_snapshot(
    base: FeatureSnapshotRecord, context: BanditContext
) -> FeatureSnapshotRecord:
    """A second snapshot so the decision can be rebuilt without nesting feature values."""

    key = f"{base.snapshot_id}|{context.version}|policy_context"
    return FeatureSnapshotRecord(
        snapshot_id=FeatureSnapshotId(uuid5(_SNAPSHOT_NAMESPACE, key)),
        learner_id=base.learner_id,
        skill_id=base.skill_id,
        captured_at=base.captured_at,
        protocol_version=base.protocol_version,
        taxonomy_version=base.taxonomy_version,
        feature_definition_version=context.version,
        values=context.to_feature_values(),
        missingness=dict(context.missingness),
        source_as_of=dict(base.source_as_of),
        purpose="policy_context",
    )


class BanditContextBuilder:
    def __init__(
        self,
        *,
        catalogue_codes: tuple[str, ...],
        skill_ids: tuple[str, ...],
        response_formats: tuple[str, ...] = PILOT_RESPONSE_FORMATS,
        mastery_gateway: MasteryEvidenceGateway | None = None,
    ) -> None:
        if not catalogue_codes or len(set(catalogue_codes)) != len(catalogue_codes):
            raise ValueError("catalogue codes must be a non-empty unique sequence")
        if not skill_ids or len(set(skill_ids)) != len(skill_ids):
            raise ValueError("skill ids must be a non-empty unique sequence")
        self.catalogue_codes = catalogue_codes
        self.skill_ids = skill_ids
        self.response_formats = response_formats
        self._mastery = mastery_gateway or NullMasteryGateway()
        self.feature_names = feature_names(catalogue_codes, skill_ids, response_formats)

    def build(
        self,
        snapshot: FeatureSnapshotRecord,
        belief: MisconceptionDistribution,
        item: QuestionContext,
        history: SupportHistory,
    ) -> BanditContext:
        values = _values(
            snapshot=snapshot,
            belief=belief,
            item=item,
            history=history,
            catalogue_codes=self.catalogue_codes,
            skill_ids=self.skill_ids,
            response_formats=self.response_formats,
            mastery=self._mastery.parent_skill_mastery(
                learner_id=snapshot.learner_id, skill_id=str(snapshot.skill_id)
            ),
        )
        if tuple(values) != tuple(self.feature_names):
            raise ValueError("context feature order drifted from bandit-context-v1")
        vector = tuple(values[name] for name in self.feature_names)
        missingness = {
            name: values[name] == 1.0
            for name in self.feature_names
            if name.endswith("_missing")
            or name.startswith("missing_")
            or name.endswith("_uncertain")
        }
        return BanditContext(CONTEXT_VERSION, self.feature_names, vector, missingness)


def feature_names(
    catalogue_codes: tuple[str, ...],
    skill_ids: tuple[str, ...],
    response_formats: tuple[str, ...],
) -> tuple[str, ...]:
    names = [
        "recent_accuracy",
        "recent_accuracy_missing",
        "mastery",
        "mastery_missing",
        "support_need",
        "support_need_missing",
        "support_need_uncertain",
    ]
    for scaffold_type in HISTORY_TYPES:
        names.extend(
            (
                f"{scaffold_type}_ig_mean",
                f"{scaffold_type}_ig_mean_missing",
                f"{scaffold_type}_count",
                f"{scaffold_type}_count_missing",
            )
        )
    names.extend(("support_dependency", "support_dependency_missing"))
    names.extend(f"skill:{skill_id}" for skill_id in skill_ids)
    names.append("skill_unknown")
    names.extend(("difficulty", "difficulty_missing"))
    names.extend(f"format:{name}" for name in response_formats)
    names.append("format_unknown")
    names.extend(f"template_hash_{index}" for index in range(TEMPLATE_BINS))
    names.append("template_missing")
    names.extend(f"belief:{code}" for code in catalogue_codes)
    names.extend(
        (
            "belief_extra_mass",
            "belief_incomplete",
            "entropy",
            "confidence",
            "abstained",
            "failed_attempt_count",
            "failed_attempt_count_missing",
            "response_time_ratio",
            "response_time_ratio_missing",
            "diagnostic_support_need",
            "diagnostic_support_need_missing",
            "learner_state_reliability",
            "learner_state_reliability_missing",
            "missing_learner_block",
            "missing_question_block",
            "missing_diagnostic_block",
        )
    )
    return tuple(names)


def _values(
    *,
    snapshot: FeatureSnapshotRecord,
    belief: MisconceptionDistribution,
    item: QuestionContext,
    history: SupportHistory,
    catalogue_codes: tuple[str, ...],
    skill_ids: tuple[str, ...],
    response_formats: tuple[str, ...],
    mastery: float | None,
) -> dict[str, float]:
    recent = _number(snapshot.values.get("recent_accuracy"))
    support_need = _number(snapshot.values.get("learner_support_need"))
    reliability = _number(snapshot.values.get("learner_state_reliability"))
    dependency = history.support_dependency_index
    difficulty = (
        item.difficulty
        if item.difficulty is not None
        else _number(snapshot.values.get("item_difficulty"))
    )
    ratio = _number(snapshot.values.get("response_time_ratio"))
    failed = _number(snapshot.values.get("failed_attempt_count"))
    if failed is None:
        failed = _number(snapshot.values.get("attempt_count"))
    names = feature_names(catalogue_codes, skill_ids, response_formats)
    values = dict.fromkeys(names, 0.0)
    _put(values, "recent_accuracy", recent)
    _put(values, "mastery", mastery)
    _put(values, "support_need", support_need)
    values["support_need_uncertain"] = 1.0 if support_need is None else 0.0
    history_missing = True
    for scaffold_type in HISTORY_TYPES:
        mean = history.mean_valid_ig.get(scaffold_type)
        count = history.counts.get(scaffold_type)
        _put(values, f"{scaffold_type}_ig_mean", float(mean) if mean is not None else None)
        _put(values, f"{scaffold_type}_count", float(count) if count is not None else None)
        if mean is not None or count is not None:
            history_missing = False
    _put(values, "support_dependency", dependency)
    skill_known = item.skill_id in skill_ids
    if skill_known:
        values[f"skill:{item.skill_id}"] = 1.0
    values["skill_unknown"] = 0.0 if skill_known else 1.0
    _put(values, "difficulty", float(difficulty) if difficulty is not None else None)
    format_known = item.response_format in response_formats
    if format_known and item.response_format is not None:
        values[f"format:{item.response_format}"] = 1.0
    values["format_unknown"] = 0.0 if format_known else 1.0
    if item.template_key:
        values[f"template_hash_{_template_bin(item.template_key)}"] = 1.0
        values["template_missing"] = 0.0
    else:
        values["template_missing"] = 1.0
    extra = 0.0
    incomplete = False
    for code, probability in belief.probabilities.items():
        if code in catalogue_codes:
            values[f"belief:{code}"] = float(probability)
        else:
            extra += float(probability)
            incomplete = True
    if any(code not in belief.probabilities for code in catalogue_codes):
        incomplete = True
    values["belief_extra_mass"] = extra
    values["belief_incomplete"] = 1.0 if incomplete else 0.0
    values["entropy"] = float(belief.entropy)
    values["confidence"] = float(belief.confidence)
    values["abstained"] = 1.0 if belief.abstained else 0.0
    _put(values, "failed_attempt_count", failed)
    _put(values, "response_time_ratio", ratio)
    _put(values, "diagnostic_support_need", support_need)
    _put(values, "learner_state_reliability", reliability)
    learner_missing = (
        recent is None
        and mastery is None
        and support_need is None
        and history_missing
        and dependency is None
    )
    question_missing = (not skill_known) and difficulty is None and not item.template_key
    diagnostic_missing = ratio is None and support_need is None and reliability is None
    values["missing_learner_block"] = 1.0 if learner_missing else 0.0
    values["missing_question_block"] = 1.0 if question_missing else 0.0
    values["missing_diagnostic_block"] = 1.0 if diagnostic_missing else 0.0
    return values


def _put(values: dict[str, float], name: str, observed: float | None) -> None:
    if observed is None:
        values[name] = 0.0
        values[f"{name}_missing"] = 1.0
        return
    values[name] = float(observed)
    values[f"{name}_missing"] = 0.0


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _template_bin(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % TEMPLATE_BINS
