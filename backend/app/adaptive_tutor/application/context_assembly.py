from collections.abc import Collection
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.adaptive_tutor.application.contracts import TutoringContext
from app.adaptive_tutor.application.skill_mapper_contracts import (
    SkillMappingResult,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.domain import AssistanceLevel, SkillMappingStatus
from app.knowledge_tracing.application.mastery import (
    MasteryProvider,
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
    validate_mastery_result_identity,
)
from app.shared.learner.domain import Learner

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
NormalizedValue = Annotated[
    float,
    Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False),
]
AttemptCount = Annotated[int, Field(strict=True, ge=0)]


class EvidenceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    NOT_YET_OBSERVED = "NOT_YET_OBSERVED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"


class EvidenceOrigin(StrEnum):
    REAL = "REAL"
    SYNTHETIC = "SYNTHETIC"


class ContextEvidenceOrigin(StrEnum):
    REAL = "REAL"
    SYNTHETIC = "SYNTHETIC"
    MIXED = "MIXED"


class ContextInput(StrEnum):
    SKILL_MAPPING = "SKILL_MAPPING"
    LEARNER = "LEARNER"
    MASTERY = "MASTERY"
    SUPPORT_NEED = "SUPPORT_NEED"
    ASSESSMENT = "ASSESSMENT"
    ASSISTANCE_HISTORY = "ASSISTANCE_HISTORY"
    TUTORING_CONTEXT = "TUTORING_CONTEXT"


class ContextReadinessStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class ContextIssueKind(StrEnum):
    MISSING = "MISSING"
    INVALID = "INVALID"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    UNSUPPORTED = "UNSUPPORTED"


class ContextReadinessReason(StrEnum):
    SKILL_MAPPING_AMBIGUOUS = "SKILL_MAPPING_AMBIGUOUS"
    SKILL_NOT_MATCHED = "SKILL_NOT_MATCHED"
    SKILL_NOT_RELATED = "SKILL_NOT_RELATED"
    SKILL_INVALID = "SKILL_INVALID"
    LEARNER_NOT_FOUND = "LEARNER_NOT_FOUND"
    LEARNER_PROVIDER_UNAVAILABLE = "LEARNER_PROVIDER_UNAVAILABLE"
    LEARNER_PROVIDER_ERROR = "LEARNER_PROVIDER_ERROR"
    LEARNER_INVALID = "LEARNER_INVALID"
    UNSUPPORTED_GRADE = "UNSUPPORTED_GRADE"
    MASTERY_NOT_FOUND = "MASTERY_NOT_FOUND"
    MASTERY_PROVIDER_UNAVAILABLE = "MASTERY_PROVIDER_UNAVAILABLE"
    MASTERY_PROVIDER_ERROR = "MASTERY_PROVIDER_ERROR"
    MASTERY_INVALID = "MASTERY_INVALID"
    SUPPORT_NEED_NOT_FOUND = "SUPPORT_NEED_NOT_FOUND"
    SUPPORT_NEED_NOT_YET_OBSERVED = "SUPPORT_NEED_NOT_YET_OBSERVED"
    SUPPORT_NEED_PROVIDER_UNAVAILABLE = "SUPPORT_NEED_PROVIDER_UNAVAILABLE"
    SUPPORT_NEED_PROVIDER_ERROR = "SUPPORT_NEED_PROVIDER_ERROR"
    SUPPORT_NEED_INVALID = "SUPPORT_NEED_INVALID"
    ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
    ASSESSMENT_PROVIDER_UNAVAILABLE = "ASSESSMENT_PROVIDER_UNAVAILABLE"
    ASSESSMENT_PROVIDER_ERROR = "ASSESSMENT_PROVIDER_ERROR"
    ASSESSMENT_INVALID = "ASSESSMENT_INVALID"
    ASSISTANCE_HISTORY_NOT_FOUND = "ASSISTANCE_HISTORY_NOT_FOUND"
    ASSISTANCE_HISTORY_PROVIDER_UNAVAILABLE = "ASSISTANCE_HISTORY_PROVIDER_UNAVAILABLE"
    ASSISTANCE_HISTORY_PROVIDER_ERROR = "ASSISTANCE_HISTORY_PROVIDER_ERROR"
    ASSISTANCE_HISTORY_INVALID = "ASSISTANCE_HISTORY_INVALID"
    CONTEXT_INVALID = "CONTEXT_INVALID"


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    origin: EvidenceOrigin


class ContextEvidenceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: ContextInput
    source_id: NonBlankText
    origin: EvidenceOrigin
    status: NonBlankText


class ContextIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: ContextInput
    kind: ContextIssueKind
    reason: ContextReadinessReason
    message: NonBlankText


class ContextEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_id: NonBlankText


class TutorContextAssemblyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learner_id: UUID
    skill_mapping: SkillMappingResult
    skill_mapping_source: EvidenceSource


class LearnerLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    status: EvidenceStatus
    learner: Learner | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is EvidenceStatus.AVAILABLE and self.learner is None:
            raise ValueError("AVAILABLE requires learner")
        if self.status is not EvidenceStatus.AVAILABLE and self.learner is not None:
            raise ValueError("only AVAILABLE may contain learner")
        return self


class SupportNeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EvidenceStatus
    support_need: NormalizedValue | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is EvidenceStatus.AVAILABLE and self.support_need is None:
            raise ValueError("AVAILABLE requires numeric support_need")
        if self.status is not EvidenceStatus.AVAILABLE and self.support_need is not None:
            raise ValueError("only AVAILABLE may contain support_need")
        return self


class AssessmentEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EvidenceStatus
    attempt_count: AttemptCount | None = None
    is_correct: StrictBool | None = None
    error_severity: NormalizedValue | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is EvidenceStatus.NOT_YET_OBSERVED:
            if (
                self.attempt_count != 0
                or self.is_correct is not None
                or self.error_severity is not None
            ):
                raise ValueError("NOT_YET_OBSERVED requires an explicit zero-attempt state")
            return self

        if self.status is not EvidenceStatus.AVAILABLE:
            if any(
                value is not None
                for value in (self.attempt_count, self.is_correct, self.error_severity)
            ):
                raise ValueError("unavailable assessment evidence must not contain values")
            return self

        if self.attempt_count is None:
            raise ValueError("AVAILABLE requires attempt_count")
        if self.attempt_count == 0:
            if self.is_correct is not None or self.error_severity is not None:
                raise ValueError("zero attempts require null correctness and severity")
        elif self.is_correct is None or self.error_severity is None:
            raise ValueError("completed attempts require correctness and severity")
        return self


class AssistanceHistoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EvidenceStatus
    previous_assistance_level: AssistanceLevel | None = None
    previous_hint_effective: StrictBool | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is EvidenceStatus.NOT_YET_OBSERVED:
            if (
                self.previous_assistance_level is not None
                or self.previous_hint_effective is not None
            ):
                raise ValueError("NOT_YET_OBSERVED history must not contain values")
            return self

        if self.status is not EvidenceStatus.AVAILABLE:
            if (
                self.previous_assistance_level is not None
                or self.previous_hint_effective is not None
            ):
                raise ValueError("unavailable history must not contain values")
            return self

        if self.previous_assistance_level is None:
            raise ValueError("AVAILABLE history requires previous_assistance_level")
        return self


class LearnerProvider(Protocol):
    source: EvidenceSource

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult: ...


class ContextMasteryProvider(MasteryProvider, Protocol):
    source: EvidenceSource


class SupportNeedProvider(Protocol):
    source: EvidenceSource

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult: ...


class AssessmentEvidenceProvider(Protocol):
    source: EvidenceSource

    def get_assessment_evidence(
        self, request: ContextEvidenceRequest
    ) -> AssessmentEvidenceResult: ...


class AssistanceHistoryProvider(Protocol):
    source: EvidenceSource

    def get_assistance_history(
        self, request: ContextEvidenceRequest
    ) -> AssistanceHistoryResult: ...


class ContextAssemblyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ContextReadinessStatus
    context: TutoringContext | None = None
    learner_grade: Literal[4, 5] | None = None
    issues: tuple[ContextIssue, ...] = ()
    provenance: tuple[ContextEvidenceProvenance, ...]
    evidence_origin: ContextEvidenceOrigin

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is ContextReadinessStatus.READY:
            if self.context is None or self.learner_grade is None or self.issues:
                raise ValueError("READY requires context, learner grade, and no issues")
        elif self.context is not None or self.learner_grade is not None or not self.issues:
            raise ValueError("NOT_READY requires issues and no context or learner grade")
        return self


