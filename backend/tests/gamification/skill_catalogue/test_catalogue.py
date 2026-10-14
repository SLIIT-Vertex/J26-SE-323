import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.gamification.domain.types import ProtocolVersion, SkillId, TaxonomyVersion
from app.gamification.modeling.shared.feature_building import (
    DecisionFeatureInput,
    FeatureBuilder,
)
from app.gamification.skill_catalogue.contracts import ReviewStatus
from app.gamification.skill_catalogue.json_repository import (
    SKILL_REVIEW_DATA_DIRECTORY,
    load_development_skill_catalogue,
    load_skill_reviews,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_inventory_preserves_all_stable_codes_indices_and_question_mappings() -> None:
    inventory = read_jsonl(SKILL_REVIEW_DATA_DIRECTORY / "skill-inventory.jsonl")
    mappings = read_jsonl(SKILL_REVIEW_DATA_DIRECTORY / "question-skill-mappings.jsonl")

    assert len(inventory) == 30
    assert [record["stable_index"] for record in inventory] == list(range(30))
    assert len({record["skill_code"] for record in inventory}) == 30
    assert len({record["question_id"] for record in mappings}) == 328
    assert len(mappings) == 331
    assert {record["skill_code"] for record in mappings} <= {
        record["skill_code"] for record in inventory
    }
    assert [
        record["skill_code"] for record in mappings if record["question_id"] == "3.59"
    ] == ["ENV-HLT", "ENV-CIV"]


def test_all_sinhala_medium_grade_five_candidates_have_draft_bindings() -> None:
    candidates = read_jsonl(
        PROJECT_ROOT
        / "data"
        / "gamification"
        / "grade5-curriculum-game-dataset"
        / "v2"
        / "skill_candidates.jsonl"
    )
    bindings = read_jsonl(
        SKILL_REVIEW_DATA_DIRECTORY / "grade5-candidate-skill-bindings.jsonl"
    )

    assert len(candidates) == 548
    assert {record["subject"] for record in candidates} == {"MAT", "ENV", "SIN", "ENG"}
    assert len(bindings) == len(candidates)
    assert {record["skill_candidate_id"] for record in bindings} == {
        record["skill_candidate_id"] for record in candidates
    }
    assert all(record["status"] == "draft" for record in bindings)
    assert all(record["rationale"] for record in bindings)
    catalogue = load_development_skill_catalogue()
    assert len(catalogue.bindings) == 548
    assert all(
        catalogue.resolve_candidate(str(record["skill_candidate_id"]), allow_draft=True)
        == record["knowledge_tracing_skill_id"]
        for record in bindings
    )


def test_draft_bindings_are_blocked_by_default_and_explicit_in_development() -> None:
    catalogue = load_development_skill_catalogue()

    with pytest.raises(PermissionError, match="both draft"):
        catalogue.resolve_candidate("G5-MAT-C03")
    assert catalogue.resolve_candidate("G5-MAT-C03", allow_draft=True) == "MAT-FRC"
    with pytest.raises(LookupError, match="no skill binding"):
        catalogue.resolve_candidate("G5-MAT-UNMAPPED", allow_draft=True)

    retired = replace(catalogue.skills["MAT-FRC"], status=ReviewStatus.RETIRED)
    retired_catalogue = replace(catalogue, skills={**catalogue.skills, "MAT-FRC": retired})
    with pytest.raises(PermissionError, match="both draft"):
        retired_catalogue.resolve_candidate("G5-MAT-C03", allow_draft=True)


def test_approved_skill_requires_real_review_metadata_and_in_scope_labels() -> None:
    review = load_skill_reviews()[0]
    with pytest.raises(ValueError, match="development-only"):
        replace(review, status=ReviewStatus.APPROVED)
    with pytest.raises(ValueError, match="reviewer identity"):
        replace(review, status=ReviewStatus.APPROVED, development_only=False)
    approved = replace(
        review,
        status=ReviewStatus.APPROVED,
        development_only=False,
        reviewer_id="reviewer-001",
        reviewed_on="2026-10-14",
    )
    assert approved.labels["ta"] is None

    with pytest.raises(ValueError, match="in-scope language"):
        replace(
            review,
            status=ReviewStatus.APPROVED,
            development_only=False,
            reviewer_id="reviewer-001",
            reviewed_on="2026-10-14",
            required_label_languages=("en", "si", "ta"),
            deferred_languages=(),
        )


def test_phase_four_feature_contract_accepts_bound_skill_without_redesign() -> None:
    catalogue = load_development_skill_catalogue()
    bound = catalogue.bind_feature_values(
        {"skill_id": "G5-MAT-C01-L01-O01", "current_score": 0.0},
        allow_draft=True,
    )
    assert bound["skill_id"] == "MAT-NUM"
    assert bound["source_skill_candidate_id"] == "G5-MAT-C01-L01-O01"
    assert bound["skill_taxonomy_version"] == catalogue.taxonomy_version

    snapshot = FeatureBuilder().build(
        DecisionFeatureInput(
            learner_id=UUID("00000000-0000-0000-0000-000000000501"),
            skill_id=SkillId(str(bound["skill_id"])),
            captured_at=datetime(2026, 10, 14, tzinfo=UTC),
            protocol_version=ProtocolVersion("adaptive-episode-v1"),
            skill_taxonomy_version=TaxonomyVersion(catalogue.taxonomy_version),
            misconception_catalogue_version="provisional-misconceptions-v1",
            support_catalogue_version="provisional-support-v1",
            current_score=0.0,
            recent_correctness=(False,),
            attempt_count=1,
        )
    )
    assert snapshot.skill_id == "MAT-NUM"
    assert snapshot.taxonomy_version == catalogue.taxonomy_version


def test_manifest_hashes_and_development_gates_are_current() -> None:
    manifest = json.loads((SKILL_REVIEW_DATA_DIRECTORY / "manifest.json").read_text())

    assert manifest["counts"] == {
        "approved_bindings": 0,
        "approved_skills": 0,
        "development_skill_reviews": 25,
        "grade5_candidate_skill_bindings": 548,
        "question_skill_mappings": 331,
        "questions": 328,
        "skills": 30,
    }
    assert manifest["gates"]["development_phase_5a"] == "pass"
    assert manifest["gates"]["development_phase_5b"] == "ready"
    assert manifest["gates"]["phase_5b"] == "ready_for_sinhala_medium_development"
    assert (
        manifest["gates"]["external_research_validation"]
        == "deferred_not_required_for_development"
    )
    assert manifest["delivery_scope"] == {
        "content_languages": ["si", "en", "bilingual"],
        "deferred_languages": ["ta"],
        "learner_medium": "si",
        "required_label_languages": ["en", "si"],
        "support_language": "si",
    }
    for name, metadata in manifest["files"].items():
        path = SKILL_REVIEW_DATA_DIRECTORY / name
        assert path.stat().st_size == metadata["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
    for name, metadata in manifest["sources"].items():
        assert hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() == metadata["sha256"]


def test_model_slice_evaluation_uses_bound_skill_and_language_dimensions() -> None:
    report = json.loads(
        (SKILL_REVIEW_DATA_DIRECTORY / "model-slice-evaluation.json").read_text()
    )
    assert report["synthetic"] is True
    assert report["authorized_research_evidence"] is False
    assert report["learner_medium"] == "si"
    assert report["record_count"] == 8
    assert report["skill_slices"] == {
        "LAN-BIL": {"accuracy": 0.5, "sample_count": 4},
        "MAT-FRC": {"accuracy": 1.0, "sample_count": 1},
        "MAT-NUM": {"accuracy": 1.0, "sample_count": 1},
        "MAT-OPS": {"accuracy": 1.0, "sample_count": 2},
    }
    assert report["content_language_slices"] == {
        "bilingual": {"accuracy": 1.0, "sample_count": 4},
        "en": {"accuracy": 0.5, "sample_count": 4},
    }


def test_skill_catalogue_does_not_import_knowledge_tracing_implementation() -> None:
    package = PROJECT_ROOT / "backend" / "app" / "gamification" / "skill_catalogue"
    for path in package.glob("*.py"):
        assert "app.knowledge_tracing" not in path.read_text()
