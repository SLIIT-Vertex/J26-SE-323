from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from alembic import command
from app.config import get_settings
from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.domain.types import (
    EpisodeId,
    FeatureSnapshotId,
    PolicyDecisionId,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)
from app.gamification.infrastructure.db.independence_gain_store import (
    SqlAlchemyIndependenceGainMeasurementStore,
)
from app.gamification.infrastructure.db.misconception_inference_store import SqlAlchemyModel1Store
from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    AuthoritativeAttemptV3Model,
    FeatureSnapshotModel,
    GameSessionModel,
    IndependenceMeasurementV3Model,
    IndependenceOutcomeModel,
    InteractionEventModel,
    ItemPresentationV3Model,
    ItemResponseModel,
    Model1BeliefProbabilityV4Model,
    Model1BeliefSnapshotV4Model,
    Model1FeatureSnapshotV4Model,
    Model2CandidateDecisionV5Model,
    Model2ContextSnapshotV5Model,
    Model2RewardLinkV5Model,
    Model2ScaffoldDecisionV5Model,
    ProbeReservationV3Model,
    ScaffoldExposureRecordV3Model,
    SupportCandidateModel,
    VerificationPairModel,
)
from app.gamification.infrastructure.db.repositories import (
    SqlAlchemyFeatureSnapshotStore,
    SqlAlchemyPolicyDecisionStore,
    reconstruct_episode_evidence,
)
from app.gamification.infrastructure.db.support_selection_store import SqlAlchemyModel2Store
from app.gamification.modeling.independence_gain.measurement import (
    IndependenceGainError,
    IndependenceMeasurement,
    PolicyUpdateStatus,
    ScoreTotal,
)
from app.gamification.modeling.misconception_inference.inference import (
    Model1Error,
    replay_inference,
)
from app.gamification.modeling.support_selection.selection import (
    Model2Error,
    PolicyMode,
    RewardLink,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.modeling.independence_gain.test_measurement import valid_input
from tests.gamification.modeling.misconception_inference.test_inference import (
    inference_input as model1_input,
)
from tests.gamification.modeling.misconception_inference.test_inference import (
    model as model1_model,
)
from tests.gamification.modeling.support_selection.test_selection import (
    context_input as model2_context_input,
)
from tests.gamification.modeling.support_selection.test_selection import (
    decide as model2_decide,
)

from .fixtures import (
    DECISION_ID,
    EPISODE_ID,
    LEARNER_ID,
    NOW,
    SESSION_ID,
    SKILL_CODE,
    seed_complete_synthetic_episode,
)

BACKEND_ROOT = Path(__file__).parents[2]
INDEPENDENCE_GAIN_TABLES = {
    "game_sessions",
    "item_responses",
    "adaptive_episodes",
    "interaction_events",
    "feature_snapshots",
    "model_versions",
    "misconception_inferences",
    "misconception_probabilities",
    "support_decisions",
    "support_candidates",
    "support_exposures",
    "verification_pairs",
    "independence_outcomes",
    "policy_update_cursors",
    "learner_skill_summaries",
    "learner_evidence_outbox",
    "experiments",
    "experiment_arms",
    "experiment_assignments",
    "delivery_jobs",
    "learning_reward_entries",
    "research_exports",
    "consent_eligibility_references",
}
INDEPENDENCE_GAIN_MEASUREMENT_TABLES = {
    "item_presentations_v3",
    "probe_reservations_v3",
    "scaffold_exposure_records_v3",
    "support_withdrawal_confirmations_v3",
    "authoritative_attempts_v3",
    "independence_measurements_v3",
}
MISCONCEPTION_INFERENCE_TABLES = {
    "model1_feature_snapshots_v4",
    "model1_belief_snapshots_v4",
    "model1_belief_probabilities_v4",
}
SUPPORT_SELECTION_TABLES = {
    "model2_context_snapshots_v5",
    "model2_scaffold_decisions_v5",
    "model2_candidate_decisions_v5",
    "model2_reward_links_v5",
}
LEARNING_FLOW_ORCHESTRATION_TABLES = {
    "learning_flow_episode_runs",
    "learning_flow_probe_reservations",
    "learning_flow_episode_events",
    "learning_flow_idempotency_receipts",
    "learning_flow_audit_events",
}
MODEL1_PRESENTATION_ID = uuid4()


def sqlite_engine(url: str = "sqlite://") -> Engine:
    options: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if url == "sqlite://":
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture
def engine() -> Engine:
    value = sqlite_engine()
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        Base.metadata.drop_all(value)
        value.dispose()


@pytest.fixture
def db(engine: Engine) -> Session:
    with Session(engine) as session:
        yield session


def test_all_independence_gain_tables_and_named_constraints_exist(engine: Engine) -> None:
    inspector = inspect(engine)
    assert INDEPENDENCE_GAIN_TABLES <= set(inspector.get_table_names())

    for table_name in INDEPENDENCE_GAIN_TABLES:
        checks = inspector.get_check_constraints(table_name)
        assert all(check["name"] for check in checks), table_name
        foreign_keys = inspector.get_foreign_keys(table_name)
        assert all(foreign_key["referred_table"] for foreign_key in foreign_keys), table_name


def test_important_query_indexes_exist_and_are_selected(engine: Engine) -> None:
    inspector = inspect(engine)
    assert "ix_game_sessions_learner_started" in {
        index["name"] for index in inspector.get_indexes("game_sessions")
    }
    assert "ix_interaction_events_episode_type" in {
        index["name"] for index in inspector.get_indexes("interaction_events")
    }
    assert "ix_independence_outcomes_validity_time" in {
        index["name"] for index in inspector.get_indexes("independence_outcomes")
    }

    with engine.connect() as connection:
        plan = connection.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM interaction_events "
                "WHERE episode_id = :episode_id AND event_type = :event_type"
            ),
            {"episode_id": str(uuid4()), "event_type": "support_withdrawn"},
        )
        assert "ix_interaction_events_episode_type" in " ".join(str(row) for row in plan)


