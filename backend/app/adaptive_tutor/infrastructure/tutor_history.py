from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.adaptive_tutor.application.context_assembly import (
    AssistanceHistoryBasis,
    AssistanceHistoryResult,
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
)
from app.adaptive_tutor.application.hint_effectiveness import (
    HintEffectiveness,
    as_controller_evidence,
)
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode
from app.shared.database.base import Base

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, strict=True),
]
JsonType = JSON().with_variant(JSONB(), "postgresql")

# Required provenance for research-only presentation events. These record that an unverified
# experimental draft was shown to an adult researcher; they never imply learner delivery.
RESEARCH_PRESENTATION_PROVENANCE = "EXPERIMENTAL_UNVERIFIED_RESEARCH_ONLY"


class TutorHistoryEventType(StrEnum):
    ASSISTANCE_SELECTED = "ASSISTANCE_SELECTED"
    RESPONSE_GENERATED = "RESPONSE_GENERATED"
    RESPONSE_VERIFIED = "RESPONSE_VERIFIED"
    DELIVERY_AUTHORIZED = "DELIVERY_AUTHORIZED"
    RESPONSE_DELIVERED = "RESPONSE_DELIVERED"
    OUTCOME_OBSERVED = "OUTCOME_OBSERVED"
    EFFECTIVENESS_STATUS_RECORDED = "EFFECTIVENESS_STATUS_RECORDED"
    RESEARCH_PRESENTATION = "RESEARCH_PRESENTATION"


class TutorHistoryEventStatus(StrEnum):
    GENERATED = "GENERATED"
    GENERATION_FAILED = "GENERATION_FAILED"
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    DELIVERED = "DELIVERED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    UNKNOWN = "UNKNOWN"
    OBSERVED = "OBSERVED"
    NOT_MEASURED = "NOT_MEASURED"
    PRESENTED_TO_RESEARCHER = "PRESENTED_TO_RESEARCHER"
    EFFECTIVE = HintEffectiveness.EFFECTIVE.value
    INEFFECTIVE = HintEffectiveness.INEFFECTIVE.value
    INSUFFICIENT_EVIDENCE = HintEffectiveness.INSUFFICIENT_EVIDENCE.value


_ALLOWED_STATUSES = {
    TutorHistoryEventType.RESPONSE_GENERATED: {
        TutorHistoryEventStatus.GENERATED,
        TutorHistoryEventStatus.GENERATION_FAILED,
    },
    TutorHistoryEventType.RESPONSE_VERIFIED: {
        TutorHistoryEventStatus.PASS,
        TutorHistoryEventStatus.FAIL,
        TutorHistoryEventStatus.INDETERMINATE,
    },
    TutorHistoryEventType.DELIVERY_AUTHORIZED: {
        TutorHistoryEventStatus.AUTHORIZED,
        TutorHistoryEventStatus.DENIED,
    },
    TutorHistoryEventType.RESPONSE_DELIVERED: {
        TutorHistoryEventStatus.DELIVERED,
        TutorHistoryEventStatus.DELIVERY_FAILED,
        TutorHistoryEventStatus.UNKNOWN,
    },
    TutorHistoryEventType.OUTCOME_OBSERVED: {TutorHistoryEventStatus.OBSERVED},
    TutorHistoryEventType.EFFECTIVENESS_STATUS_RECORDED: {
        TutorHistoryEventStatus.NOT_MEASURED,
        TutorHistoryEventStatus.EFFECTIVE,
        TutorHistoryEventStatus.INEFFECTIVE,
        TutorHistoryEventStatus.INSUFFICIENT_EVIDENCE,
    },
    TutorHistoryEventType.RESEARCH_PRESENTATION: {
        TutorHistoryEventStatus.PRESENTED_TO_RESEARCHER,
    },
}


class TutorHistoryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    idempotency_key: NonBlankText
    decision_id: UUID
    learner_id: UUID
    skill_id: NonBlankText
    session_id: UUID
    interaction_id: NonBlankText
    interaction_sequence: Annotated[int, Field(strict=True, ge=1)]
    event_sequence: Annotated[int, Field(strict=True, ge=1)]
    event_type: TutorHistoryEventType
    occurred_at: AwareDatetime
    provenance: NonBlankText
    assistance_level: AssistanceLevel | None = None
    policy_version: NonBlankText | None = None
    reason_codes: tuple[DecisionReasonCode, ...] = ()
    status: TutorHistoryEventStatus | None = None
    assessment_reference: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_event_shape(self) -> Self:
        if self.event_type is TutorHistoryEventType.ASSISTANCE_SELECTED:
            if (
                self.assistance_level is None
                or self.policy_version is None
                or not self.reason_codes
                or self.status is not None
            ):
                raise ValueError("selection requires level, policy, reasons, and no status")
        elif (
            self.assistance_level is not None
            or self.policy_version is not None
            or self.reason_codes
            or self.status not in _ALLOWED_STATUSES[self.event_type]
        ):
            raise ValueError("lifecycle event fields do not match its event type")

        if (self.event_type is TutorHistoryEventType.RESEARCH_PRESENTATION) != (
            self.provenance == RESEARCH_PRESENTATION_PROVENANCE
        ):
            raise ValueError("research presentation provenance is reserved for that event type")

        if (
            self.event_type
            in {
                TutorHistoryEventType.OUTCOME_OBSERVED,
                TutorHistoryEventType.EFFECTIVENESS_STATUS_RECORDED,
            }
            and self.assessment_reference is None
        ):
            raise ValueError("outcome and effectiveness events require assessment_reference")
        if (
            self.event_type
            not in {
                TutorHistoryEventType.OUTCOME_OBSERVED,
                TutorHistoryEventType.EFFECTIVENESS_STATUS_RECORDED,
            }
            and self.assessment_reference is not None
        ):
            raise ValueError("only outcome and effectiveness events may link assessment evidence")
        return self


