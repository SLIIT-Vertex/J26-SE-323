import argparse
import importlib.util
import json
import socket
from pathlib import Path

import pytest
import sqlalchemy
from pydantic import ValidationError

from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.evaluation import (
    EvaluationManifest,
    binary_violation_metrics,
    evaluate_reference_policy,
    ordinal_assistance_metrics,
    render_evaluation_summary,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = REPOSITORY_ROOT / "backend/app/adaptive_tutor/application/reference_scenarios.json"
MANIFEST = REPOSITORY_ROOT / "research/adaptive-tutor/evaluation-manifest-v1.json"
SCHEMA = REPOSITORY_ROOT / "research/adaptive-tutor/evaluation-dataset-schema-v1.json"
EVALUATOR_PATH = REPOSITORY_ROOT / "backend/scripts/evaluate_adaptive_tutor.py"
EVALUATOR_SPEC = importlib.util.spec_from_file_location("adaptive_tutor_evaluator", EVALUATOR_PATH)
assert EVALUATOR_SPEC and EVALUATOR_SPEC.loader
EVALUATOR = importlib.util.module_from_spec(EVALUATOR_SPEC)
EVALUATOR_SPEC.loader.exec_module(EVALUATOR)


def document() -> dict:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))


def manifest() -> EvaluationManifest:
    return EvaluationManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))


def test_empty_ordinal_dataset_has_explicit_zero_denominators() -> None:
    metrics = ordinal_assistance_metrics([], [])

    assert metrics["sample_size"] == 0
    assert metrics["agreement"] == {"numerator": 0, "denominator": 0, "value": None}
    assert metrics["weighted_cohens_kappa"] is None
    assert all(count == 0 for row in metrics["confusion_matrix"].values() for count in row.values())


def test_all_correct_ordinal_labels_have_perfect_metrics() -> None:
    labels = list(AssistanceLevel)

    metrics = ordinal_assistance_metrics(labels, labels)

    assert metrics["agreement"]["value"] == 1.0
    assert metrics["weighted_cohens_kappa"] == 1.0
    assert metrics["over_support_rate"]["numerator"] == 0
    assert metrics["under_support_rate"]["numerator"] == 0