def test_session_and_event_idempotency_and_ordering_constraints(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    duplicate_session = GameSessionModel(
        id=uuid4(),
        learner_id=LEARNER_ID,
        client_session_id=uuid4(),
        idempotency_key="synthetic-session-1",
        status="active",
        language="si",
        app_version="test-v1",
        device_class="test",
        started_at=NOW,
        last_event_sequence=0,
    )
    db.add(duplicate_session)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()

    first = InteractionEventModel(
        event_id=uuid4(),
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        episode_id=EPISODE_ID,
        event_type="support_withdrawn",
        event_version=1,
        sequence_no=5,
        client_occurred_at=NOW,
        server_received_at=NOW,
        client_tz_offset_min=330,
        payload={"synthetic": True},
        payload_hash="a" * 64,
        consent_scope_version="synthetic-consent-v1",
    )
    duplicate_sequence = InteractionEventModel(
        event_id=uuid4(),
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        episode_id=EPISODE_ID,
        event_type="verification_presented",
        event_version=1,
        sequence_no=5,
        client_occurred_at=NOW + timedelta(seconds=1),
        server_received_at=NOW + timedelta(seconds=1),
        client_tz_offset_min=330,
        payload={"synthetic": True},
        payload_hash="b" * 64,
        consent_scope_version="synthetic-consent-v1",
    )
    db.add_all([first, duplicate_sequence])
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "model",
    [
        ItemResponseModel(
            id=uuid4(),
            session_id=SESSION_ID,
            learner_id=LEARNER_ID,
            item_id="invalid-score",
            item_version="v1",
            skill_code=SKILL_CODE,
            skill_taxonomy_version="provisional-v1",
            attempt_no=1,
            phase="baseline",
            support_state="unsupported",
            answer_json={"synthetic": True},
            is_correct=False,
            score=Decimal("1.1000"),
            hint_count=0,
            idempotency_key="invalid-score",
            submitted_at=NOW,
        ),
        SupportCandidateModel(
            decision_id=DECISION_ID,
            action_id="ineligible-with-propensity",
            action_type="conceptual_hint",
            eligible=False,
            ineligibility_reasons_json=["NOT_APPROVED"],
            propensity=0.5,
            rank=2,
        ),
        VerificationPairModel(
            id=uuid4(),
            episode_id=EPISODE_ID,
            baseline_item_id="same-item",
            baseline_item_version="v1",
            verification_item_id="same-item",
            verification_item_version="v1",
            skill_code=SKILL_CODE,
            equivalence_version="synthetic-v1",
            difficulty_delta=0.0,
            surface_similarity=1.0,
            answer_overlap=1.0,
            review_status="draft",
        ),
        IndependenceOutcomeModel(
            id=uuid4(),
            episode_id=EPISODE_ID,
            verification_pair_id=uuid4(),
            baseline_score=Decimal("0.0000"),
            verification_score=Decimal("1.0000"),
            raw_independence_gain=Decimal("1.00000"),
            validity="valid",
            baseline_support_state="supported",
            verification_support_state="unsupported",
            formula_version="provisional-v1",
            calculated_at=NOW,
        ),
    ],
)
def test_research_integrity_constraints_reject_invalid_rows(db: Session, model: object) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    db.add(model)
    with pytest.raises(IntegrityError):
        db.flush()


