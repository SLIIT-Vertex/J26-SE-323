import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from app.adaptive_tutor.application.context_assembly import TutorContextAssembler
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.generation import DeterministicFakeLlmProvider, LlmProvider
from app.adaptive_tutor.application.orchestration import TutorOrchestrator
from app.adaptive_tutor.application.skill_mapper_contracts import (
    SkillMappingRequest,
    SkillMappingResult,
)
from app.adaptive_tutor.application.verification import (
    DeterministicFakeSemanticVerifier,
    SemanticVerificationResult,
    SemanticVerifier,
    TrustedAnswerReference,
    VerificationCheckOutcome,
)
from app.adaptive_tutor.domain import (
    AssistanceLevel,
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
)
from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.adaptive_tutor.infrastructure.synthetic_context import (
    REFERENCE_SCENARIOS,
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.curriculum.application import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

_RESPONSES = {
    AssistanceLevel.INDEPENDENT_RETRY: "Try the problem once yourself.",
    AssistanceLevel.METACOGNITIVE_PROMPT: "What strategy could you try first?",
    AssistanceLevel.CONCEPTUAL_HINT: "Think about the main idea behind this problem.",
    AssistanceLevel.TARGETED_HINT: "Start with the next useful step, then pause.",
    AssistanceLevel.GUIDED_STEPS: "Begin with one step. What should you do next?",
    AssistanceLevel.SIMILAR_WORKED_EXAMPLE: (
        "For a different example, two groups of three make six. Now try your problem."
    ),
    AssistanceLevel.FULL_EXPLANATION: (
        "Use the approved idea to work through each part carefully and explain the result."
    ),
}


class UnknownSyntheticLearnerError(LookupError):
    """The learner UUID is not one of the controlled Reference Policy fixtures."""


@dataclass(frozen=True, slots=True)
class SyntheticDemoSkillMapper:
    matched_result: SkillMappingResult

    def map(self, request: SkillMappingRequest) -> SkillMappingResult:
        controlled_result = {
            "can you help me?": SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=LearningIntent.HINT_REQUEST,
                clarification_needed=True,
                clarification_question="Which learning topic do you need help with?",
                reason_codes=(SkillMappingReasonCode.INSUFFICIENT_EVIDENCE,),
            ),
            "how do plants make food?": SkillMappingResult(
                status=SkillMappingStatus.NO_MATCH,
                intent=LearningIntent.EXPLANATION_REQUEST,
                clarification_needed=False,
                reason_codes=(SkillMappingReasonCode.OUTSIDE_SUPPORTED_TAXONOMY,),
            ),
            "hello!": SkillMappingResult(
                status=SkillMappingStatus.NOT_SKILL_RELATED,
                intent=LearningIntent.GREETING,
                clarification_needed=False,
                reason_codes=(SkillMappingReasonCode.NOT_SKILL_RELATED,),
            ),
        }.get(request.learner_message.casefold())
        return controlled_result or self.matched_result


@dataclass(frozen=True, slots=True)
class SyntheticCurriculumRetriever:
    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult:
        source = CurriculumSourceRecord(
            source_id="SYNTHETIC-TUTOR-API-SOURCE",
            title="Synthetic Tutor API demonstration source",
            publisher_authority="Synthetic research fixture",
            grade=request.grade,
            subject="Synthetic mathematics",
            language=request.requested_language,
            source_type="synthetic-demo-fixture",
            source_location="repository://synthetic/adaptive-tutor-api",
            source_version="synthetic-v1",
            metadata_status=MetadataStatus.VERIFIED,
            ingestion_status=IngestionStatus.INGESTED,
            review_status=CurriculumReviewStatus.APPROVED,
            usage_rights_status=UsageRightsStatus.PERMITTED,
        )
        passage = RetrievedCurriculumPassage(
            chunk=CurriculumChunk(
                chunk_id="SYNTHETIC-TUTOR-API-CHUNK",
                source_id=source.source_id,
                source_version="synthetic-v1",
                content="Use the approved synthetic concept to explain the solution clearly.",
                grade=request.grade,
                subject="Synthetic mathematics",
                language=request.requested_language or "en",
                skill_ids=(request.skill_id,),
                page_number=1,
                section_locator="Synthetic demonstration section",
                review_status=CurriculumReviewStatus.APPROVED,
            ),
            source=source,
            score=1.0,
        )
        return CurriculumRetrievalResult(
            status=CurriculumRetrievalStatus.FOUND,
            passages=(passage,),
        )


