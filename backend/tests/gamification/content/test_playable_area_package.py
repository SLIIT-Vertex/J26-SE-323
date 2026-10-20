"""The playable-area package loads one loop for each shipped Grade 5 area."""

from __future__ import annotations

import hashlib
import inspect
import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.gamification.application.fixture_round import FixtureRoundService, reset_fixture_rounds
from app.gamification.content.area_support_catalog import GAME_SUPPORT_TYPES, assignment
from app.gamification.content.curriculum_registry import CURRICULUM_CONTENT_DIRECTORY
from app.gamification.content.draft_mission_catalog import (
    BLOCKED_AREA_IDS,
    load_draft_mission_catalog,
)
from app.gamification.content.playable_area_package import (
    PACKAGE_VERSION,
    PLAYABLE_AREA_PACKAGE_DIRECTORY,
    PlayableAreaRow,
    load_playable_area_package,
)

FIXTURE_AREAS = (
    "G5-AREA-MAT-01",
    "G5-AREA-MAT-02",
    "G5-AREA-MAT-04",
    "G5-AREA-MAT-05",
    "G5-AREA-MAT-06",
    "G5-AREA-MAT-08",
    "G5-AREA-MAT-10",
    "G5-AREA-MAT-15",
    "G5-AREA-MAT-03",
    "G5-AREA-MAT-13",
    "G5-AREA-MAT-14",
    "G5-AREA-MAT-07",
    "G5-AREA-MAT-09",
    "G5-AREA-MAT-11",
    "G5-AREA-MAT-12",
    "G5-AREA-MAT-16",
    "G5-AREA-SIN-03",
    "G5-AREA-SIN-04",
    "G5-AREA-SIN-05",
    "G5-AREA-SIN-06",
    "G5-AREA-SIN-07",
    "G5-AREA-SIN-08",
    "G5-AREA-SIN-09",
    "G5-AREA-SIN-10",
    "G5-AREA-SIN-11",
    "G5-AREA-SIN-12",
    "G5-AREA-SIN-13",
    "G5-AREA-SIN-01",
    "G5-AREA-SIN-02",
    "G5-AREA-SIN-14",
    "G5-AREA-SIN-15",
    "G5-AREA-SIN-16",
    "G5-AREA-SIN-17",
    "G5-AREA-SIN-18",
    "G5-AREA-SIN-19",
    "G5-AREA-SIN-20",
    "G5-AREA-SIN-21",
    "G5-AREA-SIN-22",
    "G5-AREA-SIN-23",
    "G5-AREA-SIN-24",
    "G5-AREA-SIN-25",
    "G5-AREA-ENV-01",
    "G5-AREA-ENV-02",
    "G5-AREA-ENV-03",
    "G5-AREA-ENV-04",
    "G5-AREA-ENV-05",
    "G5-AREA-ENV-06",
    "G5-AREA-ENV-07",
    "G5-AREA-ENV-08",
    "G5-AREA-ENV-09",
    "G5-AREA-ENV-10",
    "G5-AREA-ENV-11",
    "G5-AREA-ENV-12",
    "G5-AREA-ENV-13",
    "G5-AREA-ENV-14",
    "G5-AREA-ENV-15",
    "G5-AREA-ENV-16",
)
MARKET_GAME_AREAS = (
    "G5-AREA-MAT-01",
    "G5-AREA-MAT-02",
    "G5-AREA-MAT-04",
    "G5-AREA-MAT-06",
    "G5-AREA-MAT-08",
    "G5-AREA-MAT-10",
    "G5-AREA-MAT-15",
)

_PROMPT = "සැකිලි"
_RUBRIC = {
    "rubric_id": "schema-rubric",
    "rubric_version": "schema-v1",
    "scoring_version": "schema-v1",
    "maximum_score": 1,
    "server_authoritative": True,
    "correct_only_when_every_part_correct": True,
}


def _item(role: str, *, surface: str, answer: str, assistance: str) -> dict[str, object]:
    return {
        "measurement_role": role,
        "assistance_state": assistance,
        "item_revision_id": f"schema-{role}",
        "parallel_family_id": "schema-family",
        "prompt_si": _PROMPT,
        "surface_form": surface,
        "correct_response": answer,
        "rubric": dict(_RUBRIC),
    }


