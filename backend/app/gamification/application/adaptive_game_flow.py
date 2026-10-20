"""Shared application boundary for skill-area-specific adaptive game profiles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID


class AdaptiveGameFlow(Protocol):
    area_id: str
    experience_id: str

    def open(
        self,
        *,
        learner_id: UUID,
        session_id: UUID,
        condition: str,
        environment: str,
        allow_draft: bool,
        atomic_skill_id: str,
        idempotency_key: str,
    ) -> dict[str, object]: ...

    def submit_before(
        self,
        episode_id: UUID,
        *,
        option_id: str | None,
        constructed_response: Mapping[str, object] | None,
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None,
        idempotency_key: str,
        visual: Mapping[str, float] | None = None,
        learner_state_session_id: UUID | None = None,
    ) -> dict[str, object]: ...

    def complete_support(
        self,
        episode_id: UUID,
        *,
        duration_ms: int,
        steps_viewed: int,
        manifest_revision_id: str,
        interaction_summary: Mapping[str, object],
        idempotency_key: str,
    ) -> dict[str, object]: ...

    def withdraw(
        self,
        episode_id: UUID,
        *,
        request_id: UUID,
        support_revision_id: str,
        manifest_revision_id: str,
        all_support_removed: bool,
        answer_revealing_state_cleared: bool,
        input_handlers_cleared: bool,
        idempotency_key: str,
    ) -> dict[str, object]: ...

    def present_after(self, episode_id: UUID, *, idempotency_key: str) -> dict[str, object]: ...

    def submit_after(
        self,
        episode_id: UUID,
        *,
        option_id: str | None,
        constructed_response: Mapping[str, object] | None,
        response_time_ms: int | None,
        idempotency_key: str,
        visual: Mapping[str, float] | None = None,
        learner_state_session_id: UUID | None = None,
    ) -> dict[str, object]: ...
