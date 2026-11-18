"""The games' help-order bandit: today's order at the start, the credit rule, and how it learns.

Every equivalence check is against the frozen rule-based orders, never against the rules.
"""

import importlib.util
import json
import shutil
from functools import cache
from pathlib import Path

import pytest

from app.gamification.modeling.shared.expert_data import EXPERT_MODEL_DATA_DIRECTORY
from app.gamification.modeling.support_selection.context import (
    GAME_CONTEXT_VERSION,
    BanditContext,
)
from app.gamification.modeling.support_selection.game_bandit import (
    CREDIT_RULE_VERSION,
    CreditObservation,
    GameHelpBandit,
    episode_observations,
    load_game_help_bandit,
)
from app.gamification.modeling.support_selection.learned_policy import LinUCBPolicy

ROOT = Path(__file__).resolve().parents[5]
ORDERS = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "rule_based_support_orders.json").read_text("utf-8")
)
AGREEMENT_TOOL = (
    ROOT / "tools" / "gamification" / "support_selection" / "compare_bandit_with_rule_orders.py"
)
CALM = {"status": "available", "state": "calm"}


def _frozen_order(decision) -> list[str]:
    source = decision["delivered"] if decision["subject"] == "SIN" else decision["decision"]
    return list(source["support_order"])


def _order(bandit, decision=None, *, history=(), **changes):
    arguments = {
        "model1_label": None,
        "model1_uncertain": False,
        "learning_state_input": CALM,
        "history": list(history),
        "eligible": bandit.supports,
        "renderable": bandit.supports,
    }
    if decision is not None:
        arguments.update(
            model1_label=decision["model1_label"],
            model1_uncertain=decision["model1_uncertain"],
            learning_state_input=ORDERS["learning_state_readings"][decision["learning_state"]],
            renderable=decision["renderable"],
        )
    arguments.update(changes)
    return bandit.order(**arguments)


def _episode(rounds, after_correct, *, stop=None, condition="proposed", valid=True, follow_up=None):
    earned = "1" if after_correct else "0"
    state = {
        "condition": condition,
        "validity": "valid" if valid else "invalid",
        "measurement": {
            "after_earned": earned,
            "after_maximum": "1",
            "raw_independence_gain": earned if valid else None,
        },
        "attempts": [{"role": "unsupported_before", "correct": False}],
        "support_loop": {
            "rounds": [
                {"scaffold_type": support, "outcome": outcome} for support, outcome in rounds
            ],
            "types_used": [support for support, _ in rounds],
            "stop_reason": stop
            or ("supported_success" if rounds[-1][1] == "succeeded" else "order_exhausted"),
        },
    }
    if follow_up is not None:
        state["follow_up"] = follow_up
    return state


def _roles(state):
    return [
        (o.support, o.role, o.score, o.weight)
        for o in episode_observations(state, failed_round_weight=0.5)
    ]


# --- Equivalence with today's orders --------------------------------------------------------


def test_expert_start_reproduces_every_frozen_order_without_history() -> None:
    bandits = {subject: load_game_help_bandit(subject) for subject in ("MAT", "ENG", "SIN")}
    checked = set()
    for decision in ORDERS["decisions"]:
        if decision["condition"] != "proposed" or decision["history"] != "none":
            continue
        chosen = _order(bandits[decision["subject"]], decision)
        assert list(chosen.order) == _frozen_order(decision), decision
        checked.add((decision["subject"], decision["helps"], decision["learning_state"]))
    assert {helps for _, helps, _ in checked} == {
        "all_eligible",
        "lead_not_drawable",
        "worked_example_only",
    }
    assert {state for _, _, state in checked} == set(ORDERS["learning_state_readings"])


def test_every_label_reaches_its_family_cell() -> None:
    for subject in ("MAT", "ENG", "SIN"):
        bandit = load_game_help_bandit(subject)
        for label, row in ORDERS["reason_families"][subject]["labels"].items():
            assert bandit.reason_family(label) == row["reason_family"]


