import pytest

from app.gamification.application.learning_flow_orchestration import LearningFlowOrchestrationError
from app.gamification.content import sinhala_riddles as r
from tests.gamification.helpers.sinhala_flow_helpers import play, state, world


def wrong(record):
    game = record["game_data"]
    answer = r.correct_response(game)
    other = next(c["card_id"] for c in game["answer_cards"] if c["card_id"] != answer["answer_card_id"])
    return {**answer, "answer_card_id": other}


@pytest.mark.parametrize("condition", ["baseline", "proposed"])
@pytest.mark.parametrize("skill", list(r.SKILLS))
def test_both_skills_run_the_durable_loop(condition, skill):
    flow, publisher, learner = world()
    episode, final, seen = play(flow, learner, r, skill, condition, wrong, support_success=False)
    st = state(flow, episode)
    assert st["exposure_check"]["fresh"] is True
    assert st["validity"] == "valid" and st["measurement"]["raw_independence_gain"] == "1"
    assert len(st["policy_updates"]) == (1 if condition == "proposed" else 0)
    assert list(dict.fromkeys(seen)) == ["visual_guidance", "worked_parallel_example", "step_by_step_guidance"] or condition == "proposed"
    assert "🎉" in final["server_score"]["feedback_si"]
    assert {row["measurement_role"] for row in publisher.records} <= {"unsupported_before", "unsupported_after"}


def test_earlier_reveals_are_never_fresh_probes_and_exhaustion_invalidates():
    flow, _, learner = world()
    skill = "G5-SIN-RID-FIGURATIVE-01"
    revealed: set[str] = set()
    outcomes = []
    for _ in range(10):
        try:
            episode, _, _ = play(flow, learner, r, skill, "proposed", wrong)
        except LearningFlowOrchestrationError as error:
            # Every after probe already used: the pool is exhausted and open fails closed.
            assert error.code == "SINHALA_RIDDLE_POOL_EXHAUSTED"
            outcomes.append("exhausted")
            break
        st = state(flow, episode)
        probes = set(st["exposure_check"]["probe_answer_families"])
        if st["exposure_check"]["fresh"]:
            assert not probes & revealed
        else:
            assert "PROBE_POOL_EXHAUSTED_OR_PREVIOUSLY_REVEALED" in st["exclusion_reasons"]
            assert st["policy_updates"] == []
        outcomes.append(st["exposure_check"]["fresh"])
        revealed |= r.revealed_families(skill, int(st["seed"]))
    # The eight-riddle pool cannot stay fresh for one learner: practice, then exhaustion.
    assert outcomes[0] is True and (False in outcomes or outcomes[-1] == "exhausted")


def test_kokaa_revealed_in_direct_chapter_blocks_riddle_17_as_probe():
    flow, _, learner = world()
    for _ in range(3):
        episode, _, _ = play(flow, learner, r, "G5-SIN-RID-DIRECT-01", "baseline", wrong)
        if "kokaa" in r.revealed_families("G5-SIN-RID-DIRECT-01", int(state(flow, episode)["seed"])):
            break
    else:
        pytest.skip("this seed sequence never revealed කොකා")
    episode, _, _ = play(flow, learner, r, "G5-SIN-RID-FIGURATIVE-01", "baseline", wrong)
    st = state(flow, episode)
    assert st["exposure_check"]["fresh"] is False or "kokaa" not in st["exposure_check"]["probe_answer_families"]