def test_all_incorrect_extreme_labels_preserve_ordinal_direction() -> None:
    metrics = ordinal_assistance_metrics(["L0", "L6"], ["L6", "L0"])

    assert metrics["agreement"]["value"] == 0.0
    assert metrics["over_support_rate"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert metrics["under_support_rate"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert metrics["weighted_cohens_kappa"] == -1.0


def test_missing_predictions_are_abstentions_not_ordinal_guesses() -> None:
    metrics = ordinal_assistance_metrics(["L0", "L3"], [None, "L3"])

    assert metrics["agreement"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert metrics["missing_prediction_rate"] == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert metrics["paired_predictions"] == 1
    assert metrics["confusion_matrix"]["L0"]["MISSING"] == 1


@pytest.mark.parametrize(
    ("expected", "observed"),
    [
        (["L7"], ["L0"]),
        (["L0"], ["L7"]),
        (["L0"], []),
    ],
)
def test_invalid_or_mismatched_ordinal_labels_are_rejected(
    expected: list[str], observed: list[str]
) -> None:
    with pytest.raises(ValueError):
        ordinal_assistance_metrics(expected, observed)


def test_violation_metrics_cover_zero_denominators_and_indeterminate() -> None:
    empty = binary_violation_metrics([], [])
    metrics = binary_violation_metrics(
        [True, True, False, False, True],
        [True, False, True, False, None],
    )

    assert empty["precision"] is None
    assert empty["recall"] is None
    assert empty["f1"] is None
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
    assert metrics["false_negative_rate"] == 0.5
    assert metrics["indeterminate_rate"] == 0.2


def test_invalid_violation_labels_are_rejected() -> None:
    with pytest.raises(ValueError):
        binary_violation_metrics([True], ["FAIL"])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        binary_violation_metrics([True], [1])  # type: ignore[list-item]


def test_reference_policy_evaluation_is_reproducible_and_exact() -> None:
    first = evaluate_reference_policy(
        document(), manifest(), dataset_source=str(SCENARIOS.relative_to(REPOSITORY_ROOT))
    )
    second = evaluate_reference_policy(
        document(), manifest(), dataset_source=str(SCENARIOS.relative_to(REPOSITORY_ROOT))
    )

    assert first == second
    controller = first["controller_reference_policy"]
    transitions = first["transition_conformance"]
    assert controller["agreement"] == {"numerator": 20, "denominator": 20, "value": 1.0}
    assert controller["weighted_cohens_kappa"] == 1.0
    assert controller["over_support_rate"]["numerator"] == 0
    assert controller["under_support_rate"]["numerator"] == 0
    assert transitions["transition_direction_agreement"] == {
        "numerator": 13,
        "denominator": 13,
        "value": 1.0,
    }
    assert transitions["transition_reason_conformance"]["value"] == 1.0


def test_reference_report_preserves_provenance_and_does_not_invent_grade() -> None:
    report = evaluate_reference_policy(
        document(), manifest(), dataset_source="canonical-reference.json"
    )

    assert report["dataset"]["provenance"] == manifest().dataset_provenance.model_dump(mode="json")
    assert report["dataset"]["provenance"]["independent_labels"] is False
    assert all(record["grade"] is None for record in report["records"])
    assert all(record["language"] is None for record in report["records"])
    assert all("learner_id" not in record for record in report["records"])
    assert all(record["independent_labels"] is False for record in report["records"])
    assert all(record["actual_learner_observations"] is False for record in report["records"])
    assert all(record["contains_identifiable_child_data"] is False for record in report["records"])
    assert all(
        record["input_evidence"] == {"canonical_record_reference": record["source_provenance"]}
        for record in report["records"]
    )
    assert {record["label_author"] for record in report["records"]} == {
        "MindBridge Adaptive Tutor project design team"
    }
    assert report["verifier_violation_metrics"]["evaluation_status"] == "NOT_EVALUATED"


def test_dataset_and_manifest_versions_are_validated() -> None:
    wrong_dataset_manifest = manifest().model_copy(update={"dataset_version": "other-v1"})

    with pytest.raises(ValueError, match="dataset version"):
        evaluate_reference_policy(
            document(), wrong_dataset_manifest, dataset_source="canonical-reference.json"
        )
    with pytest.raises(ValidationError):
        EvaluationManifest.model_validate(
            {**manifest().model_dump(), "schema_version": "unsupported-v2"}
        )


def test_dataset_schema_defines_all_requested_dataset_families() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert {
        "controller_dataset",
        "transition_dataset",
        "skill_mapper_dataset",
        "verifier_dataset",
        "curriculum_dataset",
        "baseline_dataset",
        "expert_review_dataset",
    }.issubset(schema["$defs"])
    assert schema["$defs"]["common_record"]["properties"]["contains_identifiable_child_data"] == {
        "const": False
    }


def test_exporter_writes_identical_machine_and_human_results(tmp_path: Path) -> None:
    json_output = tmp_path / "report.json"
    summary_output = tmp_path / "report.md"
    args = argparse.Namespace(
        dataset=SCENARIOS,
        manifest=MANIFEST,
        json_output=json_output,
        summary_output=summary_output,
    )

    report = EVALUATOR.run(args)

    assert json.loads(json_output.read_text(encoding="utf-8")) == report
    assert summary_output.read_text(encoding="utf-8") == render_evaluation_summary(report)
    assert "20/20" in summary_output.read_text(encoding="utf-8")
    assert "NOT_EVALUATED" in summary_output.read_text(encoding="utf-8")


def test_evaluation_uses_no_network_or_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("evaluation attempted external I/O")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(sqlalchemy, "create_engine", forbidden)

    report = evaluate_reference_policy(
        document(), manifest(), dataset_source="canonical-reference.json"
    )

    assert report["controller_reference_policy"]["agreement"]["value"] == 1.0
