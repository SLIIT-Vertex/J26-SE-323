from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

from app.adaptive_tutor.application.context_assembly import ContextEvidenceOrigin
from app.adaptive_tutor.application.contracts import TutoringContext
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
LEVELS = tuple(AssistanceLevel)
LEVEL_INDEX = {level: index for index, level in enumerate(LEVELS)}


class EvaluationDataOrigin(StrEnum):
    DESIGN_AUTHORED_SYNTHETIC = "DESIGN_AUTHORED_SYNTHETIC"
    REAL = "REAL"


class EvaluationLabelStatus(StrEnum):
    DESIGN_AUTHORED_UNREVIEWED = "DESIGN_AUTHORED_UNREVIEWED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    INDEPENDENTLY_LABELLED = "INDEPENDENTLY_LABELLED"


class EvaluationSplit(StrEnum):
    REFERENCE_POLICY = "REFERENCE_POLICY"
    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class TransitionKind(StrEnum):
    ESCALATION = "ESCALATION"
    MAINTAINED = "MAINTAINED"
    FADING = "FADING"


class IntegratedEvaluationPartition(StrEnum):
    DESIGN_AUTHORED = "DESIGN_AUTHORED"
    SYNTHETIC_INTEGRATION = "SYNTHETIC_INTEGRATION"
    REAL_INFRASTRUCTURE = "REAL_INFRASTRUCTURE"
    INDEPENDENT_VALIDATION = "INDEPENDENT_VALIDATION"


class DatasetProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_origin: EvaluationDataOrigin
    label_status: EvaluationLabelStatus
    review_status: NonBlankText
    label_author: NonBlankText
    source_provenance: NonBlankText
    independent_labels: Literal[False]
    actual_learner_observations: Literal[False]


class EvaluationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["adaptive-tutor-evaluation-manifest-v1"]
    experiment_id: NonBlankText
    evaluation_date: date
    dataset_version: NonBlankText
    implementation_version: NonBlankText
    configuration: dict[str, Any]
    dataset_provenance: DatasetProvenance

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if not self.configuration:
            raise ValueError("evaluation configuration must not be empty")
        return self


class ControllerEvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: NonBlankText
    dataset_version: NonBlankText
    dataset_split: EvaluationSplit
    data_origin: EvaluationDataOrigin
    label_status: EvaluationLabelStatus
    review_status: NonBlankText
    label_author: NonBlankText
    source_provenance: NonBlankText
    independent_labels: Literal[False]
    actual_learner_observations: Literal[False]
    contains_identifiable_child_data: Literal[False]
    input_evidence: dict[str, NonBlankText]
    skill_id: NonBlankText
    grade: Literal[4, 5] | None = None
    language: NonBlankText | None = None
    expected_assistance_level: AssistanceLevel
    observed_assistance_level: AssistanceLevel
    previous_assistance_level: AssistanceLevel | None = None
    expected_transition: TransitionKind | None = None
    observed_transition: TransitionKind | None = None
    observed_reason_codes: tuple[DecisionReasonCode, ...]
    applicable_research_questions: tuple[NonBlankText, ...]


