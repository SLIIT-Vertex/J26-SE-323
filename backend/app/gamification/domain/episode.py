from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Final, Mapping
from uuid import UUID

from app.gamification.domain.exceptions import (
    DomainValidationError,
    EpisodeTransitionError,
)
from app.gamification.domain.types import EpisodeId, EpisodePhase, ProtocolVersion, SkillId

ADAPTIVE_EPISODE_PROTOCOL: Final = ProtocolVersion("adaptive-episode-v1")

_NEXT_PHASE: Mapping[EpisodePhase, EpisodePhase] = MappingProxyType(
    {
        EpisodePhase.CREATED: EpisodePhase.BASELINE_STARTED,
        EpisodePhase.BASELINE_STARTED: EpisodePhase.BASELINE_RECORDED,
        EpisodePhase.BASELINE_RECORDED: EpisodePhase.STRUGGLE_ASSESSED,
        EpisodePhase.STRUGGLE_ASSESSED: EpisodePhase.MISCONCEPTION_RECORDED,
        EpisodePhase.MISCONCEPTION_RECORDED: EpisodePhase.SUPPORT_DECIDED,
        EpisodePhase.SUPPORT_DECIDED: EpisodePhase.SUPPORT_DELIVERED,
        EpisodePhase.SUPPORT_DELIVERED: EpisodePhase.SUPPORT_WITHDRAWN,
        EpisodePhase.SUPPORT_WITHDRAWN: EpisodePhase.VERIFICATION_SCHEDULED,
        EpisodePhase.VERIFICATION_SCHEDULED: EpisodePhase.VERIFICATION_STARTED,
        EpisodePhase.VERIFICATION_STARTED: EpisodePhase.VERIFICATION_RECORDED,
        EpisodePhase.VERIFICATION_RECORDED: EpisodePhase.OUTCOME_RECORDED,
        EpisodePhase.OUTCOME_RECORDED: EpisodePhase.COMPLETED,
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

        terminal_early = target in {EpisodePhase.ABANDONED, EpisodePhase.INVALIDATED}
        expected = _NEXT_PHASE.get(self.phase)
        if target != expected and not terminal_early:
            raise EpisodeTransitionError(
                f"illegal adaptive episode transition: {self.phase} -> {target}"
            )

        normalized_reason = reason.strip() if reason is not None else None
        if terminal_early and not normalized_reason:
            raise DomainValidationError(f"{target} requires a stable reason code")
        if not terminal_early and reason is not None:
            raise DomainValidationError("reason is only valid for abandoned or invalidated phases")

        return replace(
            self,
            phase=target,
            transitioned_at=at,
            terminal_reason=normalized_reason,
        )

