"""Deterministic Independence Gain measurement.

This module is deliberately independent of HTTP and ORM code.  It consumes immutable
presentation, rubric, scoring, reservation, exposure, withdrawal, and event records and returns
an append-only measurement suitable for persistence and replay.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from threading import Lock
from uuid import UUID

from app.gamification.domain.types import AssistanceState, ExperimentMode, MeasurementRole

FORMULA_VERSION = "raw-independence-gain-v1"
MEASUREMENT_VERSION = "independence-measurement-v1"
RESERVATION_VERSION = "platform-probe-reservation-v1"
PERCENT = Decimal(100)


class IndependenceGainError(ValueError):
    """An Independence Gain invariant was violated before a measurement could be recorded."""


class ProbeUnavailableError(IndependenceGainError):
    pass


class ProbeExposureError(IndependenceGainError):
    pass


class PolicyUpdateStatus(StrEnum):
    AUTHORIZED_DELAYED = "authorized_delayed"
    NOT_AUTHORIZED_BASELINE = "not_authorized_baseline"
    NOT_AUTHORIZED_INVALID = "not_authorized_invalid"


@dataclass(frozen=True, slots=True)
class ItemRubric:
    item_revision_id: str
    rubric_version: str
    scoring_version: str
    maximum_score: Decimal
    correct_response: str
    defective: bool = False

    def __post_init__(self) -> None:
        if self.maximum_score <= 0:
            raise IndependenceGainError("rubric maximum_score must be positive")


@dataclass(frozen=True, slots=True)
class Presentation:
    presentation_id: UUID
    episode_id: UUID
    learner_id: UUID
    item_revision_id: str
    skill_id: str
    parallel_family_id: str
    equivalence_version: str
    role: MeasurementRole
    assistance_state: AssistanceState
    sequence: int
    created_at: datetime
    reservation_id: UUID | None = None

    def __post_init__(self) -> None:
        unsupported = {
            MeasurementRole.UNSUPPORTED_BEFORE,
            MeasurementRole.UNSUPPORTED_AFTER,
            MeasurementRole.RETENTION,
        }
        if self.sequence < 1:
            raise IndependenceGainError("presentation sequence must be positive")
        if self.role in unsupported and self.assistance_state is not AssistanceState.NONE:
            raise IndependenceGainError("unsupported presentations require assistance_state=none")
        if (
            self.role is MeasurementRole.SUPPORTED_PRACTICE
            and self.assistance_state is AssistanceState.NONE
        ):
            raise IndependenceGainError("supported practice requires explicit assistance")


@dataclass(frozen=True, slots=True)
class AttemptSubmission:
    attempt_id: UUID
    presentation_id: UUID
    response: str
    assistance_state: AssistanceState
    submitted_at: datetime
    idempotency_key: str
    client_claimed_score: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ScoredAttempt:
    attempt_id: UUID
    presentation_id: UUID
    item_revision_id: str
    role: MeasurementRole
    assistance_state: AssistanceState
    earned_score: Decimal
    maximum_score: Decimal
    rubric_version: str
    scoring_version: str
    server_authoritative: bool
    idempotency_key: str
    scored_at: datetime


def development_curriculum_scorer(*, allow_draft: bool = False) -> ServerAuthoritativeScorer:
    """Compose the draft content slice only when a caller explicitly opts into development use."""

    if not allow_draft:
        raise PermissionError("draft content requires allow_draft=True")
    from app.gamification.content.curriculum_registry import (
        load_curriculum_public_package,
        load_curriculum_server_answer_keys,
    )

    package = load_curriculum_public_package(allow_draft=True)
    keys = load_curriculum_server_answer_keys()
    items = {row.revision_id: row for row in package.item_revisions}
    return ServerAuthoritativeScorer(
        {
            revision_id: ItemRubric(
                item_revision_id=revision_id,
                rubric_version=f"{key.scoring_version}-rubric-v1",
                scoring_version=key.scoring_version,
                maximum_score=Decimal(items[revision_id].maximum_score),
                correct_response=key.correct_option_id,
            )
            for revision_id, key in keys.items()
        }
    )


class ServerAuthoritativeScorer:
    """Score from an immutable server rubric; client score claims are never consulted."""

    def __init__(self, rubrics: Mapping[str, ItemRubric]) -> None:
        self._rubrics = dict(rubrics)
        self._attempts: dict[str, tuple[str, ScoredAttempt]] = {}

    def score(self, presentation: Presentation, attempt: AttemptSubmission) -> ScoredAttempt:
        if attempt.presentation_id != presentation.presentation_id:
            raise IndependenceGainError("attempt presentation does not match")
        fingerprint = sha256(
            f"{attempt.attempt_id}|{attempt.presentation_id}|{attempt.response}|"
            f"{attempt.assistance_state}|{attempt.submitted_at.isoformat()}".encode()
        ).hexdigest()
        prior = self._attempts.get(attempt.idempotency_key)
        if prior is not None:
            if prior[0] != fingerprint:
                raise IndependenceGainError("IDEMPOTENCY_CONFLICT")
            return prior[1]
        if attempt.assistance_state is not presentation.assistance_state:
            raise IndependenceGainError("attempt assistance state conflicts with presentation")
        try:
            rubric = self._rubrics[presentation.item_revision_id]
        except KeyError as error:
            raise IndependenceGainError("unknown immutable item/rubric version") from error
        earned = rubric.maximum_score if attempt.response == rubric.correct_response else Decimal(0)
        result = ScoredAttempt(
            attempt_id=attempt.attempt_id,
            presentation_id=presentation.presentation_id,
            item_revision_id=presentation.item_revision_id,
            role=presentation.role,
            assistance_state=attempt.assistance_state,
            earned_score=earned,
            maximum_score=rubric.maximum_score,
            rubric_version=rubric.rubric_version,
            scoring_version=rubric.scoring_version,
            server_authoritative=True,
            idempotency_key=attempt.idempotency_key,
            scored_at=attempt.submitted_at,
        )
        self._attempts[attempt.idempotency_key] = (fingerprint, result)
        return result


@dataclass(frozen=True, slots=True)
class ProbeReservation:
    reservation_id: UUID
    episode_id: UUID
    learner_id: UUID
    item_revision_id: str
    parallel_family_id: str
    role: MeasurementRole
    reserved_at: datetime
    expires_at: datetime
    reservation_version: str = RESERVATION_VERSION
    used_at: datetime | None = None
    contamination_sources: tuple[str, ...] = ()


class ProbeReservationLedger:
    """Process-safe reference semantics for a platform-wide durable reservation adapter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[UUID, ProbeReservation] = {}
        self._active: dict[tuple[UUID, str], UUID] = {}
        self._exposed: set[tuple[UUID, str]] = set()

    def reserve(self, reservation: ProbeReservation) -> ProbeReservation:
        if reservation.role not in {
            MeasurementRole.UNSUPPORTED_BEFORE,
            MeasurementRole.UNSUPPORTED_AFTER,
        }:
            raise IndependenceGainError("only unsupported probes may be reserved")
        if reservation.expires_at <= reservation.reserved_at:
            raise IndependenceGainError("probe reservation expiry must follow reservation time")
        key = (reservation.learner_id, reservation.item_revision_id)
        with self._lock:
            if key in self._exposed:
                raise ProbeUnavailableError("probe was previously exposed to this learner")
            active_id = self._active.get(key)
            if active_id is not None:
                active = self._by_id[active_id]
                if active.expires_at > reservation.reserved_at and active.used_at is None:
                    raise ProbeUnavailableError("probe already has an active reservation")
                self._active.pop(key, None)
            self._by_id[reservation.reservation_id] = reservation
            self._active[key] = reservation.reservation_id
            return reservation

    def expose(self, *, learner_id: UUID, item_revision_id: str, component: str, at: datetime) -> None:
        """Record exposure from a game, paper, tutor, example, or presentation."""

        if component not in {"game", "paper_generator", "tutor", "worked_example", "presentation"}:
            raise IndependenceGainError("unknown probe-consuming component")
        key = (learner_id, item_revision_id)
        with self._lock:
            self._exposed.add(key)
            reservation_id = self._active.get(key)
            if reservation_id is None:
                return
            reservation = self._by_id[reservation_id]
            if component == "presentation" and reservation.used_at is None:
                self._by_id[reservation_id] = replace(reservation, used_at=at)
                self._active.pop(key, None)
                return
            sources = tuple(sorted({*reservation.contamination_sources, component}))
            self._by_id[reservation_id] = replace(reservation, contamination_sources=sources)

    def get(self, reservation_id: UUID) -> ProbeReservation:
        return self._by_id[reservation_id]