class TutorContextAssembler:
    """Validate provider evidence and assemble, but never evaluate, Controller V1 input."""

    def __init__(
        self,
        *,
        learner_provider: LearnerProvider,
        mastery_provider: ContextMasteryProvider,
        support_need_provider: SupportNeedProvider,
        assessment_provider: AssessmentEvidenceProvider,
        history_provider: AssistanceHistoryProvider,
        valid_skill_ids: Collection[str],
        supported_grades: Collection[int] = (4, 5),
    ) -> None:
        self._learner_provider = learner_provider
        self._mastery_provider = mastery_provider
        self._support_need_provider = support_need_provider
        self._assessment_provider = assessment_provider
        self._history_provider = history_provider
        self._valid_skill_ids = frozenset(valid_skill_ids)
        self._supported_grades = frozenset(supported_grades)
        if not self._valid_skill_ids:
            raise ValueError("valid_skill_ids must not be empty")
        if not self._supported_grades:
            raise ValueError("supported_grades must not be empty")

    def assemble(self, request: TutorContextAssemblyRequest) -> ContextAssemblyResult:
        provenance = [
            ContextEvidenceProvenance(
                input=ContextInput.SKILL_MAPPING,
                source_id=request.skill_mapping_source.source_id,
                origin=request.skill_mapping_source.origin,
                status=request.skill_mapping.status.value,
            )
        ]
        mapping_issue = self._mapping_issue(request.skill_mapping)
        if mapping_issue is not None:
            return _not_ready((mapping_issue,), provenance)

        assert request.skill_mapping.skill_id is not None
        skill_id = request.skill_mapping.skill_id
        try:
            validate_skill_ids_against_taxonomy(request.skill_mapping, self._valid_skill_ids)
        except ValueError:
            return _not_ready(
                (
                    _issue(
                        ContextInput.SKILL_MAPPING,
                        ContextIssueKind.INVALID,
                        ContextReadinessReason.SKILL_INVALID,
                        "Confirmed skill is not in the authoritative taxonomy.",
                    ),
                ),
                provenance,
            )

        learner_result, learner_issue = self._read_learner(request.learner_id, provenance)
        if learner_issue is not None:
            return _not_ready((learner_issue,), provenance)
        assert learner_result is not None and learner_result.learner is not None
        learner = learner_result.learner
        if learner.id != request.learner_id:
            return _not_ready(
                (
                    _issue(
                        ContextInput.LEARNER,
                        ContextIssueKind.INVALID,
                        ContextReadinessReason.LEARNER_INVALID,
                        "Learner result identity does not match the request.",
                    ),
                ),
                provenance,
            )
        if learner.grade not in self._supported_grades:
            return _not_ready(
                (
                    _issue(
                        ContextInput.LEARNER,
                        ContextIssueKind.UNSUPPORTED,
                        ContextReadinessReason.UNSUPPORTED_GRADE,
                        "Learner grade is outside the supported Grade 4-5 scope.",
                    ),
                ),
                provenance,
            )

        evidence_request = ContextEvidenceRequest(
            learner_id=request.learner_id,
            skill_id=skill_id,
        )
        mastery, mastery_issue = self._read_mastery(evidence_request, provenance)
        support, support_issue = self._read_support_need(evidence_request, provenance)
        assessment, assessment_issue = self._read_assessment(evidence_request, provenance)
        history, history_issue = self._read_history(evidence_request, provenance)
        issues = tuple(
            issue
            for issue in (mastery_issue, support_issue, assessment_issue, history_issue)
            if issue is not None
        )
        if issues:
            return _not_ready(issues, provenance)

        assert mastery is not None and mastery.mastery is not None
        assert support is not None and support.support_need is not None
        assert assessment is not None and assessment.attempt_count is not None
        assert history is not None
        try:
            context = TutoringContext(
                learner_id=request.learner_id,
                skill_id=skill_id,
                mastery=mastery.mastery,
                support_need=support.support_need,
                attempt_count=assessment.attempt_count,
                is_correct=assessment.is_correct,
                error_severity=assessment.error_severity,
                previous_assistance_level=history.previous_assistance_level,
                previous_hint_effective=history.previous_hint_effective,
            )
        except ValidationError:
            return _not_ready(
                (
                    _issue(
                        ContextInput.TUTORING_CONTEXT,
                        ContextIssueKind.INVALID,
                        ContextReadinessReason.CONTEXT_INVALID,
                        "Combined evidence violates the canonical TutoringContext contract.",
                    ),
                ),
                provenance,
            )

        return ContextAssemblyResult(
            status=ContextReadinessStatus.READY,
            context=context,
            learner_grade=learner.grade,
            provenance=tuple(provenance),
            evidence_origin=_combined_origin(provenance),
        )

    def _mapping_issue(self, mapping: SkillMappingResult) -> ContextIssue | None:
        if mapping.status is SkillMappingStatus.MATCHED:
            return None
        if mapping.status is SkillMappingStatus.AMBIGUOUS:
            return _issue(
                ContextInput.SKILL_MAPPING,
                ContextIssueKind.MISSING,
                ContextReadinessReason.SKILL_MAPPING_AMBIGUOUS,
                "Skill mapping requires clarification.",
            )
        if mapping.status is SkillMappingStatus.NOT_SKILL_RELATED:
            return _issue(
                ContextInput.SKILL_MAPPING,
                ContextIssueKind.UNSUPPORTED,
                ContextReadinessReason.SKILL_NOT_RELATED,
                "Message is not skill-related.",
            )
        return _issue(
            ContextInput.SKILL_MAPPING,
            ContextIssueKind.MISSING,
            ContextReadinessReason.SKILL_NOT_MATCHED,
            "No supported skill was confirmed.",
        )

    def _read_learner(
        self,
        learner_id: UUID,
        provenance: list[ContextEvidenceProvenance],
    ) -> tuple[LearnerLookupResult | None, ContextIssue | None]:
        try:
            raw_result = self._learner_provider.get_learner(learner_id)
        except Exception:  # noqa: BLE001 - integration boundary fails closed
            _append_provider_provenance(
                provenance,
                ContextInput.LEARNER,
                self._learner_provider.source,
                EvidenceStatus.PROVIDER_ERROR,
            )
            return None, _provider_error_issue(ContextInput.LEARNER)
        try:
            result = _revalidate(LearnerLookupResult, raw_result)
        except (TypeError, ValidationError):
            _append_provider_provenance(
                provenance,
                ContextInput.LEARNER,
                self._learner_provider.source,
                EvidenceStatus.INVALID_EVIDENCE,
            )
            return None, _issue(
                ContextInput.LEARNER,
                ContextIssueKind.INVALID,
                ContextReadinessReason.LEARNER_INVALID,
                "Learner evidence is invalid.",
            )
        _append_provider_provenance(
            provenance, ContextInput.LEARNER, self._learner_provider.source, result.status
        )
        if result.status is EvidenceStatus.AVAILABLE:
            return result, None
        return None, _status_issue(ContextInput.LEARNER, result.status)

    def _read_mastery(
        self,
        request: ContextEvidenceRequest,
        provenance: list[ContextEvidenceProvenance],
    ) -> tuple[MasteryResult | None, ContextIssue | None]:
        mastery_request = MasteryRetrievalRequest(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
        )
        try:
            raw_result = self._mastery_provider.get_mastery(mastery_request)
        except Exception:  # noqa: BLE001 - integration boundary fails closed
            _append_provider_provenance(
                provenance,
                ContextInput.MASTERY,
                self._mastery_provider.source,
                EvidenceStatus.PROVIDER_ERROR,
            )
            return None, _provider_error_issue(ContextInput.MASTERY)
        try:
            result = _revalidate(MasteryResult, raw_result)
            validate_mastery_result_identity(mastery_request, result)
        except (TypeError, ValidationError, ValueError):
            _append_provider_provenance(
                provenance,
                ContextInput.MASTERY,
                self._mastery_provider.source,
                EvidenceStatus.INVALID_EVIDENCE,
            )
            return None, _issue(
                ContextInput.MASTERY,
                ContextIssueKind.INVALID,
                ContextReadinessReason.MASTERY_INVALID,
                "Mastery evidence is invalid or does not match the request.",
            )
        _append_provider_provenance(
            provenance, ContextInput.MASTERY, self._mastery_provider.source, result.status
        )
        if result.status is MasteryStatus.AVAILABLE:
            return result, None
        return None, _mastery_status_issue(result.status)

    def _read_support_need(
        self,
        request: ContextEvidenceRequest,
        provenance: list[ContextEvidenceProvenance],
    ) -> tuple[SupportNeedResult | None, ContextIssue | None]:
        try:
            raw_result = self._support_need_provider.get_support_need(request)
        except Exception:  # noqa: BLE001 - integration boundary fails closed
            _append_provider_provenance(
                provenance,
                ContextInput.SUPPORT_NEED,
                self._support_need_provider.source,
                EvidenceStatus.PROVIDER_ERROR,
            )
            return None, _provider_error_issue(ContextInput.SUPPORT_NEED)
        try:
            result = _revalidate(SupportNeedResult, raw_result)
        except (TypeError, ValidationError):
            _append_provider_provenance(
                provenance,
                ContextInput.SUPPORT_NEED,
                self._support_need_provider.source,
                EvidenceStatus.INVALID_EVIDENCE,
            )
            return None, _issue(
                ContextInput.SUPPORT_NEED,
                ContextIssueKind.INVALID,
                ContextReadinessReason.SUPPORT_NEED_INVALID,
                "Support-need evidence must be a reviewed normalized numeric value.",
            )
        _append_provider_provenance(
            provenance,
            ContextInput.SUPPORT_NEED,
            self._support_need_provider.source,
            result.status,
        )
        if result.status is EvidenceStatus.AVAILABLE:
            return result, None
        return None, _status_issue(ContextInput.SUPPORT_NEED, result.status)

    def _read_assessment(
        self,
        request: ContextEvidenceRequest,
        provenance: list[ContextEvidenceProvenance],
    ) -> tuple[AssessmentEvidenceResult | None, ContextIssue | None]:
        try:
            raw_result = self._assessment_provider.get_assessment_evidence(request)
        except Exception:  # noqa: BLE001 - integration boundary fails closed
            _append_provider_provenance(
                provenance,
                ContextInput.ASSESSMENT,
                self._assessment_provider.source,
                EvidenceStatus.PROVIDER_ERROR,
            )
            return None, _provider_error_issue(ContextInput.ASSESSMENT)
        try:
            result = _revalidate(AssessmentEvidenceResult, raw_result)
        except (TypeError, ValidationError):
            _append_provider_provenance(
                provenance,
                ContextInput.ASSESSMENT,
                self._assessment_provider.source,
                EvidenceStatus.INVALID_EVIDENCE,
            )
            return None, _issue(
                ContextInput.ASSESSMENT,
                ContextIssueKind.INVALID,
                ContextReadinessReason.ASSESSMENT_INVALID,
                "Assessment evidence violates the canonical attempt semantics.",
            )
        _append_provider_provenance(
            provenance,
            ContextInput.ASSESSMENT,
            self._assessment_provider.source,
            result.status,
        )
        if result.status in {EvidenceStatus.AVAILABLE, EvidenceStatus.NOT_YET_OBSERVED}:
            return result, None
        return None, _status_issue(ContextInput.ASSESSMENT, result.status)

    def _read_history(
        self,
        request: ContextEvidenceRequest,
        provenance: list[ContextEvidenceProvenance],
    ) -> tuple[AssistanceHistoryResult | None, ContextIssue | None]:
        try:
            raw_result = self._history_provider.get_assistance_history(request)
        except Exception:  # noqa: BLE001 - integration boundary fails closed
            _append_provider_provenance(
                provenance,
                ContextInput.ASSISTANCE_HISTORY,
                self._history_provider.source,
                EvidenceStatus.PROVIDER_ERROR,
            )
            return None, _provider_error_issue(ContextInput.ASSISTANCE_HISTORY)
        try:
            result = _revalidate(AssistanceHistoryResult, raw_result)
        except (TypeError, ValidationError):
            _append_provider_provenance(
                provenance,
                ContextInput.ASSISTANCE_HISTORY,
                self._history_provider.source,
                EvidenceStatus.INVALID_EVIDENCE,
            )
            return None, _issue(
                ContextInput.ASSISTANCE_HISTORY,
                ContextIssueKind.INVALID,
                ContextReadinessReason.ASSISTANCE_HISTORY_INVALID,
                "Assistance-history evidence is internally inconsistent.",
            )
        _append_provider_provenance(
            provenance,
            ContextInput.ASSISTANCE_HISTORY,
            self._history_provider.source,
            result.status,
        )
        if result.status in {EvidenceStatus.AVAILABLE, EvidenceStatus.NOT_YET_OBSERVED}:
            return result, None
        return None, _status_issue(ContextInput.ASSISTANCE_HISTORY, result.status)


