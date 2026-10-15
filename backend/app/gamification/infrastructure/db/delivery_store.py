"""Durable delivery jobs. Claim is transactional; rollback drops an uncommitted insert."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import DeliveryJobModel


class SqlAlchemyDeliveryStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self, *, kind: str, idempotency_key: str, payload: dict[str, object]
    ) -> DeliveryJobModel:
        existing = self._session.scalar(
            select(DeliveryJobModel).where(DeliveryJobModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        row = DeliveryJobModel(
            id=uuid4(),
            kind=kind,
            status="queued",
            idempotency_key=idempotency_key,
            payload_json=payload,
            attempts=0,
            claim_token=None,
            error_code=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def claim_next(self, worker_id: str) -> DeliveryJobModel | None:
        statement = (
            select(DeliveryJobModel)
            .where(DeliveryJobModel.status == "queued")
            .order_by(DeliveryJobModel.created_at)
            .limit(1)
        )
        bind = self._session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        row = self._session.scalar(statement)
        if row is None:
            return None
        row.status = "claimed"
        row.claim_token = worker_id
        row.attempts += 1
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return row
