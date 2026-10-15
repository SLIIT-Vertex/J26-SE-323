from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.gamification.api.contracts import LearnerEvidenceContract
from app.gamification.application.policy_update import (
    InMemoryPolicyTrainingLog,
    InMemorySupportPolicySource,
    PolicyTrainingExample,
    UpdateSupportPolicy,
)
from app.gamification.application.records import ConsentDecision, LearnerEvidenceEvent
from app.gamification.application.skill_summary import UpdateLearnerSkillSummary
from app.gamification.domain.types import ContractVersion, OutcomeValidity, SkillId
from app.gamification.infrastructure.curriculum_adapter import SharedCurriculumAdapter
from app.gamification.infrastructure.db.episode_store import SqlAlchemyLearningRecordStore
from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    GameSessionModel,
    LearnerEvidenceOutboxModel,
    ModelVersionModel,
    PolicyUpdateCursorModel,
)
from app.gamification.infrastructure.db.policy_artifact_store import (
    SqlAlchemyPolicyArtifactStore,
    SqlAlchemyPolicyUpdateCursor,
)
from app.gamification.infrastructure.evidence_publisher import SqlAlchemyLearnerEvidenceOutbox
from app.gamification.infrastructure.gateways.knowledge_tracing_mastery import (
    KnowledgeTracingMasteryGateway,
)
from app.gamification.infrastructure.gateways.learner_state_support_need import (
    LearnerStateSupportNeedGateway,
)
from app.gamification.infrastructure.memory import (
    FixedClock,
    InMemoryAuditOutput,
    InMemoryConsentStore,
    InMemoryLearningRecordStore,
)
from app.gamification.modeling.shared.artifact_registry import (
    ApprovalGatedArtifactRegistry,
    ModelArtifactBundle,
)
from app.gamification.modeling.support_selection.context import (
    BanditContext,
    bandit_context_from_values,
)
from app.gamification.modeling.support_selection.learned_policy import LinUCBPolicy
from app.knowledge_tracing.application.mastery import MasteryResult, MasteryStatus
from app.learner_state.application.support_need import SupportNeedResult, SupportNeedStatus
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

AT = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
LEARNER = UUID("00000000-0000-4000-8000-000000000501")
OTHER = UUID("00000000-0000-4000-8000-000000000502")
FINE = "G5-MAT-C03-L01-O01"
PARENT = "MAT-FRC"
ROOT = Path(__file__).resolve().parents[3]
WORKBOOK = ROOT / "docs" / "skill_nodes.xlsx"


def universal_skill_ids() -> set[str]:
    return {node.skill_id for node in XlsxSkillTaxonomyCatalog(WORKBOOK).load()}


def consent_for(*learner_ids: UUID) -> InMemoryConsentStore:
    return InMemoryConsentStore(
        [
            ConsentDecision(
                learner_id=learner_id,
                purpose="research",
                granted=True,
                consent_version="consent-v1",
                decided_at=AT - timedelta(days=1),
                expires_at=None,
                contract_version=ContractVersion("gamification-consent-v1"),
            )
            for learner_id in learner_ids
        ]
    )


