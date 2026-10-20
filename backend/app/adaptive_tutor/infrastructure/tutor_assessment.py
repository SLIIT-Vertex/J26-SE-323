from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.shared.database.base import Base

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, strict=True),
]
NormalizedValue = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]
PositiveSequence = Annotated[int, Field(strict=True, ge=1)]


class AssessmentInteractionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"


class AssessmentAttemptStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class TutorAssessmentInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    interaction_id: UUID
    idempotency_key: NonBlankText
    learner_id: UUID
    session_id: UUID
    skill_id: NonBlankText
    interaction_sequence: PositiveSequence
    source_component: NonBlankText
    question_reference: NonBlankText
    question_version: NonBlankText
    authorization_reference: NonBlankText
    status: AssessmentInteractionStatus = AssessmentInteractionStatus.OPEN
    opened_at: AwareDatetime
    expires_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None
    provenance: NonBlankText

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.expires_at is not None and self.expires_at < self.opened_at:
            raise ValueError("interaction expiry cannot precede opening")
        if self.status is AssessmentInteractionStatus.OPEN and self.closed_at is not None:
            raise ValueError("open interaction cannot have a closed_at timestamp")
        if self.status is not AssessmentInteractionStatus.OPEN and self.closed_at is None:
            raise ValueError("closed or invalidated interaction requires closed_at")
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("interaction closing cannot precede opening")
        return self


