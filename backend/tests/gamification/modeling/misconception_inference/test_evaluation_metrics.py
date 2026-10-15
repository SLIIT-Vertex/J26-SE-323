import pytest

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
    macro_f1,
)


def _record(label: str, predicted: str, confidence: float, **fields: object) -> dict[str, object]:
    other = "other" if predicted == label else label
    if predicted == label:
        probabilities = {label: confidence, other: 1 - confidence}
    else:
        probabilities = {predicted: confidence, label: 1 - confidence}
    return {
        "label": label,
        "probabilities": probabilities,
        "abstained": False,
        "skill_id": "skill",
        "language": "si",
        "modality_available": "full",
        **fields,
    }


def test_ece_is_zero_when_every_prediction_is_certain_and_correct() -> None:
    report = evaluate_classification([_record("m-a", "m-a", 1.0) for _ in range(10)])

    assert report.expected_calibration_error == pytest.approx(0.0)
    assert report.ece_method == "equal_width_bins"
    assert report.ece_status == "provisional_binning"
    assert sum(row.count for row in report.reliability_table) == 10


def test_ece_of_constant_confidence_wrong_predictions_is_the_confidence_gap() -> None:
    report = evaluate_classification([_record("m-a", "m-b", 0.7) for _ in range(10)])

    assert report.accuracy == 0
    assert report.expected_calibration_error == pytest.approx(abs(0.7 - 0.0))
    assert report.reliability_table[0].mean_confidence == pytest.approx(0.7)
    assert report.reliability_table[0].accuracy == 0


def test_macro_f1_matches_a_hand_built_confusion_matrix() -> None:
    labels = ("a", "a", "b")
    predictions = ("a", "b", "b")
    records = [
        _record(label, prediction, 0.8, skill_id="s")
        for label, prediction in zip(labels, predictions)
    ]

    # Class a: precision 1, recall 1/2, F1 2/3. Class b: precision 1/2, recall 1, F1 2/3.
    assert macro_f1(labels, predictions) == pytest.approx(2 / 3)
    report = evaluate_classification(records)
    assert report.macro_f1 == pytest.approx(2 / 3)
    assert report.per_class_recall == {"a": pytest.approx(0.5), "b": pytest.approx(1.0)}


def test_report_includes_slices_baselines_and_abstention_coverage() -> None:
    records = [
        _record("m-a", "m-a", 0.9, language="si", modality_available="full"),
        {
            "label": "m-b",
            "probabilities": {"m-a": 0.5, "m-b": 0.5},
            "abstained": True,
            "skill_id": "other-skill",
            "language": "en",
            "modality_available": "missing",
            "structured_error_code": "error-b",
        },
    ]

    report = evaluate_classification(records, top_k=2)

    assert set(report.slice_reports) == {"skill_id", "language", "modality_available"}
    assert report.answered_count == 1
    assert report.answered_accuracy == 1
    assert report.top_k_recall == 1
    assert set(report.baselines) == {"most_frequent_per_skill", "deterministic_error_map"}
    assert report.log_loss > 0
