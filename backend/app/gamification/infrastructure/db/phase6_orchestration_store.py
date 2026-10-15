"""Transactional persistence for the durable orchestration boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gamification.application.phase6_orchestration import (
    Phase6PersistenceError,
    StoredPhase6Run,
)
from app.gamification.infrastructure.db.models import (
    LearningRewardEntryModel,
    Phase6AuditEventModel,
    Phase6EpisodeEventModel,
    Phase6EpisodeRunModel,
    Phase6IdempotencyReceiptModel,
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class SqlAlchemyPhase6Store:
    """One transaction owns a command receipt, projection, events, and audit rows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _row(self, episode_id: UUID, *, for_update: bool = False) -> Phase6EpisodeRunModel:
        statement = select(Phase6EpisodeRunModel).where(
            Phase6EpisodeRunModel.episode_id == episode_id
        )
        if for_update and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        row = self.session.scalar(statement)
        if row is None:
            raise Phase6PersistenceError("EPISODE_NOT_FOUND")
        if digest(row.state_json) != row.state_sha256:
            raise Phase6PersistenceError("STATE_HASH_MISMATCH")
        return row

    def get(self, episode_id: UUID, *, for_update: bool = False) -> StoredPhase6Run:
        row = self._row(episode_id, for_update=for_update)
        return StoredPhase6Run(
            episode_id=row.episode_id,
            revision=row.revision,
            state=dict(row.state_json),
        )

    def receipt(self, key: str, request_sha256: str) -> dict[str, object] | None:
        row = self.session.get(Phase6IdempotencyReceiptModel, key)
        if row is None:
            return None
        if row.request_sha256 != request_sha256:
            raise Phase6PersistenceError("IDEMPOTENCY_CONFLICT")
        return dict(row.response_json)

    def create(
        self,
        *,
        state: dict[str, object],
        idempotency_key: str,
        request_sha256: str,
        response: dict[str, object],
        now: datetime,
    ) -> None:
        self._validate_key(idempotency_key)
        episode_id = UUID(str(state["episode_id"]))
        self.session.add(
            Phase6EpisodeRunModel(
                episode_id=episode_id,
                session_id=UUID(str(state["session_id"])),
                learner_id=UUID(str(state["learner_id"])),
                skill_id=str(state["skill_id"]),
                content_package_version=str(state["content_package_version"]),
                protocol_version=str(state["protocol_version"]),
                environment=str(state["environment"]),
                condition=str(state["condition"]),
                status=str(state["status"]),
                revision=int(state["revision"]),
                state_json=state,
                state_sha256=digest(state),
                created_at=now,
                updated_at=now,
            )
        )
        self._append_event(episode_id, state["events"][-1], now)
        self._audit(episode_id, "episode_opened", ("DEVELOPMENT_ONLY",), now)
        self._save_receipt(idempotency_key, request_sha256, episode_id, response, now)
        self.session.flush()

    def replace(
        self,
        *,
        episode_id: UUID,
        expected_revision: int,
        state: dict[str, object],
        new_events: tuple[dict[str, object], ...],
        audit_type: str,
        audit_reasons: tuple[str, ...],
        idempotency_key: str,
        request_sha256: str,
        response: dict[str, object],
        now: datetime,
    ) -> None:
        self._validate_key(idempotency_key)
        row = self._row(episode_id, for_update=True)
        if row.revision != expected_revision:
            raise Phase6PersistenceError("CONCURRENT_MODIFICATION")
        row.status = str(state["status"])
        row.revision = int(state["revision"])
        row.state_json = state
        row.state_sha256 = digest(state)
        row.updated_at = now
        for event in new_events:
            self._append_event(row.episode_id, event, now)
        reward = state.get("reward")
        if isinstance(reward, dict) and int(reward.get("points", 0)) > 0:
            existing_reward = self.session.scalar(
                select(LearningRewardEntryModel).where(
                    LearningRewardEntryModel.learner_id == row.learner_id,
                    LearningRewardEntryModel.episode_id == row.episode_id,
                )
            )
            if existing_reward is None:
                self.session.add(
                    LearningRewardEntryModel(
                        id=uuid4(),
                        learner_id=row.learner_id,
                        episode_id=row.episode_id,
                        points=int(reward["points"]),
                        reason_code=str(reward["reason"]),
                        created_at=now,
                    )
                )
        self._audit(row.episode_id, audit_type, audit_reasons, now)
        self._save_receipt(
            idempotency_key, request_sha256, row.episode_id, response, now
        )
        self.session.flush()

    def reconstruct(self, episode_id: UUID) -> dict[str, object]:
        row = self._row(episode_id)
        events = self.session.scalars(
            select(Phase6EpisodeEventModel)
            .where(Phase6EpisodeEventModel.episode_id == episode_id)
            .order_by(Phase6EpisodeEventModel.sequence)
        ).all()
        for event in events:
            if digest(event.payload_json) != event.payload_sha256:
                raise Phase6PersistenceError("EVENT_HASH_MISMATCH")
        expected = list(range(1, len(events) + 1))
        if [event.sequence for event in events] != expected:
            raise Phase6PersistenceError("EVENT_SEQUENCE_GAP")
        return {
            "contract_version": "phase6-reconstruction-v1",
            "episode_id": str(episode_id),
            "state": dict(row.state_json),
            "state_sha256": row.state_sha256,
            "events": [dict(event.payload_json) for event in events],
            "event_hashes": [event.payload_sha256 for event in events],
        }

    def export_manifest(self, episode_id: UUID) -> dict[str, object]:
        record = self.reconstruct(episode_id)
        state = record["state"]
        assert isinstance(state, dict)
        safe = {
            "contract_version": "phase6-research-export-v1",
            "episode_id": str(episode_id),
            "learner_id": state["learner_id"],
            "skill_id": state["skill_id"],
            "content_package_version": state["content_package_version"],
            "protocol_version": state["protocol_version"],
            "condition": state["condition"],
            "status": state["status"],
            "validity": state.get("validity"),
            "raw_independence_gain": state.get("raw_independence_gain"),
            "policy_update_status": state.get("policy_update_status"),
            "state_sha256": record["state_sha256"],
            "event_hashes": record["event_hashes"],
            "exclusions": state.get("exclusion_reasons", []),
            "contains_item_text": False,
            "contains_answers": False,
        }
        return {**safe, "manifest_sha256": digest(safe)}

    def _append_event(self, episode_id: UUID, event: object, now: datetime) -> None:
        if not isinstance(event, dict):
            raise Phase6PersistenceError("INVALID_EVENT")
        payload = dict(event)
        self.session.add(
            Phase6EpisodeEventModel(
                event_id=UUID(str(payload["event_id"])),
                episode_id=episode_id,
                sequence=int(payload["sequence"]),
                event_type=str(payload["event_type"]),
                payload_json=payload,
                payload_sha256=digest(payload),
                occurred_at=now,
            )
        )

    def _save_receipt(
        self,
        key: str,
        request_sha256: str,
        episode_id: UUID,
        response: dict[str, object],
        now: datetime,
    ) -> None:
        self.session.add(
            Phase6IdempotencyReceiptModel(
                idempotency_key=key,
                request_sha256=request_sha256,
                episode_id=episode_id,
                response_json=response,
                created_at=now,
            )
        )

    def _audit(
        self,
        episode_id: UUID,
        event_type: str,
        reasons: tuple[str, ...],
        now: datetime,
    ) -> None:
        self.session.add(
            Phase6AuditEventModel(
                id=uuid4(),
                episode_id=episode_id,
                event_type=event_type,
                reason_codes_json=list(reasons),
                metadata_json={"component": "gamification", "contract": "phase6-v1"},
                occurred_at=now,
            )
        )

    @staticmethod
    def _validate_key(key: str) -> None:
        if not key or len(key) > 128:
            raise Phase6PersistenceError("IDEMPOTENCY_KEY_REQUIRED")

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


def utc_now() -> datetime:
    return datetime.now(UTC)
