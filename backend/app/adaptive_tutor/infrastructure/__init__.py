"""Adaptive Tutor infrastructure adapters."""

from app.adaptive_tutor.infrastructure.assessment_evidence import (
    LedgerAssessmentEvidenceProvider,
    UnresolvedAssessmentEvidenceProvider,
)
from app.adaptive_tutor.infrastructure.composition import (
    DenyAllShadowAuthorizer,
    InternalTutorComposition,
    TrustedShadowRequestFactory,
    build_internal_tutor_composition,
    build_research_tutor_service,
)
from app.adaptive_tutor.infrastructure.embeddings import (
    DEFAULT_E5_MODEL,
    DEFAULT_E5_REVISION,
    SentenceTransformerE5EmbeddingModel,
)
from app.adaptive_tutor.infrastructure.gemini import (
    GeminiConfigurationError,
    GeminiGenerationConfig,
    GeminiLlmProvider,
    select_tutor_llm_provider,
)
from app.adaptive_tutor.infrastructure.knowledge_tracing_mastery import (
    KnowledgeTracingMasteryProvider,
)
from app.adaptive_tutor.infrastructure.learner_state_support_need import (
    LearnerStateSupportNeedProvider,
)
from app.adaptive_tutor.infrastructure.local_research import (
    build_local_research_tutor_service,
)
from app.adaptive_tutor.infrastructure.semantic_verifier import (
    ConfiguredSemanticVerifier,
    OpenAICompatibleStructuredSemanticClient,
    SemanticVerifierProviderConfig,
    build_semantic_verifier_from_settings,
)
from app.adaptive_tutor.infrastructure.shadow_mode import (
    RealDataControllerShadow,
    ShadowControllerRequest,
    ShadowControllerResult,
    ShadowExecutionStatus,
    StaticShadowAuthorizer,
)
from app.adaptive_tutor.infrastructure.shared_learner import SharedLearnerProvider
from app.adaptive_tutor.infrastructure.skill_mapper_resources import (
    JsonSkillRelevanceCatalog,
    JsonSkillTaxonomyEnrichmentCatalog,
    SkillRetrievalEnrichment,
)
from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.adaptive_tutor.infrastructure.synthetic_context import (
    SyntheticFixtureMode,
    SyntheticTutorContextFixture,
)
from app.adaptive_tutor.infrastructure.tutor_assessment import (
    AssessmentAttemptStatus,
    AssessmentAttemptWrite,
    SqlAlchemyTutorAssessmentRepository,
    TutorAssessmentInteraction,
)
from app.adaptive_tutor.infrastructure.tutor_history import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryEvent,
    TutorHistoryEventStatus,
    TutorHistoryEventType,
    TutorHistoryProvider,
    TutorInteractionEventModel,
)

__all__ = [
    "DEFAULT_E5_MODEL",
    "DEFAULT_E5_REVISION",
    "AssessmentAttemptStatus",
    "AssessmentAttemptWrite",
    "ConfiguredSemanticVerifier",
    "DenyAllShadowAuthorizer",
    "GeminiConfigurationError",
    "GeminiGenerationConfig",
    "GeminiLlmProvider",
    "InternalTutorComposition",
    "JsonSkillRelevanceCatalog",
    "JsonSkillTaxonomyEnrichmentCatalog",
    "KnowledgeTracingMasteryProvider",
    "LearnerStateSupportNeedProvider",
    "LedgerAssessmentEvidenceProvider",
    "OpenAICompatibleStructuredSemanticClient",
    "RealDataControllerShadow",
    "SemanticVerifierProviderConfig",
    "SentenceTransformerE5EmbeddingModel",
    "ShadowControllerRequest",
    "ShadowControllerResult",
    "ShadowExecutionStatus",
    "SharedLearnerProvider",
    "SkillRetrievalEnrichment",
    "SqlAlchemyTutorAssessmentRepository",
    "SqlAlchemyTutorHistoryRepository",
    "StaticShadowAuthorizer",
    "SyntheticFixtureMode",
    "SyntheticTutorContextFixture",
    "TrustedShadowRequestFactory",
    "TutorAssessmentInteraction",
    "TutorHistoryEvent",
    "TutorHistoryEventStatus",
    "TutorHistoryEventType",
    "TutorHistoryProvider",
    "TutorInteractionEventModel",
    "UnresolvedAssessmentEvidenceProvider",
    "XlsxSkillTaxonomyCatalog",
    "build_internal_tutor_composition",
    "build_local_research_tutor_service",
    "build_research_tutor_service",
    "build_semantic_verifier_from_settings",
    "select_tutor_llm_provider",
]
