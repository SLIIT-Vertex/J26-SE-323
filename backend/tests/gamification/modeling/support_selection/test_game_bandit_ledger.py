"""Decision snapshots and ledger entries of the games' help-order bandit, without a database."""

import json

import pytest

from app.gamification.modeling.support_selection.game_bandit import load_game_help_bandit
from app.gamification.modeling.support_selection.game_bandit_ledger import (
    DecisionSnapshot,
    LedgerEntry,
    apply_entry,
    canonical_sha256,
    ledger_entries,
    replay,
    snapshot_of,
)

CALM = {"status": "available", "state": "calm"}


def _episode(episode_id, rounds, after_correct, *, condition="proposed", valid=True):
    earned = "1" if after_correct else "0"
    return {
        "episode_id": episode_id,
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
            "stop_reason": "supported_success"
            if rounds[-1][1] == "succeeded"
            else "order_exhausted",
        },
    }


def _decision(bandit, history=()):
    chosen = bandit.order(
        model1_label=None,
        model1_uncertain=False,
        learning_state_input=CALM,
        history=list(history),
        eligible=bandit.supports,
        renderable=bandit.supports,
    )
    return chosen, snapshot_of(chosen, subject=bandit.subject, inputs={"note": "test"})


def test_a_snapshot_keeps_every_scored_context_exactly_and_survives_json() -> None:
    bandit = load_game_help_bandit("MAT")
    history = [_episode("e0", [("visual_guidance", "succeeded")], True)]
    chosen, snapshot = _decision(bandit, history)
    restored = DecisionSnapshot.from_record(json.loads(json.dumps(snapshot.as_record())))
    assert set(restored.vectors) == set(chosen.contexts)
    for support, context in chosen.contexts.items():
        assert restored.context(support).values == context.values
        assert all(value != 0.0 for value in restored.vectors[support].values())
    assert canonical_sha256(restored.as_record()) == canonical_sha256(snapshot.as_record())


def test_the_hash_survives_what_postgresql_does_to_numbers() -> None:
    stored = {"zero": -0.0, "large": 1.2345678901234567e20, "whole": 32.0, "flag": True}
    returned = {"zero": 0, "large": 123456789012345670000, "whole": 32.0, "flag": True}
    assert canonical_sha256(stored) == canonical_sha256(returned)
    assert canonical_sha256({"flag": True}) != canonical_sha256({"flag": 1.0})
    assert canonical_sha256({"value": 0.1}) != canonical_sha256({"value": 0.10000000000000002})


def test_ledger_entries_follow_the_credit_rule_in_the_artifact_settings() -> None:
    bandit = load_game_help_bandit("MAT")
    _, snapshot = _decision(bandit)
    state = _episode(
        "e1", [("visual_guidance", "failed"), ("step_by_step_guidance", "succeeded")], True
    )
    entries = ledger_entries(state, snapshot=snapshot, settings=bandit.settings)
    assert sorted((e.support, e.role, e.score, e.weight) for e in entries) == [
        ("step_by_step_guidance", "credited", 1.0, 1.0),
        ("visual_guidance", "failed_round", 0.0, 0.5),
    ]
    assert {e.credit_rule_version for e in entries} == {bandit.settings["credit_rule_version"]}
    assert {e.episode_id for e in entries} == {"e1"}
    baseline = _episode("e2", [("visual_guidance", "succeeded")], True, condition="baseline")
    invalid = _episode("e3", [("visual_guidance", "succeeded")], True, valid=False)
    assert ledger_entries(baseline, snapshot=snapshot, settings=bandit.settings) == ()
    assert ledger_entries(invalid, snapshot=snapshot, settings=bandit.settings) == ()


def test_a_shown_help_that_was_not_scored_is_a_defect() -> None:
    bandit = load_game_help_bandit("SIN")
    _, snapshot = _decision(bandit)
    state = _episode("e1", [("conceptual_reexplanation", "succeeded")], True)
    with pytest.raises(ValueError, match="not scored"):
        ledger_entries(state, snapshot=snapshot, settings=bandit.settings)


def test_replay_gives_exactly_the_live_state() -> None:
    live = load_game_help_bandit("ENG")
    start = live.parameters()
    applied = []
    history: list[dict] = []
    for number, rounds in enumerate(
        (
            [("visual_guidance", "failed"), ("step_by_step_guidance", "succeeded")],
            [("visual_guidance", "succeeded")],
            [("visual_guidance", "failed"), ("conceptual_reexplanation", "failed")],
        )
    ):
        _, snapshot = _decision(live, history)
        state = _episode(f"e{number}", rounds, number != 2)
        for entry in ledger_entries(state, snapshot=snapshot, settings=live.settings):
            apply_entry(live, entry, snapshot)
            applied.append((entry, snapshot))
        history.append(state)
    assert live.parameters() != start
    assert replay(start, applied).parameters() == live.parameters()


def test_an_entry_from_another_credit_rule_is_refused() -> None:
    bandit = load_game_help_bandit("MAT")
    _, snapshot = _decision(bandit)
    entry = LedgerEntry("e1", "visual_guidance", "credited", 1.0, 1.0, "another-credit-rule")
    with pytest.raises(ValueError, match="another credit rule"):
        apply_entry(bandit, entry, snapshot)
    with pytest.raises(ValueError, match="unknown observation role"):
        LedgerEntry("e1", "visual_guidance", "follow_up", 1.0, 1.0, "x")