@dataclass(frozen=True, slots=True)
class ScaffoldExposure:
    exposure_id: UUID
    episode_id: UUID
    scaffold_revision_id: str
    rendered_step_ids: tuple[str, ...]
    answer_revealing: bool
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class SupportWithdrawal:
    confirmation_id: UUID
    episode_id: UUID
    exposure_id: UUID
    all_support_removed: bool
    answer_revealing_state_cleared: bool
    client_confirmed_at: datetime
    server_verified_at: datetime


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    event_id: UUID
    sequence: int
    event_type: str
    presentation_id: UUID | None


@dataclass(frozen=True, slots=True)
class MeasurementInput:
    measurement_id: UUID
    episode_id: UUID
    decision_id: UUID
    experiment_mode: ExperimentMode
    presentations: tuple[Presentation, ...]
    attempts: tuple[ScoredAttempt, ...]
    reservations: tuple[ProbeReservation, ...]
    scaffold_exposures: tuple[ScaffoldExposure, ...]
    withdrawal: SupportWithdrawal | None
    events: tuple[NormalizedEvent, ...]
    expected_event_sequence_end: int
    episode_complete: bool = True
    interrupted: bool = False
    abandoned: bool = False
    censored: bool = False
    duplicate_conflict: bool = False
    family_compatible: bool = True
    content_versions_compatible: bool = True
    scoring_versions_compatible: bool = True
    later_invalidated_content: bool = False


