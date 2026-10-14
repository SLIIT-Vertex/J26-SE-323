from collections.abc import Callable, Iterable
from datetime import datetime
from uuid import UUID

from app.gamification.application.records import (
    AuditEvent,
    ConsentDecision,
    FeatureSnapshotRecord,
    GamificationAttempt,
    LearnerSkillSummary,
    LearnerStateEvidence,
    ModelArtifact,
    PolicyDecisionRecord,
    SupportAssetRequest,
    SupportAssetResult,
)
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ItemId,
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


class InMemoryLearningRecordStore:
    def __init__(self, summaries: Iterable[LearnerSkillSummary] = ()) -> None:
        self._summaries = {
            (summary.learner_id, summary.skill_id): summary for summary in summaries
        }
        self.recorded_attempts: list[GamificationAttempt] = []

    def get_skill_summary(
        self, *, learner_id: UUID, skill_id: SkillId
    ) -> LearnerSkillSummary | None:
        return self._summaries.get((learner_id, str(skill_id)))

    def get(self, *, learner_id: UUID, skill_id: str) -> LearnerSkillSummary | None:
        return self._summaries.get((learner_id, skill_id))

    def save(self, summary: LearnerSkillSummary) -> None:
        self._summaries[(summary.learner_id, summary.skill_id)] = summary

    def record_attempt(self, attempt: GamificationAttempt) -> None:
        self.recorded_attempts.append(attempt)

    def seen_item_ids(self, *, learner_id: UUID) -> tuple[ItemId, ...]:
        seen: list[ItemId] = []
        for attempt in self.recorded_attempts:
            if attempt.learner_id == learner_id and attempt.item_id not in seen:
                seen.append(attempt.item_id)
        return tuple(seen)


class StubLearnerStateGateway:
    def __init__(self, evidence: Iterable[LearnerStateEvidence] = ()) -> None:
        self._evidence = {(record.learner_id, record.skill_id): record for record in evidence}

    def get_support_evidence(
        self,
        *,
        learner_id: UUID,
        skill_id: SkillId,
        observed_no_earlier_than: datetime,
    ) -> LearnerStateEvidence | None:
        record = self._evidence.get((learner_id, skill_id))
        if record is None or record.observed_at < observed_no_earlier_than:
            return None
        return record


class InMemorySupportAssetProvider:
    def __init__(
        self, responder: Callable[[SupportAssetRequest], SupportAssetResult]
    ) -> None:
        self._responder = responder
        self.requests: list[SupportAssetRequest] = []

    def create_verified_support(self, request: SupportAssetRequest) -> SupportAssetResult:
        self.requests.append(request)
        return self._responder(request)


class InMemoryConsentStore:
    def __init__(self, decisions: Iterable[ConsentDecision]) -> None:
        self._decisions = {
            (decision.learner_id, decision.purpose): decision for decision in decisions
        }

    def get_consent(self, *, learner_id: UUID, purpose: str) -> ConsentDecision:
        try:
            return self._decisions[(learner_id, purpose)]
        except KeyError as error:
            raise LookupError("no consent decision exists for learner and purpose") from error