class _MasteryProvider:
    def __init__(self, result: MasteryResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.requests: list[object] = []

    def get_mastery(self, request: object) -> MasteryResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class _SupportProvider:
    def __init__(self, result: SupportNeedResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.requests: list[object] = []

    def get_support_need(self, request: object) -> SupportNeedResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _mastery_gateway(provider: _MasteryProvider, crosswalk: dict[str, str] | None = None):
    return KnowledgeTracingMasteryGateway(
        provider=provider,
        crosswalk=crosswalk if crosswalk is not None else {FINE: PARENT},
        allowed_universal_ids=universal_skill_ids(),
        audit=InMemoryAuditOutput(),
        clock=FixedClock(AT),
    )


def _support_gateway(provider: _SupportProvider, crosswalk: dict[str, str] | None = None):
    return LearnerStateSupportNeedGateway(
        provider=provider,
        crosswalk=crosswalk if crosswalk is not None else {FINE: PARENT},
        allowed_universal_ids=universal_skill_ids(),
        audit=InMemoryAuditOutput(),
        clock=FixedClock(AT),
    )


def _assert_universal(requested: list[str]) -> None:
    allowed = universal_skill_ids()
    assert requested
    assert FINE not in requested
    assert set(requested) <= allowed


@pytest.mark.parametrize(
    "status",
    [
        MasteryStatus.NOT_FOUND,
        MasteryStatus.PROVIDER_UNAVAILABLE,
        MasteryStatus.PROVIDER_ERROR,
    ],
)
def test_non_available_mastery_is_missingness_with_an_audit(status: MasteryStatus) -> None:
    provider = _MasteryProvider(
        MasteryResult(learner_id=LEARNER, skill_id=PARENT, status=status, mastery=None)
    )
    gateway = _mastery_gateway(provider)

    assert gateway.get_mastery(learner_id=LEARNER, skill_id=SkillId(FINE)) is None
    _assert_universal(gateway.requested_skill_ids)
    assert gateway._audit.events[-1].reason_codes == (f"MASTERY_{status.value}",)


def test_mastery_provider_exception_and_missing_crosswalk_do_not_raise() -> None:
    provider = _MasteryProvider(error=RuntimeError("down"))
    gateway = _mastery_gateway(provider)
    assert gateway.get_mastery(learner_id=LEARNER, skill_id=SkillId(FINE)) is None
    _assert_universal(gateway.requested_skill_ids)
    assert gateway._audit.events[-1].reason_codes == ("MASTERY_PROVIDER_EXCEPTION",)

    missing = _mastery_gateway(_MasteryProvider(), crosswalk={})
    assert missing.get_mastery(learner_id=LEARNER, skill_id=SkillId(FINE)) is None
    assert missing.requested_skill_ids == []
    assert missing._audit.events[-1].reason_codes == ("MASTERY_CROSSWALK_MISSING",)

    unknown = _mastery_gateway(_MasteryProvider(), crosswalk={FINE: "NOT-A-SKILL"})
    assert unknown.get_mastery(learner_id=LEARNER, skill_id=SkillId(FINE)) is None
    assert unknown.requested_skill_ids == []
    assert unknown._audit.events[-1].reason_codes == ("UNIVERSAL_SKILL_NOT_IN_TAXONOMY",)


def test_available_mastery_keeps_the_gamification_skill_and_universal_parent() -> None:
    provider = _MasteryProvider(
        MasteryResult(
            learner_id=LEARNER, skill_id=PARENT, status=MasteryStatus.AVAILABLE, mastery=0.4
        )
    )
    evidence = _mastery_gateway(provider).get_mastery(learner_id=LEARNER, skill_id=SkillId(FINE))

    assert evidence is not None
    assert evidence.mastery_probability == 0.4
    assert str(evidence.skill_id) == FINE
    assert evidence.universal_skill_id == PARENT
    assert evidence.uncertainty is None
    assert evidence.observed_at is None
    assert provider.requests[0].skill_id == PARENT


def test_support_need_statuses_map_to_evidence_or_missingness() -> None:
    available = _support_gateway(
        _SupportProvider(
            SupportNeedResult(
                learner_id=LEARNER,
                skill_id=PARENT,
                status=SupportNeedStatus.AVAILABLE,
                support_need=0.8,
                observed_at=AT,
            )
        )
    )
    evidence = available.get_support_evidence(
        learner_id=LEARNER,
        skill_id=SkillId(FINE),
        observed_no_earlier_than=AT - timedelta(days=1),
    )
    assert evidence is not None and evidence.support_need == 0.8 and evidence.uncertain is False
    _assert_universal(available.requested_skill_ids)

    uncertain = _support_gateway(
        _SupportProvider(
            SupportNeedResult(
                learner_id=LEARNER,
                skill_id=PARENT,
                status=SupportNeedStatus.UNCERTAIN,
                observed_at=AT,
            )
        )
    )
    flagged = uncertain.get_support_evidence(
        learner_id=LEARNER,
        skill_id=SkillId(FINE),
        observed_no_earlier_than=AT - timedelta(days=1),
    )
    assert flagged is not None and flagged.uncertain is True and flagged.support_need is None

    missing = _support_gateway(
        _SupportProvider(
            SupportNeedResult(
                learner_id=LEARNER, skill_id=PARENT, status=SupportNeedStatus.NOT_FOUND
            )
        )
    )
    assert (
        missing.get_support_evidence(
            learner_id=LEARNER,
            skill_id=SkillId(FINE),
            observed_no_earlier_than=AT - timedelta(days=1),
        )
        is None
    )
    assert missing._audit.events[-1].reason_codes == ("SUPPORT_NEED_NOT_FOUND",)

    stale = _support_gateway(
        _SupportProvider(
            SupportNeedResult(
                learner_id=LEARNER,
                skill_id=PARENT,
                status=SupportNeedStatus.AVAILABLE,
                support_need=0.8,
                observed_at=AT - timedelta(days=8),
            )
        )
    )
    assert (
        stale.get_support_evidence(
            learner_id=LEARNER,
            skill_id=SkillId(FINE),
            observed_no_earlier_than=AT - timedelta(days=7),
        )
        is None
    )
    assert stale._audit.events[-1].reason_codes == ("LEARNER_STATE_STALE",)

    broken = _support_gateway(_SupportProvider(error=RuntimeError("down")))
    assert (
        broken.get_support_evidence(
            learner_id=LEARNER,
            skill_id=SkillId(FINE),
            observed_no_earlier_than=AT - timedelta(days=1),
        )
        is None
    )
    _assert_universal(broken.requested_skill_ids)
    assert broken._audit.events[-1].reason_codes == ("SUPPORT_NEED_PROVIDER_EXCEPTION",)


def test_curriculum_adapter_sends_the_universal_skill_id() -> None:
    class _Retriever:
        def __init__(self) -> None:
            self.request = None

        def retrieve(self, request: object) -> str:
            self.request = request
            return "recorded"

    retriever = _Retriever()
    adapter = SharedCurriculumAdapter(retriever, {FINE: PARENT})  # type: ignore[arg-type]
    assert adapter.retrieve(learner_question="fractions", skill_id=FINE, grade=5) == "recorded"
    assert retriever.request is not None
    assert retriever.request.skill_id == PARENT
    assert retriever.request.purpose == "CONTENT_AUTHORING"
    with pytest.raises(ValueError, match="universal skill"):
        adapter.retrieve(learner_question="fractions", skill_id="missing", grade=5)


def test_policy_context_json_restores_the_bandit_vector() -> None:
    context = BanditContext("bandit-context-v1", ("bias",), (1.0,), {})
    restored = bandit_context_from_values(context.to_feature_values())

    assert restored.version == context.version
    assert restored.names == context.names
    assert restored.values == context.values


def _example(
    episode_id: str,
    learner_id: UUID,
    *,
    validity: OutcomeValidity = OutcomeValidity.VALID,
    raw_gain: float | None = 1.0,
    at: datetime = AT,
) -> PolicyTrainingExample:
    return PolicyTrainingExample(
        episode_id=episode_id,
        learner_id=learner_id,
        decided_at=at,
        context=BanditContext("bandit-context-v1", ("bias",), (1.0,), {}),
        arm="visual",
        propensity=0.5,
        validity=validity,
        raw_gain=raw_gain,
    )


def _approved_source() -> tuple[ApprovalGatedArtifactRegistry, str, InMemorySupportPolicySource]:
    manifest = type("Manifest", (), {"digest": "a" * 64, "synthetic": True})()
    bundle = ModelArtifactBundle.create(
        model_name="support-policy",
        model_version="contextual-bandit-v1",
        source_commit="c5-seed",
        feature_definition_version="bandit-context-v1",
        manifest=manifest,
        seed=1,
        parameters=LinUCBPolicy().parameters(),
    )
    registry = ApprovalGatedArtifactRegistry()
    registry.register(bundle)
    registry.activate(
        model_name="support-policy",
        artifact_sha256=bundle.artifact_sha256,
        approved=True,
        approver="policy-owner",
        approved_at=AT,
    )
    return registry, bundle.artifact_sha256, InMemorySupportPolicySource(registry)


def _job(
    examples: tuple[PolicyTrainingExample, ...], consent: InMemoryConsentStore
) -> tuple[UpdateSupportPolicy, InMemoryPolicyTrainingLog, ApprovalGatedArtifactRegistry, str]:
    registry, active_hash, source = _approved_source()
    log = InMemoryPolicyTrainingLog(examples)
    audit = InMemoryAuditOutput()
    job = UpdateSupportPolicy(
        log=log,
        policies=source,
        consent=consent,
        audit=audit,
        seed=7,
        source_commit="c5-policy-update",
    )
    return job, log, registry, active_hash


def test_one_episode_does_not_update_the_policy() -> None:
    job, log, registry, active_hash = _job((_example("episode-1", LEARNER),), consent_for(LEARNER))

    result = job.execute(AT)

    assert result.status == "batch_below_minimum"
    assert result.consumed_episode_ids == ()
    assert log.consumed == []
    assert registry.active("support-policy").artifact_sha256 == active_hash  # type: ignore[union-attr]
    assert job._policies.drafts == []


def test_policy_update_is_batched_consent_aware_and_idempotent() -> None:
    examples = (
        _example("episode-1", LEARNER, at=AT),
        _example("episode-2", OTHER, at=AT + timedelta(seconds=1)),
        _example("episode-3", uuid4(), at=AT + timedelta(seconds=2)),
        _example("episode-4", LEARNER, validity=OutcomeValidity.INVALID, raw_gain=None),
    )
    job, log, registry, active_hash = _job(examples, consent_for(LEARNER, OTHER))

    first = job.execute(AT)
    second = job.execute(AT)
    replay_job, _replay_log, _replay_registry, _replay_active = _job(
        examples[:2], consent_for(LEARNER, OTHER)
    )
    replay = replay_job.execute(AT)

    assert first.status == "drafted"
    assert first.artifact_sha256 is not None
    assert first.artifact_sha256 != active_hash
    assert first.consumed_episode_ids == ("episode-1", "episode-2")
    assert ("episode-3", "CONSENT_SCOPE_MISSING") in first.skipped
    assert ("episode-4", "INVALID_OUTCOME") in first.skipped
    assert registry.active("support-policy").artifact_sha256 == active_hash  # type: ignore[union-attr]
    draft = job._policies.drafts[0]
    assert draft.parameters["arms"] != registry.active("support-policy").parameters["arms"]  # type: ignore[union-attr]
    assert second.status == "unchanged"
    assert second.artifact_sha256 == first.artifact_sha256
    assert second.consumed_episode_ids == ()
    assert len(log.consumed) == 4
    assert replay.artifact_sha256 == first.artifact_sha256
    assert any(
        event.metadata.get("artifact_sha256") == first.artifact_sha256
        for event in job._audit.events
    )


def test_supported_and_unsupported_counts_do_not_mix() -> None:
    store = InMemoryLearningRecordStore()
    updater = UpdateLearnerSkillSummary(store)
    updater.record_attempt(learner_id=LEARNER, skill_id=FINE, correct=False, supported=False, at=AT)
    summary = updater.record_attempt(
        learner_id=LEARNER, skill_id=FINE, correct=True, supported=True, at=AT
    )

    assert summary.unsupported_attempts == 1
    assert summary.supported_attempts == 1
    assert summary.independent_accuracy == 0.0
    assert summary.supported_accuracy == 1.0
    assert summary.mean_independence_gain is None
    changed = updater.record_valid_gain(learner_id=LEARNER, skill_id=FINE, raw_gain=1.0, at=AT)
    assert changed.mean_independence_gain == 1.0
    assert changed.independent_accuracy == 0.0
    assert changed.supported_accuracy == 1.0
    assert changed.support_dependency_index == 0.5


def _evidence_body(**payload: object) -> dict[str, object]:
    body: dict[str, object] = {
        "contract_version": "gamification-learner-evidence-v1",
        "event_type": "attempt_summary",
        "learner_id": LEARNER,
        "skill_id": FINE,
        "universal_skill_id": PARENT,
        "timestamp": AT,
        "source_component": "gamification",
        "model_version": "gamification-attempt-v1",
        "confidence": None,
        "evidence_reference": {"episode_id": "episode-1"},
        "payload": {"unsupported_score": 0.0, "supported": False},
    }
    body.update(payload)
    return body


def test_learner_evidence_contract_requires_both_skill_ids_and_rejects_answers() -> None:
    contract = LearnerEvidenceContract.model_validate(_evidence_body())
    assert contract.skill_id == FINE
    assert contract.universal_skill_id == PARENT
    with pytest.raises(ValidationError):
        LearnerEvidenceContract.model_validate(_evidence_body(note="extra"))
    with pytest.raises(ValidationError, match="item text or answers"):
        LearnerEvidenceContract.model_validate(
            _evidence_body(payload={"answer": "four eighths", "unsupported_score": 0.0})
        )


def _sqlite_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return Session(engine)


def test_outbox_summary_and_draft_artifact_round_trip() -> None:
    session = _sqlite_session()
    session_id = uuid4()
    episode_id = uuid4()
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=AT, updated_at=AT)
    )
    session.flush()
    session.add(
        GameSessionModel(
            id=session_id,
            learner_id=LEARNER,
            client_session_id=uuid4(),
            idempotency_key="c5-session",
            status="active",
            language="si",
            app_version="test-v1",
            device_class="test",
            started_at=AT,
            last_event_sequence=0,
            created_at=AT,
            updated_at=AT,
        )
    )
    session.flush()
    session.add(
        AdaptiveEpisodeModel(
            id=episode_id,
            session_id=session_id,
            learner_id=LEARNER,
            skill_code=FINE,
            skill_taxonomy_version="grade5-pilot-skills-v1",
            phase="completed",
            trigger_type="TWO_INCORRECT_ATTEMPTS",
            episode_protocol_version="adaptive-episode-v1",
            opened_at=AT,
            transitioned_at=AT,
            revision=1,
            created_at=AT,
        )
    )
    session.flush()
    event = LearnerEvidenceEvent(
        event_type="attempt_summary",
        learner_id=LEARNER,
        skill_id=FINE,
        universal_skill_id=PARENT,
        timestamp=AT,
        model_version="gamification-attempt-v1",
        confidence=None,
        evidence_reference={"episode_id": "episode-1"},
        payload={"unsupported_score": 0.0, "supported": False},
    )
    outbox = SqlAlchemyLearnerEvidenceOutbox(session)
    outbox.publish(event)
    outbox.publish(event)
    rows = session.scalars(select(LearnerEvidenceOutboxModel)).all()
    assert len(rows) == 1
    assert rows[0].attempt_count == 2
    assert rows[0].payload_json["payload"] == {"unsupported_score": 0.0, "supported": False}
    assert "answer" not in rows[0].payload_json["payload"]

    store = SqlAlchemyLearningRecordStore(session)
    UpdateLearnerSkillSummary(store).record_attempt(
        learner_id=LEARNER, skill_id=FINE, correct=True, supported=False, at=AT
    )
    summary = store.get_skill_summary(learner_id=LEARNER, skill_id=SkillId(FINE))
    assert summary is not None and summary.independent_accuracy == 1.0

    manifest = type("Manifest", (), {"digest": "b" * 64, "synthetic": True})()
    approved = ModelArtifactBundle.create(
        model_name="support-policy",
        model_version="contextual-bandit-v1",
        source_commit="c5-seed",
        feature_definition_version="bandit-context-v1",
        manifest=manifest,
        seed=1,
        parameters=LinUCBPolicy().parameters(),
    )
    session.add(
        ModelVersionModel(
            id=uuid4(),
            model_name=approved.model_name,
            model_role="support_policy",
            semantic_version="contextual-bandit-v1",
            artifact_uri=f"gamification://support-policy/{approved.artifact_sha256}",
            artifact_sha256=approved.artifact_sha256,
            feature_definition_version=approved.feature_definition_version,
            training_dataset_id=approved.dataset_manifest_digest,
            metrics_json={
                "model_name": approved.model_name,
                "model_version": approved.model_version,
                "source_commit": approved.source_commit,
                "feature_definition_version": approved.feature_definition_version,
                "dataset_manifest_digest": approved.dataset_manifest_digest,
                "seed": approved.seed,
                "parameters": dict(approved.parameters),
            },
            approval_status="approved",
            approved_by="policy-owner",
            approved_at=AT,
            created_at=AT,
        )
    )
    session.flush()
    artifacts = SqlAlchemyPolicyArtifactStore(session)
    assert artifacts.active_bundle() is not None
    assert artifacts.active_bundle().artifact_sha256 == approved.artifact_sha256  # type: ignore[union-attr]
    draft = ModelArtifactBundle.create(
        model_name="support-policy",
        model_version="contextual-bandit-v1",
        source_commit="c5-policy-update",
        feature_definition_version="bandit-context-v1",
        manifest=manifest,
        seed=2,
        parameters=LinUCBPolicy().parameters(),
    )
    artifacts.register_draft(draft)
    artifacts.register_draft(draft)
    versions = session.scalars(select(ModelVersionModel)).all()
    assert len(versions) == 2
    approved_row = next(row for row in versions if row.approval_status == "approved")
    draft_row = next(row for row in versions if row.approval_status == "draft")
    assert approved_row.artifact_sha256 == approved.artifact_sha256
    assert draft_row.artifact_sha256 == draft.artifact_sha256
    assert draft_row.approved_by is None
    cursor = SqlAlchemyPolicyUpdateCursor(session)
    cursor.mark(episode_id, artifact_sha256=draft.artifact_sha256, reason=None, consumed_at=AT)
    cursor.mark(episode_id, artifact_sha256="0" * 64, reason="SHOULD_NOT_REPLACE", consumed_at=AT)
    cursors = session.scalars(select(PolicyUpdateCursorModel)).all()
    assert len(cursors) == 1
    assert cursors[0].artifact_sha256 == draft.artifact_sha256
    assert cursors[0].reason_code is None
    session.close()