class IntegratedEvaluationRecord(BaseModel):
    """One offline software-behavior observation, never a learner-outcome claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: NonBlankText
    partition: IntegratedEvaluationPartition
    coverage_tags: tuple[NonBlankText, ...]
    expected_ready: StrictBool
    observed_ready: StrictBool
    expected_assistance_level: AssistanceLevel | None = None
    observed_assistance_level: AssistanceLevel | None = None
    should_fail_closed: StrictBool = False
    observed_fail_closed: StrictBool = False
    provenance: ContextEvidenceOrigin | None = None
    expected_evidence_items: Annotated[int, Field(strict=True, ge=0)] = 0
    available_evidence_items: Annotated[int, Field(strict=True, ge=0)] = 0

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if not self.coverage_tags:
            raise ValueError("integrated evaluation record requires coverage tags")
        if self.expected_ready != (self.expected_assistance_level is not None):
            raise ValueError("expected readiness and assistance level must agree")
        if self.observed_ready != (self.observed_assistance_level is not None):
            raise ValueError("observed readiness and assistance level must agree")
        if self.available_evidence_items > self.expected_evidence_items:
            raise ValueError("available evidence cannot exceed expected evidence")
        if self.observed_ready and self.provenance is None:
            raise ValueError("ready observation requires provenance")
        return self


def integrated_evaluation_metrics(
    records: Sequence[IntegratedEvaluationRecord | Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate offline integration behavior while preserving evidence partitions."""

    parsed = tuple(
        record
        if isinstance(record, IntegratedEvaluationRecord)
        else IntegratedEvaluationRecord.model_validate(record)
        for record in records
    )
    scenario_passes = sum(_integrated_scenario_passed(record) for record in parsed)
    expected_fail_closed = tuple(record for record in parsed if record.should_fail_closed)
    provenance = {origin.value: 0 for origin in ContextEvidenceOrigin}
    provenance["NONE"] = 0
    partitions = {
        partition.value: {"scenario_count": 0, "passed": 0}
        for partition in IntegratedEvaluationPartition
    }
    for record in parsed:
        provenance[record.provenance.value if record.provenance is not None else "NONE"] += 1
        partition = partitions[record.partition.value]
        partition["scenario_count"] += 1
        partition["passed"] += _integrated_scenario_passed(record)

    policy_records = tuple(
        record for record in parsed if record.expected_assistance_level is not None
    )
    policy_metrics = ordinal_assistance_metrics(
        [record.expected_assistance_level for record in policy_records],
        [record.observed_assistance_level for record in policy_records],
    )
    return {
        "evaluation_status": "EVALUATED",
        "scenario_count": len(parsed),
        "scenario_pass_rate": _rate(scenario_passes, len(parsed)),
        "context_readiness_rate": _rate(
            sum(record.observed_ready for record in parsed), len(parsed)
        ),
        "controller_policy_agreement": policy_metrics,
        "fail_closed_rate": _rate(
            sum(record.observed_fail_closed for record in expected_fail_closed),
            len(expected_fail_closed),
        ),
        "provenance_distribution": provenance,
        "evidence_coverage": _rate(
            sum(record.available_evidence_items for record in parsed),
            sum(record.expected_evidence_items for record in parsed),
        ),
        "partition_results": partitions,
        "coverage_tags": sorted({tag for record in parsed for tag in record.coverage_tags}),
        "baseline_and_ablation": _not_evaluated(
            "No preregistered baseline or ablation dataset is available."
        ),
        "human_inter_rater_agreement": _not_evaluated(
            "No approved independent ordinal severity annotations are available."
        ),
        "interpretation": (
            "Offline software-behavior conformance only; no real learner validation or "
            "educational-effect claim."
        ),
    }


def ordinal_assistance_metrics(
    expected_labels: Sequence[AssistanceLevel | str],
    observed_labels: Sequence[AssistanceLevel | str | None],
) -> dict[str, Any]:
    """Calculate ordinal controller metrics; missing observations remain explicit abstentions."""

    if len(expected_labels) != len(observed_labels):
        raise ValueError("expected and observed label counts must match")

    expected = tuple(_level(label) for label in expected_labels)
    observed = tuple(_level(label) if label is not None else None for label in observed_labels)
    columns = (*LEVELS, "MISSING")
    confusion = {
        expected_level.value: {
            (actual.value if isinstance(actual, AssistanceLevel) else actual): 0
            for actual in columns
        }
        for expected_level in LEVELS
    }

    correct = over_support = under_support = missing = 0
    paired: list[tuple[AssistanceLevel, AssistanceLevel]] = []
    for expected_level, observed_level in zip(expected, observed, strict=True):
        key = observed_level.value if observed_level is not None else "MISSING"
        confusion[expected_level.value][key] += 1
        if observed_level is None:
            missing += 1
            continue
        paired.append((expected_level, observed_level))
        if observed_level is expected_level:
            correct += 1
        elif LEVEL_INDEX[observed_level] > LEVEL_INDEX[expected_level]:
            over_support += 1
        else:
            under_support += 1

    return {
        "sample_size": len(expected),
        "paired_predictions": len(paired),
        "agreement": _rate(correct, len(expected)),
        "weighted_cohens_kappa": _quadratic_weighted_kappa(paired),
        "over_support_rate": _rate(over_support, len(paired)),
        "under_support_rate": _rate(under_support, len(paired)),
        "missing_prediction_rate": _rate(missing, len(expected)),
        "confusion_matrix": confusion,
    }


def binary_violation_metrics(
    expected_violations: Sequence[bool],
    observed_violations: Sequence[bool | None],
) -> dict[str, Any]:
    """Metrics for a future independently labelled verifier dataset; None is INDETERMINATE."""

    if len(expected_violations) != len(observed_violations):
        raise ValueError("expected and observed label counts must match")

    true_positive = false_positive = true_negative = false_negative = indeterminate = 0
    for expected, observed in zip(expected_violations, observed_violations, strict=True):
        if not isinstance(expected, bool) or (
            observed is not None and not isinstance(observed, bool)
        ):
            raise ValueError("violation labels must be boolean or an observed None")
        if observed is None:
            indeterminate += 1
        elif expected and observed:
            true_positive += 1
        elif not expected and observed:
            false_positive += 1
        elif expected and not observed:
            false_negative += 1
        else:
            true_negative += 1

    precision = _value(true_positive, true_positive + false_positive)
    recall = _value(true_positive, true_positive + false_negative)
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    return {
        "sample_size": len(expected_violations),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "indeterminate": indeterminate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": _value(false_positive, false_positive + true_negative),
        "false_negative_rate": _value(false_negative, false_negative + true_positive),
        "indeterminate_rate": _value(indeterminate, len(expected_violations)),
    }


