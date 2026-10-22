from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.gamification.application.support_rounds import SupportRoundService
from app.gamification.infrastructure.db.models import (
    LearningFlowIdempotencyReceiptModel,
    LearningFlowSupportRoundModel,
)
from tests.gamification.helpers.support_loop_helpers import (
    correct_answer,
    finish_help,
    flow_for,
    fresh_item,
    orchestrator_with_learner,
    skip_watch_only_help,
    walk_every_help,
    withdraw_and_present_after,
    wrong_answer,
)

AREA = "G5-AREA-MAT-01"
SKILL = "G5-MAT-NUM-REPRESENTED-01"


def _failed_episode(
    *,
    condition: str = "proposed",
    area: str = AREA,
    skill: str = SKILL,
    answerable: bool = True,
):
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
    # Most of these tests are about answerable rounds; a visual demonstration is only watched.
    if answerable:
        skip_watch_only_help(game_flow)
    state = orchestrator.reconstruct(episode_id)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    response = orchestrator.submit_before(
        episode_id,
        option_id=None,
        constructed_response=wrong_answer(game_flow, before),
        response_time_ms=400,
        interaction_summary={"attempt_count": 1, "move_count": 1},
        idempotency_key=f"before:{uuid4()}",
    )
    return orchestrator, session, game_flow, episode_id, response


def _current_record(orchestrator, game_flow, episode_id: UUID) -> Mapping[str, object]:
    state = orchestrator.reconstruct(episode_id)["state"]
    return game_flow._support_rounds.current_item(state)


def test_wrong_supported_answer_opens_next_server_type_once_and_is_idempotent():
    orchestrator, session, game_flow, episode_id, shown = _failed_episode(condition="baseline")
    first = shown["support"]["scaffold_type"]
    current = _current_record(orchestrator, game_flow, episode_id)
    key = f"supported:{uuid4()}"
    advanced = orchestrator.submit_supported(
        episode_id,
        constructed_response=wrong_answer(game_flow, current),
        response_time_ms=300,
        interaction_summary={"move_count": 1},
        idempotency_key=key,
    )
    repeated = orchestrator.submit_supported(
        episode_id,
        constructed_response=wrong_answer(game_flow, current),
        response_time_ms=300,
        interaction_summary={"move_count": 1},
        idempotency_key=key,
    )

    assert repeated == advanced
    assert advanced["support_round"]["another_round_required"] is True
    assert advanced["support"]["scaffold_type"] != first
    state = orchestrator.reconstruct(episode_id)["state"]
    used = state["support_loop"]["types_used"]
    # A watched visual demonstration comes before the first answerable round.
    watched = sum(row["outcome"] == "viewed" for row in state["support_loop"]["rounds"])
    assert len(used) == len(set(used)) == 2 + watched
    assert len(session.scalars(select(LearningFlowSupportRoundModel)).all()) == 2 + watched


def test_withdrawal_only_after_supported_success_and_public_payload_has_no_current_answer():
    orchestrator, _session, game_flow, episode_id, shown = _failed_episode()
    current = _current_record(orchestrator, game_flow, episode_id)
    completed = orchestrator.submit_supported(
        episode_id,
        constructed_response=correct_answer(game_flow, current),
        response_time_ms=250,
        interaction_summary={"move_count": 1},
        idempotency_key=f"supported:{uuid4()}",
    )

    assert shown["support_round"]["withdrawal_allowed"] is False
    assert completed["support_round"]["withdrawal_allowed"] is True
    assert completed["support"] is None
    public = str(shown["support"]).lower()
    assert "correct_response" not in public
    assert "answer_key" not in public
    assert "rubric" not in public
    assert "support_order" not in public


def test_last_wrong_type_withdraws_without_repeating_or_looping_forever():
    orchestrator, _session, game_flow, episode_id, response = _failed_episode(condition="baseline")
    calls = 0
    while not response["support_round"]["withdrawal_allowed"]:
        calls += 1
        assert calls <= 16
        status = response["support_round"]
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
        current = _current_record(orchestrator, game_flow, episode_id)
        response = orchestrator.submit_supported(
            episode_id,
            constructed_response=wrong_answer(game_flow, current),
            response_time_ms=100,
            interaction_summary={"move_count": 1},
            idempotency_key=f"wrong:{calls}:{uuid4()}",
        )

    state = orchestrator.reconstruct(episode_id)["state"]
    assert state["support_loop"]["stop_reason"] == "order_exhausted"
    assert state["support_loop"]["types_used"] == state["support_loop"]["order"]
    assert len(state["support_loop"]["types_used"]) == len(set(state["support_loop"]["types_used"]))