@dataclass(frozen=True, slots=True)
class ScoreTotal:
    presentation_ids: tuple[UUID, ...]
    earned: Decimal
    maximum: Decimal


@dataclass(frozen=True, slots=True)
class IndependenceMeasurement:
    measurement_id: UUID
    episode_id: UUID
    decision_id: UUID
    before: ScoreTotal
    after: ScoreTotal
    raw_independence_gain: Decimal | None
    percentage_point_value: Decimal | None
    formula_version: str
    scoring_versions: tuple[str, ...]
    rubric_versions: tuple[str, ...]
    equivalence_version: str
    valid: bool
    exclusion_reasons: tuple[str, ...]
    policy_update_status: PolicyUpdateStatus
    measurement_version: str
    calculated_at: datetime


@dataclass(frozen=True, slots=True)
class SecondaryMeasurement:
    """A named diagnostic that can never substitute for raw Independence Gain."""

    name: str
    value: Decimal
    formula_version: str


def support_dependency_rate(*, helped_attempts: int, eligible_attempts: int) -> SecondaryMeasurement:
    if helped_attempts < 0 or eligible_attempts <= 0 or helped_attempts > eligible_attempts:
        raise IndependenceGainError("invalid support-dependency counts")
    return SecondaryMeasurement(
        name="support_dependency_rate",
        value=Decimal(helped_attempts) / Decimal(eligible_attempts),
        formula_version="support-dependency-rate-v1",
    )


def assert_unsupported_after_may_begin(
    presentation: Presentation, withdrawal: SupportWithdrawal | None
) -> None:
    if presentation.role is not MeasurementRole.UNSUPPORTED_AFTER:
        raise IndependenceGainError("presentation is not an unsupported-after probe")
    if presentation.assistance_state is not AssistanceState.NONE:
        raise IndependenceGainError("support remains active")
    if (
        withdrawal is None
        or not withdrawal.all_support_removed
        or not withdrawal.answer_revealing_state_cleared
        or withdrawal.server_verified_at > presentation.created_at
    ):
        raise IndependenceGainError("support withdrawal is not fully confirmed")


