"""In-memory and outbox publishers for gamification-learner-evidence-v1."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.api.contracts import LearnerEvidenceContract
from app.gamification.application.records import LearnerEvidenceEvent
from app.gamification.infrastructure.db.models import LearnerEvidenceOutboxModel


class InMemoryLearnerEvidencePublisher:
    def __init__(self) -> None:
        self.events: list[LearnerEvidenceEvent] = []
        self._payloads: dict[str, dict[str, object]] = {}

    def publish(self, event: LearnerEvidenceEvent) -> None:
        payload = LearnerEvidenceContract.model_validate(event.as_contract()).model_dump(
            mode="json"
        )
        if event.idempotency_key in self._payloads:
            return
        self._payloads[event.idempotency_key] = payload
        self.events.append(event)

    def payload(self, idempotency_key: str) -> dict[str, object]:
        return self._payloads[idempotency_key]


class SqlAlchemyLearnerEvidenceOutbox:
    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(self, event: LearnerEvidenceEvent) -> None:
        payload = LearnerEvidenceContract.model_validate(event.as_contract()).model_dump(
            mode="json"
        )
        existing = self._session.scalar(
            select(LearnerEvidenceOutboxModel).where(
                LearnerEvidenceOutboxModel.idempotency_key == event.idempotency_key
            )
        )
        if existing is not None:
            existing.attempt_count += 1
            return
        self._session.add(
            LearnerEvidenceOutboxModel(
                id=uuid4(),
                idempotency_key=event.idempotency_key,
                event_type=event.event_type,
                learner_id=event.learner_id,
                skill_code=event.skill_id,
                universal_skill_id=event.universal_skill_id,
                payload_json=payload,
                contract_version="gamification-learner-evidence-v1",
                status="pending",
                attempt_count=1,
                created_at=datetime.now(UTC),
            )
        )
        self._session.flush()
