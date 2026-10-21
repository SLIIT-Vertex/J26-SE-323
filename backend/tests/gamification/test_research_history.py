import re
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.application.research_dashboard import ResearchDashboardService
from app.gamification.demo_seed.plan import build_plan
from app.gamification.demo_seed.runner import SeedRunner
from app.gamification.infrastructure.db.research_dashboard_reader import (
    SqlAlchemyResearchDashboardReader,
)
from app.gamification.validation.simulated_cohort import Assumptions, report, run_cohort
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

CHILD = UUID("00000000-0000-4000-8000-0000000000c1")


@pytest.fixture
def world():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=CHILD, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    yield session, get_learning_flow_orchestrator(session)
    session.close()


def _play(world, pattern="responds_to_round_2"):
    session, orchestrator = world
    plan = build_plan(
        {"version": "history-test", "learner_id": str(CHILD), "areas": {"G5-AREA-MAT-03": pattern}},
        {"G5-AREA-MAT-03": ["G5-MAT-PAT-RATIO-2-01"]},
    )
    SeedRunner(orchestrator, plan).run()
    # The history only reads untagged games, so these test games are untagged here.
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.gamification.infrastructure.db.learning_flow_store import digest
    from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel

    for row in session.scalars(select(LearningFlowEpisodeRunModel)).all():
        state = dict(row.state_json)
        state.pop("seed_source", None)
        row.state_json = state
        row.state_sha256 = digest(state)
        flag_modified(row, "state_json")
    session.commit()
    return ResearchDashboardService(SqlAlchemyResearchDashboardReader(session))


def test_each_model_lists_every_game_newest_first_with_what_changed(world):
    service = _play(world)

    for model in ("misconception", "support", "gain"):
        sessions = service.model_history(CHILD, model)["sessions"]
        assert len(sessions) == 3
        assert sessions[0]["played_at"] >= sessions[-1]["played_at"]
        assert all(entry["headline"] for entry in sessions)
        assert all(entry["unchanged"] or entry["changed"] for entry in sessions)

    support = service.model_history(CHILD, "support")["sessions"]
    proposed = [entry for entry in support if not entry["comparison_group"]]
    # The game where help worked on round 2 credits that help in the child's record.
    assert any(
        "alone afterwards 1 of 1 times" in line for entry in proposed for line in entry["changed"]
    )
    # The comparison group never changes the record.
    baseline = [entry for entry in support if entry["comparison_group"]]
    assert baseline and all(
        "Comparison-group games never change the record." in entry["unchanged"]
        for entry in baseline
    )
    gain = service.model_history(CHILD, "gain")["sessions"]
    assert any(entry["headline"].startswith("Gain +1") for entry in gain)
    code = re.compile(r"\b[a-z]+_[a-z_]+\b")
    for model in ("misconception", "support", "gain"):
        for entry in service.model_history(CHILD, model)["sessions"]:
            assert len(entry["changes"]) <= 2
            assert len(entry["changed_short"]) <= 2
            assert len(entry["changes"]) == len(entry["changed_short"])
            for line in entry["changed_short"]:
                assert len(line.split()) <= 10
                assert code.search(line) is None


def test_a_game_being_played_appears_straight_away(world):
    _session, orchestrator = world
    service = _play(world)
    opened = orchestrator.open_episode(
        learner_id=CHILD,
        session_id=UUID("00000000-0000-4000-8000-0000000000d1"),
        grade=5,
        medium="si",
        condition="proposed",
        environment="development",
        allow_draft=True,
        area_id="G5-AREA-MAT-03",
        atomic_skill_id="G5-MAT-PAT-RATIO-3-01",
        idempotency_key="now-open",
    )

    newest = service.model_history(CHILD, "misconception")["sessions"][0]

    assert newest["episode_id"] == opened["episode_id"]
    assert newest["in_progress"] is True
    assert newest["play_status"] == "live"
    assert newest["headline"] == "Waiting for the first answer."
    support = service.model_series(CHILD, "support")
    live_points = [point for point in support["points"] if point["episode_id"] == opened["episode_id"]]
    assert live_points and live_points[0]["outcome"] == "live"
    gain = service.model_series(CHILD, "gain")
    assert opened["episode_id"] not in {point["episode_id"] for point in gain["points"]}


