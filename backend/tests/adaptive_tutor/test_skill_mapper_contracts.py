import pytest
from pydantic import ValidationError

from app.adaptive_tutor.application import (
    SkillMappingRequest,
    SkillMappingResult,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.domain import (
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
)


def matched_result(**overrides: object) -> SkillMappingResult:
    data: dict[str, object] = {
        "status": SkillMappingStatus.MATCHED,
        "intent": LearningIntent.EXPLANATION_REQUEST,
        "skill_id": "MAT-FRC",
        "confidence": 0.8,
        "clarification_needed": False,
        "reason_codes": [SkillMappingReasonCode.DIRECT_SKILL_EVIDENCE],
    }
    data.update(overrides)
    return SkillMappingResult.model_validate(data)


@pytest.mark.parametrize(
    "learner_message",
    [
        "How do I add these fractions?",
        "භාග දෙකක් එකතු කරන්නේ කොහොමද?",
        "இரண்டு எண்களை எப்படி வகுப்பது?",
        "bage dekak ekathu karanne kohomada?",
        "intha kanakkula epdi divide panrathu?",
        "මේ fraction eka explain pannunga",
        "How do I devide 48 by 6?",
    ],
)
def test_request_accepts_language_neutral_text(learner_message: str) -> None:
    request = SkillMappingRequest(learner_message=learner_message)

    assert request.learner_message == learner_message


@pytest.mark.parametrize("learner_message", ["", "   "])
def test_request_rejects_blank_message(learner_message: str) -> None:
    with pytest.raises(ValidationError):
        SkillMappingRequest(learner_message=learner_message)


def test_request_requires_learner_message() -> None:
    with pytest.raises(ValidationError):
        SkillMappingRequest.model_validate({})


def test_request_accepts_bounded_context_and_optional_hints() -> None:
    request = SkillMappingRequest(
        learner_message="Why did you multiply that?",
        conversation_context=[
            {"role": "LEARNER", "message": "How do I add these fractions?"},
            {"role": "TUTOR", "message": "Think about a common denominator."},
        ],
        active_skill_id="MAT-FRC",
        preferred_language="Singlish",
    )

    assert len(request.conversation_context) == 2
    assert request.active_skill_id == "MAT-FRC"


def test_request_rejects_more_than_eight_context_turns() -> None:
    turns = [{"role": "LEARNER", "message": f"turn {index}"} for index in range(9)]

    with pytest.raises(ValidationError):
        SkillMappingRequest(learner_message="Help me", conversation_context=turns)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_normalized(confidence: float) -> None:
    with pytest.raises(ValidationError):
        matched_result(confidence=confidence)


@pytest.mark.parametrize("missing_field", ["skill_id", "confidence"])
def test_matched_requires_skill_and_confidence(missing_field: str) -> None:
    data = matched_result().model_dump()
    data[missing_field] = None

    with pytest.raises(ValidationError, match="MATCHED requires skill_id and confidence"):
        SkillMappingResult.model_validate(data)


@pytest.mark.parametrize(
    "status",
    [
        SkillMappingStatus.AMBIGUOUS,
        SkillMappingStatus.NO_MATCH,
        SkillMappingStatus.NOT_SKILL_RELATED,
    ],
)
def test_non_matched_result_rejects_confirmed_skill(status: SkillMappingStatus) -> None:
    data = matched_result().model_dump()
    data.update(
        status=status,
        clarification_needed=status is SkillMappingStatus.AMBIGUOUS,
        clarification_question="Which topic do you mean?"
        if status is SkillMappingStatus.AMBIGUOUS
        else None,
    )

    with pytest.raises(
        ValidationError,
        match="only MATCHED may contain a confirmed skill_id and confidence",
    ):
        SkillMappingResult.model_validate(data)


def test_ambiguous_result_requires_question() -> None:
    with pytest.raises(
        ValidationError,
        match="clarification_question is required when clarification is needed",
    ):
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.HINT_REQUEST,
            clarification_needed=True,
        )