def _row(**overrides: object) -> dict[str, object]:
    """In-memory schema fixture. It is not written into the shipped package."""
    payload: dict[str, object] = {
        "area_id": "G5-AREA-MAT-01",
        "template_id": "market_mission",
        "source_status": "mapped_draft",
        "items": [
            _item(
                "unsupported_before",
                surface="surface-before",
                answer="answer-before",
                assistance="none",
            ),
            _item(
                "supported_practice",
                surface="surface-practice",
                answer="answer-practice",
                assistance="scaffold_active",
            ),
            _item(
                "unsupported_after",
                surface="surface-after",
                answer="answer-after",
                assistance="none",
            ),
        ],
        "eligible_support_types": [
            "visual_guidance",
            "worked_parallel_example",
            "step_by_step_guidance",
        ],
        "scaffold": {
            "support_type": "step_by_step_guidance",
            "body_si": _PROMPT,
            "answer_leakage_rule": "no_probe_values_or_answers",
        },
        "universal_skill_id": "MAT-NUM",
        "no_universal_parent": False,
        "prompt_si": _PROMPT,
        "curriculum_source_id": None,
    }
    payload.update(overrides)
    return payload


def test_empty_package_loads(tmp_path) -> None:
    payload = {
        "package_version": PACKAGE_VERSION,
        "authoring_basis": "package_contract_only",
        "areas": [],
    }
    data = (json.dumps(payload, indent=2) + "\n").encode()
    (tmp_path / "areas.json").write_bytes(data)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "authoring_basis": "package_contract_only",
                "files": {"areas.json": hashlib.sha256(data).hexdigest()},
                "package_version": PACKAGE_VERSION,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    package = load_playable_area_package(tmp_path)

    assert package.areas == ()
    assert package.authoring_basis == "package_contract_only"
    assert package.component_places.knowledge_tracing.mastery_reader == "MasteryProvider"
    assert package.component_places.knowledge_tracing.writes_tables is False
    assert package.component_places.adaptive_tutor.chooses_scaffold is False
    assert package.component_places.shared_learner.duplicates_learner_profile is False
    assert PlayableAreaRow.model_validate(_row()).area_id == "G5-AREA-MAT-01"


def test_shipped_package_has_one_fixture_per_shared_template() -> None:
    package = load_playable_area_package()

    assert tuple(row.area_id for row in package.areas) == FIXTURE_AREAS
    fractions = next(row for row in package.areas if row.area_id == "G5-AREA-MAT-05")
    assert fractions.template_id == "half_set"
    assert fractions.universal_skill_id == "MAT-FRC"
    story = next(row for row in package.areas if row.area_id == "G5-AREA-SIN-13")
    assert story.template_id == "story_studio"
    assert story.no_universal_parent is True
    assert story.universal_skill_id is None
    serialized = package.model_dump_json()
    assert "G5-MAT-C03-L01-O01" not in serialized


def test_shipped_package_lists_exactly_the_seven_market_games() -> None:
    package = load_playable_area_package()
    market_games = tuple(row for row in package.areas if row.template_id == "market_mission")

    assert tuple(row.area_id for row in market_games) == MARKET_GAME_AREAS
    assert all(
        row.eligible_support_types
        == ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
        for row in market_games
    )
    assert all(row.scaffold.support_type in row.eligible_support_types for row in market_games)
    assert all(
        tuple(item.measurement_role for item in row.items)
        == ("unsupported_before", "supported_practice", "unsupported_after")
        for row in market_games
    )
    assert all("Medium-confidence trace." in row.prompt_si for row in market_games)