@dataclass(frozen=True, slots=True)
class SyntheticTrustedAnswerProvider:
    def get_trusted_answer(
        self,
        *,
        student_question: str,
        skill_id: str,
        grade: int,
    ) -> TrustedAnswerReference:
        return TrustedAnswerReference(
            accepted_answers=("999",),
            provenance="synthetic API demonstration answer",
        )


def build_synthetic_tutor_orchestrator(
    learner_id: UUID,
    *,
    fixture_mode: SyntheticFixtureMode = SyntheticFixtureMode.COMPLETE,
    llm_provider: LlmProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    use_default_semantic_verifier: bool = True,
    include_curriculum: bool = True,
    max_regeneration_attempts: int = 2,
) -> TutorOrchestrator:
    fixture = _fixture_for_learner(learner_id, fixture_mode)
    return build_controlled_tutor_orchestrator(
        fixture,
        llm_provider=llm_provider,
        semantic_verifier=semantic_verifier,
        use_default_semantic_verifier=use_default_semantic_verifier,
        include_curriculum=include_curriculum,
        max_regeneration_attempts=max_regeneration_attempts,
    )


def build_controlled_tutor_orchestrator(
    fixture: SyntheticTutorContextFixture,
    *,
    llm_provider: LlmProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    use_default_semantic_verifier: bool = True,
    include_curriculum: bool = True,
    max_regeneration_attempts: int = 2,
) -> TutorOrchestrator:
    valid_skill_ids = _valid_skill_ids()
    context_assembler = TutorContextAssembler(
        learner_provider=fixture,
        mastery_provider=fixture,
        support_need_provider=fixture,
        assessment_provider=fixture,
        history_provider=fixture,
        valid_skill_ids=valid_skill_ids,
    )
    selected_semantic_verifier = semantic_verifier
    if selected_semantic_verifier is None and use_default_semantic_verifier:
        selected_semantic_verifier = DeterministicFakeSemanticVerifier(_passing_semantic_result())
    return TutorOrchestrator(
        skill_mapper=SyntheticDemoSkillMapper(fixture.assembly_request().skill_mapping),
        skill_mapper_source=fixture.source,
        context_assembler=context_assembler,
        controller=ScaffoldingController(),
        llm_provider=llm_provider
        or DeterministicFakeLlmProvider(response=_RESPONSES[fixture.expected_assistance_level]),
        valid_skill_ids=valid_skill_ids,
        curriculum_retriever=SyntheticCurriculumRetriever() if include_curriculum else None,
        semantic_verifier=selected_semantic_verifier,
        trusted_answer_provider=SyntheticTrustedAnswerProvider(),
        semantic_verifier_is_simulated=selected_semantic_verifier is not None,
        max_regeneration_attempts=max_regeneration_attempts,
    )


def _fixture_for_learner(
    learner_id: UUID,
    mode: SyntheticFixtureMode = SyntheticFixtureMode.COMPLETE,
) -> SyntheticTutorContextFixture:
    document = json.loads(REFERENCE_SCENARIOS.read_text(encoding="utf-8"))
    scenario_id = next(
        (
            item["scenario_id"]
            for item in document["scenarios"]
            if UUID(item["learner_id"]) == learner_id
        ),
        None,
    )
    if scenario_id is None:
        raise UnknownSyntheticLearnerError
    return SyntheticTutorContextFixture.select(
        scenario_id,
        allow_synthetic=True,
        mode=mode,
    )


@lru_cache
def _valid_skill_ids() -> frozenset[str]:
    nodes = XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    return frozenset(node.skill_id for node in nodes)


def _passing_semantic_result() -> SemanticVerificationResult:
    return SemanticVerificationResult(
        assistance_level_compliance=VerificationCheckOutcome.PASS,
        answer_leakage=VerificationCheckOutcome.PASS,
        factual_support=VerificationCheckOutcome.PASS,
        language_appropriateness=VerificationCheckOutcome.PASS,
        age_appropriateness=VerificationCheckOutcome.PASS,
    )
