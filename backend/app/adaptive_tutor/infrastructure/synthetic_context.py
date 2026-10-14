import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self
from uuid import UUID

from app.adaptive_tutor.application.context_assembly import (
    AssessmentEvidenceResult,
    AssistanceHistoryResult,
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
    SupportNeedResult,
    TutorContextAssemblyRequest,
)
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
)
from app.knowledge_tracing.application.mastery import (
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
)
from app.shared.learner.domain import Learner

REFERENCE_SCENARIOS = Path(__file__).parents[1] / "application" / "reference_scenarios.json"


class SyntheticFixtureMode(StrEnum):
    COMPLETE = "COMPLETE"
    COLD_START = "COLD_START"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True, slots=True)
class SyntheticTutorContextFixture:
    """Explicit, offline-only evidence sourced from Reference Policy V1 examples."""

    scenario: Mapping[str, Any]
    mode: SyntheticFixtureMode
    source: EvidenceSource

    @classmethod
    def select(
        cls,
        scenario_id: str,
        *,
        allow_synthetic: bool = False,
        mode: SyntheticFixtureMode = SyntheticFixtureMode.COMPLETE,
    ) -> Self:
        if not allow_synthetic:
            raise PermissionError("synthetic fixtures require allow_synthetic=True")
        document = json.loads(REFERENCE_SCENARIOS.read_text(encoding="utf-8"))
        scenario = next(
            (item for item in document["scenarios"] if item["scenario_id"] == scenario_id),
            None,
        )
        if scenario is None:
            raise ValueError(f"unknown reference scenario: {scenario_id}")
        return cls(
            scenario=MappingProxyType(scenario),
            mode=mode,
            source=EvidenceSource(
                source_id=f"synthetic:reference-policy-v1:{scenario_id}:{mode.value}",
                origin=EvidenceOrigin.SYNTHETIC,
            ),
        )

    @property
    def learner_id(self) -> UUID:
        return UUID(self.scenario["learner_id"])

    @property
    def skill_id(self) -> str:
        return str(self.scenario["skill_id"])

    @property
    def expected_assistance_level(self) -> AssistanceLevel:
        return AssistanceLevel(self.scenario["expected_assistance_level"])

    def assembly_request(self) -> TutorContextAssemblyRequest:
        return TutorContextAssemblyRequest(
            learner_id=self.learner_id,
            skill_mapping=SkillMappingResult(
                status=SkillMappingStatus.MATCHED,
                intent=LearningIntent.EXPLANATION_REQUEST,
                skill_id=self.skill_id,
                confidence=1.0,
                clarification_needed=False,
                reason_codes=(SkillMappingReasonCode.DIRECT_SKILL_EVIDENCE,),
            ),
            skill_mapping_source=self.source,
        )

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        if learner_id != self.learner_id:
            return LearnerLookupResult(status=EvidenceStatus.NOT_FOUND)
        return LearnerLookupResult(
            status=EvidenceStatus.AVAILABLE,
            learner=Learner(
                id=self.learner_id,
                grade=4,
                preferred_language="synthetic-unspecified",
            ),
        )

    def get_mastery(self, request: MasteryRetrievalRequest) -> MasteryResult:
        if self.mode is SyntheticFixtureMode.PROVIDER_FAILURE:
            status = MasteryStatus.PROVIDER_ERROR
            mastery = None
        elif self.mode is SyntheticFixtureMode.COLD_START or (
            request.learner_id,
            request.skill_id,
        ) != (self.learner_id, self.skill_id):
            status = MasteryStatus.NOT_FOUND
            mastery = None
        else:
            status = MasteryStatus.AVAILABLE
            mastery = self.scenario["mastery"]
        return MasteryResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=status,
            mastery=mastery,
        )

    def get_support_need(self, request: ContextEvidenceRequest) -> SupportNeedResult:
        if self.mode is SyntheticFixtureMode.PROVIDER_FAILURE:
            return SupportNeedResult(status=EvidenceStatus.PROVIDER_ERROR)
        if self.mode is SyntheticFixtureMode.COLD_START:
            return SupportNeedResult(status=EvidenceStatus.NOT_YET_OBSERVED)
        if not self._matches(request):
            return SupportNeedResult(status=EvidenceStatus.NOT_FOUND)
        return SupportNeedResult(
            status=EvidenceStatus.AVAILABLE,
            support_need=self.scenario["support_need"],
        )

    def get_assessment_evidence(self, request: ContextEvidenceRequest) -> AssessmentEvidenceResult:
        if self.mode is SyntheticFixtureMode.PROVIDER_FAILURE:
            return AssessmentEvidenceResult(status=EvidenceStatus.PROVIDER_ERROR)
        if self.mode is SyntheticFixtureMode.COLD_START:
            return AssessmentEvidenceResult(
                status=EvidenceStatus.NOT_YET_OBSERVED,
                attempt_count=0,
            )
        if not self._matches(request):
            return AssessmentEvidenceResult(status=EvidenceStatus.NOT_FOUND)
        return AssessmentEvidenceResult(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=self.scenario["attempt_count"],
            is_correct=self.scenario["is_correct"],
            error_severity=self.scenario["error_severity"],
        )

    def get_assistance_history(self, request: ContextEvidenceRequest) -> AssistanceHistoryResult:
        if self.mode is SyntheticFixtureMode.PROVIDER_FAILURE:
            return AssistanceHistoryResult(status=EvidenceStatus.PROVIDER_ERROR)
        if self.mode is SyntheticFixtureMode.COLD_START:
            return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)
        if not self._matches(request):
            return AssistanceHistoryResult(status=EvidenceStatus.NOT_FOUND)
        previous_level = self.scenario["previous_assistance_level"]
        if previous_level is None:
            return AssistanceHistoryResult(status=EvidenceStatus.NOT_YET_OBSERVED)
        return AssistanceHistoryResult(
            status=EvidenceStatus.AVAILABLE,
            previous_assistance_level=previous_level,
            previous_hint_effective=self.scenario["previous_hint_effective"],
        )

    def _matches(self, request: ContextEvidenceRequest) -> bool:
        return (request.learner_id, request.skill_id) == (self.learner_id, self.skill_id)