def test_mathematics_development_list_has_sixteen_playable_areas() -> None:
    package = load_playable_area_package()
    catalog = load_draft_mission_catalog()
    expected = {
        "G5-AREA-MAT-01": "market_mission",
        "G5-AREA-MAT-02": "market_mission",
        "G5-AREA-MAT-03": "pattern_temple",
        "G5-AREA-MAT-04": "market_mission",
        "G5-AREA-MAT-05": "half_set",
        "G5-AREA-MAT-06": "market_mission",
        "G5-AREA-MAT-07": "parcel_workshop",
        "G5-AREA-MAT-08": "market_mission",
        "G5-AREA-MAT-09": "parcel_workshop",
        "G5-AREA-MAT-10": "market_mission",
        "G5-AREA-MAT-11": "parcel_workshop",
        "G5-AREA-MAT-12": "parcel_workshop",
        "G5-AREA-MAT-13": "pattern_temple",
        "G5-AREA-MAT-14": "pattern_temple",
        "G5-AREA-MAT-15": "market_mission",
        "G5-AREA-MAT-16": "word_workshop",
    }
    support = (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )
    roles = ("unsupported_before", "supported_practice", "unsupported_after")
    rows = {row.area_id: row for row in package.areas}

    assert tuple(expected) == tuple(
        f"G5-AREA-MAT-{index:02d}" for index in range(1, 17)
    )
    fractions = catalog.mission("G5-AREA-MAT-05")
    assert fractions.template_id == "half_set"
    assert any(slot.node_id == "G5-MAT-C03-L01-O01" for slot in fractions.outcome_slots)
    for area_id, template_id in expected.items():
        mission = catalog.mission(area_id)
        assert mission.template_id == template_id
        row = rows[area_id]
        assert row.template_id == template_id
        assert row.eligible_support_types == support
        assert row.scaffold.support_type in support
        assert tuple(item.measurement_role for item in row.items) == roles


def test_sinhala_form_areas_are_playable_word_workshop_loops() -> None:
    package = load_playable_area_package()
    catalog = load_draft_mission_catalog()
    form_areas = (
        "G5-AREA-SIN-01",
        "G5-AREA-SIN-02",
        *(f"G5-AREA-SIN-{index:02d}" for index in range(14, 26)),
    )
    support = (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )
    roles = ("unsupported_before", "supported_practice", "unsupported_after")
    rows = {row.area_id: row for row in package.areas}

    assert len(form_areas) == 14
    story = rows["G5-AREA-SIN-13"]
    assert story.prompt_si == "ආරාධනා පත්‍ර"
    assert story.items[0].prompt_si == "ආරාධනා පත්‍රයක පළමුව ලියන්නේ කුමක්ද?"
    spelling = rows["G5-AREA-SIN-16"]
    traced = catalog.mission("G5-AREA-SIN-16").draft_item_slots[0]
    assert traced.confidence == "high"
    assert traced.item_text in spelling.prompt_si
    assert "මෙය නිල ප්‍රශ්නයක් නොවේ." in spelling.prompt_si
    for area_id in form_areas:
        row = rows[area_id]
        mission = catalog.mission(area_id)
        assert row.template_id == "word_workshop"
        assert row.no_universal_parent is True
        assert row.universal_skill_id is None
        assert row.eligible_support_types == support
        assert row.scaffold.support_type in support
        assert tuple(item.measurement_role for item in row.items) == roles
        assert "මෙය නිල ප්‍රශ්නයක් නොවේ." in row.prompt_si
        visible = " ".join(item.prompt_si for item in row.items) + " " + row.scaffold.body_si
        for held in mission.held_slots:
            assert held.held is True
            assert held.traced_text not in visible
            assert held.traced_text not in row.prompt_si
        matched = [
            slot
            for slot in mission.draft_item_slots
            if slot.area_match and slot.confidence == "high"
        ]
        if matched:
            assert matched[0].item_text in row.prompt_si
            continue
        assert mission.draft_item_slots == ()
        assert traced.item_text not in row.prompt_si


