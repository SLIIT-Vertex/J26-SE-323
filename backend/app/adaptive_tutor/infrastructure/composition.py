"""Deny-by-default composition for metadata-only real-provider Tutor shadowing."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.adaptive_tutor.application.context_assembly import (
    AssessmentEvidenceProvider,
    EvidenceSource,
    TutorContextAssembler,
)
from app.adaptive_tutor.application.controller import ScaffoldingController
from app.adaptive_tutor.application.generation import LlmProvider
from app.adaptive_tutor.application.orchestration import (
    SkillMapper,
    TrustedAnswerProvider,
    TutorOrchestrator,
)
from app.adaptive_tutor.application.verification import SemanticVerifier
from app.adaptive_tutor.infrastructure.assessment_evidence import (
    LedgerAssessmentEvidenceProvider,
    UnresolvedAssessmentEvidenceProvider,
)
from app.adaptive_tutor.infrastructure.knowledge_tracing_mastery import (
    KnowledgeTracingMasteryProvider,
)
from app.adaptive_tutor.infrastructure.learner_state_support_need import (
    LearnerStateSupportNeedProvider,
)
from app.adaptive_tutor.infrastructure.research_sessions import (
    ExperimentalHintGenerator,
    ResearchTutorService,
)
from app.adaptive_tutor.infrastructure.shadow_mode import (
    RealDataControllerShadow,
    ShadowAuthorizer,
    ShadowControllerRequest,
)
from app.adaptive_tutor.infrastructure.shared_learner import SharedLearnerProvider
from app.adaptive_tutor.infrastructure.tutor_assessment import (
    SqlAlchemyTutorAssessmentRepository,
)
from app.adaptive_tutor.infrastructure.tutor_history import (
    SqlAlchemyTutorHistoryRepository,
    TutorHistoryProvider,
)
from app.curriculum.application import CurriculumRetriever
from app.knowledge_tracing.application.mastery_service import Estimator, MasteryService
from app.knowledge_tracing.domain.feature_spec import FeatureSpec
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.learner_state.application.support_need import StoredSupportNeedProvider
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.shared.learner.repository import SqlAlchemyLearnerRepository
from app.shared.learner.service import LearnerService


class DenyAllShadowAuthorizer:
    def is_authorized(self, principal_id: UUID, learner_id: UUID) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class _TrustedSession:
    principal_id: UUID
    learner_id: UUID
    expires_at: datetime


class TrustedShadowRequestFactory:
    """Issues server-owned shadow session, interaction, sequence and time values."""

    def __init__(
        self,
        authorizer: ShadowAuthorizer,
        *,
        lifetime: timedelta = timedelta(minutes=30),
    ) -> None:
        self._authorizer = authorizer
        self._lifetime = lifetime
        self._sessions: dict[UUID, _TrustedSession] = {}
        self._sequences: dict[UUID, int] = {}
        self._lock = Lock()

    def start(self, principal_id: UUID, learner_id: UUID, *, now: datetime | None = None) -> UUID:
        if not self._authorizer.is_authorized(principal_id, learner_id):
            raise PermissionError("Tutor shadow access denied")
        current = now or datetime.now(UTC)
        session_id = uuid4()
        with self._lock:
            self._sessions[session_id] = _TrustedSession(
                principal_id=principal_id,
                learner_id=learner_id,
                expires_at=current + self._lifetime,
            )
            self._sequences[session_id] = 0
        return session_id

    def create_request(
        self,
        *,
        principal_id: UUID,
        learner_id: UUID,
        session_id: UUID,
        student_message: str,
        preferred_language: str | None,
        max_age_ms: int,
        now: datetime | None = None,
    ) -> ShadowControllerRequest:
        current = now or datetime.now(UTC)
        with self._lock:
            session = self._sessions.get(session_id)
            if (
                session is None
                or session.principal_id != principal_id
                or session.learner_id != learner_id
                or current >= session.expires_at
                or not self._authorizer.is_authorized(principal_id, learner_id)
            ):
                raise PermissionError("Tutor shadow session is invalid or expired")
            sequence = self._sequences[session_id] + 1
            self._sequences[session_id] = sequence
        return ShadowControllerRequest(
            correlation_id=uuid4(),
            principal_id=principal_id,
            learner_id=learner_id,
            student_message=student_message,
            preferred_language=preferred_language,
            session_id=session_id,
            interaction_id=str(uuid4()),
            interaction_sequence=sequence,
            as_of=current,
            max_age_ms=max_age_ms,
        )


@dataclass(frozen=True, slots=True)
class InternalTutorComposition:
    shadow: RealDataControllerShadow
    requests: TrustedShadowRequestFactory


def build_internal_tutor_composition(
    *,
    session: Session,
    skill_mapper: SkillMapper,
    skill_mapper_source: EvidenceSource,
    estimator: Estimator,
    feature_spec: FeatureSpec,
    valid_skill_ids: Collection[str],
    authorizer: ShadowAuthorizer | None = None,
    assessment_provider: AssessmentEvidenceProvider | None = None,
) -> InternalTutorComposition:
    """Connect real read adapters without adding generation or delivery capabilities."""

    access = authorizer or DenyAllShadowAuthorizer()
    history_repository = SqlAlchemyTutorHistoryRepository(session)
    context = TutorContextAssembler(
        learner_provider=SharedLearnerProvider(
            LearnerService(SqlAlchemyLearnerRepository(session))
        ),
        mastery_provider=KnowledgeTracingMasteryProvider(
            MasteryService(
                SqlAlchemyMasteryRepository(session),
                estimator,
                feature_spec,
            ),
            valid_skill_ids,
        ),
        support_need_provider=LearnerStateSupportNeedProvider(
            StoredSupportNeedProvider(SqlAlchemyLearnerSkillStateRepository(session))
        ),
        assessment_provider=assessment_provider or UnresolvedAssessmentEvidenceProvider(),
        history_provider=TutorHistoryProvider(history_repository),
        valid_skill_ids=valid_skill_ids,
    )
    return InternalTutorComposition(
        shadow=RealDataControllerShadow(
            authorizer=access,
            skill_mapper=skill_mapper,
            skill_mapper_source=skill_mapper_source,
            context_assembler=context,
            history_repository=history_repository,
            valid_skill_ids=valid_skill_ids,
        ),
        requests=TrustedShadowRequestFactory(access),
    )


def build_research_tutor_service(
    *,
    session: Session,
    skill_mapper: SkillMapper,
    skill_mapper_source: EvidenceSource,
    estimator: Estimator,
    feature_spec: FeatureSpec,
    valid_skill_ids: Collection[str],
    curriculum_retriever: CurriculumRetriever,
    llm_provider: LlmProvider,
    semantic_verifier: SemanticVerifier | None,
    trusted_answer_provider: TrustedAnswerProvider | None,
    eligible_scorer_sources: Collection[str],
    eligible_severity_policy_versions: Collection[str],
    semantic_verifier_is_simulated: bool = False,
    controlled_research_assessment: bool = True,
    authorized_generation_providers: Collection[str] = (),
    freshness_ms: int = 60_000,
    decision_only: bool = False,
    experimental_generator: ExperimentalHintGenerator | None = None,
    experimental_cold_start_mastery: float | None = None,
    experimental_missing_support_need: float | None = None,
) -> ResearchTutorService:
    """Compose the local research workflow from existing real read adapters.

    This function does not create authentication, approve a corpus or enable an
    HTTP route. Callers must explicitly inject reviewed providers and policies.
    """

    learners = SqlAlchemyLearnerRepository(session)
    assessments = SqlAlchemyTutorAssessmentRepository(session)
    history = SqlAlchemyTutorHistoryRepository(session)
    context = TutorContextAssembler(
        learner_provider=SharedLearnerProvider(
            LearnerService(learners)
        ),
        mastery_provider=KnowledgeTracingMasteryProvider(
            MasteryService(
                SqlAlchemyMasteryRepository(session),
                estimator,
                feature_spec,
            ),
            valid_skill_ids,
            cold_start_default=experimental_cold_start_mastery,
        ),
        support_need_provider=LearnerStateSupportNeedProvider(
            StoredSupportNeedProvider(SqlAlchemyLearnerSkillStateRepository(session)),
            not_found_default=experimental_missing_support_need,
        ),
        assessment_provider=LedgerAssessmentEvidenceProvider(
            assessments,
            valid_skill_ids=valid_skill_ids,
            eligible_scorer_sources=eligible_scorer_sources,
            eligible_severity_policy_versions=eligible_severity_policy_versions,
            controlled_research=controlled_research_assessment,
        ),
        history_provider=TutorHistoryProvider(history),
        valid_skill_ids=valid_skill_ids,
    )
    orchestrator = TutorOrchestrator(
        skill_mapper=skill_mapper,
        skill_mapper_source=skill_mapper_source,
        context_assembler=context,
        controller=ScaffoldingController(),
        llm_provider=llm_provider,
        valid_skill_ids=valid_skill_ids,
        curriculum_retriever=curriculum_retriever,
        semantic_verifier=semantic_verifier,
        trusted_answer_provider=trusted_answer_provider,
        semantic_verifier_is_simulated=semantic_verifier_is_simulated,
        authorized_generation_providers=authorized_generation_providers,
        decision_only=decision_only,
    )
    return ResearchTutorService(
        skill_mapper=skill_mapper,
        orchestrator=orchestrator,
        assessments=assessments,
        history=history,
        eligible_severity_policy_versions=frozenset(eligible_severity_policy_versions),
        freshness_ms=freshness_ms,
        experimental_generator=experimental_generator,
        learner_exists=lambda learner_id: learners.get(learner_id) is not None,
    )
