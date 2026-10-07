from uuid import uuid4

import pytest

from app.adaptive_tutor.application import ScaffoldingController, TutoringContext
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode


def tutoring_context(**overrides: object) -> TutoringContext:
    data: dict[str, object] = {
        "learner_id": uuid4(),
        "skill_id": "MAT-FRC",
        "mastery": 0.5,
        "support_need": 0.5,
        "attempt_count": 1,
        "is_correct": False,
        "error_severity": 0.4,
        "previous_assistance_level": None,
        "previous_hint_effective": None,
    }
    data.update(overrides)
    return TutoringContext.model_validate(data)


def test_identical_input_produces_identical_explainable_decision() -> None:
    controller = ScaffoldingController()
    context = tutoring_context()

    first = controller.decide(context)
    second = controller.decide(context)

    assert first == second
    assert isinstance(first.assistance_level, AssistanceLevel)
    assert first.reason_codes


def test_high_mastery_first_minor_error_preserves_independence() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(mastery=0.9, support_need=0.1, error_severity=0.1)
    )

    assert decision.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert DecisionReasonCode.HIGH_MASTERY in decision.reason_codes
    assert DecisionReasonCode.LOW_ERROR_SEVERITY in decision.reason_codes


def test_limited_high_mastery_minor_difficulty_maintains_low_assistance() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            mastery=0.9,
            error_severity=0.1,
            attempt_count=2,
            previous_assistance_level=AssistanceLevel.METACOGNITIVE_PROMPT,
            previous_hint_effective=False,
        )
    )

    assert decision.assistance_level is AssistanceLevel.METACOGNITIVE_PROMPT
    assert DecisionReasonCode.SUPPORT_MAINTAINED in decision.reason_codes


def test_persistent_difficulty_overrides_high_mastery_minor_error_safeguard() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            mastery=0.9,
            error_severity=0.1,
            attempt_count=3,
            previous_assistance_level=AssistanceLevel.METACOGNITIVE_PROMPT,
            previous_hint_effective=False,
        )
    )

    assert decision.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
    assert DecisionReasonCode.ESCALATION_JUSTIFIED in decision.reason_codes


def test_repeated_difficulty_and_ineffective_hint_support_escalation() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            attempt_count=3,
            previous_assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
            previous_hint_effective=False,
        )
    )

    assert decision.assistance_level is AssistanceLevel.TARGETED_HINT
    assert DecisionReasonCode.REPEATED_DIFFICULTY in decision.reason_codes
    assert DecisionReasonCode.PREVIOUS_HINT_INEFFECTIVE in decision.reason_codes
    assert DecisionReasonCode.ESCALATION_JUSTIFIED in decision.reason_codes


def test_ineffective_hint_without_enough_attempts_does_not_automatically_escalate() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            attempt_count=2,
            previous_assistance_level=AssistanceLevel.GUIDED_STEPS,
            previous_hint_effective=False,
        )
    )

    assert decision.assistance_level is AssistanceLevel.GUIDED_STEPS
    assert DecisionReasonCode.SUPPORT_MAINTAINED in decision.reason_codes


def test_effective_hint_does_not_force_fading_when_substantial_difficulty_remains() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            mastery=0.1,
            support_need=0.9,
            error_severity=0.9,
            attempt_count=6,
            previous_assistance_level=AssistanceLevel.SIMILAR_WORKED_EXAMPLE,
            previous_hint_effective=True,
        )
    )

    assert decision.assistance_level is AssistanceLevel.SIMILAR_WORKED_EXAMPLE
    assert DecisionReasonCode.PREVIOUS_HINT_EFFECTIVE in decision.reason_codes
    assert DecisionReasonCode.SUPPORT_MAINTAINED in decision.reason_codes
    assert DecisionReasonCode.FADING_JUSTIFIED not in decision.reason_codes


def test_success_after_assistance_fades_to_independence() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            attempt_count=4,
            is_correct=True,
            error_severity=0.0,
            previous_assistance_level=AssistanceLevel.GUIDED_STEPS,
            previous_hint_effective=True,
        )
    )

    assert decision.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert DecisionReasonCode.SUCCESS_AFTER_ASSISTANCE in decision.reason_codes
    assert DecisionReasonCode.FADING_JUSTIFIED in decision.reason_codes


@pytest.mark.parametrize(
    ("is_correct", "error_severity"),
    [(False, 0.4), (True, 0.0)],
)
def test_l0_is_maintained_without_false_fading_reason(
    is_correct: bool, error_severity: float
) -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            attempt_count=2,
            is_correct=is_correct,
            error_severity=error_severity,
            previous_assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
            previous_hint_effective=True,
        )
    )

    assert decision.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert DecisionReasonCode.SUPPORT_MAINTAINED in decision.reason_codes
    assert DecisionReasonCode.FADING_JUSTIFIED not in decision.reason_codes


def test_actual_l1_to_l0_fading_retains_fading_reason() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            attempt_count=2,
            previous_assistance_level=AssistanceLevel.METACOGNITIVE_PROMPT,
            previous_hint_effective=True,
        )
    )

    assert decision.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert DecisionReasonCode.FADING_JUSTIFIED in decision.reason_codes


def test_unknown_hint_effectiveness_preserves_previous_assistance() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(
            mastery=0.9,
            error_severity=0.1,
            attempt_count=2,
            previous_assistance_level=AssistanceLevel.FULL_EXPLANATION,
            previous_hint_effective=None,
        )
    )

    assert decision.assistance_level is AssistanceLevel.FULL_EXPLANATION
    assert (
        DecisionReasonCode.PREVIOUS_HINT_EFFECTIVENESS_UNKNOWN
        in decision.reason_codes
    )
    assert DecisionReasonCode.SUPPORT_MAINTAINED in decision.reason_codes


def test_zero_attempts_are_pre_interaction_not_first_attempt() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(attempt_count=0, is_correct=None, error_severity=None)
    )

    assert decision.assistance_level is AssistanceLevel.INDEPENDENT_RETRY
    assert decision.reason_codes == (DecisionReasonCode.PRE_INTERACTION,)


def test_one_attempt_retains_first_attempt_semantics() -> None:
    decision = ScaffoldingController().decide(tutoring_context(attempt_count=1))

    assert DecisionReasonCode.FIRST_ATTEMPT in decision.reason_codes
    assert DecisionReasonCode.PRE_INTERACTION not in decision.reason_codes


@pytest.mark.parametrize(
    "evidence",
    [
        {"mastery": 0.1},
        {"support_need": 0.9},
    ],
)
def test_one_strong_signal_alone_does_not_produce_full_explanation(
    evidence: dict[str, float],
) -> None:
    decision = ScaffoldingController().decide(tutoring_context(**evidence))

    assert decision.assistance_level is AssistanceLevel.CONCEPTUAL_HINT


def test_first_failure_does_not_jump_to_strong_assistance() -> None:
    decision = ScaffoldingController().decide(
        tutoring_context(mastery=0.1, support_need=0.9, error_severity=0.9)
    )

    assert decision.assistance_level is AssistanceLevel.TARGETED_HINT
    assert decision.assistance_level not in {
        AssistanceLevel.GUIDED_STEPS,
        AssistanceLevel.SIMILAR_WORKED_EXAMPLE,
        AssistanceLevel.FULL_EXPLANATION,
    }


def test_skill_identity_does_not_change_the_decision() -> None:
    controller = ScaffoldingController()
    math_decision = controller.decide(tutoring_context(skill_id="MAT-FRC"))
    aptitude_decision = controller.decide(tutoring_context(skill_id="APT-LOG"))

    assert math_decision == aptitude_decision
