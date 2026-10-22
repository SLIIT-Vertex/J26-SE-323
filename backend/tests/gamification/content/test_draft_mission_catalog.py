"""The draft mission catalog is development-only and fails closed in production."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gamification.content.draft_mission_catalog import (
    DRAFT_MISSION_CATALOG_DIRECTORY,
    MEDIUM_CONFIDENCE_CAVEAT,
    load_draft_mission_catalog,
)

ROOT = Path(__file__).resolve().parents[4]
COVERAGE = (
    ROOT
    / "research"
    / "adaptive_gamified_learning_plan"
    / "coverage"
    / "grade5-supplied-area-coverage-v1.jsonl"
)
BLOCKED_AREA_IDS = ("G5-AREA-SIN-11", "G5-AREA-SIN-12")
EXISTING_HALF_SET_SKILL_ID = "G5-MAT-C03-L01-O01"
MISSION_FIELDS = {
    "area_id",
    "cited_node_id",
    "development_only",
    "draft_item_slots",
    "held_slots",
    "outcome_slots",
    "publication_status",
    "template_id",
}
DRAFT_ITEM_FIELDS = {
    "area_match",
    "confidence",
    "draft_item",
    "item_text",
    "node_id",
    "parent_area_id",
    "publication_status",
}
HELD_FIELDS = {
    "child_question",
    "confidence",
    "draft_item",
    "held",
    "node_id",
    "parent_area_id",
    "publication_status",
    "traced_text",
}
SLOT_FIELDS = {
    "confidence",
    "draft_item",
    "item_text",
    "node_id",
    "parent_area_id",
    "publication_status",
    "supplied_area_match",
    "trace_competency_id",
}
TRACE = ROOT / "data" / "curriculum" / "grade5-curriculum-trace" / "v1" / "curriculum_nodes.jsonl"
CURRICULUM_SLICE = (
    ROOT / "data" / "gamification" / "grade5-sinhala-curriculum-slice" / "v1" / "public_content.json"
)

# Assignments from the draft-app plan. Shapes use Pattern Temple. Roman numerals
# use the existing Word Workshop mechanic. The two blocked Sinhala areas are omitted.
EXPECTED_TEMPLATES = {
    "market_mission": {
        "G5-AREA-MAT-01",
        "G5-AREA-MAT-02",
        "G5-AREA-MAT-04",
        "G5-AREA-MAT-06",
        "G5-AREA-MAT-08",
        "G5-AREA-MAT-10",
        "G5-AREA-MAT-15",
    },
    "half_set": {"G5-AREA-MAT-05"},
    "pattern_temple": {"G5-AREA-MAT-03", "G5-AREA-MAT-13", "G5-AREA-MAT-14"},
    "parcel_workshop": {
        "G5-AREA-MAT-07",
        "G5-AREA-MAT-09",
        "G5-AREA-MAT-11",
        "G5-AREA-MAT-12",
    },
    "story_studio": {"G5-AREA-SIN-13"},
    "pillam_journey": {"G5-AREA-SIN-01"},
    "punctuation_journey": {"G5-AREA-SIN-02"},
    "riddle_journey": {"G5-AREA-SIN-03"},
    "eco_explorer": {f"G5-AREA-ENV-{number:02d}" for number in range(1, 17)},
}
EXPECTED_TEMPLATES["word_workshop"] = {
    "G5-AREA-MAT-16",
    *(f"G5-AREA-SIN-{number:02d}" for number in range(4, 11)),
    *(f"G5-AREA-SIN-{number:02d}" for number in range(14, 26) if number != 16),
}
# Outcomes once traced to the retired G5-AREA-SIN-16 area; no mission carries them now.
RETIRED_SINHALA_NODES = frozenset(
    {
        "G5-SIN-C04-L10-O08",
        "G5-SIN-C04-L01-O01",
        "G5-SIN-C04-L01-O02",
        "G5-SIN-C04-L03-O01",
        "G5-SIN-C04-L06-O01",
        "G5-SIN-C04-L06-O02",
        "G5-SIN-C04-L06-O03",
        "G5-SIN-C04-L06-O04",
        "G5-SIN-C04-L06-O05",
        "G5-SIN-C04-L07-O01",
        "G5-SIN-C04-L09-O01",
    }
)


def _coverage_rows() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in COVERAGE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _development_catalog():
    return load_draft_mission_catalog()


def test_development_load_returns_54_missions() -> None:
    catalog = _development_catalog()
    area_ids = [mission.area_id for mission in catalog.missions]

    assert len(catalog.missions) == 54
    assert len(set(area_ids)) == 54
    assert area_ids[:16] == [f"G5-AREA-MAT-{number:02d}" for number in range(1, 17)]
    assert area_ids[16:38] == [
        f"G5-AREA-SIN-{number:02d}" for number in range(1, 26) if number not in {11, 12, 16}
    ]
    assert area_ids[38:] == [f"G5-AREA-ENV-{number:02d}" for number in range(1, 17)]
    assert catalog.development_only is True
    assert catalog.publication_status == "blocked"
    assert all(mission.development_only is True for mission in catalog.missions)
    assert all(mission.publication_status == "blocked" for mission in catalog.missions)


def test_loader_reads_the_catalog_without_a_runtime_switch() -> None:
    catalog = load_draft_mission_catalog()
    assert len(catalog.missions) == 54


def test_blocked_areas_are_absent() -> None:
    catalog = _development_catalog()
    area_ids = {mission.area_id for mission in catalog.missions}
    raw = (DRAFT_MISSION_CATALOG_DIRECTORY / "missions.json").read_text(encoding="utf-8")

    assert BLOCKED_AREA_IDS[0] not in area_ids
    assert BLOCKED_AREA_IDS[1] not in area_ids
    assert BLOCKED_AREA_IDS[0] not in raw
    assert BLOCKED_AREA_IDS[1] not in raw
    with pytest.raises(KeyError):
        catalog.mission("G5-AREA-SIN-11")
    with pytest.raises(KeyError):
        catalog.mission("G5-AREA-SIN-12")


def test_each_area_uses_its_assigned_template() -> None:
    catalog = _development_catalog()
    actual = {mission.area_id: mission.template_id for mission in catalog.missions}
    assigned = set().union(*EXPECTED_TEMPLATES.values())

    assert assigned == set(actual)
    assert sum(len(areas) for areas in EXPECTED_TEMPLATES.values()) == 54
    for template_id, areas in EXPECTED_TEMPLATES.items():
        assert {area_id: actual[area_id] for area_id in areas} == dict.fromkeys(areas, template_id)


@pytest.mark.requires_research
def test_cited_nodes_come_from_mapped_draft_rows() -> None:
    catalog = _development_catalog()
    rows = _coverage_rows()
    mapped = [row for row in rows if row["mapping_status"] == "MAPPED_DRAFT"]
    cited: dict[str, str] = {}
    for row in mapped:
        outcome = row["outcome_or_competency"]
        assert isinstance(outcome, dict)
        cited[str(row["area_id"])] = str(outcome["node_id"])

    assert len(mapped) == 54
    assert {mission.area_id: mission.cited_node_id for mission in catalog.missions} == cited
    fractions = catalog.mission("G5-AREA-MAT-05")
    assert fractions.cited_node_id == "G5-MAT-C03"
    assert fractions.template_id == "half_set"
    assert fractions.cited_node_id != EXISTING_HALF_SET_SKILL_ID


@pytest.mark.requires_research
def test_package_omits_games_english_rows_and_the_2009_guide() -> None:
    raw = json.loads(
        (DRAFT_MISSION_CATALOG_DIRECTORY / "missions.json").read_text(encoding="utf-8")
    )
    text = json.dumps(raw)

    assert set(raw) == {
        "development_only",
        "missions",
        "package_version",
        "publication_status",
    }
    assert all(set(mission) == MISSION_FIELDS for mission in raw["missions"])
    assert "games.jsonl" not in text
    assert "SRC-G5-MAT-TG-02" not in text
    assert "2009" not in text
    assert "name_en" not in text
    assert "text_en" not in text
    assert "correct_option_id" not in text
    assert all(row["subject"] != "ENG" for row in _coverage_rows())
    assert not any(mission["area_id"].startswith("G5-AREA-ENG") for mission in raw["missions"])
    assert all(
        set(slot) == SLOT_FIELDS for mission in raw["missions"] for slot in mission["outcome_slots"]
    )
    assert all(
        set(slot) == DRAFT_ITEM_FIELDS
        for mission in raw["missions"]
        for slot in mission["draft_item_slots"]
    )
    assert all(set(slot) == HELD_FIELDS for mission in raw["missions"] for slot in mission["held_slots"])
    assert all(
        slot["child_question"] is None for mission in raw["missions"] for slot in mission["held_slots"]
    )


def _trace_nodes() -> list[dict[str, object]]:
    return [
        json.loads(line) for line in TRACE.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_mathematics_missions_carry_65_unapproved_outcome_slots() -> None:
    catalog = _development_catalog()
    nodes = {str(node["curriculum_node_id"]): node for node in _trace_nodes()}
    mathematics = [mission for mission in catalog.missions if mission.area_id.startswith("G5-AREA-MAT-")]
    others = [mission for mission in catalog.missions if mission not in mathematics]
    slots = [slot for mission in mathematics for slot in mission.outcome_slots]
    outcomes = [
        node
        for node in nodes.values()
        if node["subject"] == "MAT" and node["node_type"] == "learning_outcome"
    ]

    assert len(mathematics) == 16
    assert len(outcomes) == 65
    assert len(slots) == 65
    assert {slot.node_id for slot in slots} == {str(node["curriculum_node_id"]) for node in outcomes}
    assert all(slot.confidence == "medium" for slot in slots)
    assert all(slot.draft_item is True for slot in slots)
    assert all(slot.publication_status == "blocked" for slot in slots)
    assert all(MEDIUM_CONFIDENCE_CAVEAT in slot.item_text for slot in slots)
    assert all(others_mission.outcome_slots == () for others_mission in others)
    for slot in slots:
        outcome = nodes[slot.node_id]
        sentence = str(outcome["text_primary"])
        assert slot.item_text.startswith(sentence)
        assert outcome["extraction_confidence"] == "medium"
        level = nodes[str(outcome["parent_node_id"])]
        competency_id = str(level["parent_node_id"])
        assert slot.trace_competency_id == competency_id
        assert slot.parent_area_id.startswith("G5-AREA-MAT-")
        if slot.supplied_area_match:
            assert catalog.mission(slot.parent_area_id).cited_node_id == competency_id
        else:
            assert competency_id in {"G5-MAT-C10", "G5-MAT-C19"}
            assert competency_id in slot.item_text

    half = next(slot for slot in slots if slot.node_id == EXISTING_HALF_SET_SKILL_ID)
    assert half.parent_area_id == "G5-AREA-MAT-05"
    assert half.draft_item is True
    assert half.publication_status == "blocked"
    slice_package = json.loads(CURRICULUM_SLICE.read_text(encoding="utf-8"))
    assert slice_package["skill"]["skill_id"] == EXISTING_HALF_SET_SKILL_ID
    assert half.item_text != slice_package["source"]["exact_outcome_si"]


def test_remaining_outcomes_are_draft_items_or_held_slots() -> None:
    catalog = _development_catalog()
    nodes = {str(node["curriculum_node_id"]): node for node in _trace_nodes()}
    buildable = {mission.area_id for mission in catalog.missions}
    sinhala = [mission for mission in catalog.missions if mission.area_id.startswith("G5-AREA-SIN-")]
    environmental = [
        mission for mission in catalog.missions if mission.area_id.startswith("G5-AREA-ENV-")
    ]
    mathematics = [
        mission for mission in catalog.missions if mission.area_id.startswith("G5-AREA-MAT-")
    ]
    draft_items = [slot for mission in sinhala for slot in mission.draft_item_slots]
    sinhala_held = [slot for mission in sinhala for slot in mission.held_slots]
    environmental_held = [slot for mission in environmental for slot in mission.held_slots]
    high = [
        node
        for node in nodes.values()
        if node["subject"] == "SIN"
        and node["node_type"] == "learning_outcome"
        and node["grade"] == 5
        and node["extraction_confidence"] == "high"
        and node["curriculum_node_id"] not in RETIRED_SINHALA_NODES
    ]
    low = [
        node
        for node in nodes.values()
        if node["subject"] == "SIN"
        and node["node_type"] == "learning_outcome"
        and node["grade"] == 5
        and node["extraction_confidence"] == "low"
        and node["curriculum_node_id"] not in RETIRED_SINHALA_NODES
    ]
    environmental_outcomes = [
        node
        for node in nodes.values()
        if node["subject"] == "ENV"
        and node["node_type"] == "learning_outcome"
        and node["grade"] == 5
    ]
    cited = {mission.cited_node_id: mission.area_id for mission in sinhala}

    assert len(draft_items) == len(high) == 7
    assert len(sinhala_held) == len(low) == 66
    assert len(environmental_held) == len(environmental_outcomes) == 117
    assert {slot.node_id for slot in draft_items} == {str(node["curriculum_node_id"]) for node in high}
    assert {slot.node_id for slot in sinhala_held} == {str(node["curriculum_node_id"]) for node in low}
    assert {slot.node_id for slot in environmental_held} == {
        str(node["curriculum_node_id"]) for node in environmental_outcomes
    }
    assert all(slot.child_question is None for slot in (*sinhala_held, *environmental_held))
    assert all(slot.draft_item is False and slot.held is True for slot in sinhala_held)
    assert all(slot.draft_item is False and slot.held is True for slot in environmental_held)
    assert all(slot.confidence == "low" and slot.publication_status == "blocked" for slot in sinhala_held)
    assert all(
        slot.confidence == "low" and slot.publication_status == "blocked" for slot in environmental_held
    )
    assert all(slot.draft_item is True and slot.publication_status == "blocked" for slot in draft_items)
    assert all(mission.draft_item_slots == () and mission.held_slots == () for mission in mathematics)
    assert all(mission.draft_item_slots == () for mission in environmental)
    assert buildable.isdisjoint(BLOCKED_AREA_IDS)
    for slot in draft_items:
        outcome = nodes[slot.node_id]
        assert slot.item_text == outcome["text_primary"]
        assert slot.confidence == "high"
        if slot.node_id in cited:
            assert slot.parent_area_id == cited[slot.node_id]
            assert slot.area_match is True
        else:
            assert slot.node_id in {
                "G5-SIN-C04-L10-O03",
                "G5-SIN-C04-L10-O04",
                "G5-SIN-C04-L10-O05",
            }
            assert slot.parent_area_id == "G5-AREA-SIN-22"
            assert slot.area_match is False
    for slot in (*sinhala_held, *environmental_held):
        outcome = nodes[slot.node_id]
        assert slot.traced_text == outcome["text_primary"]
        assert outcome["text_en"] not in {slot.traced_text, None}
        assert slot.parent_area_id in buildable
        assert slot.parent_area_id not in BLOCKED_AREA_IDS
    for slot in environmental_held:
        lesson = nodes[catalog.mission(slot.parent_area_id).cited_node_id]
        outcome = nodes[slot.node_id]
        start = int(str(lesson["source_page_from"]))
        end = int(str(lesson["source_page_to"]))
        assert start <= int(str(outcome["source_page_from"])) <= end
        assert start <= int(str(outcome["source_page_to"])) <= end


