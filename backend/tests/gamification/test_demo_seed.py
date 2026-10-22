from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.demo_seed.cleanup import delete_seeded
from app.gamification.demo_seed.plan import PATTERNS, ROTATION, build_plan, load_config
from app.gamification.demo_seed.runner import SeedRunner, multi_help_areas
from app.gamification.demo_seed.verify import verify
from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

SEED_FILE = Path(__file__).resolve().parents[2] / "demo_seeds" / "shared_learner_demo_v1.yaml"
LEARNER = UUID("00000000-0000-4000-8000-000000000721")
# A small plan over two subjects that still takes every decision path.
MINI_AREAS = {
    "G5-AREA-MAT-03": ["G5-MAT-PAT-DIFF-ASC-01", "G5-MAT-PAT-DIFF-DESC-01"],
    "G5-AREA-ENG-12": ["G5-ENG-FAMILY-BILINGUAL-01"],
}
MINI_CONFIG = {
    "version": "demo-seed-test",
    "learner_id": str(LEARNER),
    "areas": {"G5-AREA-MAT-03": "responds_to_round_2", "G5-AREA-ENG-12": "exits_after_help"},
}


@pytest.fixture
def world():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    yield session, get_learning_flow_orchestrator(session)
    session.close()


def _seed(world):
    session, orchestrator = world
    plan = build_plan(MINI_CONFIG, MINI_AREAS)
    report = SeedRunner(orchestrator, plan).run()
    return session, orchestrator, plan, report


def _verify(session, orchestrator, plan):
    return {
        check.name: check
        for check in verify(
            session,
            orchestrator,
            LEARNER,
            expected_skills=[skill.skill_id for skill in plan.skills],
            seed_version=plan.version,
        )
    }


def test_seed_plays_through_the_real_models_and_every_check_passes(world):
    session, orchestrator, plan, report = _seed(world)

    assert report.failed == []
    assert report.played == plan.episode_count - len(report.pool_exhausted)
    checks = _verify(session, orchestrator, plan)
    # These summarise the whole 126-skill seed; three skills cannot reach every type and path.
    whole_seed = {
        "Every help type is delivered in some round",
        "Preferences are per skill: different skills learned different types",
        "Decision paths taken",
    }
    failing = {
        name: check.failures
        for name, check in checks.items()
        if not check.passed and name not in whole_seed
    }
    assert failing == {}
    assert checks["Decision paths taken"].checked > 0


def test_running_the_seed_again_changes_nothing(world):
    session, orchestrator, plan, first = _seed(world)
    before = {
        row.episode_id: row.state_sha256
        for row in session.scalars(select(LearningFlowEpisodeRunModel)).all()
    }

    again = SeedRunner(orchestrator, plan).run()

    assert again.played == 0
    assert again.already_seeded == first.played
    after = {
        row.episode_id: row.state_sha256
        for row in session.scalars(select(LearningFlowEpisodeRunModel)).all()
    }
    assert after == before


def _tamper(session, change) -> None:
    row = next(
        row
        for row in session.scalars(select(LearningFlowEpisodeRunModel)).all()
        if row.state_json.get("model2")
        and row.state_json.get("measurement")
        and row.state_json["condition"] == "proposed"
    )
    state = copy.deepcopy(row.state_json)
    change(state)
    row.state_json = state
    flag_modified(row, "state_json")
    session.commit()


def test_verify_catches_a_help_order_the_logic_would_not_choose(world):
    session, orchestrator, plan, _ = _seed(world)

    def reverse(state):
        state["model2"]["support_order"] = list(reversed(state["model2"]["support_order"]))

    _tamper(session, reverse)

    check = _verify(session, orchestrator, plan)[
        "Recomputing the help order from the stored inputs and the history at that moment gives "
        "the stored order, mode and reason family"
    ]
    assert check.passed is False


def test_verify_catches_a_gain_the_scores_do_not_give(world):
    session, orchestrator, plan, _ = _seed(world)

    def inflate(state):
        state["measurement"]["raw_independence_gain"] = "2"

    _tamper(session, inflate)

    check = _verify(session, orchestrator, plan)[
        "Gain = after earned/maximum − before earned/maximum, recomputed from the stored scores"
    ]
    assert check.passed is False


def test_cleanup_removes_only_the_seeded_episodes(world, tmp_path):
    session, orchestrator, plan, report = _seed(world)
    live = orchestrator.open_episode(
        learner_id=LEARNER,
        session_id=UUID("00000000-0000-4000-8000-0000000000aa"),
        grade=5,
        medium="si",
        condition="proposed",
        environment="development",
        allow_draft=True,
        area_id="G5-AREA-MAT-03",
        atomic_skill_id="G5-MAT-PAT-RATIO-2-01",
        idempotency_key="live-open",
    )

    deleted = delete_seeded(session, LEARNER, plan.version, backup_directory=tmp_path)
    import gzip
    import json

    snapshots = list(tmp_path.glob("*.json.gz"))
    assert len(snapshots) == 1
    with gzip.open(snapshots[0], "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    assert "learning_flow_episode_runs" in snapshot["tables"]

    assert deleted == report.played
    remaining = session.scalars(select(LearningFlowEpisodeRunModel)).all()
    assert [str(row.episode_id) for row in remaining] == [live["episode_id"]]


def test_the_seed_file_covers_every_multi_help_skill(world):
    _, orchestrator = world
    config = load_config(SEED_FILE)
    areas = multi_help_areas(orchestrator)

    plan = build_plan(config, areas)

    planned = {skill.skill_id for skill in plan.skills}
    assert planned == {skills[0] for skills in areas.values()}
    assert len(plan.skills) == 37
    assert plan.episode_count == 55
    assert set(ROTATION) == set(PATTERNS)
    assert {skill.pattern for skill in plan.skills} == set(PATTERNS)