class TutorInteractionEventModel(Base):
    __tablename__ = "tutor_interaction_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tutor_events_idempotency"),
        UniqueConstraint(
            "session_id",
            "interaction_sequence",
            "event_sequence",
            name="uq_tutor_events_sequence",
        ),
        UniqueConstraint(
            "decision_id",
            "event_type",
            "assessment_reference",
            name="uq_tutor_events_assessment_link",
        ),
        CheckConstraint("interaction_sequence >= 1", name="ck_tutor_events_interaction_sequence"),
        CheckConstraint("event_sequence >= 1", name="ck_tutor_events_event_sequence"),
        Index(
            "ix_tutor_events_history",
            "learner_id",
            "skill_id",
            "session_id",
            "interaction_sequence",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    interaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    interaction_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provenance: Mapped[str] = mapped_column(String(128), nullable=False)
    assistance_level: Mapped[str | None] = mapped_column(String(2))
    policy_version: Mapped[str | None] = mapped_column(String(128))
    reason_codes: Mapped[list[str]] = mapped_column(JsonType, nullable=False)
    status: Mapped[str | None] = mapped_column(String(32))
    assessment_reference: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _to_event(model: TutorInteractionEventModel) -> TutorHistoryEvent:
    occurred_at = model.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return TutorHistoryEvent(
        event_id=model.id,
        idempotency_key=model.idempotency_key,
        decision_id=model.decision_id,
        learner_id=model.learner_id,
        skill_id=model.skill_id,
        session_id=model.session_id,
        interaction_id=model.interaction_id,
        interaction_sequence=model.interaction_sequence,
        event_sequence=model.event_sequence,
        event_type=model.event_type,
        occurred_at=occurred_at,
        provenance=model.provenance,
        assistance_level=model.assistance_level,
        policy_version=model.policy_version,
        reason_codes=tuple(model.reason_codes),
        status=model.status,
        assessment_reference=model.assessment_reference,
    )


class SqlAlchemyTutorHistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: TutorHistoryEvent) -> tuple[TutorHistoryEvent, bool]:
        existing = self._by_idempotency_key(event.idempotency_key)
        if existing is not None:
            if existing != event:
                raise ValueError("idempotency key already belongs to a different Tutor event")
            return existing, False

        self._session.add(
            TutorInteractionEventModel(
                id=event.event_id,
                idempotency_key=event.idempotency_key,
                decision_id=event.decision_id,
                learner_id=event.learner_id,
                skill_id=event.skill_id,
                session_id=event.session_id,
                interaction_id=event.interaction_id,
                interaction_sequence=event.interaction_sequence,
                event_sequence=event.event_sequence,
                event_type=event.event_type.value,
                occurred_at=event.occurred_at,
                provenance=event.provenance,
                assistance_level=(
                    event.assistance_level.value if event.assistance_level is not None else None
                ),
                policy_version=event.policy_version,
                reason_codes=[reason.value for reason in event.reason_codes],
                status=event.status.value if event.status is not None else None,
                assessment_reference=event.assessment_reference,
            )
        )
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self._by_idempotency_key(event.idempotency_key)
            if existing == event:
                return existing, False
            raise
        return event, True

    def before(
        self,
        *,
        learner_id: UUID,
        skill_id: str,
        session_id: UUID,
        interaction_sequence: int,
    ) -> tuple[TutorHistoryEvent, ...]:
        rows = self._session.scalars(
            select(TutorInteractionEventModel)
            .where(
                TutorInteractionEventModel.learner_id == learner_id,
                TutorInteractionEventModel.skill_id == skill_id,
                TutorInteractionEventModel.session_id == session_id,
                TutorInteractionEventModel.interaction_sequence < interaction_sequence,
            )
            .order_by(
                TutorInteractionEventModel.interaction_sequence.desc(),
                TutorInteractionEventModel.event_sequence.desc(),
                TutorInteractionEventModel.id.desc(),
            )
        ).all()
        return tuple(_to_event(row) for row in rows)

    def in_interaction(
        self,
        *,
        learner_id: UUID,
        skill_id: str,
        session_id: UUID,
        interaction_sequence: int,
    ) -> tuple[TutorHistoryEvent, ...]:
        """Events already recorded for one interaction, newest first."""

        rows = self._session.scalars(
            select(TutorInteractionEventModel)
            .where(
                TutorInteractionEventModel.learner_id == learner_id,
                TutorInteractionEventModel.skill_id == skill_id,
                TutorInteractionEventModel.session_id == session_id,
                TutorInteractionEventModel.interaction_sequence == interaction_sequence,
            )
            .order_by(
                TutorInteractionEventModel.event_sequence.desc(),
                TutorInteractionEventModel.id.desc(),
            )
        ).all()
        return tuple(_to_event(row) for row in rows)

    def next_event_sequence(self, *, session_id: UUID, interaction_sequence: int) -> int:
        latest = self._session.scalar(
            select(func.max(TutorInteractionEventModel.event_sequence)).where(
                TutorInteractionEventModel.session_id == session_id,
                TutorInteractionEventModel.interaction_sequence == interaction_sequence,
            )
        )
        return (latest or 0) + 1

    def _by_idempotency_key(self, key: str) -> TutorHistoryEvent | None:
        row = self._session.scalars(
            select(TutorInteractionEventModel).where(
                TutorInteractionEventModel.idempotency_key == key
            )
        ).first()
        return _to_event(row) if row is not None else None


