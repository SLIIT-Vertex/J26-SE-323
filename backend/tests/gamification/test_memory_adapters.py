from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.gamification.application.records import FeatureSnapshotRecord, LearnerStateEvidence
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)
from app.gamification.infrastructure.memory import (
    FixedClock,
    InMemoryFeatureSnapshotStore,
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
    skill_id = SkillId("G5-MAT-C03-L01-O01")
    observed_at = datetime(2026, 10, 13, tzinfo=UTC)
    evidence = LearnerStateEvidence(
        learner_id=learner_id,
        skill_id=skill_id,
        universal_skill_id="MAT-FRC",
        support_need=0.5,
        confidence=0.8,
        reliability=0.7,
        observed_at=observed_at,
        contract_version="learner-state-v1",
    )
    gateway = StubLearnerStateGateway([evidence])

    assert (
        gateway.get_support_evidence(
            learner_id=learner_id,
            skill_id=skill_id,
            observed_no_earlier_than=observed_at,
        )
        == evidence
    )
    assert (
        gateway.get_support_evidence(
            learner_id=learner_id,
            skill_id=skill_id,
            observed_no_earlier_than=observed_at + timedelta(seconds=1),
        )
        is None
    )


def test_fixed_clock_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        FixedClock(datetime(2026, 10, 13))  # noqa: DTZ001 - validates rejection

