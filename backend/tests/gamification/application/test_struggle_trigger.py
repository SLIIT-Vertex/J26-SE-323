from datetime import UTC, datetime, timedelta

import pytest

from app.gamification.application.struggle_trigger import (
    TRIGGER_VERSION,
    StruggleEvidence,
    StruggleTrigger,
    StruggleTriggerConfig,
)

AT = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


def evidence(**overrides: object) -> StruggleEvidence:
    values: dict[str, object] = {
        "captured_at": AT,
        "incorrect_attempt_count": 0,
        "response_time_ms": 1_000,
        "selected_option_is_misconception_linked": False,
        "learner_requested_help": False,
        "learner_support_need": None,
        "learner_state_observed_at": None,
        "source_as_of": {"baseline_response": AT - timedelta(seconds=1)},
    }
    values.update(overrides)
    return StruggleEvidence(**values)  # type: ignore[arg-type]


def test_config_version_and_thresholds_are_provisional() -> None:
    config = StruggleTriggerConfig()

    assert config.trigger_version == TRIGGER_VERSION == "struggle-trigger-v1"
    assert config.thresholds_status == "provisional_assumption"
    assert config.incorrect_attempt_threshold == 2


def test_each_rule_fires_on_its_own_input() -> None:
    trigger = StruggleTrigger()
    cases = {
        "TWO_INCORRECT_ATTEMPTS": {"incorrect_attempt_count": 2},
        "RESPONSE_TIME_OVER_SKILL_THRESHOLD": {"response_time_ms": 60_001},
        "MISCONCEPTION_LINKED_OPTION_SELECTED": {"selected_option_is_misconception_linked": True},
        "LEARNER_REQUESTED_HELP": {"learner_requested_help": True},
        "LEARNER_STATE_SUPPORT_NEED": {
            "learner_support_need": 0.7,
            "learner_state_observed_at": AT,
        },
    }

    for reason, overrides in cases.items():
        decision = trigger.evaluate(evidence(**overrides))
        assert decision.fired
        assert reason in decision.reason_codes
        assert decision.config_version == TRIGGER_VERSION


def test_two_rules_are_both_recorded_and_the_first_is_the_trigger_type() -> None:
    decision = StruggleTrigger().evaluate(
        evidence(incorrect_attempt_count=2, learner_requested_help=True)
    )

    assert decision.trigger_type == "TWO_INCORRECT_ATTEMPTS"
    assert decision.reason_codes == ("TWO_INCORRECT_ATTEMPTS", "LEARNER_REQUESTED_HELP")


def test_missing_inputs_do_not_fire_and_are_named() -> None:
    decision = StruggleTrigger().evaluate(
        evidence(
            incorrect_attempt_count=None,
            response_time_ms=None,
            selected_option_is_misconception_linked=None,
            learner_requested_help=None,
        )
    )

    assert not decision.fired
    assert decision.trigger_type == "no_struggle"
    assert decision.missing_inputs == (
        "incorrect_attempt_count",
        "response_time_ms",
        "selected_option_is_misconception_linked",
        "learner_requested_help",
        "learner_support_need",
    )


def test_stale_learner_state_does_not_fire_support_need() -> None:
    decision = StruggleTrigger().evaluate(
        evidence(
            learner_support_need=0.99,
            learner_state_observed_at=AT - timedelta(days=8),
        )
    )

    assert "LEARNER_STATE_SUPPORT_NEED" not in decision.reason_codes
    assert decision.skipped_rules == ("LEARNER_STATE_STALE",)


def test_future_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="future evidence"):
        StruggleTrigger().evaluate(
            evidence(source_as_of={"baseline_response": AT + timedelta(seconds=1)})
        )