def evaluate_reference_policy(
    document: Mapping[str, Any],
    manifest: EvaluationManifest | Mapping[str, Any],
    *,
    dataset_source: str,
) -> dict[str, Any]:
    """Run Controller V1 against the canonical design-authored reference scenarios."""

    parsed_manifest = (
        manifest
        if isinstance(manifest, EvaluationManifest)
        else EvaluationManifest.model_validate(manifest)
    )
    dataset_version = document.get("policy_version")
    if dataset_version != parsed_manifest.dataset_version:
        raise ValueError("manifest dataset version does not match the reference policy")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list):
        raise TypeError("reference policy scenarios must be a list")
    scenario_ids = [scenario.get("scenario_id") for scenario in scenarios]
    if any(not scenario_id for scenario_id in scenario_ids) or len(scenario_ids) != len(
        set(scenario_ids)
    ):
        raise ValueError("reference policy scenario IDs must be non-blank and unique")

    provenance = parsed_manifest.dataset_provenance
    controller = ScaffoldingController()
    context_fields = set(TutoringContext.model_fields)
    records: list[ControllerEvaluationRecord] = []
    for scenario in scenarios:
        context = TutoringContext.model_validate(
            {field: scenario[field] for field in context_fields}
        )
        expected = _level(scenario["expected_assistance_level"])
        decision = controller.decide(context)
        expected_transition = _transition(context.previous_assistance_level, expected)
        observed_transition = _transition(
            context.previous_assistance_level,
            decision.assistance_level,
        )
        record_reference = f"{dataset_source}#{scenario['scenario_id']}"
        records.append(
            ControllerEvaluationRecord(
                scenario_id=scenario["scenario_id"],
                dataset_version=dataset_version,
                dataset_split=EvaluationSplit.REFERENCE_POLICY,
                data_origin=provenance.data_origin,
                label_status=provenance.label_status,
                review_status=provenance.review_status,
                label_author=provenance.label_author,
                source_provenance=record_reference,
                independent_labels=provenance.independent_labels,
                actual_learner_observations=provenance.actual_learner_observations,
                contains_identifiable_child_data=False,
                input_evidence={"canonical_record_reference": record_reference},
                skill_id=scenario["skill_id"],
                expected_assistance_level=expected,
                observed_assistance_level=decision.assistance_level,
                previous_assistance_level=context.previous_assistance_level,
                expected_transition=expected_transition,
                observed_transition=observed_transition,
                observed_reason_codes=decision.reason_codes,
                applicable_research_questions=("RQ1", "RQ2"),
            )
        )

    ordinal = ordinal_assistance_metrics(
        [record.expected_assistance_level for record in records],
        [record.observed_assistance_level for record in records],
    )
    transitions = _transition_metrics(records)
    return {
        "schema_version": "adaptive-tutor-evaluation-report-v1",
        "experiment": parsed_manifest.model_dump(mode="json"),
        "dataset": {
            "version": dataset_version,
            "status": document.get("status"),
            "source": dataset_source,
            "record_count": len(records),
            "provenance": provenance.model_dump(mode="json"),
        },
        "controller_reference_policy": {
            "evaluation_status": "EVALUATED",
            **ordinal,
            "interpretation": (
                "Reference Policy V1 conformance on design-authored scenarios; not expert "
                "agreement or pedagogical effectiveness."
            ),
        },
        "transition_conformance": transitions,
        "fail_closed_behavior": _not_evaluated(
            "Existing missing-input checks are implementation tests, not a frozen evaluation set."
        ),
        "verifier_violation_metrics": _not_evaluated(
            "No independently labelled verifier violation dataset exists."
        ),
        "curriculum_grounding_metrics": _not_evaluated(
            "No approved runtime curriculum corpus and independently reviewed grounding labels exist."
        ),
        "learner_outcome_metrics": _not_evaluated(
            "No ethically approved learner observations or outcome measurements exist."
        ),
        "records": [record.model_dump(mode="json") for record in records],
    }