def test_a_first_help_that_did_not_transfer_moves_on_only_in_sinhala() -> None:
    agreement = _agreement()
    for subject in ("MAT", "ENG", "SIN"):
        row = agreement[subject]["helped_but_not_independent"]
        assert row["same_first_help"] == row["decisions"], subject


def test_no_help_can_be_drawn() -> None:
    bandit = load_game_help_bandit("MAT")
    with pytest.raises(ValueError, match="NO_RENDERABLE_SUPPORT"):
        _order(bandit, renderable=())


# --- Credit rule, one test per row of the scoring table -------------------------------------


def test_credited_help_with_right_alone_scores_the_gain_at_full_weight() -> None:
    state = _episode([("visual_guidance", "failed"), ("step_by_step_guidance", "succeeded")], True)
    assert ("step_by_step_guidance", "credited", 1.0, 1.0) in _roles(state)


def test_credited_help_with_wrong_alone_scores_zero_at_full_weight() -> None:
    state = _episode([("visual_guidance", "succeeded")], False)
    assert _roles(state) == [("visual_guidance", "credited", 0.0, 1.0)]


def test_each_failed_round_scores_zero_at_half_weight() -> None:
    state = _episode(
        [
            ("visual_guidance", "failed"),
            ("simpler_same_game", "failed"),
            ("step_by_step_guidance", "succeeded"),
        ],
        True,
    )
    assert _roles(state) == [
        ("step_by_step_guidance", "credited", 1.0, 1.0),
        ("visual_guidance", "failed_round", 0.0, 0.5),
        ("simpler_same_game", "failed_round", 0.0, 0.5),
    ]


def test_helps_never_shown_get_nothing() -> None:
    state = _episode([("visual_guidance", "succeeded")], True)
    assert {support for support, *_ in _roles(state)} == {"visual_guidance"}


def test_order_ran_out_but_right_alone_credits_no_help() -> None:
    state = _episode([("visual_guidance", "failed"), ("step_by_step_guidance", "failed")], True)
    assert _roles(state) == []


def test_baseline_episode_teaches_nothing() -> None:
    state = _episode([("visual_guidance", "succeeded")], True, condition="baseline")
    assert _roles(state) == []


def test_invalid_episode_teaches_nothing_not_even_its_failed_rounds() -> None:
    state = _episode(
        [("visual_guidance", "failed"), ("step_by_step_guidance", "succeeded")], True, valid=False
    )
    assert _roles(state) == []


def test_watched_demonstration_credits_the_last_help() -> None:
    state = _episode(
        [("visual_guidance", "failed"), ("worked_parallel_example", "viewed")],
        True,
        stop="support_viewed",
    )
    assert _roles(state) == [
        ("worked_parallel_example", "credited", 1.0, 1.0),
        ("visual_guidance", "failed_round", 0.0, 0.5),
    ]


def test_follow_up_help_after_a_wrong_after_answer_is_ignored() -> None:
    follow_up = {
        "status": "finished",
        "support_loop": {
            "rounds": [{"scaffold_type": "conceptual_reexplanation", "outcome": "succeeded"}],
            "stop_reason": "supported_success",
        },
    }
    state = _episode([("visual_guidance", "succeeded")], False, follow_up=follow_up)
    assert _roles(state) == [("visual_guidance", "credited", 0.0, 1.0)]


def test_each_help_type_is_observed_at_most_once() -> None:
    state = _episode(
        [
            ("visual_guidance", "failed"),
            ("visual_guidance", "failed"),
            ("step_by_step_guidance", "succeeded"),
        ],
        True,
    )
    supports = [support for support, *_ in _roles(state)]
    assert sorted(supports) == sorted(set(supports))


def test_older_single_help_episodes_credit_their_one_help() -> None:
    state = {
        "condition": "proposed",
        "validity": "valid",
        "measurement": {"after_earned": "1", "after_maximum": "1", "raw_independence_gain": "1"},
        "model2": {"selected_action": "visual_guidance"},
    }
    assert _roles(state) == [("visual_guidance", "credited", 1.0, 1.0)]