def _append_provider_provenance(
    provenance: list[ContextEvidenceProvenance],
    input_name: ContextInput,
    source: EvidenceSource,
    status: StrEnum,
) -> None:
    provenance.append(
        ContextEvidenceProvenance(
            input=input_name,
            source_id=source.source_id,
            origin=source.origin,
            status=status.value,
        )
    )


def _revalidate[ModelT: BaseModel](model_type: type[ModelT], result: object) -> ModelT:
    data = result.model_dump() if isinstance(result, BaseModel) else result
    return model_type.model_validate(data, from_attributes=True)


def _combined_origin(
    provenance: Collection[ContextEvidenceProvenance],
) -> ContextEvidenceOrigin:
    origins = {item.origin for item in provenance}
    if origins == {EvidenceOrigin.REAL}:
        return ContextEvidenceOrigin.REAL
    if origins == {EvidenceOrigin.SYNTHETIC}:
        return ContextEvidenceOrigin.SYNTHETIC
    return ContextEvidenceOrigin.MIXED


def _not_ready(
    issues: tuple[ContextIssue, ...],
    provenance: Collection[ContextEvidenceProvenance],
) -> ContextAssemblyResult:
    provenance_tuple = tuple(provenance)
    return ContextAssemblyResult(
        status=ContextReadinessStatus.NOT_READY,
        issues=issues,
        provenance=provenance_tuple,
        evidence_origin=_combined_origin(provenance_tuple),
    )


