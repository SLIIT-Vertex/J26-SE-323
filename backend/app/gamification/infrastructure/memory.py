from collections.abc import Callable, Iterable
from datetime import datetime
from uuid import UUID

from app.gamification.application.records import (
    AuditEvent,
    ConsentDecision,
    CurriculumEvidence,
    FeatureSnapshotRecord,
    LearnerStateEvidence,
    MasteryEvidence,
    ModelArtifact,
    NormalizedAttempt,
    PolicyDecisionRecord,
    TutorSupportRequest,
    TutorSupportResult,
)
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ModelId,
    PolicyDecisionId,
    SkillId,
)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock values must include a UTC offset")


class FixedClock:
    def __init__(self, value: datetime) -> None:
        _require_aware(value)
        self._value = value

    def now(self) -> datetime:
        return self._value


class InMemoryAuditOutput:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def write(self, event: AuditEvent) -> None:
        self.events.append(event)


class InMemoryFeatureSnapshotStore:
    def __init__(self) -> None:
        self._records: dict[FeatureSnapshotId, FeatureSnapshotRecord] = {}

    def add(self, snapshot: FeatureSnapshotRecord) -> None:
        if snapshot.snapshot_id in self._records:
            raise ValueError(f"feature snapshot already exists: {snapshot.snapshot_id}")
        self._records[snapshot.snapshot_id] = snapshot

    def get(self, snapshot_id: FeatureSnapshotId) -> FeatureSnapshotRecord | None:
        return self._records.get(snapshot_id)


class InMemoryPolicyDecisionStore:
    def __init__(self) -> None:
        self._records: dict[PolicyDecisionId, PolicyDecisionRecord] = {}

    def add(self, decision: PolicyDecisionRecord) -> None:
        if decision.decision_id in self._records:
            raise ValueError(f"policy decision already exists: {decision.decision_id}")
        self._records[decision.decision_id] = decision

    def get(self, decision_id: PolicyDecisionId) -> PolicyDecisionRecord | None:
        return self._records.get(decision_id)


class InMemoryModelRegistry:
    def __init__(self, artifacts: Iterable[ModelArtifact] = ()) -> None:
        self._approved: dict[ModelId, ModelArtifact] = {}
        for artifact in artifacts:
            self.register(artifact)

    def register(self, artifact: ModelArtifact) -> None:
        if artifact.approved:
            self._approved[artifact.model_id] = artifact

    def get_approved(self, model_id: ModelId) -> ModelArtifact | None:
        return self._approved.get(model_id)


class StubKnowledgeTracingGateway:
    def __init__(self, mastery: Iterable[MasteryEvidence] = ()) -> None:
        self._mastery = {
            (evidence.learner_id, evidence.skill_id): evidence for evidence in mastery
        }
        self.recorded_attempts: list[NormalizedAttempt] = []

    def get_mastery(self, *, learner_id: UUID, skill_id: SkillId) -> MasteryEvidence | None:
        return self._mastery.get((learner_id, skill_id))

    def record_attempt(self, attempt: NormalizedAttempt) -> None:
        self.recorded_attempts.append(attempt)


class StubLearnerStateGateway:
    def __init__(self, evidence: Iterable[LearnerStateEvidence] = ()) -> None:
        self._evidence = {record.learner_id: record for record in evidence}

    def get_support_evidence(
        self, *, learner_id: UUID, observed_no_earlier_than: datetime
    ) -> LearnerStateEvidence | None:
        record = self._evidence.get(learner_id)
        if record is None or record.observed_at < observed_no_earlier_than:
            return None
        return record


class StubTutorSupportGateway:
    def __init__(
        self, responder: Callable[[TutorSupportRequest], TutorSupportResult]
    ) -> None:
        self._responder = responder
        self.requests: list[TutorSupportRequest] = []

    def create_verified_support(self, request: TutorSupportRequest) -> TutorSupportResult:
        self.requests.append(request)
        return self._responder(request)


class StubConsentGateway:
    def __init__(self, decisions: Iterable[ConsentDecision]) -> None:
        self._decisions = {
            (decision.learner_id, decision.purpose): decision for decision in decisions
        }

    def get_consent(self, *, learner_id: UUID, purpose: str) -> ConsentDecision:
        try:
            return self._decisions[(learner_id, purpose)]
        except KeyError as error:
            raise LookupError("no consent decision exists for learner and purpose") from error


class StubCurriculumRetriever:
    """Returns pre-approved references only; it performs no retrieval or ranking logic."""

    def __init__(self, evidence: Iterable[CurriculumEvidence] = ()) -> None:
        self._evidence = tuple(evidence)

    def find_approved(
        self, *, skill_id: SkillId, language: str, limit: int
    ) -> tuple[CurriculumEvidence, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        matches = (
            item
            for item in self._evidence
            if item.approved and item.skill_id == skill_id and item.language == language
        )
        return tuple(list(matches)[:limit])

