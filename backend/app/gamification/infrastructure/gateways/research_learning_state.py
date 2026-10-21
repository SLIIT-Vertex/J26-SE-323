"""Read only the published Learning State support-need contract."""

from datetime import UTC, datetime
from uuid import UUID

from app.learner_state.application.support_need import (
    RECOMMENDED_MAX_STATE_AGE_MS,
    SupportNeedProvider,
    SupportNeedRequest,
)


def read_learning_state(
    provider: SupportNeedProvider | None,
    *,
    learner_id: UUID,
    skill_id: str,
    session_id: str,
    at: datetime,
) -> dict[str, object]:
    if provider is None:
        return {"status": "not_available", "reason": "NOT_FOUND"}
    try:
        result = provider.get_support_need(
            SupportNeedRequest(
                learner_id=learner_id,
                skill_id=skill_id,
                session_id=session_id,
                max_age_ms=RECOMMENDED_MAX_STATE_AGE_MS,
            )
        )
        if result.status != "AVAILABLE" and not (
            result.status == "UNCERTAIN"
            and result.recommended_action == "request_reengagement_support"
        ):
            return {"status": "not_available", "reason": str(result.status)}
        observed = result.observed_at
        observed = observed.replace(tzinfo=UTC) if observed.tzinfo is None else observed
        age_ms = int((at - observed).total_seconds() * 1000)
        if result.session_id != session_id or not 0 <= age_ms <= RECOMMENDED_MAX_STATE_AGE_MS:
            return {"status": "not_available", "reason": "STALE"}
        state = (
            "disengaged"
            if result.recommended_action == "request_reengagement_support"
            else "confused"
            if result.support_need is not None and result.support_need >= 0.6
            else "calm"
        )
        return {
            "status": "available",
            "state": state,
            "support_need": result.support_need,
            "age_ms": age_ms,
            "observed_at": observed.isoformat(),
            "session_id": session_id,
        }
    except Exception:  # noqa: BLE001 -- optional provider failures cannot fail a game
        # Optional evidence cannot fail a game or silently reuse a stale reading.
        return {"status": "not_available", "reason": "PROVIDER_UNAVAILABLE"}


class ResearchLearningStateGateway:
    def __init__(self, provider: SupportNeedProvider):
        self.provider = provider

    def read(self, *, learner_id, skill_id, session_id, at):
        return read_learning_state(
            self.provider, learner_id=learner_id, skill_id=skill_id, session_id=session_id, at=at
        )
