from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from alembic import command
from app.gamification.application.episode_use_cases import (
    AssessStruggleCommand,
    CalculateIndependenceOutcomeCommand,
    InferMisconceptionBeliefsCommand,
    OpenAdaptiveEpisodeCommand,
    RecordSupportExposureCommand,
    RecordVerificationResponseCommand,
    ScheduleUnsupportedVerificationCommand,
    SelectSupportActionCommand,
    WithdrawSupportCommand,
    wire_episode_use_cases,
)
from app.gamification.application.struggle_trigger import StruggleEvidence
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.loader import load_pilot_content_package
from app.gamification.domain.types import (
    CatalogueVersion,
    DecisionMode,
    EpisodeId,
    EpisodePhase,
    SkillId,
)
from app.gamification.infrastructure.db.episode_store import SqlAlchemyUnitOfWork
from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    GameSessionModel,
    ItemResponseModel,
)
from app.gamification.infrastructure.db.repositories import reconstruct_episode_evidence
from app.gamification.modeling.independence_gain.calculator import RawIndependenceGainCalculator
from app.gamification.modeling.misconception_inference.probabilistic_model import (
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.support_selection.reference_policy import SafeSupportPolicy
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

from .test_persistence import BACKEND_ROOT, sqlite_engine

AT = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
LEARNER_ID = UUID("00000000-0000-4000-8000-000000000301")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000302")
EPISODE_ID = EpisodeId(UUID("00000000-0000-4000-8000-000000000303"))
SKILL = SkillId("G5-MAT-C03-L01-O01")
BASELINE_ITEM = "G5-MAT-FRC-I010"


def test_seeded_episode_reconstructs_from_baseline_to_outcome(tmp_path: Path) -> None:
    engine = sqlite_engine(f"sqlite:///{tmp_path / 'episode.sqlite'}")
    Base.metadata.create_all(engine)
    package = load_pilot_content_package(allow_draft=True)
    catalog = PilotContentCatalog(package)
    with Session(engine) as session:
        _seed_session(session)
        uow = SqlAlchemyUnitOfWork(session)
        cases = wire_episode_use_cases(
            uow=uow,
            episodes=uow.episodes,
            catalog=catalog,
            predictor=ProbabilisticMisconceptionModel(
                catalogue_version=catalog.misconception_catalogue_version(),
                error_likelihoods={"MAT-FRC-M06": {"MAT-FRC-M06": 4.0}},
                class_priors={
                    "MAT-FRC-M05": 0.2,
                    "MAT-FRC-M06": 0.5,
                    "MAT-FRC-M07": 0.2,
                    "unknown/other": 0.1,
                },
                abstain_threshold=0.99,
            ),
            selector=SafeSupportPolicy(
                catalogue_version=CatalogueVersion(catalog.support_catalogue_version()),
                reference_table=catalog.reference_policy_table(),
            ),
            calculator=RawIndependenceGainCalculator(),
            allow_draft=True,
        )
        cases.open_episode.execute(
            OpenAdaptiveEpisodeCommand(
                episode_id=EPISODE_ID,
                session_id=SESSION_ID,
                learner_id=LEARNER_ID,
                skill_id=SKILL,
                taxonomy_version="grade5-pilot-skills-v1",
                item_id=BASELINE_ITEM,
                selected_option_id="A",
                submitted_at=AT,
                device_capabilities=frozenset({"choice_quest"}),
                variation_seed=3,
                response_time_ms=4_000,
                incorrect_attempt_count=2,
                learner_requested_help=False,
            )
        )
        cases.assess_struggle.execute(
            AssessStruggleCommand(
                episode_id=EPISODE_ID,
                evidence=StruggleEvidence(
                    captured_at=AT + timedelta(seconds=1),
                    incorrect_attempt_count=2,
                    response_time_ms=4_000,
                    selected_option_is_misconception_linked=True,
                    learner_requested_help=False,
                    source_as_of={"baseline_response": AT},
                ),
                at=AT + timedelta(seconds=1),
            )
        )
        cases.infer_beliefs.execute(
            InferMisconceptionBeliefsCommand(
                episode_id=EPISODE_ID,
                at=AT + timedelta(seconds=2),
                attempt_count=2,
                recent_correctness=(False,),
                source_as_of={"baseline_response": AT},
            )
        )
        cases.select_support.execute(
            SelectSupportActionCommand(episode_id=EPISODE_ID, at=AT + timedelta(seconds=3), seed=3)
        )
        cases.record_exposure.execute(
            RecordSupportExposureCommand(
                episode_id=EPISODE_ID,
                at=AT + timedelta(seconds=4),
                duration_ms=1_000,
                step_count=1,
                supported_item_id=BASELINE_ITEM,
                supported_option_id="C",
            )
        )
        cases.withdraw_support.execute(
            WithdrawSupportCommand(episode_id=EPISODE_ID, at=AT + timedelta(seconds=5))
        )
        scheduled = cases.schedule_verification.execute(
            ScheduleUnsupportedVerificationCommand(
                episode_id=EPISODE_ID, at=AT + timedelta(seconds=6)
            )
        )
        assert scheduled.verification_pair is not None
        verification = catalog.item(str(scheduled.verification_pair.verification_item_id))
        cases.record_verification.execute(
            RecordVerificationResponseCommand(
                episode_id=EPISODE_ID,
                at=AT + timedelta(seconds=7),
                selected_option_id=verification.correct_option_id or "",
            )
        )
        cases.calculate_outcome.execute(
            CalculateIndependenceOutcomeCommand(episode_id=EPISODE_ID, at=AT + timedelta(seconds=8))
        )

        bundle = reconstruct_episode_evidence(session, EPISODE_ID)
        row = session.get(AdaptiveEpisodeModel, EPISODE_ID)
        supported = session.scalar(
            select(ItemResponseModel).where(ItemResponseModel.phase == "supported")
        )
        assert row is not None
        trigger_type = row.trigger_type
        trigger_reasons = list((row.trigger_reasons_json or {})["reasons"])
        withdrawn_at = row.support_withdrawn_at
        baseline_template = row.baseline_template
        supported_phase = None if supported is None else supported.phase
        supported_state = None if supported is None else supported.support_state

    assert bundle.episode.phase is EpisodePhase.COMPLETED
    assert bundle.baseline_response is not None
    assert bundle.baseline_response.phase == "baseline"
    assert bundle.baseline_response.support_state == "unsupported"
    assert bundle.feature_snapshot is not None
    assert bundle.feature_snapshot.purpose == "policy_context"
    assert "bandit_context" in bundle.feature_snapshot.values
    assert bundle.misconception_beliefs
    assert bundle.policy_decision is not None
    assert bundle.policy_decision.selected_action_id == "G5-MAT-FRC-SC2-STP"
    assert bundle.policy_decision.mode is DecisionMode.DETERMINISTIC_REFERENCE
    assert bundle.support_exposures[0].delivery_status == "completed"
    assert bundle.support_exposures[0].maximum_duration_ms == 90_000
    assert bundle.verification_pair is not None
    assert bundle.verification_pair.unseen_verification_item is True
    assert bundle.verification_pair.answer_overlap == 0.0
    assert bundle.verification_response is not None
    assert bundle.verification_response.phase == "verification"
    assert bundle.verification_response.support_state == "unsupported"
    assert bundle.outcome is not None
    assert bundle.outcome.validity == "valid"
    assert bundle.outcome.raw_independence_gain == 1.0
    assert trigger_type == "TWO_INCORRECT_ATTEMPTS"
    assert trigger_reasons == [
        "TWO_INCORRECT_ATTEMPTS",
        "MISCONCEPTION_LINKED_OPTION_SELECTED",
    ]
    assert withdrawn_at is not None
    assert baseline_template == "choice_quest"
    assert supported_phase == "supported"
    assert supported_state == "supported"
    engine.dispose()


def test_trigger_reason_migration_upgrades_and_downgrades(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "migration.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = sqlite_engine(database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["learners"]])
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "gam_20261013_02")
    upgraded = sqlite_engine(database_url)
    columns = {column["name"] for column in inspect(upgraded).get_columns("adaptive_episodes")}
    assert "trigger_reasons_json" not in columns
    upgraded.dispose()

    command.upgrade(config, "gam_20261014_02")
    head = sqlite_engine(database_url)
    columns = {column["name"] for column in inspect(head).get_columns("adaptive_episodes")}
    exposure_columns = {column["name"] for column in inspect(head).get_columns("support_exposures")}
    checks = " ".join(
        check["sqltext"] for check in inspect(head).get_check_constraints("support_exposures")
    )
    assert "trigger_reasons_json" in columns
    assert "baseline_template" in columns
    assert "maximum_duration_ms" in exposure_columns
    assert "completed_over_budget" in checks
    head.dispose()

    command.downgrade(config, "gam_20261013_02")
    restored = sqlite_engine(database_url)
    columns = {column["name"] for column in inspect(restored).get_columns("adaptive_episodes")}
    checks = " ".join(
        check["sqltext"] for check in inspect(restored).get_check_constraints("support_exposures")
    )
    assert "trigger_reasons_json" not in columns
    assert "completed_over_budget" not in checks
    restored.dispose()
    get_settings.cache_clear()


def test_decision_mode_migration_adds_the_authored_reference_mode(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "mode.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = sqlite_engine(database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["learners"]])
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "gam_20261014_03")
    upgraded = sqlite_engine(database_url)
    checks = " ".join(
        check["sqltext"] for check in inspect(upgraded).get_check_constraints("support_decisions")
    )
    assert "performance_triggered_fixed" in checks
    upgraded.dispose()

    command.downgrade(config, "gam_20261014_02")
    restored = sqlite_engine(database_url)
    checks = " ".join(
        check["sqltext"] for check in inspect(restored).get_check_constraints("support_decisions")
    )
    assert "performance_triggered_fixed" not in checks
    assert "deterministic_reference" in checks
    restored.dispose()
    get_settings.cache_clear()


def test_reward_loop_migration_upgrades_and_downgrades(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "reward.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = sqlite_engine(database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["learners"]])
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "gam_20261014_04")
    upgraded = sqlite_engine(database_url)
    tables = set(inspect(upgraded).get_table_names())
    assert {
        "policy_update_cursors",
        "learner_skill_summaries",
        "learner_evidence_outbox",
    } <= tables
    upgraded.dispose()

    command.downgrade(config, "gam_20261014_03")
    restored = sqlite_engine(database_url)
    restored_tables = set(inspect(restored).get_table_names())
    assert "policy_update_cursors" not in restored_tables
    assert "learner_skill_summaries" not in restored_tables
    assert "learner_evidence_outbox" not in restored_tables
    restored.dispose()
    get_settings.cache_clear()


def _seed_session(session: Session) -> None:
    session.add(
        LearnerModel(
            id=LEARNER_ID,
            grade=5,
            preferred_language="si",
            created_at=AT,
            updated_at=AT,
        )
    )
    session.flush()
    session.add(
        GameSessionModel(
            id=SESSION_ID,
            learner_id=LEARNER_ID,
            client_session_id=UUID("00000000-0000-4000-8000-000000000310"),
            idempotency_key="c3-episode-session",
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
    session.commit()
