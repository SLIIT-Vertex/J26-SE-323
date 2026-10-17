import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.gamification.skill_catalogue import (
    ReviewStatus,
    UniversalSkillLink,
    load_universal_skill_crosswalk,
)
from app.gamification.skill_catalogue.json_repository import SKILL_REVIEW_DATA_DIRECTORY

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BUILDER_PATH = PROJECT_ROOT / "tools/gamification/skills/build_skill_review_package.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("skill_review_package_builder", BUILDER_PATH)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
sys.modules[BUILDER_SPEC.name] = BUILDER
BUILDER_SPEC.loader.exec_module(BUILDER)

CROSSWALK_PATH = SKILL_REVIEW_DATA_DIRECTORY / "universal-skill-crosswalk.jsonl"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def universal_skill_ids() -> set[str]:
    return {node.skill_id for node in XlsxSkillTaxonomyCatalog(BUILDER.TAXONOMY_WORKBOOK).load()}


def test_every_gamification_skill_has_exactly_one_draft_universal_parent() -> None:
    candidates = read_jsonl(BUILDER.SOURCE)
    rows = read_jsonl(CROSSWALK_PATH)
    links = load_universal_skill_crosswalk()

    assert len(rows) == len(links) == 548
    assert [row["gamification_skill_id"] for row in rows] == [
        candidate["skill_candidate_id"] for candidate in candidates
    ]
    assert {link.status for link in links.values()} == {ReviewStatus.DRAFT}
    assert {link.crosswalk_version for link in links.values()} == {"grade5-universal-crosswalk-v1"}
    assert all(row["reviewer_id"] is None and row["reviewed_on"] is None for row in rows)


def test_every_parent_exists_in_the_team_taxonomy_and_fits_learner_state() -> None:
    taxonomy = universal_skill_ids()
    parents = {link.universal_skill_id for link in load_universal_skill_crosswalk().values()}

    assert len(taxonomy) == 30
    assert parents <= taxonomy
    assert max(len(parent) for parent in parents) <= 16


def test_fractions_subtree_maps_to_the_fractions_universal_node() -> None:
    links = load_universal_skill_crosswalk()

    fractions = {skill_id for skill_id in links if skill_id.startswith("G5-MAT-C03")}
    assert fractions == {
        "G5-MAT-C03",
        "G5-MAT-C03-L01",
        "G5-MAT-C03-L01-O01",
        "G5-MAT-C03-L01-O02",
        "G5-MAT-C03-L01-O03",
    }
    assert {links[skill_id].universal_skill_id for skill_id in fractions} == {"MAT-FRC"}
    assert links["G5-MAT-C05-L01-O01"].universal_skill_id == "MAT-FRC"


def test_crosswalk_restores_the_pinned_support_selection_bindings() -> None:
    try:
        bindings, blob_sha256 = BUILDER.read_support_selection_bindings()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("Git history for the pinned skill-binding commit is not available")
    manifest = json.loads(
        (SKILL_REVIEW_DATA_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
    )
    source_key = f"git:{BUILDER.SUPPORT_SELECTION_BINDINGS_COMMIT}:{BUILDER.SUPPORT_SELECTION_BINDINGS_PATH}"

    assert manifest["sources"][source_key]["sha256"] == blob_sha256
    expected = BUILDER.build_crosswalk(read_jsonl(BUILDER.SOURCE), bindings, universal_skill_ids())
    assert read_jsonl(CROSSWALK_PATH) == expected
    by_candidate = {row["skill_candidate_id"]: row for row in bindings}
    for row in expected:
        source = by_candidate[row["gamification_skill_id"]]
        assert row["universal_skill_id"] == source["knowledge_tracing_skill_id"]
        assert row["source_binding_id"] == source["binding_id"]
    assert (
        hashlib.sha256(CROSSWALK_PATH.read_bytes()).hexdigest()
        == (manifest["files"]["universal-skill-crosswalk.jsonl"]["sha256"])
    )


def test_crosswalk_builder_rejects_unknown_or_missing_parents() -> None:
    candidates = [{"skill_candidate_id": "G5-MAT-C03"}]
    binding = {
        "skill_candidate_id": "G5-MAT-C03",
        "knowledge_tracing_skill_id": "MAT-XYZ",
        "mapping_version": "grade5-kt-skill-review-v1",
        "binding_id": "G5-MAT-C03--MAT-XYZ",
        "confidence": "high",
        "rationale": "test",
        "source_ids": ["SRC-G5-MAT-TG-01"],
    }

    with pytest.raises(ValueError, match="not in skill_nodes.xlsx"):
        BUILDER.build_crosswalk(candidates, [binding], {"MAT-FRC"})
    with pytest.raises(ValueError, match="exactly the current skill candidates"):
        BUILDER.build_crosswalk(
            candidates + [{"skill_candidate_id": "G5-MAT-C05"}], [binding], {"MAT-XYZ"}
        )


def test_universal_link_contract_enforces_identity_and_review_rules() -> None:
    link = load_universal_skill_crosswalk()["G5-MAT-C03-L01-O01"]

    with pytest.raises(ValueError, match="Universal Skill Node ID"):
        replace(link, universal_skill_id="G5-MAT-C03-L01-O01")
    with pytest.raises(ValueError, match="reviewer identity"):
        replace(link, status=ReviewStatus.APPROVED)
    assert isinstance(link, UniversalSkillLink)
