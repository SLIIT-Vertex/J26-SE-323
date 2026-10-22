"""Freshness-aware adapter from Learner State to Tutor support-need evidence."""

import logging
import math
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.adaptive_tutor.application.context_assembly import (
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    SupportNeedResult,
)
from app.learner_state.application.support_need import (
    SupportNeedProvider as LearnerStateProvider,
)
from app.learner_state.application.support_need import (
    SupportNeedRequest as LearnerStateRequest,
)
from app.learner_state.application.support_need import (
    SupportNeedResult as LearnerStateResult,
)
from app.learner_state.application.support_need import SupportNeedStatus

logger = logging.getLogger("mindbridge.adaptive_tutor.learner_state")


MISSING_SUPPORT_NEED_SOURCE = EvidenceSource(
    source_id="adaptive-tutor:experimental-missing-support-need-default",
    origin=EvidenceOrigin.SYNTHETIC,
)


class _DefaultSupportNeed(SupportNeedResult):
    """Internal marker: this value is the configured default, not stored Learner State."""


class LearnerStateSupportNeedProvider:
    """Require trusted session and time bounds before exposing stored support need."""

    source = EvidenceSource(
        source_id="learner-state:stored-support-need",
        origin=EvidenceOrigin.REAL,
    )

    def __init__(
        self,
        provider: LearnerStateProvider,
        *,
        not_found_default: float | None = None,
    ) -> None:
        self._provider = provider
        if not_found_default is not None and (
            not math.isfinite(not_found_default) or not 0.0 <= not_found_default <= 1.0
        ):
            raise ValueError("not_found_default must be within [0, 1]")
        self._not_found_default = not_found_default

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        return self.get_support_need_with_source(request)[0]

    def get_support_need_with_source(
        self, request: ContextEvidenceRequest
    ) -> tuple[SupportNeedResult, EvidenceSource]:
        """Per-value provenance: stored Learner State is REAL; only the default is SYNTHETIC."""

        result = self._lookup(request)
        if isinstance(result, _DefaultSupportNeed):
            return SupportNeedResult.model_validate(
                result.model_dump()
            ), MISSING_SUPPORT_NEED_SOURCE
        return result, self.source

    def _lookup(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        if request.session_id is None or request.as_of is None or request.max_age_ms is None:
            return self._result(EvidenceStatus.CONTEXT_REQUIRED)

        try:
            raw_result = self._provider.get_support_need(
                LearnerStateRequest(
                    learner_id=request.learner_id,
                    skill_id=request.skill_id,
                    session_id=request.session_id,
                    max_age_ms=request.max_age_ms,
                    as_of=request.as_of,
                )
            )
        except (ConnectionError, TimeoutError, OperationalError) as error:
            logger.warning("Learner State is unavailable: %s", type(error).__name__)
            return self._result(EvidenceStatus.PROVIDER_UNAVAILABLE)
        except SQLAlchemyError as error:
            logger.error("Learner State repository failed: %s", type(error).__name__)
            return self._result(EvidenceStatus.PROVIDER_ERROR)
        except Exception as error:
            logger.exception("Learner State provider failed unexpectedly: %s", type(error).__name__)
            return self._result(EvidenceStatus.PROVIDER_ERROR)

        try:
            result = LearnerStateResult.model_validate(
                raw_result.model_dump()
                if isinstance(raw_result, LearnerStateResult)
                else raw_result,
                from_attributes=True,
            )
        except (TypeError, ValidationError):
            return self._result(EvidenceStatus.INVALID_EVIDENCE)

        if (result.learner_id, result.skill_id) != (request.learner_id, request.skill_id):
            return self._result(EvidenceStatus.INVALID_EVIDENCE)
        if result.status is SupportNeedStatus.NOT_FOUND:
            if self._not_found_default is not None:
                return _DefaultSupportNeed(
                    status=EvidenceStatus.AVAILABLE,
                    support_need=self._not_found_default,
                )
            return self._result(EvidenceStatus.NOT_FOUND)
        if result.observed_at is None or result.session_id is None:
            return self._result(EvidenceStatus.INVALID_EVIDENCE)
        if result.session_id != request.session_id:
            return self._result(EvidenceStatus.SESSION_MISMATCH)

        age = _as_utc(request.as_of) - _as_utc(result.observed_at)
        if age < timedelta(0):
            return self._result(EvidenceStatus.INVALID_EVIDENCE)
        if age > timedelta(milliseconds=request.max_age_ms):
            return self._result(EvidenceStatus.STALE)
        if result.status is SupportNeedStatus.STALE:
            return self._result(EvidenceStatus.STALE)
        if result.status is SupportNeedStatus.UNCERTAIN:
            return self._result(EvidenceStatus.UNCERTAIN)
        if result.status is not SupportNeedStatus.AVAILABLE:
            return self._result(EvidenceStatus.INVALID_EVIDENCE)

        try:
            return SupportNeedResult(
                status=EvidenceStatus.AVAILABLE,
                support_need=result.support_need,
            )
        except ValidationError:
            return self._result(EvidenceStatus.INVALID_EVIDENCE)

    @staticmethod
    def _result(status: EvidenceStatus) -> SupportNeedResult:
        return SupportNeedResult(status=status)


def _as_utc(moment: datetime) -> datetime:
    """Match Learner State's convention that database-naive timestamps are UTC."""
    return moment.astimezone(UTC) if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
