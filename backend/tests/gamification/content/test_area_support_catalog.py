"""The area support catalog is provisional and fails closed in production."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gamification.content.area_support_catalog import (
    GAME_SUPPORT_TYPES,
    MATHEMATICS_SUPPORT_TYPES,
    VERBAL_RELATION_AREAS,
    assignment,
    load_area_support_catalog,
)
from app.gamification.content.draft_mission_catalog import mapped_area_ids
from app.gamification.modeling.support_selection.selection import ACTION_TYPES

ROOT = Path(__file__).resolve().parents[4]
COVERAGE = (
    ROOT
    / "research"
    / "adaptive_gamified_learning_plan"
    / "coverage"
    / "grade5-supplied-area-coverage-v1.jsonl"
)
DOCUMENT = (
    ROOT / "research" / "adaptive_gamified_learning_plan" / "coverage" / "area-support-types.md"
)
BLOCKED_AREA_IDS = ("G5-AREA-SIN-11", "G5-AREA-SIN-12")


def _development_catalog():
    return load_area_support_catalog()


def _coverage_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for line in COVERAGE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        names[str(row["area_id"])] = str(row["name_en"])
    return names


@pytest.mark.requires_research
def test_every_mapped_area_has_a_provisional_candidate_set() -> None:
    catalog = _development_catalog()
    names = _coverage_names()
    document = DOCUMENT.read_text(encoding="utf-8")

    assert tuple(row.area_id for row in catalog.rows) == mapped_area_ids()
    assert BLOCKED_AREA_IDS[0] not in {row.area_id for row in catalog.rows}
    assert BLOCKED_AREA_IDS[1] not in {row.area_id for row in catalog.rows}
    assert catalog.development_only is True
    assert catalog.publication_status == "blocked"
    assert catalog.authoring_basis == "provisional_development_assumption"
    assert catalog.review_status == "unreviewed"
    for row in catalog.rows:
        expected = assignment(row.area_id)
        assert row.name_en == names[row.area_id]
        assert row.template_id == expected.template_id
        assert row.eligible_support_types == expected.eligible_support_types
        allowed = (
            MATHEMATICS_SUPPORT_TYPES if row.subject == "MAT" else GAME_SUPPORT_TYPES
        )
        assert set(row.eligible_support_types) <= set(allowed)
        assert len(row.eligible_support_types) >= 2
        assert row.authoring_basis == "provisional_development_assumption"
        assert row.review_status == "unreviewed"
        assert f"`{row.area_id}`" in document
        assert row.name_en in document


def test_verbal_relation_areas_leave_out_a_depicting_visual() -> None:
    catalog = _development_catalog()

    # SIN-03 (riddles) left the verbal-relation rule for its own riddle_inference rule.
    assert len(VERBAL_RELATION_AREAS) == 7
    for area_id in VERBAL_RELATION_AREAS:
        choices = catalog.choices(area_id)
        assert choices == ("worked_parallel_example", "step_by_step_guidance")
        assert catalog.row(area_id).rule == "verbal_relation"
    others = [
        row
        for row in catalog.rows
        if row.area_id not in VERBAL_RELATION_AREAS and row.subject != "MAT"
    ]
    assert catalog.row("G5-AREA-SIN-03").rule == "riddle_inference"
    assert all(row.eligible_support_types == GAME_SUPPORT_TYPES for row in others)


def test_fractions_area_matches_the_game_model_actions() -> None:
    catalog = _development_catalog()

    assert GAME_SUPPORT_TYPES == ACTION_TYPES
    assert catalog.choices("G5-AREA-MAT-05") == MATHEMATICS_SUPPORT_TYPES
    assert catalog.row("G5-AREA-MAT-05").template_id == "half_set"


def test_blocked_and_unknown_areas_have_no_assignment() -> None:
    for area_id in (*BLOCKED_AREA_IDS, "G5-AREA-MAT-17"):
        with pytest.raises(ValueError):
            assignment(area_id)
    catalog = _development_catalog()
    with pytest.raises(KeyError):
        catalog.choices(BLOCKED_AREA_IDS[0])


def test_loader_reads_the_catalog_without_a_runtime_switch() -> None:
    catalog = load_area_support_catalog()
    assert len(catalog.rows) == 54
