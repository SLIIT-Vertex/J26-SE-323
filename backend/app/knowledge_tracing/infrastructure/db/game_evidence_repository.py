"""Reads the game's outbox table (`learner_evidence_outbox`) without touching it.

The table belongs to the gamified module. This file describes only the columns that are read, in a
separate, private `MetaData`, so it never imports that module's classes (they are being renamed) and
Alembic never sees it. It only ever SELECTs.
"""

from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Uuid,
    and_,
    inspect,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.game_evidence import EVENT_TYPE, GameEvidence

_outbox = Table(
    "learner_evidence_outbox",
    MetaData(),
    Column("id", Uuid),
    Column("idempotency_key", String),
    Column("event_type", String),
    Column("learner_id", Uuid),
    Column("skill_code", String),
    Column("universal_skill_id", String),
    Column("payload_json", JSON().with_variant(JSONB(), "postgresql")),
    Column("contract_version", String),
    Column("created_at", DateTime(timezone=True)),
)


class OutboxEvidenceSource:
    def __init__(self, session: Session) -> None:
        self.session = session

    def available(self) -> bool:
        """False when this database has no outbox table (the game's migrations were not run)."""
        return inspect(self.session.get_bind()).has_table(_outbox.name)

    def batches(self, size: int) -> Iterator[list[GameEvidence]]:
        """Every scored-answer record, oldest first. Paged by (time, id) so none is missed."""
        cursor: tuple[datetime, UUID] | None = None
        while True:
            statement = (
                select(_outbox)
                .where(_outbox.c.event_type == EVENT_TYPE)
                .order_by(_outbox.c.created_at, _outbox.c.id)
                .limit(size)
            )
            if cursor is not None:
                moment, last = cursor
                statement = statement.where(
                    or_(
                        _outbox.c.created_at > moment,
                        and_(_outbox.c.created_at == moment, _outbox.c.id > last),
                    )
                )
            rows = self.session.execute(statement).all()
            if not rows:
                return
            cursor = (rows[-1].created_at, rows[-1].id)
            yield [
                GameEvidence(
                    key=row.idempotency_key,
                    learner_id=row.learner_id,
                    game_skill_id=row.skill_code,
                    universal_skill_id=row.universal_skill_id,
                    event_type=row.event_type,
                    payload=row.payload_json if isinstance(row.payload_json, dict) else {},
                    contract_version=row.contract_version,
                    created_at=row.created_at,
                )
                for row in rows
            ]