class TutorHistoryProvider:
    source = EvidenceSource(
        source_id="adaptive-tutor:interaction-history", origin=EvidenceOrigin.REAL
    )
    research_presentation_source = EvidenceSource(
        source_id="adaptive-tutor:interaction-history-research-presentation",
        origin=EvidenceOrigin.SYNTHETIC,
    )

    def __init__(self, repository: SqlAlchemyTutorHistoryRepository) -> None:
        self._repository = repository

    def source_for_result(self, result: AssistanceHistoryResult) -> EvidenceSource:
        """History built on research-only presentations is never real delivery evidence."""

        if result.basis is AssistanceHistoryBasis.RESEARCH_PRESENTATION:
            return self.research_presentation_source
        return self.source

    def get_assistance_history(
        self,
        request: ContextEvidenceRequest,
    ) -> AssistanceHistoryResult:
        if (
            request.session_id is None
            or request.interaction_id is None
            or request.interaction_sequence is None
            or request.as_of is None
        ):
            return AssistanceHistoryResult(status=EvidenceStatus.CONTEXT_REQUIRED)
        try:
            session_id = UUID(request.session_id)
        except ValueError:
            return AssistanceHistoryResult(status=EvidenceStatus.INVALID_EVIDENCE)

        try:
            current = self._repository.in_interaction(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                session_id=session_id,
                interaction_sequence=request.interaction_sequence,
            )
            events = self._repository.before(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                session_id=session_id,
                interaction_sequence=request.interaction_sequence,
            )
        except (TimeoutError, ConnectionError, OperationalError):
            return AssistanceHistoryResult(status=EvidenceStatus.PROVIDER_UNAVAILABLE)
        except SQLAlchemyError:
            return AssistanceHistoryResult(status=EvidenceStatus.PROVIDER_ERROR)
        except (TypeError, ValueError, ValidationError):
            return AssistanceHistoryResult(status=EvidenceStatus.INVALID_EVIDENCE)
        except Exception:  # noqa: BLE001 - provider boundary fails closed
            return AssistanceHistoryResult(status=EvidenceStatus.PROVIDER_ERROR)

        if any(event.occurred_at > request.as_of for event in (*current, *events)):
            return AssistanceHistoryResult(status=EvidenceStatus.INVALID_EVIDENCE)

        presented = _latest_research_presentation(current)
        if presented is not None:
            return presented

        selections = [
            event
            for event in events
            if event.event_type is TutorHistoryEventType.ASSISTANCE_SELECTED
        ]
        if not selections:
            return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)

        delivery_unknown = False
        for selection in selections:
            related = [event for event in events if event.decision_id == selection.decision_id]
            deliveries = [
                event
                for event in related
                if event.event_type is TutorHistoryEventType.RESPONSE_DELIVERED
            ]
            delivery_statuses = {event.status for event in deliveries}
            if len(delivery_statuses) > 1:
                return AssistanceHistoryResult(status=EvidenceStatus.INVALID_EVIDENCE)
            if TutorHistoryEventStatus.DELIVERED not in delivery_statuses:
                delivery_unknown = (
                    delivery_unknown or TutorHistoryEventStatus.UNKNOWN in delivery_statuses
                )
                continue

            assert selection.assistance_level is not None
            return AssistanceHistoryResult(
                status=EvidenceStatus.AVAILABLE,
                previous_assistance_level=selection.assistance_level,
                previous_hint_effective=None,
                basis=AssistanceHistoryBasis.VERIFIED_DELIVERY,
            )

        return AssistanceHistoryResult(
            status=(
                EvidenceStatus.DELIVERY_UNKNOWN
                if delivery_unknown
                else EvidenceStatus.NOT_DELIVERED
            )
        )


def _latest_research_presentation(
    events: tuple[TutorHistoryEvent, ...],
) -> AssistanceHistoryResult | None:
    """Most recent assistance shown to the researcher within the current interaction.

    The PRE_INTERACTION decision is the independent-attempt baseline, not assistance, so it is
    skipped. Effectiveness comes only from a recorded EFFECTIVENESS_STATUS_RECORDED event.
    """

    for selection in events:
        if (
            selection.event_type is not TutorHistoryEventType.ASSISTANCE_SELECTED
            or DecisionReasonCode.PRE_INTERACTION in selection.reason_codes
        ):
            continue
        related = [event for event in events if event.decision_id == selection.decision_id]
        if not any(
            event.event_type is TutorHistoryEventType.RESEARCH_PRESENTATION for event in related
        ):
            continue
        effectiveness = next(
            (
                HintEffectiveness(event.status.value)
                for event in related
                if event.event_type is TutorHistoryEventType.EFFECTIVENESS_STATUS_RECORDED
                and event.status is not None
                and event.status.value in HintEffectiveness.__members__
            ),
            None,
        )
        assert selection.assistance_level is not None
        return AssistanceHistoryResult(
            status=EvidenceStatus.AVAILABLE,
            previous_assistance_level=selection.assistance_level,
            previous_hint_effective=as_controller_evidence(effectiveness),
            basis=AssistanceHistoryBasis.RESEARCH_PRESENTATION,
        )
    return None
