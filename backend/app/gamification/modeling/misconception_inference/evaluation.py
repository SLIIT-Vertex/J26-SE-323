from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ClassificationEvaluation:
    sample_count: int
    accuracy: float
    brier_score: float
    expected_calibration_error: float
    abstention_rate: float
    slices: Mapping[str, Mapping[str, float | int]]


def evaluate_classification(
    records: Sequence[Mapping[str, object]], *, slice_field: str = "skill_id"
) -> ClassificationEvaluation:
    """Evaluate supplied labels and probabilities without manufacturing evidence."""

    if not records:
        raise ValueError("classification evaluation requires labelled records")
    buckets: dict[str, list[bool]] = {}
    brier = 0.0
    calibration = 0.0
    correct = 0
    abstained = 0
    for record in records:
        label = str(record["label"])
        probabilities = dict(record["probabilities"])  # type: ignore[arg-type]
        if not probabilities or abs(
            sum(float(value) for value in probabilities.values()) - 1
        ) > 1e-9:
            raise ValueError("evaluation probabilities must sum to one")
        predicted = max(probabilities, key=lambda code: float(probabilities[code]))
        confidence = float(probabilities[predicted])
        is_abstained = bool(record.get("abstained", False))
        is_correct = predicted == label and not is_abstained
        correct += is_correct
        abstained += is_abstained
        brier += sum(
            (float(probability) - (1.0 if code == label else 0.0)) ** 2
            for code, probability in probabilities.items()
        )
        calibration += abs(confidence - float(is_correct))
        buckets.setdefault(str(record.get(slice_field, "unknown")), []).append(is_correct)
    total = len(records)
    slices = {
        key: {"sample_count": len(values), "accuracy": sum(values) / len(values)}
        for key, values in sorted(buckets.items())
    }
    return ClassificationEvaluation(
        sample_count=total,
        accuracy=correct / total,
        brier_score=brier / total,
        expected_calibration_error=calibration / total,
        abstention_rate=abstained / total,
        slices=slices,
    )
