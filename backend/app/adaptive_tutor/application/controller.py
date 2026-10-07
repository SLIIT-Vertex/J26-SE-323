from app.adaptive_tutor.application.contracts import AssistanceDecision, TutoringContext
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode

# Provisional Policy V1 thresholds: executable design assumptions, not validated findings.
HIGH_MASTERY_MIN = 0.80
LOW_MASTERY_MAX = 0.30
HIGH_SUPPORT_NEED_MIN = 0.70
LOW_ERROR_SEVERITY_MAX = 0.25
HIGH_ERROR_SEVERITY_MIN = 0.65

_LEVELS = tuple(AssistanceLevel)
_ESCALATION_ATTEMPTS = {
    AssistanceLevel.INDEPENDENT_RETRY: 2,
    AssistanceLevel.METACOGNITIVE_PROMPT: 3,
    AssistanceLevel.CONCEPTUAL_HINT: 3,
    AssistanceLevel.TARGETED_HINT: 4,
    AssistanceLevel.GUIDED_STEPS: 5,
    AssistanceLevel.SIMILAR_WORKED_EXAMPLE: 6,
}


class ScaffoldingController:
    """Deterministic Reference Policy V1 assistance selector."""

    def decide(self, context: TutoringContext) -> AssistanceDecision:
        if context.attempt_count == 0:
            return AssistanceDecision(
                assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
                reason_codes=(DecisionReasonCode.PRE_INTERACTION,),
            )

        level, decision_reasons = _select_level(context)
        reasons = _evidence_reasons(context) + decision_reasons
        return AssistanceDecision(
            assistance_level=level,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )


def _select_level(
    context: TutoringContext,
) -> tuple[AssistanceLevel, list[DecisionReasonCode]]:
    previous = context.previous_assistance_level

    if context.is_correct:
        if previous is None:
            return AssistanceLevel.INDEPENDENT_RETRY, [
                DecisionReasonCode.INDEPENDENT_SUCCESS,
                DecisionReasonCode.MINIMUM_SUFFICIENT_ASSISTANCE,
            ]
        transition_reason = (
            DecisionReasonCode.SUPPORT_MAINTAINED
            if previous is AssistanceLevel.INDEPENDENT_RETRY
            else DecisionReasonCode.FADING_JUSTIFIED
        )
        return AssistanceLevel.INDEPENDENT_RETRY, [
            DecisionReasonCode.SUCCESS_AFTER_ASSISTANCE,
            transition_reason,
        ]

    if context.previous_hint_effective is True and previous is not None:
        if _substantial_difficulty_remains(context):
            return previous, [DecisionReasonCode.SUPPORT_MAINTAINED]
        faded_level = _adjacent_level(previous, -1)
        transition_reason = (
            DecisionReasonCode.SUPPORT_MAINTAINED
            if faded_level is previous
            else DecisionReasonCode.FADING_JUSTIFIED
        )
        return faded_level, [transition_reason]

    if context.previous_hint_effective is False and previous is not None:
        if _escalation_is_justified(context):
            return _adjacent_level(previous, 1), [DecisionReasonCode.ESCALATION_JUSTIFIED]
        return previous, [DecisionReasonCode.SUPPORT_MAINTAINED]

    if previous is not None:
        return previous, [DecisionReasonCode.SUPPORT_MAINTAINED]

    return _initial_level(context), [DecisionReasonCode.MINIMUM_SUFFICIENT_ASSISTANCE]


def _initial_level(context: TutoringContext) -> AssistanceLevel:
    assert context.error_severity is not None
    high_mastery = context.mastery >= HIGH_MASTERY_MIN
    low_mastery = context.mastery <= LOW_MASTERY_MAX
    high_support = context.support_need >= HIGH_SUPPORT_NEED_MIN
    low_error = context.error_severity <= LOW_ERROR_SEVERITY_MAX
    high_error = context.error_severity >= HIGH_ERROR_SEVERITY_MIN

    if high_mastery:
        if low_error:
            return AssistanceLevel.INDEPENDENT_RETRY
        if high_error:
            return AssistanceLevel.CONCEPTUAL_HINT
        return AssistanceLevel.METACOGNITIVE_PROMPT

    if low_mastery and high_support and high_error:
        return AssistanceLevel.TARGETED_HINT
    if low_mastery or high_support or high_error:
        return AssistanceLevel.CONCEPTUAL_HINT
    return AssistanceLevel.METACOGNITIVE_PROMPT


def _escalation_is_justified(context: TutoringContext) -> bool:
    assert context.error_severity is not None
    previous = context.previous_assistance_level
    if previous is None or previous is AssistanceLevel.FULL_EXPLANATION:
        return False

    required_attempts = _ESCALATION_ATTEMPTS[previous]
    strong_combined_difficulty = (
        context.support_need >= HIGH_SUPPORT_NEED_MIN
        and context.error_severity >= HIGH_ERROR_SEVERITY_MIN
    )
    if strong_combined_difficulty and previous in {
        AssistanceLevel.METACOGNITIVE_PROMPT,
        AssistanceLevel.CONCEPTUAL_HINT,
    }:
        required_attempts -= 1

    return context.attempt_count >= required_attempts


def _substantial_difficulty_remains(context: TutoringContext) -> bool:
    assert context.error_severity is not None
    previous = context.previous_assistance_level
    if previous is None:
        return False

    required_attempts = _ESCALATION_ATTEMPTS.get(
        previous, max(_ESCALATION_ATTEMPTS.values())
    )
    return (
        context.mastery <= LOW_MASTERY_MAX
        and context.support_need >= HIGH_SUPPORT_NEED_MIN
        and context.error_severity >= HIGH_ERROR_SEVERITY_MIN
        and context.attempt_count >= required_attempts
    )


def _adjacent_level(level: AssistanceLevel, offset: int) -> AssistanceLevel:
    index = min(max(_LEVELS.index(level) + offset, 0), len(_LEVELS) - 1)
    return _LEVELS[index]


def _evidence_reasons(context: TutoringContext) -> list[DecisionReasonCode]:
    assert context.error_severity is not None
    reasons: list[DecisionReasonCode] = []
    if context.attempt_count == 1:
        reasons.append(DecisionReasonCode.FIRST_ATTEMPT)
    elif not context.is_correct:
        reasons.append(DecisionReasonCode.REPEATED_DIFFICULTY)

    if context.mastery >= HIGH_MASTERY_MIN:
        reasons.append(DecisionReasonCode.HIGH_MASTERY)
    elif context.mastery <= LOW_MASTERY_MAX:
        reasons.append(DecisionReasonCode.LOW_MASTERY)

    if context.support_need >= HIGH_SUPPORT_NEED_MIN:
        reasons.append(DecisionReasonCode.HIGH_SUPPORT_NEED)

    if context.error_severity <= LOW_ERROR_SEVERITY_MAX:
        reasons.append(DecisionReasonCode.LOW_ERROR_SEVERITY)
    elif context.error_severity >= HIGH_ERROR_SEVERITY_MIN:
        reasons.append(DecisionReasonCode.HIGH_ERROR_SEVERITY)

    if context.previous_hint_effective is True:
        reasons.append(DecisionReasonCode.PREVIOUS_HINT_EFFECTIVE)
    elif context.previous_hint_effective is False:
        reasons.append(DecisionReasonCode.PREVIOUS_HINT_INEFFECTIVE)
    elif context.previous_assistance_level is not None:
        reasons.append(DecisionReasonCode.PREVIOUS_HINT_EFFECTIVENESS_UNKNOWN)

    return reasons
