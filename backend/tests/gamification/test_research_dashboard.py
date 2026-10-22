from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import get_settings
from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.application.research_dashboard.dashboard import ResearchDashboardService
from app.gamification.demo_seed.plan import build_plan
from app.gamification.demo_seed.runner import SeedRunner
from app.gamification.infrastructure.db.research_dashboard_reader import (
    SqlAlchemyResearchDashboardReader,
)
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import wrong_answer

LEARNER = UUID("00000000-0000-4000-8000-000000000721")
RESEARCHER = {"X-Dev-Principal": "NOT_FOR_PRODUCTION", "X-Dev-Role": "researcher"}
CONFIG = {
    "version": "demo-seed-test",
    "learner_id": str(LEARNER),
    "areas": {"G5-AREA-MAT-03": "responds_to_round_2"},
}


@pytest.fixture
def world():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    orchestrator = get_learning_flow_orchestrator(session)
    plan = build_plan(CONFIG, {"G5-AREA-MAT-03": ["G5-MAT-PAT-DIFF-ASC-01"]})
    SeedRunner(orchestrator, plan).run()
    yield (
        session,
        orchestrator,
        ResearchDashboardService(SqlAlchemyResearchDashboardReader(session)),
    )
    session.close()


def test_overview_excludes_scripted_sessions_instead_of_relabelling_them(world):
    _, _, service = world
    overview = service.overview(LEARNER)
    assert overview["counts"]["episodes"] == 0
    assert overview["skills"] == []
    assert overview["recent"] == []


def test_trace_explains_every_model_from_the_stored_record(world):
    _, _, service = world
    episode = next(
        row
        for row in service.episodes(LEARNER)["episodes"]
        if row["selection_mode"] == "learned_post_withdrawal_preference"
    )

    trace = service.trace(UUID(str(episode["episode_id"])))

    assert trace["model1"]["headline"].startswith("Most likely reason:")
    assert "earlier fair tests" in " ".join(trace["model2"]["steps"])
    assert trace["model2"]["order"][0] == episode["first_help"]
    assert "help is then removed" in trace["rounds"][0]["rule"]
    assert trace["model3"]["headline"].startswith("Independence gain 1")
    assert all(step["reached"] for step in trace["pipeline"])


def test_live_shows_the_unfinished_episode_being_played_not_seeded_ones(world):
    _, orchestrator, service = world
    assert service.live(LEARNER)["active"] is False
    assert service.live(LEARNER)["trace"] is None

    opened = orchestrator.open_episode(
        learner_id=LEARNER,
        session_id=UUID("00000000-0000-4000-8000-0000000000bb"),
        grade=5,
        medium="si",
        condition="proposed",
        environment="development",
        allow_draft=True,
        area_id="G5-AREA-MAT-03",
        atomic_skill_id="G5-MAT-PAT-RATIO-2-01",
        idempotency_key="live-open",
    )
    episode_id = UUID(str(opened["episode_id"]))
    before = orchestrator.reconstruct(episode_id)["state"]["presentations"][0]
    orchestrator.submit_before(
        episode_id,
        option_id=None,
        constructed_response=wrong_answer(orchestrator._adaptive_flow(episode_id), before),
        response_time_ms=9_000,
        interaction_summary={"move_count": 3},
        idempotency_key="live-before",
    )

    live = service.live(LEARNER)

    assert live["active"] is True
    assert live["trace"]["summary"]["episode_id"] == str(episode_id)
    assert live["trace"]["model2"] is not None


@pytest.fixture
def client(world):
    session, _, _ = world

    def override():
        yield session

    main.app.dependency_overrides[get_db] = override
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_routes_need_the_researcher_principal(client):
    url = f"/api/v1/research-dashboard/learners/{LEARNER}/overview"

    assert client.get(url).status_code == 401
    learner = {**RESEARCHER, "X-Dev-Role": "learner", "X-Learner-Id": str(LEARNER)}
    assert client.get(url, headers=learner).status_code == 403
    assert client.get(url, headers=RESEARCHER).status_code == 200


def test_routes_disappear_when_the_dashboard_is_switched_off(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_dashboard_enabled", False)

    response = client.get(
        f"/api/v1/research-dashboard/learners/{LEARNER}/overview", headers=RESEARCHER
    )

    assert response.status_code == 404


def test_model_checks_route_is_removed(client):
    response = client.get(
        f"/api/v1/research-dashboard/learners/{LEARNER}/model-checks", headers=RESEARCHER
    )
    assert response.status_code == 404


def test_profile_and_rounds_use_only_stored_human_games(world):
    session, _, service = world
    from sqlalchemy import select

    from app.gamification.infrastructure.db.learning_flow_store import digest
    from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel

    rows = session.scalars(select(LearningFlowEpisodeRunModel)).all()
    # One stored session becomes an untagged fixture for this test; other fixtures stay excluded.
    state = dict(rows[0].state_json)
    state.pop("seed_source", None)
    rows[0].state_json = state
    rows[0].state_sha256 = digest(state)
    learner = session.get(LearnerModel, LEARNER)
    learner.display_name = "Test Learner"
    session.commit()
    profile = service.profile(LEARNER)
    assert profile["name"] == "Test Learner"
    assert profile["games_played"] == 1
    assert profile["areas_played"]["MAT"]


@pytest.mark.parametrize("route", ["profile", "model-series/support", "accuracy"])
def test_v2_routes_keep_researcher_access_control(client, route):
    path = f"/api/v1/research-dashboard/learners/{LEARNER}/{route}"
    assert client.get(path).status_code in {401, 403}
    response = client.get(path, headers=RESEARCHER)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "route",
    [
        "model-catalogue",
        f"learners/{LEARNER}/rounds-by-game",
    ],
)
def test_removed_research_routes_are_gone(client, route):
    response = client.get(f"/api/v1/research-dashboard/{route}", headers=RESEARCHER)
    assert response.status_code == 404
