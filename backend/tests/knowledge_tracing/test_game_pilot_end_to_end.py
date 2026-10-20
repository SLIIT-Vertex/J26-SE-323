"""The game's real division flow, through its real outbox, into the knowledge model.

This is the whole connection in one test: the game plays an episode in the pilot environment for a
learner with research consent, writes to `learner_evidence_outbox`, and our reader saves the answers
as game answers under our own skill (`MAT-OPS`, the parent of the game's `MAT-DIV`). It uses the
reader's strict default: no development switch, the game's own release flag is what lets it in.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from gamification.test_pilot_evidence_release import LEARNER, play_division, research_consent
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.gamification.infrastructure.db.learning_flow_gateways import (
    SqlAlchemyLearningFlowEvidencePublisher,
)
from app.knowledge_tracing.application.attempts import AttemptService
from app.knowledge_tracing.application.game_evidence import (
    GameEvidenceIngestor,
    checked_skills,
    load_crosswalk,
    load_game_skill_map,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import SqlAlchemyAttemptRepository
from app.knowledge_tracing.infrastructure.db.game_evidence_repository import OutboxEvidenceSource
from app.knowledge_tracing.infrastructure.db.models import AttemptModel, SkillModel
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(UTC)
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.commit()
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db:
        yield db


def read_the_outbox(session: Session, *, include_development: bool = False):
    skill_map = load_game_skill_map()
    repository = SqlAlchemyAttemptRepository(session)
    return GameEvidenceIngestor(
        OutboxEvidenceSource(session),
        AttemptService(repository, SPEC),
        repository.learner_language,
        SPEC,
        checked_skills(load_crosswalk(), skill_map),
        include_development=include_development,
        sub_skills=skill_map.sub_skills,
    ).run()


def saved(session: Session) -> list[AttemptModel]:
    session.expire_all()
    return list(session.scalars(select(AttemptModel).order_by(AttemptModel.id)))


def test_a_pilot_episode_of_a_consented_learner_reaches_the_model_under_our_skill(session: Session) -> None:
    research_consent(session)
    publisher = SqlAlchemyLearningFlowEvidencePublisher(session)
    play_division(session, "pilot", publisher=publisher)
    session.commit()

    report = read_the_outbox(session)

    assert (report.scanned, report.ingested, dict(report.skipped)) == (2, 2, {})
    rows = saved(session)
    assert [(r.skill_code, r.source) for r in rows] == [("MAT-OPS", 1), ("MAT-OPS", 1)]  # her MAT-DIV, our MAT-OPS
    assert all(r.difficulty in {"easy", "medium", "hard"} and r.question_id is None for r in rows)
    assert [r.time_ms for r in rows] == [800, 750]  # the game's real response times
    assert [r.correct for r in rows] == [False, True]  # a wrong answer, then right after support


def test_reading_the_outbox_again_does_not_count_the_answers_twice(session: Session) -> None:
    research_consent(session)
    play_division(session, "pilot", publisher=SqlAlchemyLearningFlowEvidencePublisher(session))
    session.commit()

    read_the_outbox(session)
    again = read_the_outbox(session)

    assert (again.ingested, again.already_ingested) == (0, 2)
    assert len(saved(session)) == 2


@pytest.mark.parametrize("environment", ["development", "test"])
def test_development_answers_do_not_reach_the_model_in_the_default_mode(session: Session, environment: str) -> None:
    research_consent(session)
    play_division(session, environment, publisher=SqlAlchemyLearningFlowEvidencePublisher(session))
    session.commit()

    report = read_the_outbox(session)

    assert (report.ingested, dict(report.skipped)) == (0, {"not_eligible": 2})
    assert saved(session) == []


def test_a_pilot_learner_without_consent_does_not_reach_the_model(session: Session) -> None:
    play_division(session, "pilot", publisher=SqlAlchemyLearningFlowEvidencePublisher(session))
    session.commit()

    report = read_the_outbox(session)

    assert (report.ingested, dict(report.skipped)) == (0, {"not_eligible": 2})


def test_the_trial_switch_now_reads_development_answers_into_a_local_database(session: Session) -> None:
    play_division(session, "development", publisher=SqlAlchemyLearningFlowEvidencePublisher(session))
    session.commit()

    report = read_the_outbox(session, include_development=True)

    assert (report.ingested, dict(report.skipped)) == (2, {})
    assert {r.skill_code for r in saved(session)} == {"MAT-OPS"}