def _issue(
    input_name: ContextInput,
    kind: ContextIssueKind,
    reason: ContextReadinessReason,
    message: str,
) -> ContextIssue:
    return ContextIssue(input=input_name, kind=kind, reason=reason, message=message)


def _provider_error_issue(input_name: ContextInput) -> ContextIssue:
    reason = {
        ContextInput.LEARNER: ContextReadinessReason.LEARNER_PROVIDER_ERROR,
        ContextInput.MASTERY: ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ContextInput.SUPPORT_NEED: ContextReadinessReason.SUPPORT_NEED_PROVIDER_ERROR,
        ContextInput.ASSESSMENT: ContextReadinessReason.ASSESSMENT_PROVIDER_ERROR,
        ContextInput.ASSISTANCE_HISTORY: ContextReadinessReason.ASSISTANCE_HISTORY_PROVIDER_ERROR,
    }[input_name]
    return _issue(
        input_name,
        ContextIssueKind.PROVIDER_FAILURE,
        reason,
        f"{input_name.value.replace('_', ' ').title()} provider failed safely.",
    )


def _status_issue(input_name: ContextInput, status: EvidenceStatus) -> ContextIssue:
    mapping = {
        (ContextInput.LEARNER, EvidenceStatus.NOT_FOUND): (
            ContextIssueKind.MISSING,
            ContextReadinessReason.LEARNER_NOT_FOUND,
        ),
        (ContextInput.LEARNER, EvidenceStatus.PROVIDER_UNAVAILABLE): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.LEARNER_PROVIDER_UNAVAILABLE,
        ),
        (ContextInput.LEARNER, EvidenceStatus.PROVIDER_ERROR): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.LEARNER_PROVIDER_ERROR,
        ),
        (ContextInput.SUPPORT_NEED, EvidenceStatus.NOT_FOUND): (
            ContextIssueKind.MISSING,
            ContextReadinessReason.SUPPORT_NEED_NOT_FOUND,
        ),
        (ContextInput.SUPPORT_NEED, EvidenceStatus.NOT_YET_OBSERVED): (
            ContextIssueKind.MISSING,
            ContextReadinessReason.SUPPORT_NEED_NOT_YET_OBSERVED,
        ),
        (ContextInput.SUPPORT_NEED, EvidenceStatus.PROVIDER_UNAVAILABLE): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.SUPPORT_NEED_PROVIDER_UNAVAILABLE,
        ),
        (ContextInput.SUPPORT_NEED, EvidenceStatus.PROVIDER_ERROR): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.SUPPORT_NEED_PROVIDER_ERROR,
        ),
        (ContextInput.ASSESSMENT, EvidenceStatus.NOT_FOUND): (
            ContextIssueKind.MISSING,
            ContextReadinessReason.ASSESSMENT_NOT_FOUND,
        ),
        (ContextInput.ASSESSMENT, EvidenceStatus.PROVIDER_UNAVAILABLE): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.ASSESSMENT_PROVIDER_UNAVAILABLE,
        ),
        (ContextInput.ASSESSMENT, EvidenceStatus.PROVIDER_ERROR): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.ASSESSMENT_PROVIDER_ERROR,
        ),
        (ContextInput.ASSISTANCE_HISTORY, EvidenceStatus.PROVIDER_UNAVAILABLE): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.ASSISTANCE_HISTORY_PROVIDER_UNAVAILABLE,
        ),
        (ContextInput.ASSISTANCE_HISTORY, EvidenceStatus.PROVIDER_ERROR): (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.ASSISTANCE_HISTORY_PROVIDER_ERROR,
        ),
        (ContextInput.ASSISTANCE_HISTORY, EvidenceStatus.NOT_FOUND): (
            ContextIssueKind.MISSING,
            ContextReadinessReason.ASSISTANCE_HISTORY_NOT_FOUND,
        ),
    }
    if status is EvidenceStatus.INVALID_EVIDENCE:
        reason = {
            ContextInput.LEARNER: ContextReadinessReason.LEARNER_INVALID,
            ContextInput.SUPPORT_NEED: ContextReadinessReason.SUPPORT_NEED_INVALID,
            ContextInput.ASSESSMENT: ContextReadinessReason.ASSESSMENT_INVALID,
            ContextInput.ASSISTANCE_HISTORY: ContextReadinessReason.ASSISTANCE_HISTORY_INVALID,
        }[input_name]
        return _issue(
            input_name, ContextIssueKind.INVALID, reason, "Provider reported invalid evidence."
        )
    kind, reason = mapping.get(
        (input_name, status),
        (
            ContextIssueKind.MISSING,
            {
                ContextInput.LEARNER: ContextReadinessReason.LEARNER_NOT_FOUND,
                ContextInput.SUPPORT_NEED: ContextReadinessReason.SUPPORT_NEED_NOT_FOUND,
                ContextInput.ASSESSMENT: ContextReadinessReason.ASSESSMENT_NOT_FOUND,
                ContextInput.ASSISTANCE_HISTORY: (
                    ContextReadinessReason.ASSISTANCE_HISTORY_NOT_FOUND
                ),
            }[input_name],
        ),
    )
    return _issue(input_name, kind, reason, f"{input_name.value} evidence is {status.value}.")


def _mastery_status_issue(status: MasteryStatus) -> ContextIssue:
    kind, reason = {
        MasteryStatus.NOT_FOUND: (
            ContextIssueKind.MISSING,
            ContextReadinessReason.MASTERY_NOT_FOUND,
        ),
        MasteryStatus.PROVIDER_UNAVAILABLE: (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.MASTERY_PROVIDER_UNAVAILABLE,
        ),
        MasteryStatus.PROVIDER_ERROR: (
            ContextIssueKind.PROVIDER_FAILURE,
            ContextReadinessReason.MASTERY_PROVIDER_ERROR,
        ),
    }[status]
    return _issue(ContextInput.MASTERY, kind, reason, f"Mastery evidence is {status.value}.")
