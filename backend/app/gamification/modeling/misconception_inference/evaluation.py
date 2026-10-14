import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

DEFAULT_ECE_BINS = 10
DEFAULT_TOP_K = 3
_PROBABILITY_FLOOR = 1e-15
UNKNOWN_LABEL = "unknown/other"


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    """One equal-width confidence bin. Bin count and edges are a provisional reporting choice."""

    bin_index: int
    lower: float
    upper: float
    mean_confidence: float
    accuracy: float
    count: int


@dataclass(frozen=True, slots=True)
class BaselineScore:
    """Reference score on the supplied records, not a held-out trained model."""

    name: str
    basis: str
    accuracy: float
    macro_f1: float


@dataclass(frozen=True, slots=True)
class ClassificationEvaluation:
    sample_count: int
    accuracy: float
    brier_score: float
    expected_calibration_error: float
    abstention_rate: float
    slices: Mapping[str, Mapping[str, float | int]]
    log_loss: float
    macro_f1: float
    per_class_recall: Mapping[str, float]
    top_k: int
    top_k_recall: float
    ece_bins: int
    ece_method: str
    ece_status: str
    answered_count: int
    answered_accuracy: float
    slice_reports: Mapping[str, Mapping[str, Mapping[str, float | int]]]
    reliability_table: tuple[ReliabilityBin, ...]
    baselines: Mapping[str, BaselineScore]


def _top_class(probabilities: Mapping[str, float]) -> str:
    return min(probabilities, key=lambda code: (-float(probabilities[code]), code))


def _top_k(probabilities: Mapping[str, float], k: int) -> tuple[str, ...]:
    ranked = sorted(probabilities, key=lambda code: (-float(probabilities[code]), code))
    return tuple(ranked[:k])


def macro_f1(labels: Sequence[str], predictions: Sequence[str]) -> float:
    """Unweighted mean F1 over the sorted union of true and predicted labels."""

    classes = sorted(set(labels) | set(predictions))
    scores: list[float] = []
    for code in classes:
        true_positive = sum(
            label == code and prediction == code for label, prediction in zip(labels, predictions)
        )
        predicted_count = sum(prediction == code for prediction in predictions)
        label_count = sum(label == code for label in labels)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / label_count if label_count else 0.0
        scores.append(
            0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        )
    return sum(scores) / len(scores) if scores else 0.0


def expected_calibration_error(
    confidences: Sequence[float], hits: Sequence[bool], *, bins: int = DEFAULT_ECE_BINS
) -> tuple[float, tuple[ReliabilityBin, ...]]:
    """Equal-width binned ECE. The bin count is a provisional reporting choice, not a fitted value."""

    if bins < 1:
        raise ValueError("ece bins must be positive")
    if len(confidences) != len(hits) or not confidences:
        raise ValueError("calibration requires one confidence and one outcome per record")
    width = 1.0 / bins
    grouped: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for confidence, hit in zip(confidences, hits):
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between zero and one")
        grouped[min(bins - 1, int(confidence / width))].append((confidence, hit))
    table: list[ReliabilityBin] = []
    error = 0.0
    total = len(confidences)
    for index, rows in enumerate(grouped):
        if not rows:
            continue
        mean_confidence = sum(confidence for confidence, _ in rows) / len(rows)
        accuracy = sum(hit for _, hit in rows) / len(rows)
        error += (len(rows) / total) * abs(accuracy - mean_confidence)
        table.append(
            ReliabilityBin(
                bin_index=index,
                lower=index * width,
                upper=1.0 if index == bins - 1 else (index + 1) * width,
                mean_confidence=mean_confidence,
                accuracy=accuracy,
                count=len(rows),
            )
        )
    return error, tuple(table)