def test_failed_next_type_selection_rolls_back_score_round_state_and_receipt():
    orchestrator, session, game_flow, episode_id, _shown = _failed_episode(condition="baseline")
    state_before = orchestrator.reconstruct(episode_id)["state"]
    current = game_flow._support_rounds.current_item(state_before)
    builders = dict(game_flow._support_rounds._builders)
    order = state_before["support_loop"]["order"]
    next_type = order[order.index(state_before["support_loop"]["rounds"][-1]["scaffold_type"]) + 1]

    class FailingBuilder:
        scaffold_type = next_type

        def build(self, _context):
            raise RuntimeError("next type failed")

    builders[next_type] = FailingBuilder()
    game_flow._support_rounds = SupportRoundService(builders)
    key = f"rollback:{uuid4()}"
    with pytest.raises(RuntimeError, match="next type failed"):
        orchestrator.submit_supported(
            episode_id,
            constructed_response=wrong_answer(game_flow, current),
            response_time_ms=300,
            interaction_summary={"move_count": 1},
            idempotency_key=key,
        )

    assert orchestrator.reconstruct(episode_id)["state"] == state_before
    rounds_before = len(state_before["support_loop"]["rounds"])
    assert len(session.scalars(select(LearningFlowSupportRoundModel)).all()) == rounds_before
    assert session.get(LearningFlowIdempotencyReceiptModel, key) is None


def test_simpler_same_game_keeps_skill_and_prerequisite_repair_uses_earlier_skill():
    orchestrator, _session, game_flow, episode_id, _shown = _failed_episode()
    state = orchestrator.reconstruct(episode_id)["state"]
    context = game_flow._support_context(state, game_flow._now())
    simpler = game_flow._support_rounds._builders["simpler_same_game"].build(context)
    prerequisite = game_flow._support_rounds._builders["prerequisite_repair"].build(context)

    assert simpler is not None and prerequisite is not None
    assert simpler.stages[0].item["skill_id"] == SKILL
    assert simpler.stages[0].gate_on_success is True
    assert prerequisite.stages[0].item["skill_id"] != SKILL
    assert prerequisite.stages[-1].item["skill_id"] == SKILL


@pytest.mark.parametrize(
    ("area", "skill"),
    (
        ("G5-AREA-MAT-09", "G5-MAT-LENGTH-CONVERT-01"),
        ("G5-AREA-MAT-11", "G5-MAT-CAPACITY-COMPOSE-01"),
        ("G5-AREA-MAT-13", "G5-MAT-ORIENTATION-01"),
        ("G5-AREA-MAT-14", "G5-MAT-DIRECTION-SECONDARY-01"),
        ("G5-AREA-MAT-15", "G5-MAT-DECIMAL-SHADE-01"),
    ),
)
def test_fixed_shape_games_still_build_a_scoreable_simpler_same_skill_item(area, skill):
    learner = uuid4()
    orchestrator, _session = orchestrator_with_learner(learner)
    opened = orchestrator.open_episode(
        learner_id=learner,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id=area,
        atomic_skill_id=skill,
        idempotency_key=f"open:{uuid4()}",
    )
    episode_id = UUID(str(opened["episode_id"]))
    game_flow = flow_for(orchestrator, area)
    state = orchestrator.reconstruct(episode_id)["state"]
    context = game_flow._support_context(state, game_flow._now())
    plan = game_flow._support_rounds._builders["simpler_same_game"].build(context)

    assert plan is not None
    item = plan.stages[0].item
    assert item is not None and item["skill_id"] == skill
    answer = game_flow.support_solution(item)["correct_response"]
    assert game_flow.validate_constructed_response(item, answer)[0] is True


def test_model3_and_model2_history_use_only_the_fresh_withdrawn_outcome():
    orchestrator, _session, game_flow, episode_id, _shown = _failed_episode()
    current = _current_record(orchestrator, game_flow, episode_id)
    stopped = orchestrator.submit_supported(
        episode_id,
        constructed_response=correct_answer(game_flow, current),
        response_time_ms=250,
        interaction_summary={"move_count": 1},
        idempotency_key=f"supported:{uuid4()}",
    )
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
        constructed_response=correct_answer(game_flow, after),
        response_time_ms=300,
        idempotency_key=f"after-answer:{uuid4()}",
    )
    final = orchestrator.reconstruct(episode_id)["state"]

    assert final["measurement"]["after_presentation_id"] == after["presentation_id"]
    assert final["measurement"]["supported_correctness_used_as_reward"] is False
    update = final["policy_updates"][-1]
    assert update["reward"] == final["measurement"]["raw_independence_gain"]
    assert update["support_types_used"] == final["support_loop"]["types_used"]


@pytest.mark.parametrize(
    ("area", "skill"),
    [(AREA, SKILL), ("G5-AREA-ENG-12", "G5-ENG-FAMILY-BILINGUAL-01")],
)
def test_help_stages_show_the_answer_and_scored_items_do_not(area, skill):
    orchestrator, _session, _game_flow, episode_id, response = _failed_episode(
        condition="baseline", area=area, skill=skill, answerable=False
    )
    maths = area.startswith("G5-AREA-MAT-")
    for support in walk_every_help(orchestrator, episode_id, response):
        manifest = support["game_manifest"]
        if manifest["stage_kind"] == "view":
            # A demonstration arrives solved: a worked example, or the child's own board.
            board = manifest["worked_example"] or manifest["activity"]
            answer = board["answer"]
            assert answer["mode"] == "filled"
        else:
            answer = manifest["activity"]["answer"]
            assert answer["mode"] == "tint"
        assert answer["marks"]
        if maths:
            # Maths says its answer in words in the lesson (or guided questions), never as raw
            # payload lines.
            assert answer["lines"] == []
            assert manifest["lesson"] or manifest["guidance"]
        else:
            assert answer["lines"]
        if manifest["scaffold_type"] == "step_by_step_guidance":
            assert manifest["guidance"]
            assert all(pair["answer_si"] for pair in manifest["guidance"])
            assert manifest["guidance"][-1]["answer_si"].startswith("පිළිතුර: ")

    state = orchestrator.reconstruct(episode_id)["state"]
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    assert "answer" not in before and "answer" not in before["game_data"]


