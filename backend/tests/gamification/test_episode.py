from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import uuid4

import pytest

from app.gamification.domain import (
    AdaptiveEpisode,
    DomainValidationError,
    EpisodePhase,
    EpisodeTransitionError,
)
from app.gamification.domain.episode import ADAPTIVE_EPISODE_PROTOCOL
from app.gamification.domain.types import EpisodeId, SkillId

FORWARD_PHASES = (
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
    EpisodePhase.COMPLETED,
)


def episode() -> AdaptiveEpisode:
    return AdaptiveEpisode.create(
        episode_id=EpisodeId(uuid4()),
        learner_id=uuid4(),
        skill_id=SkillId("skill-provisional-01"),
        created_at=datetime(2026, 10, 13, tzinfo=UTC),
    )


def advance_to(target: EpisodePhase) -> AdaptiveEpisode:
    current = episode()
    at = current.transitioned_at
    for phase in FORWARD_PHASES[1:]:
        if current.phase == target:
            break
        at += timedelta(seconds=1)
        current = current.transition_to(phase, at=at)
    return current


def test_creation_uses_versioned_protocol() -> None:
    current = episode()

    assert current.phase is EpisodePhase.CREATED
    assert current.protocol_version == ADAPTIVE_EPISODE_PROTOCOL


@pytest.mark.parametrize(
    ("source", "target"),
    tuple(pairwise(FORWARD_PHASES)),
)
def test_each_forward_transition_is_legal(
    source: EpisodePhase, target: EpisodePhase
) -> None:
    current = advance_to(source)

    transitioned = current.transition_to(target, at=current.transitioned_at + timedelta(seconds=1))

    assert transitioned.phase is target
    assert current.phase is source


@pytest.mark.parametrize("source", FORWARD_PHASES[:-1])
@pytest.mark.parametrize("terminal", [EpisodePhase.ABORTED, EpisodePhase.INVALIDATED])
def test_every_nonterminal_phase_can_end_early_with_reason(
    source: EpisodePhase, terminal: EpisodePhase
) -> None:
    current = advance_to(source)

    transitioned = current.transition_to(
        terminal,
        at=current.transitioned_at + timedelta(seconds=1),
        reason="PROTOCOL_STOP",
    )

    assert transitioned.phase is terminal
    assert transitioned.terminal_reason == "PROTOCOL_STOP"


@pytest.mark.parametrize("source", FORWARD_PHASES[:-1])
def test_all_other_nonterminal_targets_are_illegal(source: EpisodePhase) -> None:
    current = advance_to(source)
    legal = {
        FORWARD_PHASES[FORWARD_PHASES.index(source) + 1],
        EpisodePhase.ABORTED,
        EpisodePhase.INVALIDATED,
    }
    if source is EpisodePhase.REWARD_VALIDATED:
        legal.add(EpisodePhase.POLICY_UPDATED)

    for target in set(EpisodePhase) - legal:
        with pytest.raises(EpisodeTransitionError):
            current.transition_to(target, at=current.transitioned_at + timedelta(seconds=1))


@pytest.mark.parametrize(
    "terminal", [EpisodePhase.COMPLETED, EpisodePhase.ABORTED, EpisodePhase.INVALIDATED]
)
@pytest.mark.parametrize("target", tuple(EpisodePhase))
def test_terminal_phases_cannot_transition(
    terminal: EpisodePhase, target: EpisodePhase
) -> None:
    if terminal is EpisodePhase.COMPLETED:
        current = advance_to(terminal)
    else:
        initial = episode()
        current = initial.transition_to(
            terminal,
            at=initial.transitioned_at + timedelta(seconds=1),
            reason="PROTOCOL_STOP",
        )

    with pytest.raises(EpisodeTransitionError, match="terminal phase"):
        current.transition_to(
            target,
            at=current.transitioned_at + timedelta(seconds=1),
        )


def test_early_terminal_transition_requires_reason() -> None:
    with pytest.raises(DomainValidationError, match="requires a stable reason"):
        episode().transition_to(
            EpisodePhase.INVALIDATED,
            at=datetime(2026, 10, 13, 0, 0, 1, tzinfo=UTC),
        )


def test_validated_reward_can_be_followed_by_policy_update_before_completion() -> None:
    current = advance_to(EpisodePhase.REWARD_VALIDATED)
    updated = current.transition_to(
        EpisodePhase.POLICY_UPDATED,
        at=current.transitioned_at + timedelta(seconds=1),
    )
    completed = updated.transition_to(
        EpisodePhase.COMPLETED,
        at=updated.transitioned_at + timedelta(seconds=1),
    )

    assert completed.phase is EpisodePhase.COMPLETED


def test_policy_updated_rejects_every_target_except_completion_or_early_terminal() -> None:
    reward = advance_to(EpisodePhase.REWARD_VALIDATED)
    current = reward.transition_to(
        EpisodePhase.POLICY_UPDATED,
        at=reward.transitioned_at + timedelta(seconds=1),
    )
    legal = {EpisodePhase.COMPLETED, EpisodePhase.ABORTED, EpisodePhase.INVALIDATED}

    for target in set(EpisodePhase) - legal:
        with pytest.raises(EpisodeTransitionError):
            current.transition_to(target, at=current.transitioned_at + timedelta(seconds=1))

    for terminal in (EpisodePhase.ABORTED, EpisodePhase.INVALIDATED):
        transitioned = current.transition_to(
            terminal,
            at=current.transitioned_at + timedelta(seconds=1),
            reason="PROTOCOL_STOP",
        )
        assert transitioned.phase is terminal


def test_forward_transition_rejects_terminal_reason() -> None:
    with pytest.raises(DomainValidationError, match="reason is only valid"):
        episode().transition_to(
            EpisodePhase.BASELINE_RESERVED,
            at=datetime(2026, 10, 13, 0, 0, 1, tzinfo=UTC),
            reason="NOT_APPLICABLE",
        )


def test_transition_time_cannot_move_backwards() -> None:
    with pytest.raises(EpisodeTransitionError, match="cannot move backwards"):
        episode().transition_to(
            EpisodePhase.BASELINE_RESERVED,
            at=datetime(2026, 10, 12, tzinfo=UTC),
        )


def test_creation_and_transitions_require_aware_timestamps() -> None:
    with pytest.raises(DomainValidationError, match="UTC offset"):
        AdaptiveEpisode.create(
            episode_id=EpisodeId(uuid4()),
            learner_id=uuid4(),
            skill_id=SkillId("skill-provisional-01"),
            created_at=datetime(2026, 10, 13),
        )

    with pytest.raises(DomainValidationError, match="UTC offset"):
        episode().transition_to(EpisodePhase.BASELINE_RESERVED, at=datetime(2026, 10, 13))


def test_creation_rejects_blank_skill_identifier() -> None:
    with pytest.raises(DomainValidationError, match="skill_id"):
        AdaptiveEpisode.create(
            episode_id=EpisodeId(uuid4()),
            learner_id=uuid4(),
            skill_id=SkillId("  "),
            created_at=datetime(2026, 10, 13, tzinfo=UTC),
        )

