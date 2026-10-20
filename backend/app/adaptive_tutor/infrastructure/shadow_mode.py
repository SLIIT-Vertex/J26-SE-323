from collections.abc import Collection
from enum import StrEnum
from typing import Annotated, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.adaptive_tutor.application.context_assembly import (
    ContextEvidenceOrigin,
    ContextEvidenceProvenance,
    ContextIssue,
    ContextReadinessStatus,
    EvidenceSource,
    TutorContextAssembler,
    TutorContextAssemblyRequest,
)
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.orchestration import SkillMapper
from app.adaptive_tutor.application.skill_mapper_contracts import (
    SkillMappingRequest,
    SkillMappingResult,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.domain import AssistanceLevel, DecisionReasonCode, SkillMappingStatus
from app.adaptive_tutor.infrastructure.tutor_history import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryEvent,
    TutorHistoryEventType,
)

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, strict=True),
]
StudentMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000, strict=True),
]
CONTROLLER_POLICY_VERSION = "reference-policy-v1"


class ShadowExecutionStatus(StrEnum):
    DECIDED = "DECIDED"
    UNAUTHORIZED = "UNAUTHORIZED"
    SKILL_NOT_CONFIRMED = "SKILL_NOT_CONFIRMED"
    NOT_READY = "NOT_READY"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    HISTORY_WRITE_FAILED = "HISTORY_WRITE_FAILED"


class ShadowAuthorizer(Protocol):
    def is_authorized(self, principal_id: UUID, learner_id: UUID) -> bool: ...


class StaticShadowAuthorizer:
    """Explicit allow-list for controlled internal tests; not production authentication."""

    def __init__(self, grants: Collection[tuple[UUID, UUID]]) -> None:
        self._grants = frozenset(grants)

    def is_authorized(self, principal_id: UUID, learner_id: UUID) -> bool:
        return (principal_id, learner_id) in self._grants


class ShadowControllerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: UUID
    principal_id: UUID
    learner_id: UUID
    student_message: StudentMessage
    preferred_language: NonBlankText | None = None
    session_id: UUID
    interaction_id: NonBlankText
    interaction_sequence: Annotated[int, Field(strict=True, ge=1)]
    as_of: AwareDatetime
    max_age_ms: Annotated[int, Field(strict=True, ge=0)]


class ShadowControllerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ShadowExecutionStatus
    correlation_id: UUID
    confirmed_skill_id: NonBlankText | None = None
    assistance_level: AssistanceLevel | None = None
    controller_policy_version: NonBlankText | None = None
    controller_reason_codes: tuple[DecisionReasonCode, ...] = ()
    context_issues: tuple[ContextIssue, ...] = ()
    provenance: tuple[ContextEvidenceProvenance, ...] = ()
    evidence_origin: ContextEvidenceOrigin | None = None


class RealDataControllerShadow:
    """Internal controller-only composition. It has no API, generator, verifier, or text output."""

    def __init__(
        self,
        *,
        authorizer: ShadowAuthorizer,
        skill_mapper: SkillMapper,
        skill_mapper_source: EvidenceSource,
        context_assembler: TutorContextAssembler,
        history_repository: SqlAlchemyTutorHistoryRepository,
        valid_skill_ids: Collection[str],
        controller: ScaffoldingController | None = None,
    ) -> None:
        self._authorizer = authorizer
        self._skill_mapper = skill_mapper
        self._skill_mapper_source = skill_mapper_source
        self._context_assembler = context_assembler
        self._history_repository = history_repository
        self._valid_skill_ids = frozenset(valid_skill_ids)
        self._controller = controller or ScaffoldingController()

    def run(self, request: ShadowControllerRequest) -> ShadowControllerResult:
        if not self._authorizer.is_authorized(request.principal_id, request.learner_id):
            return ShadowControllerResult(
                status=ShadowExecutionStatus.UNAUTHORIZED,
                correlation_id=request.correlation_id,
            )

        try:
            raw_mapping = self._skill_mapper.map(
                SkillMappingRequest(
                    learner_message=request.student_message,
                    preferred_language=request.preferred_language,
                )
            )
            mapping = SkillMappingResult.model_validate(raw_mapping, from_attributes=True)
            validate_skill_ids_against_taxonomy(mapping, self._valid_skill_ids)
        except Exception:  # noqa: BLE001 - internal dependency boundary fails closed
            return ShadowControllerResult(
                status=ShadowExecutionStatus.DEPENDENCY_FAILURE,
                correlation_id=request.correlation_id,
            )

        if mapping.status is not SkillMappingStatus.MATCHED or mapping.skill_id is None:
            return ShadowControllerResult(
                status=ShadowExecutionStatus.SKILL_NOT_CONFIRMED,
                correlation_id=request.correlation_id,
            )

        assembly = self._context_assembler.assemble(
            TutorContextAssemblyRequest(
                learner_id=request.learner_id,
                skill_mapping=mapping,
                skill_mapping_source=self._skill_mapper_source,
                session_id=str(request.session_id),
                as_of=request.as_of,
                max_age_ms=request.max_age_ms,
                interaction_id=request.interaction_id,
                interaction_sequence=request.interaction_sequence,
            )
        )
        if assembly.status is ContextReadinessStatus.NOT_READY:
            return ShadowControllerResult(
                status=ShadowExecutionStatus.NOT_READY,
                correlation_id=request.correlation_id,
                confirmed_skill_id=mapping.skill_id,
                context_issues=assembly.issues,
                provenance=assembly.provenance,
                evidence_origin=assembly.evidence_origin,
            )

        assert assembly.context is not None
        decision = self._controller.decide(assembly.context)
        selection_event = TutorHistoryEvent(
            event_id=uuid5(NAMESPACE_URL, f"mindbridge:tutor-selection:{request.correlation_id}"),
            idempotency_key=f"shadow:{request.correlation_id}",
            decision_id=request.correlation_id,
            learner_id=request.learner_id,
            skill_id=mapping.skill_id,
            session_id=request.session_id,
            interaction_id=request.interaction_id,
            interaction_sequence=request.interaction_sequence,
            event_sequence=1,
            event_type=TutorHistoryEventType.ASSISTANCE_SELECTED,
            occurred_at=request.as_of,
            provenance="adaptive-tutor:real-data-shadow",
            assistance_level=decision.assistance_level,
            policy_version=CONTROLLER_POLICY_VERSION,
            reason_codes=decision.reason_codes,
        )
        try:
            self._history_repository.append(selection_event)
        except Exception:  # noqa: BLE001 - persistence boundary fails closed
            return ShadowControllerResult(
                status=ShadowExecutionStatus.HISTORY_WRITE_FAILED,
                correlation_id=request.correlation_id,
                confirmed_skill_id=mapping.skill_id,
                provenance=assembly.provenance,
                evidence_origin=assembly.evidence_origin,
            )

        return ShadowControllerResult(
            status=ShadowExecutionStatus.DECIDED,
            correlation_id=request.correlation_id,
            confirmed_skill_id=mapping.skill_id,
            assistance_level=decision.assistance_level,
            controller_policy_version=CONTROLLER_POLICY_VERSION,
            controller_reason_codes=decision.reason_codes,
            provenance=assembly.provenance,
            evidence_origin=assembly.evidence_origin,
        )
