"""Freeze and verify the synthetic expert-review development package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
)
from app.gamification.modeling.offline.dataset_manifest import DatasetManifest
from app.gamification.modeling.synthetic.datasets import (
    CLASSIFICATION_EVALUATION_EXAMPLE,
    DEVELOPMENT_RESEARCH_PROTOCOL,
    EXPERT_REVIEW_SIMULATION,
    load_synthetic_expert_review_rows,
    load_synthetic_expert_review_simulation,
)

DEFAULT_OUTPUT = EXPERT_REVIEW_SIMULATION.with_name("expert-review-simulation-manifest.json")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_commit(project_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _source_worktree_dirty(project_root: Path) -> bool:
    return bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )


def _cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    labels = sorted({label for pair in pairs for label in pair})
    observed = sum(left == right for left, right in pairs) / len(pairs)
    expected = sum(
        (sum(left == label for left, _ in pairs) / len(pairs))
        * (sum(right == label for _, right in pairs) / len(pairs))
        for label in labels
    )
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 1.0
    return observed, kappa


def build_manifest(*, project_root: Path) -> dict[str, object]:
    review_payload = load_synthetic_expert_review_simulation()
    protocol = _read_json(DEVELOPMENT_RESEARCH_PROTOCOL)
    predictions = _read_json(CLASSIFICATION_EVALUATION_EXAMPLE)
    rows = load_synthetic_expert_review_rows()
    cases = review_payload["cases"]
    assert isinstance(cases, list)

    pairs = [
        (
            case["independent_reviews"][0]["expert_misconception_label"],
            case["independent_reviews"][1]["expert_misconception_label"],
        )
        for case in cases
    ]
    raw_agreement, cohen_kappa = _cohen_kappa(pairs)
    unknown_rate = sum(case["adjudicated_label"] == "unknown/other" for case in cases) / len(
        cases
    )
    valid_outcome_rate = sum(row.valid_outcome for row in rows) / len(rows)
    dataset_manifest = DatasetManifest.build(
        rows,
        dataset_id=str(review_payload["dataset_id"]),
        split_seed=int(protocol["predeclared_engineering_thresholds"]["split_seed"]),
        synthetic=True,
    )
    evaluation = evaluate_classification(predictions)
    thresholds = protocol["predeclared_engineering_thresholds"]
    checks = {
        "minimum_case_count": len(cases) >= thresholds["minimum_case_count"],
        "minimum_reviewers_per_case": all(
            len(case["independent_reviews"]) >= thresholds["minimum_reviewers_per_case"]
            for case in cases
        ),
        "minimum_raw_primary_label_agreement": raw_agreement
        >= thresholds["minimum_raw_primary_label_agreement"],
        "maximum_unknown_or_other_rate": unknown_rate
        <= thresholds["maximum_unknown_or_other_rate"],
        "minimum_valid_outcome_rate": valid_outcome_rate
        >= thresholds["minimum_valid_outcome_rate"],
        "maximum_classification_brier_score": evaluation.brier_score
        <= thresholds["maximum_classification_brier_score"],
        "maximum_classification_ece": evaluation.expected_calibration_error
        <= thresholds["maximum_classification_ece"],
        "minimum_classification_accuracy": evaluation.accuracy
        >= thresholds["minimum_classification_accuracy"],
        "maximum_classification_abstention_rate": evaluation.abstention_rate
        <= thresholds["maximum_classification_abstention_rate"],
    }
    return {
        "schema_version": "synthetic-expert-review-manifest-v1",
        "component_owner": "hareeshagunasekara",
        "dataset_id": review_payload["dataset_id"],
        "synthetic": True,
        "contains_human_data": False,
        "authorized_research_evidence": False,
        "delivery_scope": protocol["delivery_scope"],
        "source_commit": _source_commit(project_root),
        "source_worktree_dirty": _source_worktree_dirty(project_root),
        "source_files": {
            str(path.relative_to(project_root)): {"sha256": _file_sha256(path)}
            for path in (
                DEVELOPMENT_RESEARCH_PROTOCOL,
                EXPERT_REVIEW_SIMULATION,
                CLASSIFICATION_EVALUATION_EXAMPLE,
            )
        },
        "offline_dataset_manifest": {
            **asdict(dataset_manifest),
            "manifest_sha256": dataset_manifest.digest,
        },
        "simulated_review_summary": {
            "case_count": len(cases),
            "double_reviewed_case_count": sum(
                len(case["independent_reviews"]) >= 2 for case in cases
            ),
            "raw_primary_label_agreement": raw_agreement,
            "cohen_kappa": cohen_kappa,
            "adjudicated_case_count": sum(bool(case["adjudicated_label"]) for case in cases),
            "unknown_or_other_rate": unknown_rate,
            "valid_outcome_rate": valid_outcome_rate,
        },
        "simulated_classification_evaluation": asdict(evaluation),
        "engineering_threshold_checks": checks,
        "development_gate": "pass" if all(checks.values()) else "fail",
        "research_and_child_facing_gate": "blocked_requires_authorized_replacement",
        "replacement_guide": protocol["replacement_guide"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    manifest = build_manifest(project_root=project_root)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0 if manifest["development_gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
