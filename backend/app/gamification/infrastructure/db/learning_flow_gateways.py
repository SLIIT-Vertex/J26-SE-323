"""Durable local adapters for cross-component development contracts."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import LearningFlowOrchestrationError
from app.gamification.infrastructure.db.models import (
    LearnerEvidenceOutboxModel,
    LearningFlowProbeReservationModel,
)


class SqlAlchemyProbeGateway:
    """Database-enforced stand-in for the future shared reservation service."""

    version = "probe-gateway-sql-v1"

    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve(self, *, learner_id, episode_id, item_revision_id, at) -> str:
        statement = select(LearningFlowProbeReservationModel).where(
            LearningFlowProbeReservationModel.learner_id == learner_id,
            LearningFlowProbeReservationModel.item_revision_id == item_revision_id,
        )
        if self._session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        existing = self._session.scalar(statement)
        if existing is not None:
            raise LearningFlowOrchestrationError("PROBE_ALREADY_RESERVED_OR_EXPOSED")
        reservation_id = uuid5(NAMESPACE_URL, f"{episode_id}:{item_revision_id}")
        self._session.add(
            LearningFlowProbeReservationModel(
                reservation_id=reservation_id,
                episode_id=episode_id,
                learner_id=learner_id,
                item_revision_id=item_revision_id,
                gateway_version=self.version,
                status="reserved",
                reserved_at=at,
                expires_at=at + timedelta(hours=2),
                used_at=None,
                contamination_source=None,
            )
        )
        self._session.flush()
        return str(reservation_id)

    def confirm_unexposed(self, reservation_id: str) -> bool:
        row = self._session.get(LearningFlowProbeReservationModel, UUID(reservation_id))
        return row is not None and row.status == "reserved"

    def mark_used(self, reservation_id: str, *, at) -> None:
        row = self._session.get(LearningFlowProbeReservationModel, UUID(reservation_id))
        expires_at = row.expires_at if row is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if row is None or row.status != "reserved" or expires_at is None or expires_at <= at:
            raise LearningFlowOrchestrationError("PROBE_RESERVATION_UNAVAILABLE")
        row.status = "used"
        row.used_at = at
        self._session.flush()

    def contaminate(self, reservation_id: str, *, source: str) -> None:
        if source not in {"game", "paper_generator", "tutor", "worked_example"}:
            raise LearningFlowOrchestrationError("UNKNOWN_CONTAMINATION_SOURCE")
        row = self._session.get(LearningFlowProbeReservationModel, UUID(reservation_id))
        if row is None:
            raise LearningFlowOrchestrationError("PROBE_RESERVATION_UNAVAILABLE")
        row.status = "contaminated"
        row.contamination_source = source
        self._session.flush()


class SqlAlchemyLearningFlowEvidencePublisher:
    """Durable outbox publisher that preserves assistance and measurement role."""

    version = "gamification-learner-evidence-v2"

    def __init__(self, session: Session) -> None:
        self._session = session

    def publish(self, evidence: Mapping[str, object]) -> None:
        key = f"{evidence['attempt_id']}:gamification_item_scored"
        existing = self._session.scalar(
            select(LearnerEvidenceOutboxModel).where(
                LearnerEvidenceOutboxModel.idempotency_key == key
            )
        )
        if existing is not None:
            return
        payload = dict(evidence)
        if any(field in payload for field in ("answer", "prompt", "selected_option_id")):
            raise LearningFlowOrchestrationError("EVIDENCE_PAYLOAD_LEAKAGE")
        self._session.add(
            LearnerEvidenceOutboxModel(
                id=uuid4(),
                idempotency_key=key,
                event_type="gamification_item_scored",
                learner_id=UUID(str(evidence["learner_id"])),
                skill_code=str(evidence["skill_id"]),
                universal_skill_id=str(evidence["universal_skill_id"]),
                payload_json=payload,
                contract_version=self.version,
                status="pending",
                attempt_count=1,
                created_at=datetime.now(UTC),
                published_at=None,
            )
        )
        self._session.flush()
