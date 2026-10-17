import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.gamification.skill_catalogue.contracts import ReviewStatus
from app.gamification.skill_catalogue.json_repository import (
    SKILL_REVIEW_DATA_DIRECTORY,
    load_development_skill_catalogue,
    load_skill_reviews,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_catalogue_is_an_identity_mapping_of_component_owned_candidates() -> None:
    candidates = read_jsonl(
        PROJECT_ROOT
        / "data/gamification/grade5-curriculum-game-dataset/v2/skill_candidates.jsonl"
    )
    inventory = read_jsonl(SKILL_REVIEW_DATA_DIRECTORY / "skill-inventory.jsonl")
    bindings = read_jsonl(
        SKILL_REVIEW_DATA_DIRECTORY / "grade5-candidate-skill-bindings.jsonl"
    )

    candidate_ids = [str(record["skill_candidate_id"]) for record in candidates]
    assert len(candidate_ids) == 548
    assert [record["skill_code"] for record in inventory] == candidate_ids
    assert [record["stable_index"] for record in inventory] == list(range(548))
    assert [record["gamification_skill_id"] for record in bindings] == candidate_ids
    assert all(record["skill_candidate_id"] == record["gamification_skill_id"] for record in bindings)


def test_draft_skills_require_explicit_development_access() -> None:
    catalogue = load_development_skill_catalogue()
    skill_id = "G5-MAT-C03"

    with pytest.raises(PermissionError, match="both draft"):
        catalogue.resolve_candidate(skill_id)
    assert catalogue.resolve_candidate(skill_id, allow_draft=True) == skill_id
    with pytest.raises(LookupError, match="no skill binding"):
        catalogue.resolve_candidate("G5-MAT-C99", allow_draft=True)


def test_approved_skill_requires_review_metadata() -> None:
    review = load_skill_reviews()[0]
    with pytest.raises(ValueError, match="development-only"):
        replace(review, status=ReviewStatus.APPROVED)
    with pytest.raises(ValueError, match="reviewer identity"):
        replace(review, status=ReviewStatus.APPROVED, development_only=False)


def test_manifest_hashes_candidates_taxonomy_and_pinned_support_selection_bindings() -> None:
    manifest = json.loads(
        (SKILL_REVIEW_DATA_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["ownership"] == "gamification"
    assert manifest["component_owner"] == "hareeshagunasekara"
    assert manifest["counts"] == {
        "skills": 548,
        "bindings": 548,
        "crosswalk_rows": 548,
        "approved": 0,
    }
    file_sources = {name for name in manifest["sources"] if not name.startswith("git:")}
    assert file_sources == {
        "data/gamification/grade5-curriculum-game-dataset/v2/skill_candidates.jsonl",
        "docs/skill_nodes.xlsx",
    }
    assert [name for name in manifest["sources"] if name.startswith("git:")] == [
        "git:7033835:data/gamification/skill-catalogue-review/v1/grade5-candidate-skill-bindings.jsonl"
    ]
    for name, metadata in manifest["files"].items():
        path = SKILL_REVIEW_DATA_DIRECTORY / name
        assert path.stat().st_size == metadata["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
    for name in file_sources:
        metadata = manifest["sources"][name]
        assert hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() == metadata["sha256"]


def test_catalogue_has_no_other_component_dependency_names() -> None:
    package = PROJECT_ROOT / "backend/app/gamification/skill_catalogue"
    forbidden = ("knowledge_tracing", "adaptive_tutor")
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(name in text for name in forbidden)