def test_family_words_answer_reads_as_word_pairs():
    *_, shown = _failed_episode(area="G5-AREA-ENG-12", skill="G5-ENG-FAMILY-BILINGUAL-01")
    manifest = shown["support"]["game_manifest"]
    answer = (manifest["activity"] or {}).get("answer") or manifest["worked_example"]["answer"]
    # Words the child reads on the board, never opaque tokens.
    assert all(" → " in line for line in answer["lines"])
    assert not any(mark.startswith(("e-", "s-")) for mark in answer["marks"])


def test_watched_visual_guidance_goes_straight_to_withdrawal():
    orchestrator, _session, _game_flow, episode_id, shown = _failed_episode(
        condition="baseline", answerable=False
    )
    status = shown["support_round"]
    assert shown["support"]["scaffold_type"] == "visual_guidance"
    assert status["stage_kind"] == "view"

    watched = orchestrator.complete_support(
        episode_id,
        duration_ms=100,
        steps_viewed=1,
        manifest_revision_id=status["manifest_revision_id"],
        grouped_count=0,
        group_sizes=(0, 0),
        interaction_summary={"completed": True},
        idempotency_key=f"view:{uuid4()}",
    )

    # The demonstration already showed the answer: no further help before the child tries alone.
    assert watched["support"] is None
    assert watched["support_round"]["withdrawal_allowed"] is True
    assert watched["support_round"]["another_round_required"] is False
    loop = orchestrator.reconstruct(episode_id)["state"]["support_loop"]
    assert loop["types_used"] == ["visual_guidance"]
    assert loop["stop_reason"] == "support_viewed"


def test_failed_after_item_opens_the_next_help_and_keeps_the_first_measurement():
    orchestrator, session, game_flow, episode_id, shown = _failed_episode(
        condition="baseline", answerable=False
    )
    status = shown["support_round"]
    watched = orchestrator.complete_support(
        episode_id,
        duration_ms=100,
        steps_viewed=1,
        manifest_revision_id=status["manifest_revision_id"],
        grouped_count=0,
        group_sizes=(0, 0),
        interaction_summary={"completed": True},
        idempotency_key=f"view:{uuid4()}",
    )
    withdraw_and_present_after(orchestrator, episode_id, watched["support_round"])
    after = fresh_item(orchestrator, episode_id)
    failed = orchestrator.submit_after(
        episode_id,
        option_id=None,
        constructed_response=wrong_answer(game_flow, after),
        response_time_ms=300,
        idempotency_key=f"after:{uuid4()}",
    )

    measured = orchestrator.reconstruct(episode_id)["state"]
    order = measured["support_loop"]["order"]
    # The phone is sent the next help; the episode itself is measured and complete.
    assert failed["status"] == "support_active"
    assert failed["support"]["scaffold_type"] == order[1]
    assert failed["support_round"]["withdrawal_allowed"] is False
    assert measured["status"] == "completed"
    assert measured["measurement"]["after_presentation_id"] == after["presentation_id"]
    assert measured["support_loop"]["types_used"] == ["visual_guidance"]
    assert measured["follow_up"]["support_loop"]["types_used"] == [order[1]]

    done = finish_help(orchestrator, episode_id, failed)
    presented = withdraw_and_present_after(orchestrator, episode_id, {**done})
    practice = fresh_item(orchestrator, episode_id)
    assert presented["manifest"]["presentation_id"] == practice["presentation_id"]
    assert presented["manifest"]["measurement_role"] == "unsupported_after"
    assert practice["revision_id"] not in {row["revision_id"] for row in measured["presentations"]}
    passed = orchestrator.submit_after(
        episode_id,
        option_id=None,
        constructed_response=correct_answer(game_flow, practice),
        response_time_ms=300,
        idempotency_key=f"practice:{uuid4()}",
    )

    final = orchestrator.reconstruct(episode_id)["state"]
    assert passed["status"] == "completed"
    assert passed["support"] is None
    assert passed["server_score"]["measurement_role"] == "follow_up_practice"
    assert final["follow_up"]["finish_reason"] == "independent_success"
    # Follow-up practice never touches Model 3, the reward or the durable round table.
    assert final["measurement"] == measured["measurement"]
    assert final["reward"] == measured["reward"]
    assert final["attempts"] == measured["attempts"]
    assert len(session.scalars(select(LearningFlowSupportRoundModel)).all()) == 1