def test_sinhala_verbal_relations_and_invitation_are_playable_with_exact_supports() -> None:
    package = load_playable_area_package()
    catalog = load_draft_mission_catalog()
    rows = {row.area_id: row for row in package.areas}
    verbal_ids = tuple(f"G5-AREA-SIN-{index:02d}" for index in range(3, 11))
    verbal_support = ("worked_parallel_example", "step_by_step_guidance")
    roles = ("unsupported_before", "supported_practice", "unsupported_after")

    assert set(verbal_ids) <= rows.keys()
    for area_id in verbal_ids:
        row = rows[area_id]
        mission = catalog.mission(area_id)
        assert row.template_id == "word_workshop"
        assert row.eligible_support_types == verbal_support
        assert row.scaffold.support_type == "worked_parallel_example"
        assert "visual_guidance" not in row.eligible_support_types
        assert tuple(item.measurement_role for item in row.items) == roles
        assert "මෙය නිල ප්‍රශ්නයක් නොවේ." in row.prompt_si
        visible = " ".join(item.prompt_si for item in row.items) + " " + row.scaffold.body_si
        for held in mission.held_slots:
            assert held.held is True
            assert held.traced_text not in visible
            assert held.traced_text not in row.prompt_si

    invitation = rows["G5-AREA-SIN-13"]
    assert invitation.template_id == "story_studio"
    assert invitation.eligible_support_types == (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )
    assert invitation.scaffold.support_type == "visual_guidance"
    assert "ආචාරය" in invitation.scaffold.body_si
    assert "පණිවිඩය" in invitation.scaffold.body_si
    assert "අවසාන ආචාරය" in invitation.scaffold.body_si
    assert all(item.prompt_si not in invitation.scaffold.body_si for item in invitation.items)
    visible = " ".join(item.prompt_si for item in invitation.items) + " " + invitation.scaffold.body_si
    for held in catalog.mission(invitation.area_id).held_slots:
        assert held.held is True
        assert held.traced_text not in visible


def test_no_source_placeholders_are_playable_without_source_citations() -> None:
    package = load_playable_area_package()
    raw_package = json.loads(
        (PLAYABLE_AREA_PACKAGE_DIRECTORY / "areas.json").read_text(encoding="utf-8")
    )
    rows = {row.area_id: row for row in package.areas}
    raw_rows = {row["area_id"]: row for row in raw_package["areas"]}
    support = (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )
    roles = ("unsupported_before", "supported_practice", "unsupported_after")

    for area_id in ("G5-AREA-SIN-11", "G5-AREA-SIN-12"):
        row = rows[area_id]
        raw = raw_rows[area_id]
        assert row.template_id == "word_workshop"
        assert row.source_status == "no_grade5_source"
        assert row.eligible_support_types == support
        assert row.no_universal_parent is True
        assert row.universal_skill_id is None
        assert row.curriculum_source_id is None
        assert tuple(item.measurement_role for item in row.items) == roles
        assert "5 ශ්‍රේණියේ මූලාශ්‍රයක් නොමැත" in row.prompt_si
        assert raw["curriculum_source_id"] is None
        for forbidden in (
            "source_document_id",
            "source_page",
            "page",
            "official_outcome_id",
            "cited_node_id",
        ):
            assert forbidden not in raw


def test_all_sixteen_environmental_areas_are_playable() -> None:
    package = load_playable_area_package()
    catalog = load_draft_mission_catalog()
    rows = {row.area_id: row for row in package.areas}
    included = tuple(f"G5-AREA-ENV-{index:02d}" for index in range(1, 17))
    support = (
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    )
    roles = ("unsupported_before", "supported_practice", "unsupported_after")
    parents = {
        "G5-AREA-ENV-09": "ENV-PHY",
        "G5-AREA-ENV-10": "ENV-AGR",
        "G5-AREA-ENV-11": "ENV-CIV",
        "G5-AREA-ENV-12": "ENV-CIV",
        "G5-AREA-ENV-13": "ENV-GEO",
        "G5-AREA-ENV-14": "ENV-CIV",
        "G5-AREA-ENV-15": "ENV-CIV",
        "G5-AREA-ENV-16": "ENV-CIV",
    }

    assert included == tuple(area_id for area_id in rows if area_id.startswith("G5-AREA-ENV-"))
    for area_id in included:
        row = rows[area_id]
        mission = catalog.mission(area_id)
        assert row.template_id == "eco_explorer"
        assert mission.template_id == "eco_explorer"
        assert row.eligible_support_types == support
        assert row.scaffold.support_type in support
        assert tuple(item.measurement_role for item in row.items) == roles
        assert "මෙය නිල ප්‍රශ්නයක් නොවේ." in row.prompt_si
        visible = " ".join(item.prompt_si for item in row.items) + " " + row.scaffold.body_si
        for held in mission.held_slots:
            assert held.confidence == "low"
            assert held.held is True
            assert held.traced_text not in visible
            assert held.traced_text not in row.prompt_si

    assert rows["G5-AREA-ENV-05"].universal_skill_id is None
    assert rows["G5-AREA-ENV-05"].no_universal_parent is True
    for area_id, parent in parents.items():
        assert rows[area_id].universal_skill_id == parent
        assert rows[area_id].no_universal_parent is False
    assert package.component_places.curriculum_retrieval.missing_passage_blocks_play is False
    assert package.component_places.curriculum_retrieval.absence_statuses == (
        "NO_RELEVANT_PASSAGES",
        "NO_APPROVED_SOURCE",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_ERROR",
    )
    assert package.component_places.knowledge_tracing.writes_tables is False
    assert package.component_places.knowledge_tracing.model_ingestion_eligible is False
    assert package.component_places.learner_state.missing_result_rejects_answer is False
    assert package.component_places.adaptive_tutor.chooses_scaffold is False
    assert package.component_places.participation_reward.academic_mastery_evidence is False


