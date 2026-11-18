"""Model 2 in the games: the approved help-order bandit orders the proposed condition and learns.

The baseline condition keeps the subject's fixed order and teaches the bandit nothing. A subject
without an approved artifact gets the fixed order in the proposed condition too.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.demo_seed.plan import build_plan
from app.gamification.demo_seed.runner import SeedRunner
from app.gamification.infrastructure.db.game_help_bandit_store import (
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.gamification.infrastructure.db.models import (
    GameHelpBanditSnapshotModel,
    LearningFlowAuditEventModel,
    LearningFlowEpisodeRunModel,
)
from app.gamification.infrastructure.game_help_bandit_memory import InMemoryGameHelpBanditStore
from app.gamification.modeling.support_selection.baseline_order import (
    BASELINE_RECORD_VERSION,
    BaselineOrder,
    fixed_order,
)
from app.gamification.modeling.support_selection.game_bandit import loop_credit
from app.gamification.modeling.support_selection.game_bandit_ledger import DecisionSnapshot
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from tests.gamification.helpers.support_loop_helpers import wrong_answer

LEARNER = UUID("00000000-0000-4000-8000-000000000741")
AREA = "G5-AREA-MAT-03"
SKILL = "G5-MAT-PAT-DIFF-ASC-01"
ORDERS = json.loads(
    (Path(__file__).parent / "fixtures" / "rule_based_support_orders.json").read_text("utf-8")
)


def _world(help_bandit):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    now = datetime.now(UTC)
    session.add(
        LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now)
    )
    session.commit()
    store = help_bandit(session) if callable(help_bandit) else help_bandit
    orchestrator = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(session),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=RecordingEvidencePublisher(),
        help_bandit=store,
    )
    return session, orchestrator, store


def _seed(orchestrator, pattern: str = "responds_to_round_2") -> list[dict]:
    """Play the pattern on one skill; the first skill of the area also gets a baseline episode."""

    plan = build_plan(
        {"version": "help-order-test", "learner_id": str(LEARNER), "areas": {AREA: pattern}},
        {AREA: [SKILL]},
    )
    report = SeedRunner(orchestrator, plan).run()
    assert report.failed == []
    return [
        orchestrator.reconstruct(UUID(str(row["episode_id"])))["state"]
        for row in _runs(orchestrator)
    ]


def _runs(orchestrator) -> list[dict]:
    session = orchestrator._store.session
    rows = session.scalars(
        select(LearningFlowEpisodeRunModel).order_by(LearningFlowEpisodeRunModel.created_at)
    ).all()
    return [dict(row.state_json) for row in rows]


def _helped(states, condition: str) -> list[dict]:
    return [s for s in states if s["condition"] == condition and s.get("support_loop")]


def test_an_approved_bandit_orders_the_proposed_condition_and_learns_round_by_round() -> None:
    store = InMemoryGameHelpBanditStore.with_expert_start("MAT")
    _, orchestrator, _ = _world(store)
    first, second = _helped(_seed(orchestrator), "proposed")
    model_version = store.approved("MAT").model_version_id

    record = first["model2"]
    assert record["support_selection_mode"] == "bandit_greedy"
    assert set(record["predicted_gain"]) == set(record["support_order"])
    assert record["reason_family"] and record["learning_state_input"]
    assert record["ledger_position"] == 0 and record["snapshot_id"]
    assert record["artifact_sha256"] == store.approved("MAT").artifact_sha256
    assert record["bandit_update"] == "applied"

    # Help worked on round 2: the round-1 help failed while shown, the round-2 help is credited.
    rounds = [(r["scaffold_type"], r["outcome"]) for r in first["support_loop"]["rounds"]]
    # Round 2 ends the loop by a success or, for a demonstration, by being watched.
    assert rounds[0][1] == "failed" and rounds[1][1] in ("succeeded", "viewed")
    first_rows = {
        (entry.support, entry.role, entry.score, entry.weight)
        for _, entry, _ in store.ledger(model_version)
        if entry.episode_id == first["episode_id"]
    }
    assert first_rows == {
        (rounds[0][0], "failed_round", 0.0, 0.5),
        (rounds[1][0], "credited", 1.0, 1.0),
    }
    # The next episode on the skill starts from the help that led to independent success.
    assert second["model2"]["ledger_position"] == 2
    assert second["model2"]["support_order"][0] == rounds[1][0]
    assert second["model2"]["support_order"] != first["model2"]["support_order"]
    assert store.replay_matches(model_version)


def test_the_baseline_keeps_the_fixed_order_and_teaches_nothing() -> None:
    store = InMemoryGameHelpBanditStore.with_expert_start("MAT")
    _, orchestrator, _ = _world(store)
    states = _seed(orchestrator)
    (baseline,) = _helped(states, "baseline")
    model2 = baseline["model2"]
    assert model2["support_selection_mode"] == "baseline_fixed_order"
    assert model2["support_order"] == list(
        fixed_order("MAT", model2["eligible_actions"], model2["renderable_actions"])
    )
    assert "bandit_update" not in model2 and "snapshot_id" not in model2
    learned = {
        entry.episode_id for _, entry, _ in store.ledger(store.approved("MAT").model_version_id)
    }
    assert baseline["episode_id"] not in learned


def test_without_an_approved_artifact_the_proposed_condition_gets_the_fixed_order() -> None:
    store = InMemoryGameHelpBanditStore()
    _, orchestrator, _ = _world(store)
    for state in _helped(_seed(orchestrator), "proposed"):
        model2 = state["model2"]
        assert model2["support_selection_mode"] == "no_approved_policy"
        assert model2["reason_family"] is None
        assert model2["support_order"] == list(
            fixed_order("MAT", model2["eligible_actions"], model2["renderable_actions"])
        )
        assert model2["bandit_update"] == "no_bandit_decision"
        assert state["policy_update_status"] == "authorized_delayed"


class _ForgetsOneHelp(InMemoryGameHelpBanditStore):
    """A store whose snapshots lose one scored help, so a shown help was never scored."""

    def save_snapshot(self, *, episode_id, model_version_id, snapshot, now):
        kept = dict(list(snapshot.vectors.items())[:1])
        return super().save_snapshot(
            episode_id=episode_id,
            model_version_id=model_version_id,
            snapshot=DecisionSnapshot(
                snapshot.subject,
                snapshot.context_version,
                snapshot.inputs,
                kept,
                {support: snapshot.predicted_gain[support] for support in kept},
            ),
            now=now,
        )


def test_an_unscored_help_is_recorded_and_never_fails_the_episode() -> None:
    store = _ForgetsOneHelp.with_expert_start("MAT")
    session, orchestrator, _ = _world(store)
    first, _second = _helped(_seed(orchestrator), "proposed")
    assert first["status"] == "completed"
    assert first["model2"]["bandit_update"] == "not_applied_unscored_help"
    assert first["policy_update_status"] == "not_applied_unscored_help"
    reasons = {
        reason
        for row in session.scalars(
            select(LearningFlowAuditEventModel).where(
                LearningFlowAuditEventModel.episode_id == UUID(first["episode_id"])
            )
        )
        for reason in row.reason_codes_json
    }
    assert "NOT_APPLIED_UNSCORED_HELP" in reasons
    assert store.ledger(store.approved("MAT").model_version_id) == ()


def test_a_decision_snapshot_commits_and_rolls_back_with_its_episode(monkeypatch) -> None:
    def approved_store(session):
        store = SqlAlchemyGameHelpBanditStore(session)
        draft = store.register_draft(
            InMemoryGameHelpBanditStore.with_expert_start("MAT").approved("MAT").bandit,
            now=datetime.now(UTC),
        )
        store.approve(
            subject="MAT",
            artifact_sha256=draft.artifact_sha256,
            approved_by="test",
            now=datetime.now(UTC),
        )
        session.commit()
        return store

    session, orchestrator, store = _world(approved_store)
    opened = orchestrator.open_episode(
        learner_id=LEARNER,
        session_id=uuid4(),
        grade=5,
        medium="si",
        condition="proposed",
        environment="test",
        allow_draft=True,
        area_id=AREA,
        atomic_skill_id=SKILL,
        idempotency_key="open-rollback",
    )
    episode_id = UUID(opened["episode_id"])
    flow = orchestrator._adaptive_flow(episode_id)
    before = orchestrator.reconstruct(episode_id)["state"]["presentations"][0]
    answer = wrong_answer(flow, before)

    replace = SqlAlchemyLearningFlowStore.replace

    def refuse(self, **values):
        raise RuntimeError("the episode could not be saved")

    monkeypatch.setattr(SqlAlchemyLearningFlowStore, "replace", refuse)
    with pytest.raises(RuntimeError):
        orchestrator.submit_before(
            episode_id,
            option_id=None,
            constructed_response=answer,
            response_time_ms=1_000,
            interaction_summary={"move_count": 1},
            idempotency_key="before-refused",
        )
    assert session.scalars(select(GameHelpBanditSnapshotModel)).all() == []

    monkeypatch.setattr(SqlAlchemyLearningFlowStore, "replace", replace)
    orchestrator.submit_before(
        episode_id,
        option_id=None,
        constructed_response=answer,
        response_time_ms=1_000,
        interaction_summary={"move_count": 1},
        idempotency_key="before-saved",
    )
    stored = store.snapshot_for(episode_id)
    state = orchestrator.reconstruct(episode_id)["state"]
    assert stored is not None and str(stored.snapshot_id) == state["model2"]["snapshot_id"]


def test_the_baseline_module_reproduces_every_frozen_baseline_record() -> None:
    # The version every frozen baseline record carries.
    assert BASELINE_RECORD_VERSION == ORDERS["order_policy_version"] == "support-order-v3"
    checked = 0
    for decision in ORDERS["decisions"]:
        if decision["condition"] != "baseline":
            continue
        subject = decision["subject"]
        order = fixed_order(
            subject, ORDERS["eligible_helps"][subject]["helps"], decision["renderable"]
        )
        assert BaselineOrder(order).as_record() == decision["decision"], decision
        if subject == "SIN":
            assert list(order) == decision["delivered"]["support_order"]
        checked += 1
    assert checked > 0


def test_credited_help_matches_the_ledger_rule() -> None:
    # The round that ended the loop is the one the credit rule rewards, as today's rules read it.
    store = InMemoryGameHelpBanditStore.with_expert_start("MAT")
    _, orchestrator, _ = _world(store)
    first, _ = _helped(_seed(orchestrator), "proposed")
    winner, failed = loop_credit(first)
    credited = [
        entry.support
        for _, entry, _ in store.ledger(store.approved("MAT").model_version_id)
        if entry.episode_id == first["episode_id"] and entry.role == "credited"
    ]
    assert credited == [winner] and failed