# --- Weighted update ------------------------------------------------------------------------


def _context(values=(1.0, 0.5)) -> BanditContext:
    return BanditContext(GAME_CONTEXT_VERSION, ("x", "y"), tuple(values), {})


def test_weight_one_is_exactly_the_plain_update() -> None:
    weighted, plain = LinUCBPolicy(), LinUCBPolicy()
    weighted.update(_context(), "arm", 0.7, 1.0)
    plain.update(_context(), "arm", 0.7)
    vector = _context().values
    expected_b = [0.7 * value for value in vector]
    expected_a = [
        [(1.0 if r == c else 0.0) + vector[r] * vector[c] for c in range(2)] for r in range(2)
    ]
    assert weighted.parameters() == plain.parameters()
    assert weighted.parameters()["arms"]["arm"] == {"A": expected_a, "b": expected_b}


def test_weight_zero_changes_nothing_and_a_negative_weight_is_refused() -> None:
    policy = LinUCBPolicy()
    policy.update(_context(), "arm", 1.0)
    before = policy.parameters()
    policy.update(_context(), "arm", 1.0, 0.0)
    assert policy.parameters() == before
    with pytest.raises(ValueError):
        policy.update(_context(), "arm", 1.0, -0.5)


def test_two_half_weights_equal_one_full_weight() -> None:
    halves, whole = LinUCBPolicy(), LinUCBPolicy()
    halves.update(_context(), "arm", 0.4, 0.5)
    halves.update(_context(), "arm", 0.4, 0.5)
    whole.update(_context(), "arm", 0.4, 1.0)
    left, right = halves.parameters()["arms"]["arm"], whole.parameters()["arms"]["arm"]
    assert left["b"] == pytest.approx(right["b"], abs=1e-15)
    for row_left, row_right in zip(left["A"], right["A"], strict=True):
        assert row_left == pytest.approx(row_right, abs=1e-15)


def test_worked_example_of_the_scoring_section() -> None:
    # One feature, expert gain 0.60 worth 4 pseudo-episodes.
    context = BanditContext(GAME_CONTEXT_VERSION, ("x",), (1.0,), {})

    def policy():
        return LinUCBPolicy.from_parameters(
            {
                "alpha": 0.0,
                "ridge": 1.0,
                "epsilon_min": 0.0,
                "arms": {"h": {"A": [[4.0]], "b": [2.4]}},
            }
        )

    def predicted(model):
        return round(model.predict(context, ["h"])["h"][0], 2)

    model = policy()
    seen = [predicted(model)]
    for _ in range(2):
        model.update(context, "h", 0.0, 0.5)
        seen.append(predicted(model))
    model.update(context, "h", 1.0, 1.0)
    seen.append(predicted(model))
    helped_not_independent = policy()
    helped_not_independent.update(context, "h", 0.0, 1.0)
    seen.append(predicted(helped_not_independent))
    assert seen == [0.6, 0.53, 0.48, 0.57, 0.48]


# --- Learning and calibration ---------------------------------------------------------------


def _learn(bandit, order, support, role, score, weight, independent=False):
    bandit.learn(
        CreditObservation(support, role, score, weight, independent), order.contexts[support]
    )


def test_with_no_data_every_prediction_is_the_expert_gain() -> None:
    gains = json.loads((EXPERT_MODEL_DATA_DIRECTORY / "support_gains.json").read_text("utf-8"))
    for subject in ("MAT", "ENG", "SIN"):
        bandit = load_game_help_bandit(subject)
        for cell in (c for c in gains["cells"] if c["subject"] == subject):
            for support, value in cell["expected_gain"].items():
                context = bandit.context(
                    support,
                    reason_family=cell["reason_family"],
                    model1_uncertain=cell["model1_uncertain"],
                    learning_state=cell["learning_state"],
                    history=[],
                )
                predicted = bandit.policy.predict(context, [support])[support][0]
                assert predicted == pytest.approx(value, abs=1e-12)


