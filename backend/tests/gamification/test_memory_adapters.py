from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.gamification.application.records import (
    CurriculumEvidence,
    FeatureSnapshotRecord,
    LearnerStateEvidence,
)
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)
from app.gamification.infrastructure.memory import (
    FixedClock,
    InMemoryFeatureSnapshotStore,
    InMemoryCurriculumRetriever,
    StubLearnerStateGateway,
)


def test_feature_snapshot_store_is_append_only() -> None:
    record = FeatureSnapshotRecord(
        snapshot_id=FeatureSnapshotId(uuid4()),
        learner_id=uuid4(),
        skill_id=SkillId("skill-provisional-01"),
        captured_at=datetime(2026, 10, 13, tzinfo=UTC),
        protocol_version=ProtocolVersion("adaptive-episode-v1"),
        taxonomy_version=TaxonomyVersion("provisional-v1"),
        feature_definition_version="feature-v1",
        values={"mastery": 0.5},
    )
    store = InMemoryFeatureSnapshotStore()
    store.add(record)

    assert store.get(record.snapshot_id) == record
    with pytest.raises(ValueError, match="already exists"):
        store.add(record)


def test_learner_state_stub_enforces_freshness_cutoff() -> None:
    learner_id = uuid4()
    observed_at = datetime(2026, 10, 13, tzinfo=UTC)
    evidence = LearnerStateEvidence(
        learner_id=learner_id,
        support_need=0.5,
        confidence=0.8,
        reliability=0.7,
        observed_at=observed_at,
        contract_version="learner-state-v1",
    )
    gateway = StubLearnerStateGateway([evidence])

    assert (
        gateway.get_support_evidence(
            learner_id=learner_id, observed_no_earlier_than=observed_at
        )
        == evidence
    )
    assert (
        gateway.get_support_evidence(
            learner_id=learner_id,
            observed_no_earlier_than=observed_at + timedelta(seconds=1),
        )
        is None
    )


def test_curriculum_stub_returns_only_approved_matching_references() -> None:
    skill_id = SkillId("skill-provisional-01")
    approved = CurriculumEvidence(
        evidence_id="evidence-1",
        skill_id=skill_id,
        source_version="source-v1",
        content_hash="digest-1",
        approved=True,
        language="si",
    )
    retriever = InMemoryCurriculumRetriever(
        [
            approved,
            CurriculumEvidence(
                evidence_id="evidence-2",
                skill_id=skill_id,
                source_version="source-v1",
                content_hash="digest-2",
                approved=False,
                language="si",
            ),
        ]
    )

    assert retriever.find_approved(skill_id=skill_id, language="si", limit=5) == (approved,)


def test_fixed_clock_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        FixedClock(datetime(2026, 10, 13))