def calculate_measurement(data: MeasurementInput, *, calculated_at: datetime) -> IndependenceMeasurement:
    presentations = {row.presentation_id: row for row in data.presentations}
    before_rows = tuple(
        row for row in data.attempts if row.role is MeasurementRole.UNSUPPORTED_BEFORE
    )
    after_rows = tuple(
        row for row in data.attempts if row.role is MeasurementRole.UNSUPPORTED_AFTER
    )
    before = _total(before_rows)
    after = _total(after_rows)
    reasons: set[str] = set()

    if not before_rows:
        reasons.add("MISSING_UNSUPPORTED_BEFORE")
    if not after_rows:
        reasons.add("MISSING_UNSUPPORTED_AFTER")
    if before.maximum <= 0 or after.maximum <= 0:
        reasons.add("INVALID_MAXIMUM_SCORE")
    if not data.episode_complete:
        reasons.add("INCOMPLETE_EVIDENCE")
    if data.interrupted:
        reasons.add("EPISODE_INTERRUPTED")
    if data.abandoned:
        reasons.add("EPISODE_ABANDONED")
    if data.censored:
        reasons.add("EPISODE_CENSORED")
    if data.duplicate_conflict:
        reasons.add("DUPLICATE_SUBMISSION_CONFLICT")
    if not data.family_compatible:
        reasons.add("INCOMPATIBLE_PARALLEL_FAMILY")
    if not data.content_versions_compatible:
        reasons.add("INCOMPATIBLE_CONTENT_VERSION")
    if not data.scoring_versions_compatible:
        reasons.add("INCOMPATIBLE_SCORING_VERSION")
    if data.later_invalidated_content:
        reasons.add("DEFECTIVE_OR_INVALIDATED_CONTENT")

    ordered = sorted(data.events, key=lambda row: row.sequence)
    if len({row.event_id for row in ordered}) != len(ordered):
        reasons.add("DUPLICATE_EVENT_CONFLICT")
    sequences = [row.sequence for row in ordered]
    if sequences != list(range(1, data.expected_event_sequence_end + 1)):
        reasons.add("MISSING_OR_CONFLICTING_EVENT_SEQUENCE")
    required_order = [
        "unsupported_before_scored",
        "support_exposed",
        "support_withdrawn",
        "unsupported_after_scored",
    ]
    positions = [
        next((i for i, row in enumerate(ordered) if row.event_type == kind), None)
        for kind in required_order
    ]
    if any(position is None for position in positions) or positions != sorted(positions):
        reasons.add("INVALID_EPISODE_ORDER")

    if data.withdrawal is None or not data.withdrawal.all_support_removed:
        reasons.add("SUPPORT_NOT_WITHDRAWN")
    elif not data.withdrawal.answer_revealing_state_cleared:
        reasons.add("ANSWER_REVEALING_STATE_ACTIVE")

    revision_ids: list[str] = []
    families: set[str] = set()
    skills: set[str] = set()
    equivalence_versions: set[str] = set()
    scoring_versions: set[str] = set()
    rubric_versions: set[str] = set()
    for attempt in (*before_rows, *after_rows):
        presentation = presentations.get(attempt.presentation_id)
        if presentation is None:
            reasons.add("MISSING_PRESENTATION")
            continue
        if attempt.assistance_state is not AssistanceState.NONE:
            reasons.add(_assistance_reason(attempt.assistance_state))
        if presentation.assistance_state is not AssistanceState.NONE:
            reasons.add(_assistance_reason(presentation.assistance_state))
        if attempt.item_revision_id != presentation.item_revision_id:
            reasons.add("ITEM_REVISION_MISMATCH")
        if attempt.role is not presentation.role:
            reasons.add("MEASUREMENT_ROLE_MISMATCH")
        if not attempt.server_authoritative:
            reasons.add("NONAUTHORITATIVE_SCORE")
        if (
            attempt.earned_score < 0
            or attempt.maximum_score <= 0
            or attempt.earned_score > attempt.maximum_score
        ):
            reasons.add("INCOMPATIBLE_SCORE")
        revision_ids.append(presentation.item_revision_id)
        families.add(presentation.parallel_family_id)
        skills.add(presentation.skill_id)
        equivalence_versions.add(presentation.equivalence_version)
        scoring_versions.add(attempt.scoring_version)
        rubric_versions.add(attempt.rubric_version)
    if len(revision_ids) != len(set(revision_ids)):
        reasons.add("REUSED_ITEM_OR_REVISION")
    presentation_ids = [row.presentation_id for row in (*before_rows, *after_rows)]
    if len(presentation_ids) != len(set(presentation_ids)):
        reasons.add("DUPLICATE_SUBMISSION")
    if len(families) != 1:
        reasons.add("INCOMPATIBLE_PARALLEL_FAMILY")
    if len(skills) != 1:
        reasons.add("SKILL_MISMATCH")
    if len(equivalence_versions) != 1:
        reasons.add("INCOMPATIBLE_EQUIVALENCE_VERSION")
    if len(scoring_versions) != 1:
        reasons.add("INCOMPATIBLE_SCORING_VERSION")
    if len(rubric_versions) != 1:
        reasons.add("INCOMPATIBLE_RUBRIC_VERSION")

    after_presentations = [presentations.get(row.presentation_id) for row in after_rows]
    reservations = {row.reservation_id: row for row in data.reservations}
    for presentation in after_presentations:
        if presentation is None or presentation.reservation_id is None:
            reasons.add("MISSING_PROBE_RESERVATION")
            continue
        reservation = reservations.get(presentation.reservation_id)
        if reservation is None or reservation.item_revision_id != presentation.item_revision_id:
            reasons.add("MISSING_PROBE_RESERVATION")
            continue
        if (
            reservation.episode_id != presentation.episode_id
            or reservation.learner_id != presentation.learner_id
            or reservation.parallel_family_id != presentation.parallel_family_id
            or reservation.role is not MeasurementRole.UNSUPPORTED_AFTER
        ):
            reasons.add("PROBE_RESERVATION_MISMATCH")
        if reservation.expires_at <= presentation.created_at:
            reasons.add("EXPIRED_PROBE_RESERVATION")
        if reservation.contamination_sources:
            reasons.add("EXTERNAL_PROBE_CONTAMINATION")
        if reservation.used_at is None:
            reasons.add("MISSING_PROBE_PRESENTATION_RECORD")
        elif reservation.used_at != presentation.created_at:
            reasons.add("PRIOR_PROBE_EXPOSURE")
        if (
            data.withdrawal is not None
            and data.withdrawal.server_verified_at > presentation.created_at
        ):
            reasons.add("SUPPORT_VISIBLE_DURING_UNSUPPORTED_AFTER")
    if any(exposure.answer_revealing for exposure in data.scaffold_exposures):
        reasons.add("SCAFFOLD_ANSWER_LEAKAGE")
    if any(exposure.completed_at is None for exposure in data.scaffold_exposures):
        reasons.add("INCOMPLETE_SCAFFOLD_EXPOSURE")
    if data.withdrawal is not None and data.withdrawal.exposure_id not in {
        exposure.exposure_id for exposure in data.scaffold_exposures
    }:
        reasons.add("WITHDRAWAL_EXPOSURE_MISMATCH")
    valid = not reasons
    raw: Decimal | None = None
    percentage: Decimal | None = None
    if valid:
        raw = (after.earned / after.maximum) - (before.earned / before.maximum)
        percentage = raw * PERCENT
    if valid and data.experiment_mode is ExperimentMode.PROPOSED:
        update = PolicyUpdateStatus.AUTHORIZED_DELAYED
    elif valid:
        update = PolicyUpdateStatus.NOT_AUTHORIZED_BASELINE
    else:
        update = PolicyUpdateStatus.NOT_AUTHORIZED_INVALID
    return IndependenceMeasurement(
        measurement_id=data.measurement_id,
        episode_id=data.episode_id,
        decision_id=data.decision_id,
        before=before,
        after=after,
        raw_independence_gain=raw,
        percentage_point_value=percentage,
        formula_version=FORMULA_VERSION,
        scoring_versions=tuple(sorted(scoring_versions)),
        rubric_versions=tuple(sorted(rubric_versions)),
        equivalence_version=next(iter(equivalence_versions), "unknown"),
        valid=valid,
        exclusion_reasons=tuple(sorted(reasons)),
        policy_update_status=update,
        measurement_version=MEASUREMENT_VERSION,
        calculated_at=calculated_at,
    )


def replay_measurement(data: MeasurementInput, *, calculated_at: datetime) -> IndependenceMeasurement:
    """Reconstruct using only authoritative records and normalized events."""

    return calculate_measurement(data, calculated_at=calculated_at)


def _total(rows: tuple[ScoredAttempt, ...]) -> ScoreTotal:
    return ScoreTotal(
        presentation_ids=tuple(row.presentation_id for row in rows),
        earned=sum((row.earned_score for row in rows), Decimal(0)),
        maximum=sum((row.maximum_score for row in rows), Decimal(0)),
    )


def _assistance_reason(state: AssistanceState) -> str:
    return {
        AssistanceState.SCAFFOLD_ACTIVE: "ACTIVE_ASSISTANCE",
        AssistanceState.ADULT_REPORTED: "ADULT_ASSISTANCE",
        AssistanceState.TUTOR_ACTIVE: "TUTOR_ASSISTANCE",
        AssistanceState.UNKNOWN: "UNKNOWN_ASSISTANCE",
        AssistanceState.NONE: "",
    }[state]