def test_failed_rounds_and_unindependent_results_move_the_first_help_down() -> None:
    for weight, needed in ((0.5, 2), (1.0, 1)):
        bandit = load_game_help_bandit("MAT")
        lead = _order(bandit).first
        for _ in range(needed):
            order = _order(bandit)
            assert order.first == lead
            _learn(bandit, order, lead, "failed_round" if weight < 1 else "credited", 0.0, weight)
        assert _order(bandit).first != lead, (weight, needed)


def test_valid_gains_move_a_help_up_after_two_independent_successes() -> None:
    bandit = load_game_help_bandit("ENG")
    second = _order(bandit).order[1]
    for _ in range(2):
        order = _order(bandit)
        assert order.first != second
        _learn(bandit, order, second, "credited", 1.0, 1.0, True)
    assert _order(bandit).first == second


def test_helped_but_not_independent_never_moves_a_help_up() -> None:
    bandit = load_game_help_bandit("MAT")
    order = _order(bandit)
    for support in order.order:
        before = _order(bandit).predicted_gain[support]
        _learn(bandit, _order(bandit), support, "credited", 0.0, 1.0)
        assert _order(bandit).predicted_gain[support] < before


def test_baseline_episodes_change_nothing() -> None:
    bandit = load_game_help_bandit("MAT")
    before = _order(bandit)
    episode = _episode([(before.first, "succeeded")], True, condition="baseline")
    for observation in episode_observations(episode, failed_round_weight=0.5):
        bandit.learn(observation, before.contexts[observation.support])
    assert _order(bandit).predicted_gain == before.predicted_gain


def test_a_childs_own_success_puts_even_the_last_help_first_for_that_child() -> None:
    bandit = load_game_help_bandit("MAT")
    last = _order(bandit).order[-1]
    history = [_episode([(last, "succeeded")], True)]
    assert _order(bandit, history=history).first == last
    half = [_episode([(last, "succeeded")], True), _episode([(last, "succeeded")], False)]
    assert _order(bandit, history=half).first != last
    assert _order(bandit).first != last


# --- Artifact and loading -------------------------------------------------------------------


def test_parameters_record_the_decisions_and_survive_a_round_trip() -> None:
    bandit = load_game_help_bandit("SIN")
    parameters = bandit.parameters()
    assert parameters["alpha"] == 0.0 and parameters["epsilon_min"] == 0.0
    assert parameters["exploration"] == {"alpha": 0.0, "epsilon_min": 0.0, "status": "decision"}
    assert parameters["game"]["failed_round_weight"] == 0.5
    assert parameters["game"]["credit_rule_version"] == CREDIT_RULE_VERSION
    assert parameters["game"]["supports"] == [
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    ]
    restored = GameHelpBandit.from_parameters(json.loads(json.dumps(parameters)))
    history = [_episode([("worked_parallel_example", "succeeded")], False)]
    assert _order(restored, history=history).order == _order(bandit, history=history).order


def test_loader_refuses_gains_that_do_not_match_the_manifest(tmp_path) -> None:
    copy = tmp_path / "v1"
    shutil.copytree(EXPERT_MODEL_DATA_DIRECTORY, copy)
    gains = copy / "support_gains.json"
    gains.write_text(gains.read_text("utf-8").replace("0.6", "0.9", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest hash"):
        load_game_help_bandit("MAT", directory=copy)


@cache
def _agreement():
    spec = importlib.util.spec_from_file_location(AGREEMENT_TOOL.stem, AGREEMENT_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.first_help_agreement(ORDERS)


def test_agreement_report_covers_every_history_pattern() -> None:
    agreement = _agreement()
    for subject in ("MAT", "ENG", "SIN"):
        assert set(agreement[subject]) == set(ORDERS["histories"][subject])
        none = agreement[subject]["none"]
        assert none["same_first_help"] == none["decisions"]
