"""Explicit local-only composition for the adult research Tutor path."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.adaptive_tutor.application.context_assembly import EvidenceOrigin, EvidenceSource
from app.adaptive_tutor.application.generation import LlmProvider
from app.adaptive_tutor.application.orchestration import TrustedAnswerReference
from app.adaptive_tutor.application.skill_mapper import (
    ConversationalSkillMapper,
    SemanticSkillRetriever,
)
from app.adaptive_tutor.infrastructure.composition import build_research_tutor_service
from app.adaptive_tutor.infrastructure.embeddings import (
    DEFAULT_E5_REVISION,
    SentenceTransformerE5EmbeddingModel,
)
from app.adaptive_tutor.infrastructure.gemini import select_tutor_llm_provider
from app.adaptive_tutor.infrastructure.research_sessions import (
    CONTROLLED_ANNOTATION_SOURCE,
    ExperimentalHintGenerator,
    ResearchTutorService,
)
from app.adaptive_tutor.infrastructure.semantic_verifier import (
    build_semantic_verifier_from_settings,
)
from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.config import Settings
from app.curriculum.infrastructure.embeddings import E5CurriculumEmbedder
from app.curriculum.infrastructure.hybrid_retriever import HybridCurriculumRetriever
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.knowledge_tracing.domain.feature_spec import load_feature_spec
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel
from app.shared.learner.repository import SqlAlchemyLearnerRepository

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTAL_CURRICULUM_PATH = (
    REPOSITORY_ROOT
    / "research/adaptive-tutor/fractions-live-template/fractions-content.UNREVIEWED.txt"
)


@dataclass(frozen=True)
class ConfiguredResearchTrustedAnswerProvider:
    """Serve one exact server-reviewed Fractions question/answer reference."""

    question: str
    accepted_answers: tuple[str, ...]
    provenance: str

    def get_trusted_answer(
        self,
        *,
        student_question: str,
        skill_id: str,
        grade: int,
    ) -> TrustedAnswerReference | None:
        del grade
        if skill_id != "MAT-FRC" or student_question.strip() != self.question:
            return None
        return TrustedAnswerReference(
            accepted_answers=self.accepted_answers,
            provenance=self.provenance,
        )


def configured_research_trusted_answer(
    settings: Settings,
) -> ConfiguredResearchTrustedAnswerProvider:
    """Build the exact answer reference without exposing its contents."""

    question = settings.tutor_research_trusted_question.strip()
    provenance = settings.tutor_research_trusted_answer_provenance.strip()
    if not question:
        raise ValueError("TUTOR_RESEARCH_TRUSTED_QUESTION is required")
    if not provenance:
        raise ValueError("TUTOR_RESEARCH_TRUSTED_ANSWER_PROVENANCE is required")
    try:
        raw_answers = json.loads(settings.tutor_research_trusted_answers_json)
    except json.JSONDecodeError as error:
        raise ValueError("TUTOR_RESEARCH_TRUSTED_ANSWERS_JSON must be valid JSON") from error
    if (
        not isinstance(raw_answers, list)
        or not raw_answers
        or any(not isinstance(answer, str) or not answer.strip() for answer in raw_answers)
    ):
        raise ValueError(
            "TUTOR_RESEARCH_TRUSTED_ANSWERS_JSON must be a non-empty JSON string array"
        )
    provider = ConfiguredResearchTrustedAnswerProvider(
        question=question,
        accepted_answers=tuple(answer.strip() for answer in raw_answers),
        provenance=provenance,
    )
    try:
        provider.get_trusted_answer(
            student_question=question,
            skill_id="MAT-FRC",
            grade=5,
        )
    except ValueError as error:
        raise ValueError("trusted answers must be unique, valid answer text") from error
    return provider


def validate_local_research_settings(settings: Settings) -> frozenset[str]:
    """Validate live research gates without loading models or calling providers."""

    if settings.tutor_api_mode != "research-local":
        raise ValueError("TUTOR_API_MODE must be research-local")
    if not settings.tutor_research_composition_enabled:
        raise ValueError("TUTOR_RESEARCH_COMPOSITION_ENABLED must be true")
    if not settings.tutor_research_access_key.strip():
        raise ValueError("TUTOR_RESEARCH_ACCESS_KEY is required")
    try:
        UUID(settings.tutor_researcher_id)
    except ValueError as error:
        raise ValueError("TUTOR_RESEARCHER_ID must be a UUID") from error
    if settings.tutor_llm_provider.strip().casefold() != "gemini":
        raise ValueError("the live research composition requires TUTOR_LLM_PROVIDER=gemini")
    if not settings.tutor_research_gemini_authorized:
        raise ValueError("Gemini is not authorized for the local adult research path")
    severity_policies = frozenset(
        value.strip()
        for value in settings.tutor_research_severity_policy_versions.split(",")
        if value.strip()
    )
    if not severity_policies:
        raise ValueError("at least one reviewed research severity policy is required")
    if settings.tutor_pp1_experimental_demo_enabled:
        return severity_policies
    if not settings.tutor_semantic_verifier_enabled:
        raise ValueError("the independent semantic verifier is disabled")
    if not settings.tutor_semantic_verifier_independent:
        raise ValueError("the semantic verifier independence assertion is required")
    if "gemini" in settings.tutor_semantic_verifier_provider.strip().casefold():
        raise ValueError("generator and verifier providers must differ")
    configured_research_trusted_answer(settings)
    return severity_policies


def build_local_research_tutor_service(
    settings: Settings,
    session: Session,
    *,
    gemini_client: Any | None = None,
    llm_provider: LlmProvider | None = None,
) -> ResearchTutorService:
    """Build the reviewed local slice only after every live opt-in is present.

    ``llm_provider`` replaces the configured provider outright (offline rehearsals), so its own
    name, never ``google-gemini``, labels every draft. ``gemini_client`` only wraps real Gemini.
    """

    if llm_provider is not None and gemini_client is not None:
        raise ValueError("pass either llm_provider or gemini_client, not both")

    severity_policies = validate_local_research_settings(settings)

    nodes = XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    valid_skill_ids = frozenset(node.skill_id for node in nodes)
    mapper_embeddings = SentenceTransformerE5EmbeddingModel(local_files_only=True)
    mapper = ConversationalSkillMapper(SemanticSkillRetriever(nodes, mapper_embeddings))

    feature_spec = load_feature_spec(settings.feature_spec_path)
    estimator = KnowledgeModel.load(settings.model_weights_path, feature_spec)
    llm_provider = llm_provider or select_tutor_llm_provider(settings, gemini_client=gemini_client)
    experimental = settings.tutor_pp1_experimental_demo_enabled
    semantic_verifier = (
        None
        if experimental
        else build_semantic_verifier_from_settings(
            settings,
            generator_provider_name=llm_provider.name,
        )
    )
    curriculum = HybridCurriculumRetriever(
        CurriculumVectorIndex(session),
        E5CurriculumEmbedder(local_files_only=True),
    )
    experimental_generator = None
    if experimental:
        learners = SqlAlchemyLearnerRepository(session)

        def learner_grade(learner_id: UUID) -> int | None:
            learner = learners.get(learner_id)
            return learner.grade if learner is not None else None

        experimental_generator = ExperimentalHintGenerator(
            llm_provider,
            EXPERIMENTAL_CURRICULUM_PATH.read_text(encoding="utf-8"),
            learner_grade,
        )

    return build_research_tutor_service(
        session=session,
        skill_mapper=mapper,
        skill_mapper_source=EvidenceSource(
            source_id=f"skill-mapper:e5:{DEFAULT_E5_REVISION}:canonical-taxonomy",
            origin=EvidenceOrigin.REAL,
        ),
        estimator=estimator,
        feature_spec=feature_spec,
        valid_skill_ids=valid_skill_ids,
        curriculum_retriever=curriculum,
        llm_provider=llm_provider,
        semantic_verifier=semantic_verifier,
        trusted_answer_provider=(
            None if experimental else configured_research_trusted_answer(settings)
        ),
        eligible_scorer_sources={CONTROLLED_ANNOTATION_SOURCE},
        eligible_severity_policy_versions=severity_policies,
        controlled_research_assessment=True,
        authorized_generation_providers={llm_provider.name},
        decision_only=experimental,
        experimental_generator=experimental_generator,
        experimental_cold_start_mastery=0.0 if experimental else None,
        experimental_missing_support_need=0.0 if experimental else None,
    )
