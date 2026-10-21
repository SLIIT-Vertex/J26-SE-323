"""Idempotent in-memory event acceptance rules used by episode-contract tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import UUID


class EventEnvelope(Protocol):
    event_id: UUID
    session_id: UUID
    sequence: int

    def model_dump_json(self, *, exclude: set[str]) -> str: ...


class EventLedgerError(ValueError):
    """Base error for a conflicting, out-of-order, or incomplete event stream."""


class EventConflictError(EventLedgerError):
    pass


class EventOrderingError(EventLedgerError):
    pass


class MissingEventSequenceError(EventLedgerError):
    pass


@dataclass(frozen=True, slots=True)
class EventAcceptance:
    event_id: UUID
    sequence: int
    duplicate: bool


class InMemoryEventLedger:
    """Accept stable retry IDs once and enforce a gap-free sequence per session.

    This is a deterministic domain-facing reference, not the durable persistence adapter.
    """

    def __init__(self) -> None:
        self._fingerprints: dict[UUID, str] = {}
        self._next_by_session: dict[UUID, int] = {}
        self._events_by_session: dict[UUID, list[EventEnvelope]] = {}

    def ingest(self, event: EventEnvelope) -> EventAcceptance:
        fingerprint = _fingerprint(event)
        known = self._fingerprints.get(event.event_id)
        if known is not None:
            if known != fingerprint:
                raise EventConflictError("a retried event_id must carry identical content")
            return EventAcceptance(event.event_id, event.sequence, duplicate=True)

        expected = self._next_by_session.get(event.session_id, 1)
        if event.sequence > expected:
            raise MissingEventSequenceError(
                f"missing sequence range {expected}-{event.sequence - 1} for session"
            )
        if event.sequence < expected:
            raise EventOrderingError("late event uses a sequence already occupied by another ID")

        self._fingerprints[event.event_id] = fingerprint
        self._events_by_session.setdefault(event.session_id, []).append(event)
        self._next_by_session[event.session_id] = expected + 1
        return EventAcceptance(event.event_id, event.sequence, duplicate=False)

    def ingest_batch(self, events: Iterable[EventEnvelope]) -> tuple[EventAcceptance, ...]:
        return tuple(self.ingest(event) for event in events)

    def events(self, session_id: UUID) -> tuple[EventEnvelope, ...]:
        return tuple(self._events_by_session.get(session_id, ()))

    def expected_sequence(self, session_id: UUID) -> int:
        return self._next_by_session.get(session_id, 1)


def _fingerprint(event: EventEnvelope) -> str:
    canonical = event.model_dump_json(exclude={"server_received_at"})
    return sha256(canonical.encode("utf-8")).hexdigest()
