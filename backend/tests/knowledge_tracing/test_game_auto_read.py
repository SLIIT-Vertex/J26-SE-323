"""The game's answers reach the model by themselves when GAME_EVIDENCE_AUTO_READ is on.

Plays the game's real division flow, writes through its real outbox, then asks the real mastery
endpoint. Nothing here runs `scripts.ingest_game_evidence`.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from gamification.test_pilot_evidence_release import LEARNER, play_division, research_consent
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.gamification.infrastructure.db.learning_flow_gateways import (
    SqlAlchemyLearningFlowEvidencePublisher,
)
from app.knowledge_tracing.api import game_sync, mastery_router, papers_router
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.models import SkillModel
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()
OTHER = UUID("00000000-0000-4000-8000-000000000772")


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(UTC)
        for learner in (LEARNER, OTHER):
            db.add(LearnerModel(id=learner, grade=5, preferred_language="si", created_at=now, updated_at=now))
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.commit()
    return engine


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    game_sync._last_read.clear()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    game_sync._last_read.clear()


@pytest.fixture
def switches(monkeypatch: pytest.MonkeyPatch):
    """Turn the two settings on or off for the code under test."""

    def set_(*, auto: bool, development: bool = False) -> None:
        settings = get_settings().model_copy(
            update={"game_evidence_auto_read": auto, "game_evidence_include_development": development}
        )
        monkeypatch.setattr(game_sync, "get_settings", lambda: settings)
        monkeypatch.setattr(game_sync, "MIN_SECONDS_BETWEEN_READS", 0.0)

    return set_


def play(engine: Engine, environment: str, episodes: int = 2) -> None:
    """Whole episodes of the game's real flow, written through its real outbox (2 answers each)."""
    with Session(engine) as db:
        if environment == "pilot":
            research_consent(db)
        for _ in range(episodes):
            play_division(db, environment, publisher=SqlAlchemyLearningFlowEvidencePublisher(db))
        db.commit()


def division_skill(client: TestClient) -> dict:
    body = client.get(f"/api/v1/learners/{LEARNER}/mastery")
    assert body.status_code == 200
    return next(skill for skill in body.json()["skills"] if skill["code"] == "MAT-OPS")


def test_it_is_off_by_default_so_nothing_is_read(client, engine, switches) -> None:
    switches(auto=False, development=True)
    play(engine, "development")

    assert division_skill(client)["attempts"] == 0


def test_with_the_trial_switch_new_game_answers_show_up_without_running_anything(client, engine, switches) -> None:
    switches(auto=True, development=True)
    assert division_skill(client)["attempts"] == 0  # a mastery snapshot now exists

    play(engine, "development")  # the child plays; 4 answers on her division skill (MAT-DIV -> our MAT-OPS)
    skill = division_skill(client)  # and asks again straight away

    assert skill["attempts"] == 4
    assert skill["mastery"] is not None  # 3 or more answers: the model now gives an estimate


def test_development_answers_stay_out_unless_the_trial_switch_is_on(client, engine, switches) -> None:
    switches(auto=True, development=False)
    play(engine, "development")

    assert division_skill(client)["attempts"] == 0


def test_a_consented_pilot_learner_needs_no_trial_switch(client, engine, switches) -> None:
    switches(auto=True, development=False)
    play(engine, "pilot")

    assert division_skill(client)["attempts"] == 4


def test_only_the_asking_learners_answers_are_read(client, engine, switches) -> None:
    switches(auto=True, development=True)
    play(engine, "development")

    with Session(engine) as db:
        assert game_sync.read_new_game_answers(db, OTHER) == 0  # nothing of theirs to read
    assert division_skill(client)["attempts"] == 4  # the first learner's answers are still there to read


def test_reading_again_does_not_count_an_answer_twice(client, engine, switches) -> None:
    switches(auto=True, development=True)
    play(engine, "development")

    assert division_skill(client)["attempts"] == 4
    assert division_skill(client)["attempts"] == 4


def test_a_failure_never_breaks_the_request(client, engine, switches, monkeypatch) -> None:
    switches(auto=True, development=True)
    play(engine, "development")

    def broken(*args, **kwargs):
        raise RuntimeError("the outbox is unreadable")

    monkeypatch.setattr(game_sync, "GameEvidenceIngestor", broken)

    assert division_skill(client)["attempts"] == 0  # still answers, with what the model already has


def test_the_outbox_is_read_at_most_once_every_few_seconds(engine) -> None:
    settings = get_settings().model_copy(
        update={"game_evidence_auto_read": True, "game_evidence_include_development": True}
    )
    game_sync._last_read.clear()
    play(engine, "development")
    moments = iter([100.0, 101.0, 104.5])

    with Session(engine) as db:
        first = game_sync.read_new_game_answers(db, LEARNER, settings=settings, clock=lambda: next(moments))
        second = game_sync.read_new_game_answers(db, LEARNER, settings=settings, clock=lambda: next(moments))
        third = game_sync.read_new_game_answers(db, LEARNER, settings=settings, clock=lambda: next(moments))

    assert (first, second, third) == (4, 0, 0)  # 1 s later: skipped; 4.5 s later: allowed, nothing new
    game_sync._last_read.clear()


def test_both_the_mastery_and_the_paper_route_read_first() -> None:
    wanted = {("GET", "/learners/{learner_id}/mastery"), ("POST", "/learners/{learner_id}/papers")}
    found = set()
    for module in (mastery_router, papers_router):
        for route in module.router.routes:
            if game_sync.sync_game_answers in [item.dependency for item in getattr(route, "dependencies", [])]:
                found |= {(method, route.path) for method in route.methods}
    assert found == wanted
