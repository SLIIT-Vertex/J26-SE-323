from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Final
from uuid import UUID

from app.gamification.domain.exceptions import (
    DomainValidationError,
    EpisodeTransitionError,
)
from app.gamification.domain.types import EpisodeId, EpisodePhase, ProtocolVersion, SkillId

ADAPTIVE_EPISODE_PROTOCOL: Final = ProtocolVersion("adaptive-episode-v1")

_NEXT_PHASE: Mapping[EpisodePhase, EpisodePhase] = MappingProxyType(
    {
        EpisodePhase.CREATED: EpisodePhase.BASELINE_RESERVED,
        EpisodePhase.BASELINE_RESERVED: EpisodePhase.BASELINE_ACTIVE,
        EpisodePhase.BASELINE_ACTIVE: EpisodePhase.BASELINE_SCORED,
        EpisodePhase.BASELINE_SCORED: EpisodePhase.GAMEPLAY_ACTIVE,
        EpisodePhase.GAMEPLAY_ACTIVE: EpisodePhase.DIFFICULTY_DETECTED,
        EpisodePhase.DIFFICULTY_DETECTED: EpisodePhase.MISCONCEPTION_ESTIMATED,
        EpisodePhase.MISCONCEPTION_ESTIMATED: EpisodePhase.SUPPORT_DECIDED,
        EpisodePhase.SUPPORT_DECIDED: EpisodePhase.SUPPORT_ACTIVE,
        EpisodePhase.SUPPORT_ACTIVE: EpisodePhase.SUPPORTED_PRACTICE_COMPLETE,
        EpisodePhase.SUPPORTED_PRACTICE_COMPLETE: EpisodePhase.SUPPORT_WITHDRAWN,
        EpisodePhase.SUPPORT_WITHDRAWN: EpisodePhase.INDEPENDENT_CHECK_ACTIVE,
        EpisodePhase.INDEPENDENT_CHECK_ACTIVE: EpisodePhase.INDEPENDENT_CHECK_SCORED,
        EpisodePhase.INDEPENDENT_CHECK_SCORED: EpisodePhase.REWARD_VALIDATED,
        EpisodePhase.POLICY_UPDATED: EpisodePhase.COMPLETED,
    }
)


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must include a UTC offset")


@dataclass(frozen=True, slots=True)
class AdaptiveEpisode:
    """Immutable state of one learner-skill adaptive episode.

    Transition methods return a new value so persistence can use optimistic concurrency without
    hidden in-memory mutation. Research evidence is attached by later phase-owned records.
    """

    episode_id: EpisodeId
    learner_id: UUID
    skill_id: SkillId
    protocol_version: ProtocolVersion
    phase: EpisodePhase
    created_at: datetime
    transitioned_at: datetime
    terminal_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        episode_id: EpisodeId,
        learner_id: UUID,
        skill_id: SkillId,
        created_at: datetime,
        protocol_version: ProtocolVersion = ADAPTIVE_EPISODE_PROTOCOL,
    ) -> "AdaptiveEpisode":
        _require_aware(created_at, "created_at")
        if not str(skill_id).strip():
            raise DomainValidationError("skill_id must not be blank")
        if not str(protocol_version).strip():
            raise DomainValidationError("protocol_version must not be blank")
        return cls(
            episode_id=episode_id,
            learner_id=learner_id,
            skill_id=skill_id,
            protocol_version=protocol_version,
            phase=EpisodePhase.CREATED,
            created_at=created_at,
            transitioned_at=created_at,
        )

    def transition_to(
        self,
        target: EpisodePhase,
        *,
        at: datetime,
        reason: str | None = None,
    ) -> "AdaptiveEpisode":
        _require_aware(at, "transition timestamp")
        if at < self.transitioned_at:
            raise EpisodeTransitionError("transition timestamp cannot move backwards")
        if self.phase.is_terminal:
            raise EpisodeTransitionError(f"terminal phase {self.phase} cannot transition")

        terminal_early = target in {EpisodePhase.ABORTED, EpisodePhase.INVALIDATED}
        expected = _NEXT_PHASE.get(self.phase)
        reward_can_finish_without_an_update = (
            self.phase is EpisodePhase.REWARD_VALIDATED and target is EpisodePhase.COMPLETED
        )
        reward_can_authorize_an_update = (
            self.phase is EpisodePhase.REWARD_VALIDATED and target is EpisodePhase.POLICY_UPDATED
        )
        if (
            target != expected
            and not terminal_early
            and not reward_can_finish_without_an_update
            and not reward_can_authorize_an_update
        ):
            raise EpisodeTransitionError(
                f"illegal adaptive episode transition: {self.phase} -> {target}"
            )

        normalized_reason = reason.strip() if reason is not None else None
        if terminal_early and not normalized_reason:
            raise DomainValidationError(f"{target} requires a stable reason code")
        if not terminal_early and reason is not None:
            raise DomainValidationError("reason is only valid for aborted or invalidated phases")

        return replace(
            self,
            phase=target,
            transitioned_at=at,
            terminal_reason=normalized_reason,
        )