def test_ambiguous_result_requires_clarification() -> None:
    with pytest.raises(ValidationError, match="AMBIGUOUS requires clarification"):
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.HINT_REQUEST,
            clarification_needed=False,
        )


def test_question_is_rejected_without_clarification() -> None:
    with pytest.raises(ValidationError, match="clarification_question requires"):
        matched_result(clarification_question="Which topic do you mean?")


def test_ambiguous_result_supports_ranked_unique_candidates() -> None:
    result = SkillMappingResult(
        status=SkillMappingStatus.AMBIGUOUS,
        intent=LearningIntent.EXPLANATION_REQUEST,
        candidate_skills=[
            {"skill_id": "MAT-FRC", "confidence": 0.6},
            {"skill_id": "MAT-OPS", "confidence": 0.4},
        ],
        clarification_needed=True,
        clarification_question="Do you mean fractions or basic operations?",
        reason_codes=[SkillMappingReasonCode.MULTIPLE_CANDIDATES],
    )

    assert [candidate.skill_id for candidate in result.candidate_skills] == [
        "MAT-FRC",
        "MAT-OPS",
    ]


def test_candidate_skill_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="candidate skill IDs must be unique"):
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.HINT_REQUEST,
            candidate_skills=[
                {"skill_id": "MAT-FRC", "confidence": 0.6},
                {"skill_id": "MAT-FRC", "confidence": 0.4},
            ],
            clarification_needed=True,
            clarification_question="What part of fractions do you mean?",
        )


def test_candidate_list_is_bounded() -> None:
    candidates = [
        {"skill_id": skill_id, "confidence": 0.5}
        for skill_id in ["MAT-NUM", "MAT-OPS", "MAT-FRC", "MAT-LEN", "MAT-MAS", "MAT-TIM"]
    ]

    with pytest.raises(ValidationError):
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.FOLLOW_UP_QUESTION,
            candidate_skills=candidates,
            clarification_needed=True,
            clarification_question="Which topic do you mean?",
        )


@pytest.mark.parametrize(
    "status",
    [SkillMappingStatus.NO_MATCH, SkillMappingStatus.NOT_SKILL_RELATED],
)
def test_terminal_non_match_statuses_reject_candidates(status: SkillMappingStatus) -> None:
    with pytest.raises(ValidationError, match="must not contain candidate skills"):
        SkillMappingResult(
            status=status,
            intent=LearningIntent.OFF_TOPIC,
            candidate_skills=[{"skill_id": "MAT-FRC", "confidence": 0.2}],
            clarification_needed=False,
        )


def test_taxonomy_membership_is_validated_separately() -> None:
    valid_skill_ids = {"MAT-FRC", "MAT-OPS", "MAT-TIM"}
    request = SkillMappingRequest(
        learner_message="Can I see another fractions example?",
        active_skill_id="MAT-FRC",
    )
    result = matched_result(skill_id="MAT-FRC")

    validate_skill_ids_against_taxonomy(request, valid_skill_ids)
    validate_skill_ids_against_taxonomy(result, valid_skill_ids)


def test_taxonomy_membership_rejects_unknown_ids() -> None:
    request = SkillMappingRequest(learner_message="Help", active_skill_id="NOT-REAL")

    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        validate_skill_ids_against_taxonomy(request, {"MAT-FRC"})


def test_taxonomy_membership_checks_candidate_ids() -> None:
    result = SkillMappingResult(
        status=SkillMappingStatus.AMBIGUOUS,
        intent=LearningIntent.EXPLANATION_REQUEST,
        candidate_skills=[
            {"skill_id": "MAT-FRC", "confidence": 0.6},
            {"skill_id": "NOT-REAL", "confidence": 0.4},
        ],
        clarification_needed=True,
        clarification_question="Do you mean fractions?",
    )

    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        validate_skill_ids_against_taxonomy(result, {"MAT-FRC"})