_ANSWER_KEY_FIELDS = frozenset(
    {
        "correct_response",
        "correct_option_id",
        "answer_key",
        "rubric",
        "server_answer_keys",
    }
)
_INVENTORY = {
    **{
        f"G5-AREA-MAT-{index:02d}": (
            {
                1: "market_mission",
                2: "market_mission",
                3: "pattern_temple",
                4: "market_mission",
                5: "half_set",
                6: "market_mission",
                7: "parcel_workshop",
                8: "market_mission",
                9: "parcel_workshop",
                10: "market_mission",
                11: "parcel_workshop",
                12: "parcel_workshop",
                13: "pattern_temple",
                14: "pattern_temple",
                15: "market_mission",
                16: "word_workshop",
            }[index],
            "mapped_draft",
        )
        for index in range(1, 17)
    },
    **{
        f"G5-AREA-SIN-{index:02d}": (
            "story_studio" if index == 13 else "word_workshop",
            "no_grade5_source" if index in {11, 12} else "mapped_draft",
        )
        for index in range(1, 26)
    },
    **{
        f"G5-AREA-ENV-{index:02d}": ("eco_explorer", "mapped_draft")
        for index in range(1, 17)
    },
}


def _contains_answer_key(value: object) -> bool:
    if isinstance(value, dict):
        return bool(_ANSWER_KEY_FIELDS.intersection(value)) or any(
            _contains_answer_key(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_answer_key(child) for child in value)
    return False


def test_inventory_loads_every_playable_area() -> None:
    package = load_playable_area_package()
    catalog = load_draft_mission_catalog()
    rows = {row.area_id: row for row in package.areas}
    roles = ("unsupported_before", "supported_practice", "unsupported_after")
    curriculum_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in CURRICULUM_CONTENT_DIRECTORY.glob("*.json")
    )

    assert len(_INVENTORY) == 57
    assert sum(area.startswith("G5-AREA-MAT-") for area in _INVENTORY) == 16
    assert sum(area.startswith("G5-AREA-SIN-") for area in _INVENTORY) == 25
    assert sum(area.startswith("G5-AREA-ENV-") for area in _INVENTORY) == 16
    assert package.component_places.curriculum_retrieval.index_as_curriculum_evidence is False

    fractions = catalog.mission("G5-AREA-MAT-05")
    assert fractions.template_id == "half_set"
    assert any(slot.node_id == "G5-MAT-C03-L01-O01" for slot in fractions.outcome_slots)
    assert rows["G5-AREA-MAT-05"].template_id == "half_set"

    reset_fixture_rounds()
    service = FixtureRoundService()
    for area_id, (template_id, source_status) in _INVENTORY.items():
        row = rows[area_id]
        mission = None if area_id in BLOCKED_AREA_IDS else catalog.mission(area_id)
        assert row.template_id == template_id
        assert row.source_status == source_status
        assert tuple(item.measurement_role for item in row.items) == roles
        assert all(item.rubric.server_authoritative is True for item in row.items)
        assert all(item.rubric.maximum_score > 0 for item in row.items)
        if area_id in BLOCKED_AREA_IDS:
            assert source_status == "no_grade5_source"
            assert row.curriculum_source_id is None
            assert row.eligible_support_types == GAME_SUPPORT_TYPES
        else:
            assert mission is not None
            assert mission.template_id == template_id
            assert row.eligible_support_types == assignment(area_id).eligible_support_types
        assert row.scaffold.support_type in row.eligible_support_types
        for item in row.items:
            assert item.prompt_si not in curriculum_text
        assert row.prompt_si not in curriculum_text

        learner_id = uuid4()
        opened = service.open_round(
            area_id=area_id,
            learner_id=learner_id,
            session_id=uuid4(),
            grade=5,
            medium="si",
        )
        assert not _contains_answer_key(opened)
        episode_id = opened["episode_id"]
        assert isinstance(episode_id, str)
        before_item = next(
            item for item in row.items if item.measurement_role == "unsupported_before"
        )
        options = opened["options"]
        assert isinstance(options, list)
        option_id = next(
            option["option_id"]
            for option in options
            if option["text_si"] == before_item.correct_response
        )
        answered = service.answer(
            UUID(episode_id),
            option_id=str(option_id),
            learner_id=learner_id,
        )
        assert not _contains_answer_key(answered)
        practiced = service.continue_round(UUID(episode_id), learner_id=learner_id)
        assert not _contains_answer_key(practiced)
        practice_item = next(
            item for item in row.items if item.measurement_role == "supported_practice"
        )
        practice_options = practiced["options"]
        assert isinstance(practice_options, list)
        practice_option = next(
            option["option_id"]
            for option in practice_options
            if option["text_si"] == practice_item.correct_response
        )
        withdrawn = service.answer(
            UUID(episode_id),
            option_id=str(practice_option),
            learner_id=learner_id,
        )
        assert not _contains_answer_key(withdrawn)
        after = service.continue_round(UUID(episode_id), learner_id=learner_id)
        assert not _contains_answer_key(after)
        after_item = next(
            item for item in row.items if item.measurement_role == "unsupported_after"
        )
        after_options = after["options"]
        assert isinstance(after_options, list)
        after_option = next(
            option["option_id"]
            for option in after_options
            if option["text_si"] == after_item.correct_response
        )
        finished = service.answer(
            UUID(episode_id),
            option_id=str(after_option),
            learner_id=learner_id,
        )
        assert finished["phase"] == "completed"
        assert not _contains_answer_key(finished)
        evidence = service.evidence(UUID(episode_id))
        assert len(evidence) == 3
        assert all(record["model_ingestion_eligible"] is False for record in evidence)
        assert all(record["curriculum_passage_status"] == "NO_RELEVANT_PASSAGES" for record in evidence)
        assert all(record["skill_id"] != "G5-MAT-C03-L01-O01" for record in evidence)

    assert len(rows) == 57
    assert "fixture-rubric-v1" not in curriculum_text
    assert "market-rubric-v1" not in curriculum_text