def _slice_bucket(
    records: Sequence[Mapping[str, object]], field: str, flags: Sequence[tuple[bool, bool]]
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for record, flag in zip(records, flags):
        grouped[str(record.get(field, "missing"))].append(flag)
    return {
        key: {
            "sample_count": len(values),
            "accuracy": sum(correct for correct, _ in values) / len(values),
            "abstention_rate": sum(abstained for _, abstained in values) / len(values),
        }
        for key, values in sorted(grouped.items())
    }


def _mode(labels: Sequence[str]) -> str:
    counts = Counter(labels)
    return min(counts, key=lambda label: (-counts[label], label))


def _baseline(
    name: str, basis: str, labels: Sequence[str], predictions: Sequence[str]
) -> BaselineScore:
    accuracy = sum(label == prediction for label, prediction in zip(labels, predictions)) / len(
        labels
    )
    return BaselineScore(
        name=name, basis=basis, accuracy=accuracy, macro_f1=macro_f1(labels, predictions)
    )


def _most_frequent_predictions(records: Sequence[Mapping[str, object]]) -> list[str]:
    by_skill: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_skill[str(record.get("skill_id", "missing"))].append(str(record["label"]))
    modes = {skill: _mode(labels) for skill, labels in by_skill.items()}
    return [modes[str(record.get("skill_id", "missing"))] for record in records]


def _error_map_predictions(
    records: Sequence[Mapping[str, object]], error_map: Mapping[str, str] | None
) -> tuple[list[str], str]:
    if error_map is not None:
        return [
            error_map.get(str(record.get("structured_error_code") or ""), UNKNOWN_LABEL)
            for record in records
        ], "supplied_error_map"
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        code = record.get("structured_error_code")
        if isinstance(code, str) and code:
            grouped[code].append(str(record["label"]))
    modes = {code: _mode(labels) for code, labels in grouped.items()}
    return [
        modes.get(str(record.get("structured_error_code") or ""), UNKNOWN_LABEL)
        for record in records
    ], "in_sample_error_code_majority"


def evaluate_classification(
    records: Sequence[Mapping[str, object]],
    *,
    slice_field: str = "skill_id",
    ece_bins: int = DEFAULT_ECE_BINS,
    top_k: int = DEFAULT_TOP_K,
    error_map: Mapping[str, str] | None = None,
) -> ClassificationEvaluation:
    """Evaluate supplied labels and probabilities without manufacturing evidence.

    Accuracy counts an abstention as not correct. Calibration uses whether the highest-probability
    class matches the label, so abstention does not by itself move the reliability table.
    """

    if not records:
        raise ValueError("classification evaluation requires labelled records")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    labels: list[str] = []
    predictions: list[str] = []
    confidences: list[float] = []
    top_hits: list[bool] = []
    answered_flags: list[tuple[bool, bool]] = []
    brier = 0.0
    log_loss = 0.0
    correct = 0
    abstained = 0
    top_k_hits = 0
    answered_correct = 0
    for record in records:
        label = str(record["label"])
        probabilities = {
            str(code): float(value) for code, value in dict(record["probabilities"]).items()
        }  # type: ignore[arg-type]
        if not probabilities or abs(sum(probabilities.values()) - 1) > 1e-9:
            raise ValueError("evaluation probabilities must sum to one")
        predicted = _top_class(probabilities)
        confidence = probabilities[predicted]
        is_abstained = bool(record.get("abstained", False))
        is_top_hit = predicted == label
        is_correct = is_top_hit and not is_abstained
        labels.append(label)
        predictions.append(predicted)
        confidences.append(confidence)
        top_hits.append(is_top_hit)
        answered_flags.append((is_correct, is_abstained))
        correct += is_correct
        abstained += is_abstained
        answered_correct += is_top_hit and not is_abstained
        top_k_hits += label in _top_k(probabilities, top_k)
        brier += sum(
            (probability - (1.0 if code == label else 0.0)) ** 2
            for code, probability in probabilities.items()
        )
        observed = min(max(probabilities.get(label, 0.0), _PROBABILITY_FLOOR), 1.0)
        log_loss += -math.log(observed)
    total = len(records)
    answered_count = total - abstained
    calibration, table = expected_calibration_error(confidences, top_hits, bins=ece_bins)
    label_counts = Counter(labels)
    per_class_recall = {
        code: sum(
            label == code and prediction == code for label, prediction in zip(labels, predictions)
        )
        / label_counts[code]
        for code in sorted(label_counts)
    }
    error_predictions, error_basis = _error_map_predictions(records, error_map)
    frequent_predictions = _most_frequent_predictions(records)
    return ClassificationEvaluation(
        sample_count=total,
        accuracy=correct / total,
        brier_score=brier / total,
        expected_calibration_error=calibration,
        abstention_rate=abstained / total,
        slices=_slice_bucket(records, slice_field, answered_flags),
        log_loss=log_loss / total,
        macro_f1=macro_f1(labels, predictions),
        per_class_recall=per_class_recall,
        top_k=top_k,
        top_k_recall=top_k_hits / total,
        ece_bins=ece_bins,
        ece_method="equal_width_bins",
        ece_status="provisional_binning",
        answered_count=answered_count,
        answered_accuracy=(answered_correct / answered_count) if answered_count else 0.0,
        slice_reports={
            field: _slice_bucket(records, field, answered_flags)
            for field in ("skill_id", "language", "modality_available")
        },
        reliability_table=table,
        baselines={
            "most_frequent_per_skill": _baseline(
                "most_frequent_per_skill",
                "in_sample_skill_mode",
                labels,
                frequent_predictions,
            ),
            "deterministic_error_map": _baseline(
                "deterministic_error_map", error_basis, labels, error_predictions
            ),
        },
    )