def test_episode_terminal_reason_constraint(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    invalid = AdaptiveEpisodeModel(
        id=uuid4(),
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        skill_code=SKILL_CODE,
        skill_taxonomy_version="provisional-v1",
        phase="invalidated",
        trigger_type="synthetic_rule",
        episode_protocol_version="adaptive-episode-v1",
        opened_at=NOW,
        transitioned_at=NOW,
        terminal_reason=None,
        revision=1,
    )
    db.add(invalid)
    with pytest.raises(IntegrityError):
        db.flush()


def test_response_learner_must_match_owning_session(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    other_learner_id = uuid4()
    db.add(LearnerModel(id=other_learner_id, grade=5, preferred_language="si"))
    db.commit()
    db.add(
        ItemResponseModel(
            id=uuid4(),
            session_id=SESSION_ID,
            learner_id=other_learner_id,
            item_id="cross-learner-response",
            item_version="v1",
            skill_code=SKILL_CODE,
            skill_taxonomy_version="provisional-v1",
            attempt_no=1,
            phase="baseline",
            support_state="unsupported",
            answer_json={"synthetic": True},
            is_correct=False,
            score=Decimal("0.0000"),
            hint_count=0,
            idempotency_key="cross-learner-response",
            submitted_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_feature_snapshot_adapter_is_append_only_and_rollback_safe(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    snapshot_id = FeatureSnapshotId(uuid4())
    snapshot = FeatureSnapshotRecord(
        snapshot_id=snapshot_id,
        learner_id=LEARNER_ID,
        skill_id=SkillId(SKILL_CODE),
        captured_at=datetime(2026, 10, 13, 10, 0, tzinfo=UTC),
        protocol_version=ProtocolVersion("adaptive-episode-v1"),
        taxonomy_version=TaxonomyVersion("provisional-v1"),
        feature_definition_version="feature-v1",
        values={"mastery": 0.5},
        missingness={"learner_state": True},
        source_as_of={"mastery": "2026-10-13T09:59:00Z"},
    )
    store = SqlAlchemyFeatureSnapshotStore(db)
    store.add(snapshot)
    assert store.get(snapshot_id) == snapshot

    with pytest.raises(IntegrityError):
        store.add(snapshot)
    db.rollback()

    assert db.get(FeatureSnapshotModel, snapshot_id) is None


def test_policy_store_and_episode_reconstruction_use_frozen_evidence(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()

    decision = SqlAlchemyPolicyDecisionStore(db).get(PolicyDecisionId(DECISION_ID))
    bundle = reconstruct_episode_evidence(db, EpisodeId(EPISODE_ID))

    assert decision is not None
    assert decision.selected_action_id == "synthetic-hint"
    assert [candidate.propensity for candidate in decision.candidates] == [1.0]
    assert bundle.episode.phase.value == "completed"
    assert bundle.baseline_response is not None
    assert bundle.baseline_response.support_state == "unsupported"
    assert bundle.verification_response is not None
    assert bundle.verification_response.support_state == "unsupported"
    assert [belief.misconception_code for belief in bundle.misconception_beliefs] == [
        "synthetic-m1",
        "unknown",
    ]
    assert bundle.feature_snapshot is not None
    assert bundle.feature_snapshot.source_as_of["mastery"] == "2026-10-13T09:00:30Z"
    assert bundle.policy_decision == decision
    assert bundle.support_exposures[0].delivery_status == "completed"
    assert bundle.verification_pair is not None
    assert bundle.verification_pair.review_status == "approved"
    assert bundle.outcome is not None
    assert bundle.outcome.raw_independence_gain == 1.0


def test_measurement_store_is_idempotent_and_transaction_rollback_safe(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    authoritative = valid_input()
    authoritative = replace(
        authoritative,
        episode_id=EPISODE_ID,
        decision_id=DECISION_ID,
        presentations=tuple(
            replace(row, episode_id=EPISODE_ID, learner_id=LEARNER_ID)
            for row in authoritative.presentations
        ),
        reservations=tuple(
            replace(row, episode_id=EPISODE_ID, learner_id=LEARNER_ID)
            for row in authoritative.reservations
        ),
        scaffold_exposures=tuple(
            replace(row, episode_id=EPISODE_ID) for row in authoritative.scaffold_exposures
        ),
        withdrawal=replace(authoritative.withdrawal, episode_id=EPISODE_ID),
    )
    before_id = uuid4()
    after_id = uuid4()
    measurement = IndependenceMeasurement(
        measurement_id=uuid4(),
        episode_id=EPISODE_ID,
        decision_id=DECISION_ID,
        before=ScoreTotal((before_id,), Decimal("0.5"), Decimal(1)),
        after=ScoreTotal((after_id,), Decimal(1), Decimal(1)),
        raw_independence_gain=Decimal("0.5"),
        percentage_point_value=Decimal(50),
        formula_version="raw-independence-gain-v1",
        scoring_versions=("scoring-v1",),
        rubric_versions=("rubric-v1",),
        equivalence_version="equivalence-v1",
        valid=True,
        exclusion_reasons=(),
        policy_update_status=PolicyUpdateStatus.AUTHORIZED_DELAYED,
        measurement_version="independence-measurement-v1",
        calculated_at=NOW,
    )
    store = SqlAlchemyIndependenceGainMeasurementStore(db)
    store.add_authoritative_input(authoritative)
    store.add_authoritative_input(authoritative)
    assert db.query(ItemPresentationV3Model).count() == len(authoritative.presentations)
    assert db.query(AuthoritativeAttemptV3Model).count() == len(authoritative.attempts)
    assert db.query(ProbeReservationV3Model).count() == len(authoritative.reservations)
    assert db.query(ScaffoldExposureRecordV3Model).count() == 1
    assert store.add(measurement).raw_independence_gain == Decimal("0.5")
    assert store.add(measurement).id == measurement.measurement_id
    with pytest.raises(IndependenceGainError, match="IDEMPOTENCY_CONFLICT"):
        store.add(replace(measurement, raw_independence_gain=Decimal("0.4")))
    db.rollback()
    assert db.get(IndependenceMeasurementV3Model, measurement.measurement_id) is None


def test_inference_store_reconstructs_exactly_and_rejects_conflicting_retry(
    db: Session,
) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    feature, belief = replay_inference(
        replace(
            model1_input(),
            learner_id=LEARNER_ID,
            episode_id=EPISODE_ID,
            evidence=tuple(
                replace(row, episode_id=EPISODE_ID, presentation_id=MODEL1_PRESENTATION_ID)
                for row in model1_input().evidence
            ),
            presentation_id=MODEL1_PRESENTATION_ID,
        ),
        model1_model(),
    )
    store = SqlAlchemyModel1Store(db)
    store.add(feature, belief)
    store.add(feature, belief)
    assert db.query(Model1FeatureSnapshotV4Model).count() == 1
    assert db.query(Model1BeliefSnapshotV4Model).count() == 1
    assert db.query(Model1BeliefProbabilityV4Model).count() == 3
    assert store.reconstruct(belief.belief_snapshot_id) == (feature, belief)
    with pytest.raises(Model1Error, match="BELIEF_SNAPSHOT_IDEMPOTENCY_CONFLICT"):
        store.add(feature, replace(belief, confidence=belief.confidence / 2))
    db.rollback()
    assert db.get(Model1BeliefSnapshotV4Model, belief.belief_snapshot_id) is None


def test_selection_store_reconstructs_complete_decision_and_reward_atomically(
    db: Session,
) -> None:
    seed_complete_synthetic_episode(db)
    feature, belief = replay_inference(
        replace(
            model1_input(),
            learner_id=LEARNER_ID,
            episode_id=EPISODE_ID,
            presentation_id=MODEL1_PRESENTATION_ID,
            evidence=(),
            recent_same_skill_errors=(),
            recent_error_evidence_ids=(),
            recent_errors_as_of=None,
        ),
        model1_model(),
    )
    SqlAlchemyModel1Store(db).add(feature, belief)
    source = model2_context_input()
    current = replace(source.current_unsupported, episode_id=EPISODE_ID)
    data = replace(
        source,
        learner_id=LEARNER_ID,
        episode_id=EPISODE_ID,
        presentation_id=MODEL1_PRESENTATION_ID,
        current_unsupported=current,
        recent_unsupported=tuple(
            replace(item, episode_id=EPISODE_ID) for item in source.recent_unsupported
        ),
        belief=belief,
    )
    context, decision = model2_decide(mode=PolicyMode.PROPOSED_OFFLINE, data=data)
    assert context is not None
    decision = replace(decision, decision_id=DECISION_ID)
    store = SqlAlchemyModel2Store(db)
    store.add_decision(context, decision)
    store.add_decision(context, decision)
    assert db.query(Model2ContextSnapshotV5Model).count() == 1
    assert db.query(Model2ScaffoldDecisionV5Model).count() == 1
    assert db.query(Model2CandidateDecisionV5Model).count() == 3
    assert store.reconstruct(DECISION_ID) == (context, decision)

    authoritative = valid_input()
    authoritative = replace(
        authoritative,
        episode_id=EPISODE_ID,
        decision_id=DECISION_ID,
        presentations=tuple(
            replace(item, episode_id=EPISODE_ID, learner_id=LEARNER_ID)
            for item in authoritative.presentations
        ),
        reservations=tuple(
            replace(item, episode_id=EPISODE_ID, learner_id=LEARNER_ID)
            for item in authoritative.reservations
        ),
        scaffold_exposures=tuple(
            replace(item, episode_id=EPISODE_ID) for item in authoritative.scaffold_exposures
        ),
        withdrawal=replace(authoritative.withdrawal, episode_id=EPISODE_ID),
    )
    result = IndependenceMeasurement(
        measurement_id=uuid4(),
        episode_id=EPISODE_ID,
        decision_id=DECISION_ID,
        before=ScoreTotal((uuid4(),), Decimal(0), Decimal(1)),
        after=ScoreTotal((uuid4(),), Decimal("0.5"), Decimal(1)),
        raw_independence_gain=Decimal("0.5"),
        percentage_point_value=Decimal(50),
        formula_version="raw-independence-gain-v1",
        scoring_versions=("scoring-v1",),
        rubric_versions=("rubric-v1",),
        equivalence_version="equivalence-v1",
        valid=True,
        exclusion_reasons=(),
        policy_update_status=PolicyUpdateStatus.AUTHORIZED_DELAYED,
        measurement_version="independence-measurement-v1",
        calculated_at=NOW,
    )
    measurement_store = SqlAlchemyIndependenceGainMeasurementStore(db)
    measurement_store.add_authoritative_input(authoritative)
    measurement_store.add(result)
    link = RewardLink(
        reward_link_id=uuid4(),
        decision_id=DECISION_ID,
        measurement_id=result.measurement_id,
        raw_independence_gain=Decimal("0.5"),
        formula_version="raw-independence-gain-v1",
        link_version="model2-raw-ig-reward-link-v1",
        linked_at=NOW,
    )
    assert store.add_reward_link(link) == link
    assert store.add_reward_link(link) == link
    assert db.query(Model2RewardLinkV5Model).count() == 1
    with pytest.raises(Model2Error, match="REWARD_LINK_IDEMPOTENCY_CONFLICT"):
        store.add_reward_link(replace(link, raw_independence_gain=Decimal("0.4")))
    with pytest.raises(Model2Error, match="REWARD_LINK_IDEMPOTENCY_CONFLICT"):
        store.add_reward_link(replace(link, reward_link_id=uuid4()))
    db.rollback()
    assert db.get(Model2ScaffoldDecisionV5Model, DECISION_ID) is None


def test_independence_gain_migration_upgrades_shared_learner_head_downgrades_and_reupgrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "migration-cycle.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = sqlite_engine(database_url)
    previous_table_names = ("learners",)
    Base.metadata.create_all(
        engine, tables=[Base.metadata.tables[name] for name in previous_table_names]
    )
    # The stamped historical database predates display_name; current ORM metadata includes it.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE learners DROP COLUMN display_name"))
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "gamification@head")
    migrated_engine = sqlite_engine(database_url)
    assert INDEPENDENCE_GAIN_TABLES <= set(inspect(migrated_engine).get_table_names())
    assert INDEPENDENCE_GAIN_MEASUREMENT_TABLES <= set(inspect(migrated_engine).get_table_names())
    assert MISCONCEPTION_INFERENCE_TABLES <= set(inspect(migrated_engine).get_table_names())
    assert SUPPORT_SELECTION_TABLES <= set(inspect(migrated_engine).get_table_names())
    assert LEARNING_FLOW_ORCHESTRATION_TABLES <= set(inspect(migrated_engine).get_table_names())
    migrated_engine.dispose()

    command.downgrade(config, "20261007_01")
    downgraded_engine = sqlite_engine(database_url)
    assert INDEPENDENCE_GAIN_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    assert INDEPENDENCE_GAIN_MEASUREMENT_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    assert MISCONCEPTION_INFERENCE_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    assert SUPPORT_SELECTION_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
    assert LEARNING_FLOW_ORCHESTRATION_TABLES.isdisjoint(
        inspect(downgraded_engine).get_table_names()
    )
    downgraded_engine.dispose()

    command.upgrade(config, "gamification@head")
    reupgraded_engine = sqlite_engine(database_url)
    assert INDEPENDENCE_GAIN_TABLES <= set(inspect(reupgraded_engine).get_table_names())
    assert INDEPENDENCE_GAIN_MEASUREMENT_TABLES <= set(inspect(reupgraded_engine).get_table_names())
    assert MISCONCEPTION_INFERENCE_TABLES <= set(inspect(reupgraded_engine).get_table_names())
    assert SUPPORT_SELECTION_TABLES <= set(inspect(reupgraded_engine).get_table_names())
    assert LEARNING_FLOW_ORCHESTRATION_TABLES <= set(inspect(reupgraded_engine).get_table_names())
    reupgraded_engine.dispose()
    get_settings.cache_clear()


def test_gamification_branch_label_resolves_to_an_independent_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    (gamification_head,) = script.get_revisions("gamification@head")
    assert gamification_head.revision == "gam_20261021_03"
    assert gamification_head.down_revision == "gam_20261021_02"
    assert gamification_head.revision in script.get_heads()
    for head in set(script.get_heads()) - {gamification_head.revision}:
        ancestors = {revision.revision for revision in script.iterate_revisions(head, "base")}
        assert gamification_head.revision not in ancestors


def test_indexed_history_query_returns_expected_session(db: Session) -> None:
    seed_complete_synthetic_episode(db)
    db.commit()
    rows = db.scalars(
        select(GameSessionModel)
        .where(GameSessionModel.learner_id == LEARNER_ID)
        .order_by(GameSessionModel.started_at.desc())
    ).all()
    assert [row.id for row in rows] == [SESSION_ID]
