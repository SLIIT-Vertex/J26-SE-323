from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adaptive_tutor.application import TutoringContext
from app.adaptive_tutor.domain import AssistanceLevel


def context_data() -> dict[str, object]:
    return {
        "learner_id": uuid4(),
        "skill_id": "MAT-FRC",
        "mastery": 0.5,
        "support_need": 0.5,
        "attempt_count": 1,
        "is_correct": False,
        "error_severity": 0.5,
        "previous_assistance_level": AssistanceLevel.CONCEPTUAL_HINT,
        "previous_hint_effective": False,
    }


def test_valid_skill_id_is_accepted() -> None:
    context = TutoringContext.model_validate(context_data())

    assert context.skill_id == "MAT-FRC"


@pytest.mark.parametrize("skill_id", ["", "   "])
def test_skill_id_cannot_be_empty(skill_id: str) -> None:
    data = context_data()
    data["skill_id"] = skill_id

    with pytest.raises(ValidationError):
        TutoringContext.model_validate(data)


@pytest.mark.parametrize("field", ["mastery", "support_need", "error_severity"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_normalized_values_must_be_between_zero_and_one(field: str, value: float) -> None:
    data = context_data()
    data[field] = value

    with pytest.raises(ValidationError):
        TutoringContext.model_validate(data)


def test_attempt_count_cannot_be_negative() -> None:
    data = context_data()
    data["attempt_count"] = -1

    with pytest.raises(ValidationError):
        TutoringContext.model_validate(data)


@pytest.mark.parametrize(
    ("is_correct", "error_severity"),
    [(True, None), (False, None), (None, 0.5)],
)
def test_pre_interaction_rejects_completed_attempt_evidence(
    is_correct: bool | None, error_severity: float | None
) -> None:
    data = context_data()
    data.update(
        attempt_count=0,
        is_correct=is_correct,
        error_severity=error_severity,
    )

    with pytest.raises(
        ValidationError,
        match="is_correct and error_severity must be null when attempt_count is 0",
    ):
        TutoringContext.model_validate(data)


def test_pre_interaction_accepts_null_attempt_evidence() -> None:
    data = context_data()
    data.update(attempt_count=0, is_correct=None, error_severity=None)

    context = TutoringContext.model_validate(data)

    assert context.is_correct is None
    assert context.error_severity is None


@pytest.mark.parametrize("field", ["is_correct", "error_severity"])
def test_completed_attempt_requires_outcome_evidence(field: str) -> None:
    data = context_data()
    data[field] = None

    with pytest.raises(
        ValidationError,
        match="is_correct and error_severity are required when attempt_count is at least 1",
    ):
        TutoringContext.model_validate(data)


def test_completed_attempt_accepts_normal_outcome_evidence() -> None:
    context = TutoringContext.model_validate(context_data())

    assert context.is_correct is False
    assert context.error_severity == 0.5


def test_assistance_level_must_be_valid() -> None:
    data = context_data()
    data["previous_assistance_level"] = "L7"

    with pytest.raises(ValidationError):
        TutoringContext.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [("mastery", "0.5"), ("attempt_count", 1.5), ("is_correct", "false")],
)
def test_contract_does_not_coerce_ambiguous_types(field: str, value: object) -> None:
    data = context_data()
    data[field] = value

    with pytest.raises(ValidationError):
        TutoringContext.model_validate(data)


def test_previous_state_fields_may_be_null() -> None:
    data = context_data()
    data["previous_assistance_level"] = None
    data["previous_hint_effective"] = None

    context = TutoringContext.model_validate(data)

    assert context.previous_assistance_level is None
    assert context.previous_hint_effective is None


@pytest.mark.parametrize("previous_hint_effective", [True, False])
def test_hint_effectiveness_requires_previous_assistance(
    previous_hint_effective: bool,
) -> None:
    data = context_data()
    data["previous_assistance_level"] = None
    data["previous_hint_effective"] = previous_hint_effective

    with pytest.raises(
        ValidationError,
        match="previous_hint_effective requires a previous_assistance_level",
    ):
        TutoringContext.model_validate(data)


def test_boundary_values_are_valid() -> None:
    data = context_data()
    data.update(mastery=0.0, support_need=1.0, error_severity=0.0)

    context = TutoringContext.model_validate(data)

    assert context.mastery == 0.0
    assert context.support_need == 1.0
