from datetime import timedelta

import pytest

from app.gamification.application.event_ledger import (
    EventConflictError,
    EventOrderingError,
    InMemoryEventLedger,
    MissingEventSequenceError,
)
from app.gamification.domain import AdaptiveEpisode, EpisodePhase, EpisodeTransitionError
from app.gamification.domain.types import EpisodeId, SkillId
from tests.gamification.research_contract_fixtures import (
    AT,
    CONTAMINATED_PROBE,
    DUPLICATE_EVENTS,
    EPISODE_ID,
    ILLEGAL_TRANSITION,
    INCOMPLETE_EPISODE,
    LEARNER_ID,
    MISSING_SEQUENCE_EVENTS,
    SESSION_ID,
    SUPPORT_STILL_ACTIVE,
    VALID_COMPLETE_EPISODE,
    event,
)


def _replay(phases: tuple[EpisodePhase, ...]) -> AdaptiveEpisode:
    current = AdaptiveEpisode.create(
        episode_id=EpisodeId(EPISODE_ID),
        learner_id=LEARNER_ID,
        skill_id=SkillId("synthetic-skill"),
        created_at=AT,
    )
    for offset, target in enumerate(phases[1:], start=1):
        current = current.transition_to(target, at=AT + timedelta(seconds=offset))
    return current


def test_synthetic_valid_complete_episode_replays_deterministically() -> None:
    assert VALID_COMPLETE_EPISODE.synthetic is True
    first = _replay(VALID_COMPLETE_EPISODE.phases)
    second = _replay(VALID_COMPLETE_EPISODE.phases)
    assert first == second
    assert first.phase is EpisodePhase.COMPLETED


def test_synthetic_illegal_transition_is_rejected() -> None:
    assert ILLEGAL_TRANSITION.synthetic is True
    with pytest.raises(EpisodeTransitionError):
        _replay(ILLEGAL_TRANSITION.phases)


def test_duplicate_event_is_acknowledged_idempotently() -> None:
    ledger = InMemoryEventLedger()
    accepted = ledger.ingest_batch(DUPLICATE_EVENTS)
    assert [item.duplicate for item in accepted] == [False, True]
    assert ledger.expected_sequence(SESSION_ID) == 2


def test_duplicate_id_with_changed_content_is_rejected() -> None:
    ledger = InMemoryEventLedger()
    ledger.ingest(event(1))
    changed = event(2, event_id_suffix=1)
    with pytest.raises(EventConflictError):
        ledger.ingest(changed)


def test_missing_sequence_is_detected() -> None:
    ledger = InMemoryEventLedger()
    ledger.ingest(MISSING_SEQUENCE_EVENTS[0])
    with pytest.raises(MissingEventSequenceError, match="2-2"):
        ledger.ingest(MISSING_SEQUENCE_EVENTS[1])


def test_late_new_event_for_occupied_sequence_is_rejected() -> None:
    ledger = InMemoryEventLedger()
    ledger.ingest(event(1))
    with pytest.raises(EventOrderingError):
        ledger.ingest(event(1, event_id_suffix=77))


def test_synthetic_incomplete_episode_is_not_completed() -> None:
    assert INCOMPLETE_EPISODE.synthetic is True
    replayed = _replay(INCOMPLETE_EPISODE.phases)
    assert replayed.phase is EpisodePhase.SUPPORT_DECIDED
    assert replayed.phase.is_terminal is False


def test_synthetic_probe_cannot_skip_support_withdrawal() -> None:
    assert SUPPORT_STILL_ACTIVE.synthetic is True
    with pytest.raises(EpisodeTransitionError):
        _replay(SUPPORT_STILL_ACTIVE.phases)


def test_synthetic_contaminated_probe_is_labelled_for_invalid_ig() -> None:
    assert CONTAMINATED_PROBE.synthetic is True
    assert CONTAMINATED_PROBE.probe_contaminated is True
    replayed = _replay(CONTAMINATED_PROBE.phases)
    assert replayed.phase is EpisodePhase.INDEPENDENT_CHECK_SCORED
