"""Durable purpose-specific consent decisions (for example `learner_state_camera`)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.gamification.application.records import ConsentDecision
from app.gamification.domain.types import ContractVersion
from app.gamification.infrastructure.db.models import ConsentDecisionModel

CONSENT_CONTRACT = ContractVersion("consent-decision-v1")


def _utc(value: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes even for timezone-aware columns.
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class SqlAlchemyConsentStore:
    """Keeps the latest decision per learner and purpose; a new decision replaces the old one."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_consent(self, *, learner_id: UUID, purpose: str) -> ConsentDecision:
        row = self._session.get(ConsentDecisionModel, (learner_id, purpose))
        if row is None:
            raise LookupError("no consent decision exists for learner and purpose")
        decided_at = _utc(row.decided_at)
        assert decided_at is not None
        return ConsentDecision(
            learner_id=row.learner_id,
            purpose=row.purpose,
            granted=row.granted,
            consent_version=row.consent_version,
            decided_at=decided_at,
            expires_at=_utc(row.expires_at),
            contract_version=CONSENT_CONTRACT,
        )

    def record(self, decision: ConsentDecision) -> None:
        row = self._session.get(ConsentDecisionModel, (decision.learner_id, decision.purpose))
        if row is None:
            row = ConsentDecisionModel(learner_id=decision.learner_id, purpose=decision.purpose)
            self._session.add(row)
        row.granted = decision.granted
        row.consent_version = decision.consent_version
        row.decided_at = decision.decided_at
        row.expires_at = decision.expires_at
        self._session.commit()
