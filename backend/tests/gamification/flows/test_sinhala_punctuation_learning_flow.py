from uuid import UUID, uuid4

import pytest

from app.gamification.application.learning_flow_orchestration import LearningFlowOrchestrationError
from app.gamification.content import sinhala_punctuation as p
from tests.gamification.helpers.sinhala_flow_helpers import play, state, world

OPEN_SKILLS = [s for s, skill in p.SKILLS.items() if not skill.review_blocked]


def wrong(record):
    game = record["game_data"]
    answer = p.correct_response(game)
    if answer["kind"] == "sinhala_punctuation_span":
        return {**answer, "opening_mark_token_id": answer["closing_mark_token_id"], "closing_mark_token_id": answer["opening_mark_token_id"]}
    kinds = game["rubric"]["kind_by_token"]
    first = answer["placements"][0]
    other = next(t for t, k in kinds.items() if k != kinds[first["mark_token_id"]])
    return {**answer, "placements": [{**first, "mark_token_id": other}]}


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize("skill", OPEN_SKILLS)
def test_every_open_activity_runs_the_durable_loop(condition, skill):
    flow, publisher, learner = world()
    episode, final, _ = play(flow, learner, p, skill, condition, wrong)
    st = state(flow, episode)
    assert st["model1"]["pre_decision_only"]
    assert st["withdrawal"]["teardown_receipt"]
    assert st["demonstration_ledger"][0]["source_locators"][0].startswith("IMG_748")
    if st["presentations"][0]["game_data"]["equivalence"]["ig_available"]:
        assert st["validity"] == "valid" and st["measurement"]["percentage_point_value"] == "100"
        assert len(st["policy_updates"]) == (1 if condition == "proposed" else 0)
    else:
        assert "IG_UNAVAILABLE_INSUFFICIENT_REVIEWED_POOL" in st["exclusion_reasons"]
        assert st["policy_updates"] == []
    assert {r["measurement_role"] for r in publisher.records} <= {"unsupported_before", "unsupported_after"}
    assert final["server_score"]["feedback_si"]


def test_baseline_delivers_all_three_supports_in_authored_order():
    flow, _, learner = world()
    _, _, seen = play(flow, learner, p, "G5-SIN-PUNC-QUOTE-01", "baseline", wrong, support_success=False)
    assert list(dict.fromkeys(seen)) == ["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]


def test_line_break_fails_closed_before_reservation():
    flow, _, learner = world()
    with pytest.raises(LearningFlowOrchestrationError, match="SINHALA_LINEBREAK_CONTENT_REVIEW_BLOCKED"):
        flow.open_episode(
            learner_id=learner, session_id=uuid4(), grade=5, medium="si", condition="proposed",
            environment="test", allow_draft=True, area_id=p.AREA_ID, atomic_skill_id=p.LINEBREAK_SKILL,
            idempotency_key="lb",
        )


def test_failed_retry_advances_cursor():
    flow, _, learner = world()
    first, _, _ = play(flow, learner, p, "G5-SIN-PUNC-END-01", "proposed", wrong, after_correct=False)
    second, _, _ = play(flow, learner, p, "G5-SIN-PUNC-END-01", "proposed", wrong)
    a, b = state(flow, first), state(flow, second)
    assert b["support_cursor"]["unresolved"] and b["model2"]["support_order"][0] != a["model2"]["support_order"][0]
    assert UUID(b["support_cursor"]["source_episode_id"]) == first
