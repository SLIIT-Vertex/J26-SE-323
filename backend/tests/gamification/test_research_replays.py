"""The research views of the expert-initialised models: replays, evidence and explanations."""

import random
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.api.learning_flow_router import get_learning_flow_orchestrator
from app.gamification.application.research_dashboard.dashboard import ResearchDashboardService
from app.gamification.application.research_dashboard.explain import (
    belief_uncertain,
    explain_model1,
    explain_model2,
)
from app.gamification.demo_seed.plan import build_plan
from app.gamification.demo_seed.runner import SeedRunner
from app.gamification.infrastructure.db.game_help_bandit_store import (
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.infrastructure.db.research_dashboard_reader import (
    SqlAlchemyResearchDashboardReader,
)
from app.gamification.modeling.offline.research_accuracy_report import (
    MODEL1_SETTING_VALUES,
    replay_report,
)
from app.gamification.modeling.support_selection.bandit_sensitivity import (
    SETTING_VALUES,
    evidence,
    sensitivity,
)
from app.gamification.modeling.support_selection.game_bandit import (
    load_help_order_expert_data,
    rank_by_gain,
)
from app.gamification.modeling.support_selection.game_bandit_ledger import LedgerEntry, replay
from app.gamification.validation import simulated_cohort
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.help_bandit_helpers import approve_expert_start

LEARNER = UUID("00000000-0000-4000-8000-000000000751")
AREAS = {
    "G5-AREA-MAT-03": ["G5-MAT-PAT-DIFF-ASC-01", "G5-MAT-PAT-DIFF-DESC-01"],
    "G5-AREA-ENG-12": ["G5-ENG-FAMILY-BILINGUAL-01"],
    "G5-AREA-SIN-02": ["G5-SIN-PUNC-END-01"],
}
CONFIG = {
    "version": "replay-views-test",
    "learner_id": str(LEARNER),
    "areas": {
        "G5-AREA-MAT-03": "responds_to_round_2",
        "G5-AREA-ENG-12": "helped_but_not_independent",
        "G5-AREA-SIN-02": "needs_two_tries",
    },
}


@pytest.fixture(scope="module")
def played():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    approve_expert_start(session)
    report = SeedRunner(get_learning_flow_orchestrator(session), build_plan(CONFIG, AREAS)).run()
    assert report.failed == []
    yield session
    session.close()


def _unseeded(runs):
    """The replays leave scripted games out; read the seeded games as a child's own."""

    return [
        {**run, "state": {k: v for k, v in run["state"].items() if k != "seed_source"}}
        for run in runs
    ]


# --- The help-order bandit's sensitivity replay ---------------------------------------------


def test_the_approved_settings_reproduce_every_stored_first_help(played) -> None:
    service = ResearchDashboardService(SqlAlchemyResearchDashboardReader(played))
    help_order = service._help_order()
    rows = help_order["sensitivity"]
    assert {row["subject"] for row in rows} == {"MAT", "ENG", "SIN"}
    assert not [row for row in rows if "error" in row]
    for row in rows:
        assert row["decisions"] > 0
        if row["approved"]:
            assert row["changed_first_helps"] == 0, row
    expected = {(name, value) for name, values in SETTING_VALUES.items() for value in values}
    for subject in ("MAT", "ENG", "SIN"):
        assert {(r["setting"], r["value"]) for r in rows if r["subject"] == subject} == expected


def test_a_zero_failed_round_weight_equals_a_ledger_without_failed_rounds(played) -> None:
    store = SqlAlchemyGameHelpBanditStore(played)
    gains, families, _ = load_help_order_expert_data()
    model_version, parameters = store.approved_artifacts()["MAT"]
    ledger = store.ledger_with_snapshots(model_version)
    decisions = store.decisions(model_version)
    assert any(entry.role == "failed_round" for entry, _ in ledger)
    # The ordinary pure-Python bandit, replayed without the failed rounds, at each decision.
    changed = 0
    for decision in decisions:
        kept = [
            pair for pair in ledger[: decision.ledger_position] if pair[0].role != "failed_round"
        ]
        bandit = replay(parameters, kept)
        inputs = decision.snapshot.inputs
        cell = bandit.cells[
            (inputs["reason_family"], inputs["model1_uncertain"], inputs["learning_state"])
        ]
        gains_now = {
            support: bandit.policy.predict(decision.snapshot.context(support), [support])[support][
                0
            ]
            for support in decision.snapshot.vectors
        }
        order = rank_by_gain(
            [s for s in cell["order"] if s in gains_now],
            gains_now,
            float(bandit.settings["tie_tolerance"]),
        )
        changed += int(order[0] != decision.first_help)
    rows = sensitivity(parameters, gains, families, ledger, decisions)
    zero = next(r for r in rows if r["setting"] == "failed_round_weight" and r["value"] == 0.0)
    assert zero["changed_first_helps"] == changed


def test_the_replay_refuses_expert_data_that_no_longer_builds_the_artifact(played) -> None:
    store = SqlAlchemyGameHelpBanditStore(played)
    gains, families, _ = load_help_order_expert_data()
    model_version, parameters = store.approved_artifacts()["ENG"]
    # The expert gains changed after approval: one help's gain in one English cell.
    cells = [dict(cell) for cell in gains["cells"]]
    cell = next(cell for cell in cells if cell["subject"] == "ENG")
    help_type = next(iter(cell["expected_gain"]))
    cell["expected_gain"] = {**cell["expected_gain"], help_type: 0.99}
    changed = {**gains, "cells": cells}
    with pytest.raises(ValueError, match="no longer builds"):
        sensitivity(
            parameters,
            changed,
            families,
            store.ledger_with_snapshots(model_version),
            store.decisions(model_version),
        )


def test_evidence_counts_each_kind_of_observation() -> None:
    entries = [
        LedgerEntry("e1", "visual_guidance", "failed_round", 0.0, 0.5, "v"),
        LedgerEntry("e1", "step_by_step_guidance", "credited", 1.0, 1.0, "v"),
        LedgerEntry("e2", "step_by_step_guidance", "credited", 0.0, 1.0, "v"),
        LedgerEntry("e3", "visual_guidance", "failed_round", 0.0, 0.5, "v"),
    ]
    assert evidence(entries) == [
        {
            "help": "step_by_step_guidance",
            "credited_success": 1,
            "credited_zero": 1,
            "failed_rounds": 0,
            "failed_round_weight": 0.0,
        },
        {
            "help": "visual_guidance",
            "credited_success": 0,
            "credited_zero": 0,
            "failed_rounds": 2,
            "failed_round_weight": 1.0,
        },
    ]


# --- Model 1 sensitivity replay ---------------------------------------------------------------


def test_the_approved_model1_settings_reproduce_every_stored_reading(played) -> None:
    runs = _unseeded(SqlAlchemyResearchDashboardReader(played).runs(LEARNER))
    rows = replay_report(runs, LEARNER)["model1_settings"]
    expected = {(name, value) for name, values in MODEL1_SETTING_VALUES.items() for value in values}
    assert {(row["setting"], row["value"]) for row in rows} == expected
    for row in rows:
        assert row["readings"] > 0 and row["bayesian_readings"] == row["readings"]
        if row["approved"]:
            assert row["reproduced"] == row["bayesian_readings"]
            assert row["changed_reason"] == row["changed_uncertain"] == 0


# --- Dashboard explanations and checks ------------------------------------------------------


def test_uncertain_reads_the_recorded_causes_before_the_flags() -> None:
    assert belief_uncertain({"uncertain_because": ["unknown_top"], "low_confidence": False})
    assert not belief_uncertain({"uncertain_because": [], "abstained": True})
    assert belief_uncertain({"abstained": True})
    assert not belief_uncertain({"low_confidence": False, "fallback_used": False})


def test_the_trace_shows_the_bayesian_factors_predicted_gains_and_ledger_rows(played) -> None:
    reader = SqlAlchemyResearchDashboardReader(played)
    service = ResearchDashboardService(reader)
    run = next(
        run
        for run in reader.runs(LEARNER)
        if (run["state"].get("model2") or {}).get("support_selection_mode") == "bandit_greedy"
        and (run["state"].get("model2") or {}).get("bandit_update") == "applied"
    )
    trace = service.trace(UUID(str(run["state"]["episode_id"])))
    model1 = trace["model1"]
    assert {factor["name"] for factor in model1["factors"]} >= {"The mistake in the answer"}
    assert model1["evidence_band"]
    model2 = trace["model2"]
    assert [row["help"] for row in model2["predicted_gain"]] == model2["order"]
    assert model2["ledger"] and {row["role"] for row in model2["ledger"]} <= {
        "credited",
        "failed_round",
    }
    assert all(row["role_label"] for row in model2["ledger"])
    assert explain_model2({"model2": {}}) is None
    assert explain_model1(None) is None


def test_the_accuracy_report_measures_the_models_that_run(played) -> None:
    report = ResearchDashboardService(SqlAlchemyResearchDashboardReader(played)).accuracy(LEARNER)
    model1, model2, _ = report["models"]
    assert not {m["key"] for m in model1["metrics"]} & {"reason-help", "other-help"}
    assert {s["replay"] for s in model1["settings"] if s["replay"]} == set(MODEL1_SETTING_VALUES)
    assert {m["key"] for m in model2["metrics"]} >= {"prediction-error", "prediction-bias"}
    assert {s["replay"] for s in model2["settings"] if s["replay"]} == set(SETTING_VALUES)
    assert {row["subject"] for row in model2["evidence"]} == {"MAT", "ENG", "SIN"}
    assert all(row["approved"] and row["observations"] > 0 for row in model2["evidence"])
    offline = report["offline"]
    assert offline["help_order_settings"] and "model1_settings" in offline


# --- Simulators --------------------------------------------------------------------------------


def test_simulators_no_longer_send_an_evidence_quality(played) -> None:
    flow = get_learning_flow_orchestrator(played)._area_flows["G5-AREA-MAT-03"]
    rng = random.Random(1)
    assert "evidence_quality" not in simulated_cohort._summary(flow, rng)
    assert "evidence_quality" not in SeedRunner._summary(flow, rng)


def test_an_approval_refreshes_the_cached_accuracy_report() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    service = ResearchDashboardService(SqlAlchemyResearchDashboardReader(session))

    def approved():
        evidence_rows = service.accuracy(LEARNER)["models"][1]["evidence"]
        return {row["subject"]: row["approved"] for row in evidence_rows}

    assert approved() == {"MAT": False, "ENG": False, "SIN": False}
    approve_expert_start(session, "MAT")
    # No game changed, yet the report follows the approval.
    assert approved() == {"MAT": True, "ENG": False, "SIN": False}
    session.close()
