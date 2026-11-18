"""Episodes played by today's games replay exactly through the stored-decision replay tool."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.demo_seed.plan import build_plan
from app.gamification.demo_seed.runner import SeedRunner
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools" / "gamification" / "learning_flow" / "replay_stored_rule_decisions.py"
LEARNER = UUID("00000000-0000-4000-8000-000000000733")
# One game per subject, each with several patterns, so histories, preferences and the Sinhala
# cursor all take part.
AREAS = {
    "G5-AREA-MAT-03": ["G5-MAT-PAT-DIFF-ASC-01", "G5-MAT-PAT-DIFF-DESC-01"],
    "G5-AREA-ENG-12": ["G5-ENG-FAMILY-BILINGUAL-01"],
    "G5-AREA-SIN-02": ["G5-SIN-PUNC-END-01", "G5-SIN-PUNC-QUESTION-01"],
}
CONFIG = {
    "version": "replay-test",
    "learner_id": str(LEARNER),
    "areas": {
        "G5-AREA-MAT-03": "responds_to_round_2",
        "G5-AREA-ENG-12": "helped_but_not_independent",
        "G5-AREA-SIN-02": "needs_two_tries",
    },
}


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(TOOL.stem, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seeded():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    report = SeedRunner(get_learning_flow_orchestrator(session), build_plan(CONFIG, AREAS)).run()
    assert report.failed == []
    yield session
    session.close()


def test_every_seeded_decision_replays_exactly(tool, seeded) -> None:
    result = tool.replay(seeded)
    assert result["episodes_read"] > 0
    model1 = {row["outcome"] for row in result["model1"]}
    model2 = {row["outcome"] for row in result["model2"]}
    # Model 1 beliefs come from the Bayesian model and proposed help orders from the bandit, so
    # only the baseline's fixed order still replays as a rule.
    assert model1 == {"not_rule_based"}, result["model1"]
    assert model2 == {"match", "not_rule_based"}, result["model2"]
    matched = {row["subject"] for row in result["model2"] if row["outcome"] == "match"}
    assert matched == {"MAT", "ENG", "SIN"}


def test_a_changed_stored_order_is_reported(tool, seeded) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel

    row = next(
        row
        for row in seeded.scalars(select(LearningFlowEpisodeRunModel))
        if "model2" in row.state_json and row.condition == "baseline"
    )
    stored = row.state_json["model2"]
    stored["support_order"] = list(reversed(stored["support_order"]))
    stored["selected_action"] = stored["support_order"][0]
    flag_modified(row, "state_json")
    seeded.commit()
    outcomes = {r["outcome"] for r in tool.replay(seeded)["model2"]}
    assert any(outcome.startswith("differs:") for outcome in outcomes)
