"""Ownership ports; implementations belong to adapters owned by each boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EligibilityEvidence:
    learner_id: UUID
    grade: int
    curriculum_medium: str
    pseudonymous: bool
    consent_eligibility_reference: str
    research_eligible: bool
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class ExternalEvidence:
    source: str
    source_version: str
    observed_at: datetime | None
    expires_at: datetime | None
    reliability: float | None
    missing: bool
    consent_reference: str | None = None
    eligible: bool = False
    values: Mapping[str, float | int | bool | str | None] | None = None


@dataclass(frozen=True, slots=True)
class ProbeReservation:
    reservation_id: UUID
    episode_id: UUID
    item_revision_id: str
    parallel_family_id: str
    measurement_role: str
    reservation_version: str
    reserved_at: datetime
    expires_at: datetime


class AuthenticationProfilePort(Protocol):
    def eligibility(self, learner_id: UUID) -> EligibilityEvidence: ...


class SharedCurriculumIdPort(Protocol):
    def resolve_skill_version(self, skill_id: str) -> str | None: ...

    def resolve_item_revision(self, item_revision_id: str) -> str | None: ...


class KnowledgeTracingPort(Protocol):
    def evidence(self, learner_id: UUID, skill_id: str, as_of: datetime) -> ExternalEvidence: ...


class MultimodalLearnerStatePort(Protocol):
    def evidence(self, learner_id: UUID, skill_id: str, as_of: datetime) -> ExternalEvidence: ...


class PrerequisiteSkillEvidencePort(Protocol):
    def evidence(self, learner_id: UUID, skill_id: str, as_of: datetime) -> ExternalEvidence: ...


class AccessibilityAccommodationPort(Protocol):
    def evidence(self, learner_id: UUID, skill_id: str, as_of: datetime) -> ExternalEvidence: ...


class VerifiedTutoringPort(Protocol):
    def evidence(self, learner_id: UUID, skill_id: str, as_of: datetime) -> ExternalEvidence: ...


class ProbeReservationPort(Protocol):
    def reserve(self, reservation: ProbeReservation) -> ProbeReservation: ...

    def is_contaminated(self, reservation_id: UUID) -> bool: ...


class ConsentEligibilityPort(Protocol):
    def eligibility(self, learner_id: UUID, purpose: str) -> EligibilityEvidence: ...


class ResearchAuditPort(Protocol):
    def append(self, event_type: str, subject_id: UUID, reason_codes: tuple[str, ...]) -> None: ...
