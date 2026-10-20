from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.adaptive_tutor.application import (
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
)
from app.adaptive_tutor.infrastructure import LearnerStateSupportNeedProvider
from app.learner_state.application.support_need import (
    SupportNeedRequest,
    SupportNeedResult,
    SupportNeedStatus,
)

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000021")
OTHER_LEARNER_ID = UUID("00000000-0000-4000-8000-000000000022")
SKILL_ID = "MAT-FRC"
SESSION_ID = "trusted-session"
AS_OF = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)
OBSERVED_AT = AS_OF - timedelta(seconds=30)


class StubLearnerStateProvider:
    def __init__(self, result: object | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[SupportNeedRequest] = []

    def get_support_need(self, request: SupportNeedRequest) -> object:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def context_request(**overrides: object) -> ContextEvidenceRequest:
    return ContextEvidenceRequest.model_validate(
        {
            "learner_id": LEARNER_ID,
            "skill_id": SKILL_ID,
            "session_id": SESSION_ID,
            "as_of": AS_OF,
            "max_age_ms": 60_000,
            **overrides,
        }
    )


def learner_state_result(
    status: SupportNeedStatus = SupportNeedStatus.AVAILABLE,
    *,
    learner_id: UUID = LEARNER_ID,
    skill_id: str = SKILL_ID,
    session_id: str | None = SESSION_ID,
    observed_at: datetime | None = OBSERVED_AT,
    support_need: float | None = 0.625,
) -> SupportNeedResult:
    if status is not SupportNeedStatus.AVAILABLE:
        support_need = None
    if status is SupportNeedStatus.NOT_FOUND:
        session_id = None
        observed_at = None
    return SupportNeedResult(
        learner_id=learner_id,
        skill_id=skill_id,
        status=status,
        session_id=session_id,
        observed_at=observed_at,
        support_need=support_need,
    )


def adapter(provider: StubLearnerStateProvider) -> LearnerStateSupportNeedProvider:
    return LearnerStateSupportNeedProvider(provider)  # type: ignore[arg-type]


def test_available_support_need_and_trusted_constraints_are_preserved() -> None:
    upstream = StubLearnerStateProvider(learner_state_result(support_need=0.625))
    real = adapter(upstream)

    result = real.get_support_need(context_request())

    assert result.status is EvidenceStatus.AVAILABLE
    assert result.support_need == 0.625
    assert upstream.requests == [
        SupportNeedRequest(
            learner_id=LEARNER_ID,
            skill_id=SKILL_ID,
            session_id=SESSION_ID,
            max_age_ms=60_000,
            as_of=AS_OF,
        )
    ]
    assert real.source.origin is EvidenceOrigin.REAL
    assert real.source.source_id == "learner-state:stored-support-need"


@pytest.mark.parametrize("missing", ["session_id", "as_of", "max_age_ms"])
def test_missing_trusted_context_fails_closed_without_calling_provider(missing: str) -> None:
    upstream = StubLearnerStateProvider(learner_state_result())

    result = adapter(upstream).get_support_need(context_request(**{missing: None}))

    assert result.status is EvidenceStatus.CONTEXT_REQUIRED
    assert result.support_need is None
    assert upstream.requests == []


@pytest.mark.parametrize(
    ("upstream_status", "expected_status"),
    [
        (SupportNeedStatus.NOT_FOUND, EvidenceStatus.NOT_FOUND),
        (SupportNeedStatus.UNCERTAIN, EvidenceStatus.UNCERTAIN),
        (SupportNeedStatus.STALE, EvidenceStatus.STALE),
    ],
)
def test_unavailable_learner_state_statuses_remain_distinct(
    upstream_status: SupportNeedStatus,
    expected_status: EvidenceStatus,
) -> None:
    result = adapter(
        StubLearnerStateProvider(learner_state_result(upstream_status))
    ).get_support_need(context_request())

    assert result.status is expected_status
    assert result.support_need is None


def test_explicit_experimental_missing_state_uses_labelled_zero_default() -> None:
    real = LearnerStateSupportNeedProvider(
        StubLearnerStateProvider(learner_state_result(SupportNeedStatus.NOT_FOUND)),  # type: ignore[arg-type]
        not_found_default=0.0,
    )

    result = real.get_support_need(context_request())

    assert result.status is EvidenceStatus.AVAILABLE
    assert result.support_need == 0.0
    assert real.source == EvidenceSource(
        source_id="adaptive-tutor:experimental-missing-support-need-default",
        origin=EvidenceOrigin.SYNTHETIC,
    )


def test_experimental_default_does_not_hide_uncertain_state() -> None:
    real = LearnerStateSupportNeedProvider(
        StubLearnerStateProvider(learner_state_result(SupportNeedStatus.UNCERTAIN)),  # type: ignore[arg-type]
        not_found_default=0.0,
    )

    assert real.get_support_need(context_request()).status is EvidenceStatus.UNCERTAIN


@pytest.mark.parametrize(
    ("age", "expected_status"),
    [
        (timedelta(milliseconds=60_000), EvidenceStatus.AVAILABLE),
        (timedelta(milliseconds=60_001), EvidenceStatus.STALE),
    ],
)
def test_freshness_boundary_is_inclusive(
    age: timedelta,
    expected_status: EvidenceStatus,
) -> None:
    result = adapter(
        StubLearnerStateProvider(learner_state_result(observed_at=AS_OF - age))
    ).get_support_need(context_request())

    assert result.status is expected_status


def test_future_observation_is_invalid() -> None:
    result = adapter(
        StubLearnerStateProvider(
            learner_state_result(observed_at=AS_OF + timedelta(microseconds=1))
        )
    ).get_support_need(context_request())

    assert result.status is EvidenceStatus.INVALID_EVIDENCE


def test_wrong_session_is_distinct_from_age_staleness() -> None:
    result = adapter(
        StubLearnerStateProvider(learner_state_result(session_id="another-session"))
    ).get_support_need(context_request())

    assert result.status is EvidenceStatus.SESSION_MISMATCH


@pytest.mark.parametrize(
    "result",
    [
        learner_state_result(learner_id=OTHER_LEARNER_ID),
        learner_state_result(skill_id="MAT-OPS"),
    ],
    ids=["wrong-learner", "wrong-skill"],
)
def test_result_identity_mismatch_is_invalid(result: SupportNeedResult) -> None:
    mapped = adapter(StubLearnerStateProvider(result)).get_support_need(context_request())

    assert mapped.status is EvidenceStatus.INVALID_EVIDENCE


@pytest.mark.parametrize("support_need", [float("nan"), float("inf"), -0.01, 1.01])
def test_invalid_numeric_support_need_fails_closed(support_need: float) -> None:
    malformed = SupportNeedResult.model_construct(
        learner_id=LEARNER_ID,
        skill_id=SKILL_ID,
        status=SupportNeedStatus.AVAILABLE,
        support_need=support_need,
        observed_at=OBSERVED_AT,
        session_id=SESSION_ID,
    )

    result = adapter(StubLearnerStateProvider(malformed)).get_support_need(context_request())

    assert result.status is EvidenceStatus.INVALID_EVIDENCE


@pytest.mark.parametrize(
    "malformed",
    [
        SupportNeedResult.model_construct(
            learner_id=LEARNER_ID,
            skill_id=SKILL_ID,
            status=SupportNeedStatus.AVAILABLE,
            support_need=None,
            observed_at=OBSERVED_AT,
            session_id=SESSION_ID,
        ),
        SupportNeedResult.model_construct(
            learner_id=LEARNER_ID,
            skill_id=SKILL_ID,
            status=SupportNeedStatus.UNCERTAIN,
            support_need=0.5,
            observed_at=OBSERVED_AT,
            session_id=SESSION_ID,
        ),
        {
            "learner_id": LEARNER_ID,
            "skill_id": SKILL_ID,
            "status": "AVAILABLE",
            "support_need": 0.5,
            "observed_at": "not-a-time",
            "session_id": SESSION_ID,
        },
    ],
    ids=["available-null", "numeric-uncertain", "invalid-time"],
)
def test_contradictory_or_malformed_result_fails_closed(malformed: object) -> None:
    result = adapter(StubLearnerStateProvider(malformed)).get_support_need(context_request())

    assert result.status is EvidenceStatus.INVALID_EVIDENCE


def test_database_naive_observation_is_interpreted_as_utc() -> None:
    naive = OBSERVED_AT.replace(tzinfo=None)

    result = adapter(
        StubLearnerStateProvider(learner_state_result(observed_at=naive))
    ).get_support_need(context_request())

    assert result.status is EvidenceStatus.AVAILABLE


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (TimeoutError("timed out"), EvidenceStatus.PROVIDER_UNAVAILABLE),
        (ConnectionError("offline"), EvidenceStatus.PROVIDER_UNAVAILABLE),
        (SQLAlchemyError("database failed"), EvidenceStatus.PROVIDER_ERROR),
        (RuntimeError("unexpected"), EvidenceStatus.PROVIDER_ERROR),
    ],
)
def test_provider_failures_are_mapped_safely(
    error: Exception,
    expected_status: EvidenceStatus,
) -> None:
    result = adapter(StubLearnerStateProvider(error=error)).get_support_need(context_request())

    assert result.status is expected_status
    assert result.support_need is None


def test_trusted_as_of_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        context_request(as_of=datetime(2026, 10, 17, 10, 0))  # noqa: DTZ001 - validates rejection
