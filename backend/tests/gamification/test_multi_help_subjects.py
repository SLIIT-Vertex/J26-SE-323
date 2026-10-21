"""The multi-help loop across every Mathematics and English game.

The single-episode rules (escalation, rollback, idempotency, Model 3) are tested on one game in
``test_multi_help_support_loop``. These tests check that every Mathematics and English flow follows
the same loop with its own simpler version, and that English uses its own order and wording.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
)
from app.gamification.application.support_builders import difficulty
from app.gamification.application.support_builders.cues import ENGLISH, MATHEMATICS
from app.gamification.content.area_support_catalog import assignment
from app.gamification.content.simpler_items import fewer_pairs, pair_count
from app.gamification.content.support_types import SUPPORT_TYPES
from app.gamification.infrastructure.db.models import LearningFlowSupportRoundModel
from app.gamification.modeling.support_selection.support_order import (
    ENGLISH_ORDER,
    MATHEMATICS_ORDER,
    choose_support_order,
    reason_family,
)
from tests.gamification.support_loop_helpers import (
    MATHEMATICS_AREAS,
    correct_answer,
    flow_for,
    orchestrator_with_learner,
    wrong_answer,
)

ENGLISH_AREAS = {
    "G5-AREA-ENG-01": "ClassroomActionQuestFlow",
    "G5-AREA-ENG-02": "SriLankaDiscoveryFlow",
    "G5-AREA-ENG-03": "PlantExplorerFlow",
    "G5-AREA-ENG-04": "WildlifeRangerFlow",
    "G5-AREA-ENG-05": "EverydayObjectQuestFlow",
    "G5-AREA-ENG-06": "IslandFoodFestivalFlow",
    "G5-AREA-ENG-07": "RainbowWardrobeQuestFlow",
    "G5-AREA-ENG-08": "WaterWorksAdventureFlow",
    "G5-AREA-ENG-09": "TransitTerminalQuestFlow",
    "G5-AREA-ENG-10": "BloomBuilderGardenFlow",
    "G5-AREA-ENG-11": "WorkplaceLinkCityFlow",
    "G5-AREA-ENG-12": "FamilyWordConstellationFlow",
    "G5-AREA-ENG-13": "EarthSkyExplorerFlow",
    "G5-AREA-ENG-14": "BlueprintQuestFlow",
    "G5-AREA-ENG-15": "InformationStationFlow",
    "G5-AREA-ENG-16": "HeritageMuseumQuestFlow",
    "G5-AREA-ENG-17": "ClassroomLanguageLiveFlow",
    "G5-AREA-ENG-18": "ConversationStreetFlow",
}
MULTI_HELP_AREAS = {**MATHEMATICS_AREAS, **ENGLISH_AREAS}
# Skills whose task is already the smallest of its kind: shading one half or one quarter, the one
# km-to-m fact, two-chunk names, two-choice items, and a reply sentence that cannot be cut.
NO_DESIGNED_SIMPLER_FORM = frozenset(
    {
        "G5-MAT-FRC-HALF-WHOLE-01",
        "G5-MAT-FRC-QUARTER-WHOLE-01",
        "G5-MAT-LENGTH-RELATION-01",
        "G5-ENG-OBJECT-NAME-03",
        "G5-ENG-FOOD-NAME-03",
        "G5-ENG-PLACE-NAME-03",
        "G5-ENG-CLASS-COMMAND-02",
        "G5-ENG-CLASS-QUESTION-04",
        "G5-ENG-CONV-FRAME-03",
        "G5-ENG-CONV-DESCRIBE-04",
    }
)
ENGLISH_CONTENT_MODULES = (
    "classroom_action_quest",
    "sri_lanka_discovery",
    "plant_explorer",
    "wildlife_ranger",
    "everyday_object_quest",
    "island_food_festival",
    "rainbow_wardrobe_quest",
    "water_works_adventure",
    "transit_terminal_quest",
    "bloom_builder_garden",
    "workplace_link_city",
    "family_word_constellation",
    "earth_sky_explorer",
    "blueprint_quest",
    "information_station",
    "heritage_museum_quest",
    "classroom_language_live",
    "conversation_street",
)
MATHEMATICS_CONTENT_MODULES = (
    "number_world",
    "addition_adventure",
    "number_patterns",
    "subtraction_adventure",
    "fraction_adventure",
    "multiplication_adventure",
    "time_adventure",
    "division_adventure",
    "distance_adventure",
    "money_adventure",
    "capacity_adventure",
    "mass_adventure",
    "shape_adventure",
    "direction_adventure",
    "decimal_adventure",
    "roman_adventure",
)


def _skills() -> list[tuple[str, str]]:
    orchestrator, _session = orchestrator_with_learner(uuid4())
    return [
        (area, skill) for area in MULTI_HELP_AREAS for skill in flow_for(orchestrator, area).skills
    ]


def _failed(area: str, skill: str, *, condition: str = "baseline"):
    learner = uuid4()
    orchestrator, session = orchestrator_with_learner(learner)
    opened = orchestrator.open_episode(
        learner_id=learner,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition=condition,
        environment="test",
        allow_draft=True,
        area_id=area,
        atomic_skill_id=skill,
        idempotency_key=f"open:{uuid4()}",
    )
    episode_id = UUID(str(opened["episode_id"]))
    game_flow = flow_for(orchestrator, area)
    state = orchestrator.reconstruct(episode_id)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    shown = orchestrator.submit_before(
        episode_id,
        option_id=None,
        constructed_response=wrong_answer(game_flow, before),
        response_time_ms=400,
        interaction_summary={},
        idempotency_key=f"before:{uuid4()}",
    )
    return orchestrator, session, game_flow, episode_id, shown


def test_every_mathematics_and_english_flow_runs_the_loop_with_its_own_simpler_version():
    orchestrator, _session = orchestrator_with_learner(uuid4())
    for area, flow in orchestrator._area_flows.items():
        multi_help = area in MULTI_HELP_AREAS
        assert getattr(flow, "runs_support_loop", False) is multi_help, area
        if multi_help:
            assert type(flow).__name__ == MULTI_HELP_AREAS[area]
            # A flow that inherited another game's generator would make that game's items.
            assert "generate_simpler_item" in type(flow).__dict__, area
            assert assignment(area).eligible_support_types == SUPPORT_TYPES


@pytest.mark.parametrize(("area", "skill"), _skills())
def test_designed_simpler_version_is_the_same_skill_scoreable_and_smaller(area, skill):
    orchestrator, _session = orchestrator_with_learner(uuid4())
    game_flow = flow_for(orchestrator, area)
    now = datetime.now(UTC)
    made = 0
    for seed in range(12):
        failed = game_flow.support_record(
            game_flow.generate_item(skill, role="unsupported_before", seed=seed), now
        )
        item = next(
            (
                candidate
                for offset in range(48)
                if (
                    candidate := game_flow.simpler_support_item(
                        skill, 1_000 + seed + offset, failed
                    )
                )
                is not None
            ),
            None,
        )
        if item is None:
            continue
        made += 1
        record = game_flow.support_record(item, now)
        assert record["skill_id"] == skill
        assert record["revision_id"] != failed["revision_id"]
        solution = game_flow.support_solution(record)["correct_response"]
        assert game_flow.validate_constructed_response(dict(record), dict(solution))[0] is True
        if area.startswith("G5-AREA-ENG-"):
            # Fewer words, pictures, places or turns on screen than the failed game.
            failed_level = difficulty(game_flow.support_activity(failed)["game"])
            assert difficulty(game_flow.support_activity(record)["game"])[0] < failed_level[0]
    if skill in NO_DESIGNED_SIMPLER_FORM:
        assert made == 0
    else:
        assert made > 0


@pytest.mark.parametrize(
    ("area", "skill"),
    (
        ("G5-AREA-MAT-02", "G5-MAT-C06-L01-O02"),
        ("G5-AREA-ENG-01", "G5-ENG-BEH-POSTURE-01"),
        ("G5-AREA-ENG-06", "G5-ENG-FOOD-VOCAB-01"),
        ("G5-AREA-ENG-17", "G5-ENG-CLASS-FUNCTION-01"),
    ),
)
def test_each_wrong_supported_answer_opens_the_next_server_type_until_the_order_ends(area, skill):
    orchestrator, session, game_flow, episode_id, response = _failed(area, skill)
    order = orchestrator.reconstruct(episode_id)["state"]["support_loop"]["order"]
    shown_types = []
    calls = 0
    while not response["support_round"]["withdrawal_allowed"]:
        calls += 1
        assert calls <= 16
        status = response["support_round"]
        if not shown_types or shown_types[-1] != status["scaffold_type"]:
            shown_types.append(status["scaffold_type"])
        assert response["support"]["english_tag_key"] == status["english_tag_key"]
        if status["stage_kind"] == "view":
            response = orchestrator.complete_support(
                episode_id,
                duration_ms=100,
                steps_viewed=1,
                manifest_revision_id=status["manifest_revision_id"],
                grouped_count=0,
                group_sizes=(0, 0),
                interaction_summary={"completed": True},
                idempotency_key=f"view:{calls}:{uuid4()}",
            )
            continue
        current = game_flow._support_rounds.current_item(
            orchestrator.reconstruct(episode_id)["state"]
        )
        response = orchestrator.submit_supported(
            episode_id,
            constructed_response=wrong_answer(game_flow, current),
            response_time_ms=100,
            interaction_summary={},
            idempotency_key=f"wrong:{calls}:{uuid4()}",
        )

    state = orchestrator.reconstruct(episode_id)["state"]
    assert shown_types == order == state["support_loop"]["types_used"]
    assert state["support_loop"]["stop_reason"] == "order_exhausted"
    assert len(session.scalars(select(LearningFlowSupportRoundModel)).all()) == len(order)
    expected = MATHEMATICS_ORDER if area.startswith("G5-AREA-MAT-") else ENGLISH_ORDER
    assert order == [support for support in expected if support in order]


def test_english_round_withdraws_after_supported_success_and_measures_only_the_fresh_item():
    orchestrator, _session, game_flow, episode_id, shown = _failed(
        "G5-AREA-ENG-06", "G5-ENG-FOOD-VOCAB-01", condition="proposed"
    )
    public = str(shown["support"])
    for secret in ("target_mapping", "correct_response", "answer_key", "support_order"):
        assert secret not in public
    current = game_flow._support_rounds.current_item(orchestrator.reconstruct(episode_id)["state"])
    stopped = orchestrator.submit_supported(
        episode_id,
        constructed_response=correct_answer(game_flow, current),
        response_time_ms=250,
        interaction_summary={},
        idempotency_key=f"supported:{uuid4()}",
    )
    assert stopped["support_round"]["withdrawal_allowed"] is True
    round_status = stopped["support_round"]
    orchestrator.withdraw_support(
        episode_id,
        request_id=uuid4(),
        support_revision_id=round_status["support_revision_id"],
        manifest_revision_id=round_status["manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"withdraw:{uuid4()}",
    )
    orchestrator.present_after(episode_id, idempotency_key=f"after-present:{uuid4()}")
    state = orchestrator.reconstruct(episode_id)["state"]
    after = next(row for row in state["presentations"] if row["role"] == "unsupported_after")
    orchestrator.submit_after(
        episode_id,
        option_id=None,
        constructed_response=wrong_answer(game_flow, after),
        response_time_ms=300,
        idempotency_key=f"after-answer:{uuid4()}",
    )
    final = orchestrator.reconstruct(episode_id)["state"]

    # Correct while helped, wrong alone: Model 3 and Model 2's history see only the fresh item.
    assert final["supported_correctness"] is True
    assert final["measurement"]["after_presentation_id"] == after["presentation_id"]
    assert final["measurement"]["supported_correctness_used_as_reward"] is False
    assert final["policy_updates"][-1]["reward"] == final["measurement"]["raw_independence_gain"]
    # Development episodes never feed the models.
    assert game_flow._model_eligible(final, game_flow._now()) is False


def test_an_overlapping_answer_for_a_closed_round_does_not_advance_the_order_again():
    orchestrator, _session, game_flow, episode_id, _shown = _failed(
        "G5-AREA-ENG-06", "G5-ENG-FOOD-VOCAB-01"
    )
    current = game_flow._support_rounds.current_item(orchestrator.reconstruct(episode_id)["state"])
    answer = wrong_answer(game_flow, current)
    orchestrator.submit_supported(
        episode_id,
        constructed_response=answer,
        response_time_ms=100,
        interaction_summary={},
        idempotency_key=f"first:{uuid4()}",
    )
    with pytest.raises(LearningFlowOrchestrationError):
        orchestrator.submit_supported(
            episode_id,
            constructed_response=answer,
            response_time_ms=100,
            interaction_summary={},
            idempotency_key=f"overlap:{uuid4()}",
        )

    assert len(orchestrator.reconstruct(episode_id)["state"]["support_loop"]["types_used"]) == 2


def test_english_simpler_and_prerequisite_stay_distinct():
    orchestrator, _session, game_flow, episode_id, _shown = _failed(
        "G5-AREA-ENG-06", "G5-ENG-FOOD-GROUP-02"
    )
    context = game_flow._support_context(
        orchestrator.reconstruct(episode_id)["state"], game_flow._now()
    )
    simpler = game_flow._support_rounds._builders["simpler_same_game"].build(context)
    prerequisite = game_flow._support_rounds._builders["prerequisite_repair"].build(context)

    assert simpler is not None and prerequisite is not None
    assert simpler.stages[0].item["skill_id"] == "G5-ENG-FOOD-GROUP-02"
    assert simpler.stages[0].gate_on_success is True
    assert prerequisite.stages[0].item["skill_id"] == "G5-ENG-FOOD-VOCAB-01"
    assert prerequisite.stages[-1].item["skill_id"] == "G5-ENG-FOOD-GROUP-02"
    # English help speaks about words, not carrying and borrowing.
    assert simpler.stages[0].cues_si == ENGLISH.simpler_start
    assert ENGLISH.guided_questions != MATHEMATICS.guided_questions


def test_fewer_pairs_keeps_every_heading_and_one_distractor_for_a_single_link():
    sorting = {
        "entries": [{"entry_token": f"e-{n}"} for n in range(6)],
        "zones": [{"zone_token": "z-a"}, {"zone_token": "z-b"}],
        "target_mapping": {f"e-{n}": ("z-a" if n < 3 else "z-b") for n in range(6)},
    }
    smaller = fewer_pairs(sorting, below=pair_count(sorting))
    assert smaller is not None
    assert set(smaller["target_mapping"].values()) == {"z-a", "z-b"}
    assert len(smaller["entries"]) == len(smaller["target_mapping"]) == 3

    linking = {
        "words": [{"word_token": "w-1"}, {"word_token": "w-2"}],
        "pictures": [{"picture_token": "p-1"}, {"picture_token": "p-2"}],
        "target_mapping": {"w-1": "p-1", "w-2": "p-2"},
    }
    single = fewer_pairs(linking, below=2)
    assert single is not None
    assert single["target_mapping"] == {"w-1": "p-1"}
    assert len(single["words"]) == 1
    assert len(single["pictures"]) == 2
    assert fewer_pairs(single, below=1) is None


def _labels(modules: tuple[str, ...]) -> set[str]:
    labels: set[str] = set()
    for name in modules:
        module = importlib.import_module(f"app.gamification.content.{name}")
        labels |= set(getattr(module, "MISCONCEPTIONS", ()))
    return labels


@pytest.mark.parametrize(
    ("subject", "modules"),
    (("MAT", MATHEMATICS_CONTENT_MODULES), ("ENG", ENGLISH_CONTENT_MODULES)),
)
def test_every_model1_label_names_a_kind_of_difficulty(subject, modules):
    labels = _labels(modules)
    assert labels
    families = {label: reason_family(label, subject=subject) for label in labels}
    assert set(families.values()) <= {
        "representation",
        "procedure",
        "relation",
        "prerequisite",
        "unclear",
    }
    # Only labels that name no particular difficulty are left unclear.
    unclear = {label for label, family in families.items() if family == "unclear"}
    assert "unknown_or_other" in unclear
    assert all("unknown" in label or "multiple_valid" in label for label in unclear) or (
        subject == "MAT"
    )


@pytest.mark.parametrize(
    ("label", "family", "lead"),
    (
        ("food_word_visual_confusion", "representation", "visual_guidance"),
        ("father_mother_confusion", "representation", "visual_guidance"),
        ("multiword_order_confusion", "procedure", "step_by_step_guidance"),
        ("fruit_vegetable_lesson_heading_confusion", "relation", "conceptual_reexplanation"),
        ("english_sinhala_family_word_confusion", "prerequisite", "prerequisite_repair"),
        ("unknown_or_other", "unclear", "simpler_same_game"),
    ),
)
def test_english_reasons_lead_the_english_order(label, family, lead):
    assert reason_family(label, subject="ENG") == family
    decision = choose_support_order(
        subject="ENG",
        condition="proposed",
        model1_label=label,
        model1_uncertain=False,
        eligible=SUPPORT_TYPES,
        renderable=SUPPORT_TYPES,
    )
    assert decision.first == lead
    assert decision.order[1:] == tuple(support for support in ENGLISH_ORDER if support != lead)


def test_baseline_english_order_is_the_english_fallback_without_reason_or_history():
    decision = choose_support_order(
        subject="ENG",
        condition="baseline",
        model1_label="food_word_visual_confusion",
        model1_uncertain=False,
        eligible=SUPPORT_TYPES,
        renderable=tuple(support for support in SUPPORT_TYPES if support != "prerequisite_repair"),
    )
    assert decision.order == tuple(
        support for support in ENGLISH_ORDER if support != "prerequisite_repair"
    )
    assert decision.reason_family is None


def test_history_prefers_the_type_with_independent_success_not_supported_success():
    history: list[Mapping[str, object]] = [
        {
            "condition": "proposed",
            "validity": "valid",
            "supported_correctness": True,
            "measurement": {"raw_independence_gain": "0", "after_earned": 0, "after_maximum": 1},
            "support_loop": {"types_used": ["visual_guidance"]},
        },
        {
            "condition": "proposed",
            "validity": "valid",
            "supported_correctness": False,
            "measurement": {"raw_independence_gain": "1", "after_earned": 1, "after_maximum": 1},
            "support_loop": {"types_used": ["simpler_same_game", "step_by_step_guidance"], "stop_reason": "supported_success", "rounds": [
                {"scaffold_type": "simpler_same_game", "outcome": "failed"},
                {"scaffold_type": "step_by_step_guidance", "outcome": "succeeded"},
            ]},
        },
    ]
    decision = choose_support_order(
        subject="ENG",
        condition="proposed",
        model1_label="food_word_visual_confusion",
        model1_uncertain=False,
        eligible=SUPPORT_TYPES,
        renderable=SUPPORT_TYPES,
        history=history,
    )
    assert decision.first == "step_by_step_guidance"
    assert decision.selection_mode == "learned_post_withdrawal_preference"
    assert set(decision.order) <= set(SUPPORT_TYPES)
