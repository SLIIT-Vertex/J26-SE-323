import csv
import importlib.util
import json
from pathlib import Path

import pytest

from app.adaptive_tutor.infrastructure import XlsxSkillTaxonomyCatalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVALUATOR_PATH = REPOSITORY_ROOT / "backend/scripts/evaluate_skill_mapper.py"
EVALUATOR_SPEC = importlib.util.spec_from_file_location("skill_mapper_evaluator", EVALUATOR_PATH)
assert EVALUATOR_SPEC and EVALUATOR_SPEC.loader
EVALUATOR = importlib.util.module_from_spec(EVALUATOR_SPEC)
EVALUATOR_SPEC.loader.exec_module(EVALUATOR)


def test_evaluation_metrics_separate_precision_coverage_and_abstention() -> None:
    metrics = EVALUATOR._empty_metrics()

    EVALUATOR._record(metrics, "MAT-FRC", True, True, True, True, True, True, True)
    EVALUATOR._record(metrics, "MAT-OPS", False, True, False, True, True, False, True)
    EVALUATOR._record(metrics, None, False, True, False, False, False, True, False)

    rates = EVALUATOR._rates(metrics)

    assert rates["top_1_retrieval_accuracy"] == 1.0
    assert rates["confirmed_match_precision"] == 0.5
    assert rates["confirmed_match_coverage"] == 0.5
    assert rates["false_confirmation_rate"] == 0.5
    assert rates["incorrect_abstention_rate"] == 0.5


@pytest.mark.requires_research
def test_language_review_package_covers_taxonomy_and_preserves_pending_status() -> None:
    taxonomy = {
        node.skill_id: node
        for node in XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    }
    enrichment = json.loads(
        (
            REPOSITORY_ROOT
            / "research/adaptive-tutor/skill-mapper-enrichment-v1.json"
        ).read_text(encoding="utf-8")
    )
    enriched_ids = {record["skill_id"] for record in enrichment["records"]}
    with (
        REPOSITORY_ROOT / "research/adaptive-tutor/skill-mapper-language-review-v1.csv"
    ).open(encoding="utf-8", newline="") as review_file:
        rows = list(csv.DictReader(review_file))

    assert len(rows) == len(taxonomy) == 30
    assert {row["skill_id"] for row in rows} == set(taxonomy)
    for row in rows:
        node = taxonomy[row["skill_id"]]
        assert row["official_skill_name"] == node.name
        assert row["official_sinhala_designation"] == node.sinhala_designation
        assert row["authoritative_taxonomy_scope"] == node.description
        expected_status = (
            "qualified_review_pending" if row["skill_id"] in enriched_ids else "not_drafted"
        )
        assert row["sinhala_review_status"] == expected_status
        assert row["tamil_review_status"] == expected_status
        assert not any(
            row[field]
            for field in (
                "sinhala_correction",
                "tamil_correction",
                "singlish_correction",
                "tanglish_correction",
                "reviewer_comments",
            )
        )