def test_loader_returns_the_same_games_when_the_process_is_production(monkeypatch) -> None:
    assert set(inspect.signature(load_playable_area_package).parameters) == {"path"}
    first = load_playable_area_package()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENV", "production")
    second = load_playable_area_package()

    assert len(first.areas) == 57
    assert first.model_dump() == second.model_dump()


def test_missing_unsupported_after_raises() -> None:
    payload = _row()
    items = payload["items"]
    assert isinstance(items, list)
    payload["items"] = [item for item in items if item["measurement_role"] != "unsupported_after"]

    with pytest.raises(ValidationError, match="unsupported_after"):
        PlayableAreaRow.model_validate(payload)


def test_verbal_relation_visual_guidance_raises() -> None:
    payload = _row(
        area_id="G5-AREA-SIN-03",
        template_id="word_workshop",
        eligible_support_types=[
            "visual_guidance",
            "worked_parallel_example",
            "step_by_step_guidance",
        ],
    )

    with pytest.raises(ValidationError, match="visual_guidance"):
        PlayableAreaRow.model_validate(payload)


def test_placeholder_with_a_source_citation_raises() -> None:
    payload = _row(
        area_id="G5-AREA-SIN-11",
        template_id="word_workshop",
        source_status="no_grade5_source",
        universal_skill_id=None,
        no_universal_parent=True,
        curriculum_source_id="SRC-EXAMPLE",
    )

    with pytest.raises(ValidationError, match="curriculum source citation"):
        PlayableAreaRow.model_validate(payload)