class AssessmentAttemptWrite(BaseModel):
    """Minimized score correlation; raw learner answers are intentionally excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: UUID
    interaction_id: UUID
    idempotency_key: NonBlankText
    status: AssessmentAttemptStatus
    source_component: NonBlankText
    source_score_reference: NonBlankText
    scorer_authorized: StrictBool
    source_mapping_approved: StrictBool
    is_correct: StrictBool | None = None
    partial_credit: NormalizedValue | None = None
    scoring_version: NonBlankText | None = None
    item_rubric_version: NonBlankText | None = None
    severity_category: NonBlankText | None = None
    severity_value: NormalizedValue | None = None
    severity_policy_version: NonBlankText | None = None
    severity_reviewed: StrictBool = False
    observed_at: AwareDatetime | None = None
    accepted_at: AwareDatetime | None = None
    recorded_at: AwareDatetime
    provenance: NonBlankText

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        result_fields = (
            self.is_correct,
            self.partial_credit,
            self.scoring_version,
            self.item_rubric_version,
            self.severity_category,
            self.severity_value,
            self.severity_policy_version,
            self.observed_at,
            self.accepted_at,
        )
        if self.status is AssessmentAttemptStatus.PENDING:
            if any(value is not None for value in result_fields):
                raise ValueError("pending attempt cannot contain scored outcome fields")
            if self.scorer_authorized or self.source_mapping_approved or self.severity_reviewed:
                raise ValueError("pending attempt cannot claim review or source authorization")
            return self

        required = (
            self.is_correct,
            self.scoring_version,
            self.item_rubric_version,
            self.observed_at,
            self.accepted_at,
        )
        if any(value is None for value in required):
            raise ValueError("accepted attempt requires correctness, versions, and timestamps")
        assert self.observed_at is not None and self.accepted_at is not None
        if self.recorded_at > self.accepted_at:
            raise ValueError("recorded_at cannot follow accepted_at")
        if self.observed_at > self.accepted_at:
            raise ValueError("observed_at cannot follow accepted_at")

        severity = (
            self.severity_category,
            self.severity_value,
            self.severity_policy_version,
        )
        if any(value is not None for value in severity) and any(
            value is None for value in severity
        ):
            raise ValueError("severity category, value, and policy version are all-or-none")
        if self.severity_reviewed and any(value is None for value in severity):
            raise ValueError("reviewed severity requires complete versioned severity evidence")
        if self.is_correct and self.severity_value is not None and self.severity_value != 0.0:
            raise ValueError("correct accepted evidence may only carry zero severity")
        return self


class TutorAssessmentAttempt(AssessmentAttemptWrite):
    attempt_sequence: PositiveSequence


class AssessmentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    interaction: TutorAssessmentInteraction
    accepted_attempts: tuple[TutorAssessmentAttempt, ...]
    pending_submission: bool
    as_of: AwareDatetime

    @property
    def latest_accepted(self) -> TutorAssessmentAttempt | None:
        return self.accepted_attempts[-1] if self.accepted_attempts else None


class TutorAssessmentInteractionModel(Base):
    __tablename__ = "tutor_assessment_interactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tutor_assessment_interaction_idempotency"),
        UniqueConstraint(
            "session_id",
            "interaction_sequence",
            name="uq_tutor_assessment_interaction_sequence",
        ),
        CheckConstraint(
            "interaction_sequence >= 1",
            name="ck_tutor_assessment_interaction_sequence",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'INVALIDATED')",
            name="ck_tutor_assessment_interaction_status",
        ),
        CheckConstraint(
            "(status = 'OPEN' AND closed_at IS NULL) OR "
            "(status <> 'OPEN' AND closed_at IS NOT NULL)",
            name="ck_tutor_assessment_interaction_lifecycle",
        ),
        Index(
            "ix_tutor_assessment_interaction_scope",
            "learner_id",
            "skill_id",
            "session_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    interaction_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    source_component: Mapped[str] = mapped_column(String(128), nullable=False)
    question_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    question_version: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TutorAssessmentAttemptModel(Base):
    __tablename__ = "tutor_assessment_attempts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tutor_assessment_attempt_idempotency"),
        UniqueConstraint(
            "interaction_id",
            "attempt_sequence",
            name="uq_tutor_assessment_attempt_sequence",
        ),
        UniqueConstraint(
            "source_component",
            "source_score_reference",
            name="uq_tutor_assessment_source_score",
        ),
        CheckConstraint("attempt_sequence >= 1", name="ck_tutor_assessment_attempt_sequence"),
        CheckConstraint(
            "partial_credit IS NULL OR (partial_credit >= 0 AND partial_credit <= 1)",
            name="ck_tutor_assessment_partial_credit",
        ),
        CheckConstraint(
            "severity_value IS NULL OR (severity_value >= 0 AND severity_value <= 1)",
            name="ck_tutor_assessment_severity",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED')",
            name="ck_tutor_assessment_attempt_status",
        ),
        CheckConstraint(
            "(severity_category IS NULL AND severity_value IS NULL AND "
            "severity_policy_version IS NULL) OR "
            "(severity_category IS NOT NULL AND severity_value IS NOT NULL AND "
            "severity_policy_version IS NOT NULL)",
            name="ck_tutor_assessment_severity_shape",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND is_correct IS NULL AND accepted_at IS NULL AND "
            "observed_at IS NULL AND scoring_version IS NULL AND "
            "item_rubric_version IS NULL AND severity_value IS NULL AND "
            "NOT scorer_authorized AND NOT source_mapping_approved AND "
            "NOT severity_reviewed) OR "
            "(status = 'ACCEPTED' AND is_correct IS NOT NULL AND accepted_at IS NOT NULL "
            "AND observed_at IS NOT NULL AND scoring_version IS NOT NULL AND "
            "item_rubric_version IS NOT NULL)",
            name="ck_tutor_assessment_attempt_state",
        ),
        CheckConstraint(
            "accepted_at IS NULL OR (recorded_at <= accepted_at AND observed_at <= accepted_at)",
            name="ck_tutor_assessment_attempt_times",
        ),
        CheckConstraint(
            "is_correct IS NOT TRUE OR severity_value IS NULL OR severity_value = 0",
            name="ck_tutor_assessment_correct_severity",
        ),
        Index(
            "ix_tutor_assessment_attempt_snapshot",
            "interaction_id",
            "attempt_sequence",
            "accepted_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("tutor_assessment_interactions.id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_component: Mapped[str] = mapped_column(String(128), nullable=False)
    source_score_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    scorer_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_mapping_approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    partial_credit: Mapped[float | None] = mapped_column(Float)
    scoring_version: Mapped[str | None] = mapped_column(String(128))
    item_rubric_version: Mapped[str | None] = mapped_column(String(128))
    severity_category: Mapped[str | None] = mapped_column(String(128))
    severity_value: Mapped[float | None] = mapped_column(Float)
    severity_policy_version: Mapped[str | None] = mapped_column(String(128))
    severity_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _to_interaction(row: TutorAssessmentInteractionModel) -> TutorAssessmentInteraction:
    return TutorAssessmentInteraction(
        interaction_id=row.id,
        idempotency_key=row.idempotency_key,
        learner_id=row.learner_id,
        session_id=row.session_id,
        skill_id=row.skill_id,
        interaction_sequence=row.interaction_sequence,
        source_component=row.source_component,
        question_reference=row.question_reference,
        question_version=row.question_version,
        authorization_reference=row.authorization_reference,
        status=row.status,
        opened_at=_aware(row.opened_at),
        expires_at=_aware(row.expires_at),
        closed_at=_aware(row.closed_at),
        provenance=row.provenance,
    )


def _to_attempt(row: TutorAssessmentAttemptModel) -> TutorAssessmentAttempt:
    return TutorAssessmentAttempt(
        attempt_id=row.id,
        interaction_id=row.interaction_id,
        idempotency_key=row.idempotency_key,
        attempt_sequence=row.attempt_sequence,
        status=row.status,
        source_component=row.source_component,
        source_score_reference=row.source_score_reference,
        scorer_authorized=row.scorer_authorized,
        source_mapping_approved=row.source_mapping_approved,
        is_correct=row.is_correct,
        partial_credit=row.partial_credit,
        scoring_version=row.scoring_version,
        item_rubric_version=row.item_rubric_version,
        severity_category=row.severity_category,
        severity_value=row.severity_value,
        severity_policy_version=row.severity_policy_version,
        severity_reviewed=row.severity_reviewed,
        observed_at=_aware(row.observed_at),
        accepted_at=_aware(row.accepted_at),
        recorded_at=_aware(row.recorded_at),
        provenance=row.provenance,
    )


class SqlAlchemyTutorAssessmentRepository:
    """Tutor-owned correlation ledger; it performs no scoring or severity inference."""

    _sqlite_sequence_lock = Lock()

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_interaction(
        self, interaction: TutorAssessmentInteraction
    ) -> tuple[TutorAssessmentInteraction, bool]:
        existing = self._interaction_by_idempotency(interaction.idempotency_key)
        if existing is not None:
            if existing != interaction:
                raise ValueError("interaction idempotency key belongs to different evidence")
            return existing, False

        self._session.add(
            TutorAssessmentInteractionModel(
                id=interaction.interaction_id,
                idempotency_key=interaction.idempotency_key,
                learner_id=interaction.learner_id,
                session_id=interaction.session_id,
                skill_id=interaction.skill_id,
                interaction_sequence=interaction.interaction_sequence,
                source_component=interaction.source_component,
                question_reference=interaction.question_reference,
                question_version=interaction.question_version,
                authorization_reference=interaction.authorization_reference,
                status=interaction.status.value,
                opened_at=interaction.opened_at,
                expires_at=interaction.expires_at,
                closed_at=interaction.closed_at,
                provenance=interaction.provenance,
            )
        )
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self._interaction_by_idempotency(interaction.idempotency_key)
            if existing == interaction:
                return existing, False
            raise
        return interaction, True

    def record_attempt(
        self, attempt: AssessmentAttemptWrite
    ) -> tuple[TutorAssessmentAttempt, bool]:
        with self._serialization_lock():
            existing = self._attempt_by_idempotency(attempt.idempotency_key)
            if existing is not None:
                if _without_sequence(existing) != attempt:
                    raise ValueError("attempt idempotency key belongs to different evidence")
                return existing, False

            interaction = self._session.scalar(
                select(TutorAssessmentInteractionModel)
                .where(TutorAssessmentInteractionModel.id == attempt.interaction_id)
                .with_for_update()
            )
            if interaction is None:
                raise LookupError("assessment interaction does not exist")
            if interaction.status != AssessmentInteractionStatus.OPEN.value:
                raise ValueError("assessment interaction is not open")

            latest_sequence = self._session.scalar(
                select(func.max(TutorAssessmentAttemptModel.attempt_sequence)).where(
                    TutorAssessmentAttemptModel.interaction_id == attempt.interaction_id
                )
            )
            sequence = (latest_sequence or 0) + 1
            row = TutorAssessmentAttemptModel(
                id=attempt.attempt_id,
                interaction_id=attempt.interaction_id,
                idempotency_key=attempt.idempotency_key,
                attempt_sequence=sequence,
                status=attempt.status.value,
                source_component=attempt.source_component,
                source_score_reference=attempt.source_score_reference,
                scorer_authorized=attempt.scorer_authorized,
                source_mapping_approved=attempt.source_mapping_approved,
                is_correct=attempt.is_correct,
                partial_credit=attempt.partial_credit,
                scoring_version=attempt.scoring_version,
                item_rubric_version=attempt.item_rubric_version,
                severity_category=attempt.severity_category,
                severity_value=attempt.severity_value,
                severity_policy_version=attempt.severity_policy_version,
                severity_reviewed=attempt.severity_reviewed,
                observed_at=attempt.observed_at,
                accepted_at=attempt.accepted_at,
                recorded_at=attempt.recorded_at,
                provenance=attempt.provenance,
            )
            self._session.add(row)
            try:
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                existing = self._attempt_by_idempotency(attempt.idempotency_key)
                if existing is not None and _without_sequence(existing) == attempt:
                    return existing, False
                raise
            return _to_attempt(row), True

    def accept_pending_attempt(
        self,
        accepted: AssessmentAttemptWrite,
    ) -> tuple[TutorAssessmentAttempt, bool]:
        """Resolve one pending record without creating a permanent pending snapshot."""

        if accepted.status is not AssessmentAttemptStatus.ACCEPTED:
            raise ValueError("resolved assessment evidence must be accepted")
        with self._serialization_lock():
            row = self._session.scalar(
                select(TutorAssessmentAttemptModel)
                .where(TutorAssessmentAttemptModel.id == accepted.attempt_id)
                .with_for_update()
            )
            if row is None:
                raise LookupError("pending assessment attempt does not exist")
            current = _to_attempt(row)
            if current.status is AssessmentAttemptStatus.ACCEPTED:
                if _without_sequence(current) != accepted:
                    raise ValueError("accepted replay conflicts with stored assessment evidence")
                self._session.commit()
                return current, False
            stable = (
                row.interaction_id,
                row.idempotency_key,
                row.source_component,
                row.source_score_reference,
                _aware(row.recorded_at),
                row.provenance,
            )
            proposed = (
                accepted.interaction_id,
                accepted.idempotency_key,
                accepted.source_component,
                accepted.source_score_reference,
                accepted.recorded_at,
                accepted.provenance,
            )
            if stable != proposed:
                raise ValueError("accepted evidence does not match its pending record")
            for name in (
                "status",
                "scorer_authorized",
                "source_mapping_approved",
                "is_correct",
                "partial_credit",
                "scoring_version",
                "item_rubric_version",
                "severity_category",
                "severity_value",
                "severity_policy_version",
                "severity_reviewed",
                "observed_at",
                "accepted_at",
            ):
                value = getattr(accepted, name)
                setattr(row, name, value.value if isinstance(value, StrEnum) else value)
            self._session.commit()
            return _to_attempt(row), True

    def snapshot(self, interaction_id: UUID, *, as_of: datetime) -> AssessmentSnapshot | None:
        with self._serialization_lock():
            interaction_row = self._session.scalar(
                select(TutorAssessmentInteractionModel)
                .where(TutorAssessmentInteractionModel.id == interaction_id)
                .with_for_update()
            )
            if interaction_row is None:
                self._session.commit()
                return None

            rows = self._session.scalars(
                select(TutorAssessmentAttemptModel)
                .where(
                    TutorAssessmentAttemptModel.interaction_id == interaction_id,
                    TutorAssessmentAttemptModel.recorded_at <= as_of,
                )
                .order_by(TutorAssessmentAttemptModel.attempt_sequence)
            ).all()
            accepted: list[TutorAssessmentAttempt] = []
            pending = False
            for row in rows:
                if (
                    row.status == AssessmentAttemptStatus.ACCEPTED.value
                    and _aware(row.accepted_at) is not None
                    and _aware(row.accepted_at) <= as_of
                ):
                    accepted.append(_to_attempt(row))
                else:
                    pending = True

            snapshot = AssessmentSnapshot(
                interaction=_to_interaction(interaction_row),
                accepted_attempts=tuple(accepted),
                pending_submission=pending,
                as_of=as_of,
            )
            self._session.commit()
            return snapshot

    def _serialization_lock(self):
        if self._session.bind is not None and self._session.bind.dialect.name == "sqlite":
            return self._sqlite_sequence_lock
        return nullcontext()

    def _interaction_by_idempotency(self, key: str) -> TutorAssessmentInteraction | None:
        row = self._session.scalar(
            select(TutorAssessmentInteractionModel).where(
                TutorAssessmentInteractionModel.idempotency_key == key
            )
        )
        return _to_interaction(row) if row is not None else None

    def _attempt_by_idempotency(self, key: str) -> TutorAssessmentAttempt | None:
        row = self._session.scalar(
            select(TutorAssessmentAttemptModel).where(
                TutorAssessmentAttemptModel.idempotency_key == key
            )
        )
        return _to_attempt(row) if row is not None else None


def _without_sequence(attempt: TutorAssessmentAttempt) -> AssessmentAttemptWrite:
    return AssessmentAttemptWrite.model_validate(attempt.model_dump(exclude={"attempt_sequence"}))