def test_profile_shows_the_account_and_no_learning_state(world):
    service = _play(world)

    profile = service.profile(CHILD)

    assert profile["learner_id"] == str(CHILD)
    assert profile["account_created"]
    assert profile["areas_played"]["MAT"] == ["G5-AREA-MAT-03"]
    assert profile["areas_available"] == {"MAT": 16, "ENG": 18}
    assert not {key for key in profile if "learning_state" in key}


def test_simulated_learners_measure_each_model_against_known_answers():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    assumptions = Assumptions(learners=2, sessions_per_skill=2)

    result = run_cohort(session, get_learning_flow_orchestrator(session), assumptions)
    data = report(result, assumptions)

    assert result.problems == []
    assert data["cohort"]["sessions"] == 2 * 34 * 2
    names = [model["name"] for model in data["models"]]
    assert names == [
        "Probabilistic Misconception",
        "Contextual Support Selection",
        "Independence Gain",
    ]
    for model in data["models"]:
        assert model["headline"]
        assert "reference" in model
        for metric in model["metrics"]:
            assert metric["count"] > 0 and 0 <= metric["value"] <= 1
    # Simulated learners have their own accounts and every game is tagged.
    from sqlalchemy import select

    from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel

    tags = {
        row.state_json.get("seed_source")
        for row in session.scalars(select(LearningFlowEpisodeRunModel))
    }
    assert tags == {"validation-sim-v1"}
    session.close()


def test_model_series_matches_history_counts(world):
    service = _play(world)
    expected = {
        "misconception": {"kpis", "points", "top_reasons", "memory", "recent"},
        "support": {"kpis", "points", "worked", "drivers", "recent"},
        "gain": {"kpis", "points", "grid", "by_game", "recent"},
    }
    for model, keys in expected.items():
        history = service.model_history(CHILD, model)["sessions"]
        series = service.model_series(CHILD, model)
        assert keys <= set(series)
        moments = [point["at"] for point in series["points"]]
        assert moments == sorted(moments)
        if model == "misconception":
            analysed = sum(entry["headline"].startswith("Most likely reason") for entry in history)
            assert series["kpis"]["analysed"] == analysed
        if model == "support":
            assert series["kpis"]["sessions"] == sum(
                entry["headline"].startswith("First help") for entry in history
            )
        if model == "gain":
            assert series["kpis"]["fair_tests"] == sum(
                entry["headline"].startswith("Gain ") for entry in history
            )
            for point in series["points"]:
                assert 0 <= point["low"] <= point["running_rate"] <= point["high"] <= 1


def test_support_recent_distinguishes_missing_retest_from_wrong_answer():
    from app.gamification.application.research_history import _support_series

    now = datetime.now(UTC)
    state = {
        "episode_id": "waiting",
        "skill_id": "skill",
        "condition": "proposed",
        "model2": {"support_order": ["visual_guidance"]},
        "attempts": [],
    }
    run = {"status": "support_active", "updated_at": now, "state": state}
    assert _support_series([run], now)["recent"][0]["after"] is None
    state["attempts"] = [{"role": "unsupported_after", "correct": False}]
    assert _support_series([run], now)["recent"][0]["after"] is False


def test_help_preference_ranks_every_help_most_to_least_preferred(world):
    service = _play(world)

    rows = service.model_series(CHILD, "support")["preference"]

    assert [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
    assert len({row["help"] for row in rows}) == len(rows)
    tried = [row for row in rows if row["tried"]]
    # Tried helps come first; the one credited with an independent success leads.
    assert rows[: len(tried)] == tried
    assert tried[0]["successes"] >= 1
    assert all(row["credited"] == 0 and not row["did_not_help"] for row in rows[len(tried) :])


def test_a_damaged_episode_row_is_not_read_into_the_dashboard(world):
    session, _ = world
    service = _play(world)
    from sqlalchemy import select

    from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel

    before = len(service.model_history(CHILD, "gain")["sessions"])
    row = session.scalars(select(LearningFlowEpisodeRunModel)).first()
    row.state_sha256 = "0" * 64
    session.commit()

    assert len(service.model_history(CHILD, "gain")["sessions"]) == before - 1
    assert service._reader.run(row.episode_id) is None