def render_evaluation_summary(report: Mapping[str, Any]) -> str:
    controller = report["controller_reference_policy"]
    transitions = report["transition_conformance"]
    agreement = controller["agreement"]
    over_support = controller["over_support_rate"]
    under_support = controller["under_support_rate"]
    transition_agreement = transitions["transition_direction_agreement"]
    return "\n".join(
        (
            "# Adaptive Tutor Offline Evaluation Summary",
            "",
            f"- Experiment: {report['experiment']['experiment_id']}",
            f"- Evaluation date: {report['experiment']['evaluation_date']}",
            f"- Dataset: {report['dataset']['version']} ({report['dataset']['record_count']} records)",
            "- Evidence: design-authored synthetic labels; not independently reviewed",
            (
                "- Reference Policy V1 conformance: "
                f"{agreement['numerator']}/{agreement['denominator']} "
                f"({_percent(agreement['value'])})"
            ),
            f"- Quadratic weighted Cohen's kappa: {controller['weighted_cohens_kappa']}",
            (
                f"- Over-support: {over_support['numerator']}/{over_support['denominator']}; "
                f"under-support: {under_support['numerator']}/{under_support['denominator']}"
            ),
            (
                "- Transition-direction conformance: "
                f"{transition_agreement['numerator']}/{transition_agreement['denominator']}"
            ),
            "- Verifier precision/recall/F1: NOT_EVALUATED",
            "- Educational effectiveness: NOT_EVALUATED",
            "",
            (
                "These measurements establish deterministic software-policy conformance only; "
                "they are not expert agreement or evidence of learner benefit."
            ),
            "",
        )
    )


def _transition_metrics(records: Sequence[ControllerEvaluationRecord]) -> dict[str, Any]:
    kinds = tuple(TransitionKind)
    confusion = {expected.value: {observed.value: 0 for observed in kinds} for expected in kinds}
    direction_matches = reason_matches = 0
    transition_records = [record for record in records if record.expected_transition is not None]
    required_reason = {
        TransitionKind.ESCALATION: DecisionReasonCode.ESCALATION_JUSTIFIED,
        TransitionKind.FADING: DecisionReasonCode.FADING_JUSTIFIED,
        TransitionKind.MAINTAINED: DecisionReasonCode.SUPPORT_MAINTAINED,
    }
    for record in transition_records:
        assert record.expected_transition is not None
        assert record.observed_transition is not None
        confusion[record.expected_transition.value][record.observed_transition.value] += 1
        if record.observed_transition is record.expected_transition:
            direction_matches += 1
        if required_reason[record.expected_transition] in record.observed_reason_codes:
            reason_matches += 1
    return {
        "evaluation_status": "EVALUATED",
        "sample_size": len(transition_records),
        "transition_direction_agreement": _rate(direction_matches, len(transition_records)),
        "transition_reason_conformance": _rate(reason_matches, len(transition_records)),
        "confusion_matrix": confusion,
        "interpretation": (
            "Direction and reason-code conformance on design-authored scenarios with a previous "
            "assistance level."
        ),
    }


def _integrated_scenario_passed(record: IntegratedEvaluationRecord) -> bool:
    if record.expected_ready != record.observed_ready:
        return False
    if (
        record.expected_assistance_level is not None
        and record.expected_assistance_level is not record.observed_assistance_level
    ):
        return False
    return not record.should_fail_closed or record.observed_fail_closed


def _quadratic_weighted_kappa(
    pairs: Sequence[tuple[AssistanceLevel, AssistanceLevel]],
) -> float | None:
    if not pairs:
        return None
    size = len(LEVELS)
    counts = [[0 for _ in LEVELS] for _ in LEVELS]
    expected_counts = [0 for _ in LEVELS]
    observed_counts = [0 for _ in LEVELS]
    for expected, observed in pairs:
        expected_index = LEVEL_INDEX[expected]
        observed_index = LEVEL_INDEX[observed]
        counts[expected_index][observed_index] += 1
        expected_counts[expected_index] += 1
        observed_counts[observed_index] += 1

    denominator = (size - 1) ** 2
    sample_size = len(pairs)
    observed_disagreement = (
        sum(
            ((row - column) ** 2 / denominator) * counts[row][column]
            for row in range(size)
            for column in range(size)
        )
        / sample_size
    )
    expected_disagreement = sum(
        ((row - column) ** 2 / denominator) * expected_counts[row] * observed_counts[column]
        for row in range(size)
        for column in range(size)
    ) / (sample_size**2)
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else None
    return 1 - observed_disagreement / expected_disagreement


def _transition(
    previous: AssistanceLevel | None,
    current: AssistanceLevel,
) -> TransitionKind | None:
    if previous is None:
        return None
    difference = LEVEL_INDEX[current] - LEVEL_INDEX[previous]
    if difference > 0:
        return TransitionKind.ESCALATION
    if difference < 0:
        return TransitionKind.FADING
    return TransitionKind.MAINTAINED


def _level(value: AssistanceLevel | str) -> AssistanceLevel:
    try:
        return AssistanceLevel(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid assistance level: {value}") from error


def _rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": _value(numerator, denominator),
    }


def _value(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _not_evaluated(reason: str) -> dict[str, str]:
    return {"evaluation_status": "NOT_EVALUATED", "reason": reason}


def _percent(value: float | None) -> str:
    return "NOT_EVALUATED" if value is None else f"{value:.1%}"
