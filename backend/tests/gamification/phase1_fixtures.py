"""Deterministic synthetic-only episode-contract fixtures; never educational-effectiveness evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.gamification.api.research_contracts import (
    EVENT_SCHEMA_VERSION,
    EventEnvelopeContract,
)
from app.gamification.domain.types import EpisodePhase

SYNTHETIC = True
AT = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)
LEARNER_ID = UUID("10000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("10000000-0000-4000-8000-000000000002")
EPISODE_ID = UUID("10000000-0000-4000-8000-000000000003")
PRESENTATION_ID = UUID("10000000-0000-4000-8000-000000000004")

COMPLETE_PHASES = (
    EpisodePhase.CREATED,
    EpisodePhase.BASELINE_RESERVED,
    EpisodePhase.BASELINE_ACTIVE,
    EpisodePhase.BASELINE_SCORED,
    EpisodePhase.GAMEPLAY_ACTIVE,
    EpisodePhase.DIFFICULTY_DETECTED,
    EpisodePhase.MISCONCEPTION_ESTIMATED,
    EpisodePhase.SUPPORT_DECIDED,
    EpisodePhase.SUPPORT_ACTIVE,
    EpisodePhase.SUPPORTED_PRACTICE_COMPLETE,
    EpisodePhase.SUPPORT_WITHDRAWN,
    EpisodePhase.INDEPENDENT_CHECK_ACTIVE,
    EpisodePhase.INDEPENDENT_CHECK_SCORED,
    EpisodePhase.REWARD_VALIDATED,
    EpisodePhase.POLICY_UPDATED,
    EpisodePhase.COMPLETED,
)


@dataclass(frozen=True, slots=True)
class SyntheticScenario:
    label: str
    synthetic: bool = SYNTHETIC
    phases: tuple[EpisodePhase, ...] = COMPLETE_PHASES
    support_active_at_probe: bool = False
    probe_contaminated: bool = False


VALID_COMPLETE_EPISODE = SyntheticScenario("valid_complete_episode")
ILLEGAL_TRANSITION = SyntheticScenario(
    "illegal_transition",
    phases=(EpisodePhase.CREATED, EpisodePhase.BASELINE_SCORED),
)
INCOMPLETE_EPISODE = SyntheticScenario(
    "incomplete_episode",
    phases=COMPLETE_PHASES[:8],
)
SUPPORT_STILL_ACTIVE = SyntheticScenario(
    "support_still_active",
    phases=COMPLETE_PHASES[:9] + (EpisodePhase.INDEPENDENT_CHECK_ACTIVE,),
    support_active_at_probe=True,
)
CONTAMINATED_PROBE = SyntheticScenario(
    "contaminated_probe",
    phases=COMPLETE_PHASES[:13],
    probe_contaminated=True,
)


def event(sequence: int, *, event_id_suffix: int | None = None) -> EventEnvelopeContract:
    suffix = event_id_suffix if event_id_suffix is not None else sequence
    event_type = "item_opened" if sequence == 1 else "answer_submitted"
    payload = (
        {"item_revision_id": "synthetic-item-r1", "measurement_role": "unsupported_before"}
        if event_type == "item_opened"
        else {"attempt_id": f"synthetic-attempt-{sequence}", "response_digest": "sha256:synthetic"}
    )
    return EventEnvelopeContract(
        schema_version=EVENT_SCHEMA_VERSION,
        payload_schema_version="event-payload-v1",
        event_id=UUID(f"20000000-0000-4000-8000-{suffix:012d}"),
        learner_id=LEARNER_ID,
        session_id=SESSION_ID,
        episode_id=EPISODE_ID,
        presentation_id=PRESENTATION_ID,
        sequence=sequence,
        client_occurred_at=AT + timedelta(seconds=sequence),
        server_received_at=AT + timedelta(seconds=sequence, milliseconds=50),
        offline_batch_id=UUID("20000000-0000-4000-8000-000000000099"),
        event_type=event_type,
        payload=payload,
    )


DUPLICATE_EVENTS = (event(1), event(1))
MISSING_SEQUENCE_EVENTS = (event(1), event(3))
