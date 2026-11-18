"""The games' help-order bandit in the database: approval, the safety lock and shared learning."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.gamification.application.game_help_order import (
    BANDIT_GREEDY,
    NO_APPROVED_POLICY,
    choose_game_help_order,
    learn_from_episode,
)
from app.gamification.infrastructure.db.game_help_bandit_store import (
    GameHelpBanditStoreError,
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.infrastructure.db.models import (
    GameHelpBanditLedgerModel,
    GameHelpBanditSnapshotModel,
    GameHelpBanditStateModel,
    LearningFlowEpisodeRunModel,
    ModelVersionModel,
)
from app.gamification.modeling.support_selection.game_bandit import (
    GameHelpBandit,
    load_game_help_bandit,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from scripts import approve_game_help_bandit
from tests.gamification.test_persistence import BACKEND_ROOT, sqlite_engine

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
CALM = {"status": "available", "state": "calm"}
GAME_TABLES = {"game_help_bandit_states", "game_help_bandit_snapshots", "game_help_bandit_ledger"}


@pytest.fixture
def engine(tmp_path: Path):
    engine = sqlite_engine(f"sqlite:///{tmp_path / 'bandit.sqlite'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def _learner(session: Session) -> UUID:
    learner = uuid4()
    session.add(LearnerModel(id=learner, grade=5, preferred_language="si"))
    session.flush()
    return learner


def _run(session: Session, learner: UUID, state: dict) -> None:
    session.add(
        LearningFlowEpisodeRunModel(
            episode_id=UUID(state["episode_id"]),
            session_id=uuid4(),
            learner_id=learner,
            skill_id="G5-MAT-SKILL",
            content_package_version="test",
            protocol_version="test",
            environment="test",
            condition=state["condition"],
            status="completed",
            revision=1,
            state_json=state,
            state_sha256="0" * 64,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()


def _episode(rounds=(), after_correct=True, *, condition="proposed", valid=True) -> dict:
    earned = "1" if after_correct else "0"
    rounds = list(rounds)
    return {
        "episode_id": str(uuid4()),
        "condition": condition,
        "validity": "valid" if valid else "invalid",
        "measurement": {
            "after_earned": earned,
            "after_maximum": "1",
            "raw_independence_gain": earned if valid else None,
        },
        "attempts": [{"role": "unsupported_before", "correct": False}],
        "support_loop": {
            "rounds": [
                {"scaffold_type": support, "outcome": outcome} for support, outcome in rounds
            ],
            "types_used": [support for support, _ in rounds],
            "stop_reason": "supported_success"
            if rounds and rounds[-1][1] == "succeeded"
            else "order_exhausted",
        },
    }


def _approve(store: SqlAlchemyGameHelpBanditStore, bandit: GameHelpBandit, by: str = "researcher"):
    draft = store.register_draft(bandit, now=NOW)
    return store.approve(
        subject=bandit.subject, artifact_sha256=draft.artifact_sha256, approved_by=by, now=NOW
    )


def _choose(store, state: dict, *, subject="MAT", history=()):
    bandit = load_game_help_bandit(subject)
    return choose_game_help_order(
        store,
        subject=subject,
        episode_id=UUID(state["episode_id"]),
        model1_label=None,
        model1_uncertain=False,
        learning_state_input=CALM,
        history=list(history),
        eligible=bandit.supports,
        renderable=bandit.supports,
        now=NOW,
    )


def _play(store, session, learner, outcomes, after_correct=True, *, history=(), **changes):
    """Open an episode, let the store choose its order, then show the helps in that order.

    ``outcomes`` are the rounds' outcomes; round n shows the n-th help of the chosen order.
    """

    opened = _episode((), after_correct, **changes)
    _run(session, learner, opened)
    choice = _choose(store, opened, history=history)
    rounds = list(zip(choice.order, outcomes, strict=False))
    state = _episode(rounds, after_correct, **changes) | {"episode_id": opened["episode_id"]}
    session.get(LearningFlowEpisodeRunModel, UUID(state["episode_id"])).state_json = state
    session.flush()
    return state, choice


# --- Safety lock ----------------------------------------------------------------------------


def test_without_an_approved_artifact_the_proposed_condition_gets_the_fixed_order(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    state, choice = _play(store, session, learner, ["succeeded"])
    assert choice.selection_mode == NO_APPROVED_POLICY
    assert choice.order == load_game_help_bandit("MAT").supports
    assert choice.as_record()["support_selection_mode"] == "no_approved_policy"
    assert store.snapshot_for(UUID(state["episode_id"])) is None
    assert learn_from_episode(store, state, now=NOW) == "no_bandit_decision"

    store.register_draft(load_game_help_bandit("MAT"), now=NOW)
    _, still_draft = _play(store, session, learner, ["succeeded"])
    assert still_draft.selection_mode == NO_APPROVED_POLICY


def test_an_approved_artifact_decides_and_keeps_its_snapshot(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    bandit = load_game_help_bandit("MAT")
    _approve(store, bandit)
    state, choice = _play(store, session, learner, ["succeeded"])
    expected = bandit.order(
        model1_label=None,
        model1_uncertain=False,
        learning_state_input=CALM,
        history=[],
        eligible=bandit.supports,
        renderable=bandit.supports,
    )
    assert choice.selection_mode == BANDIT_GREEDY
    assert choice.order == expected.order
    record = choice.as_record()
    assert record["predicted_gain"] == dict(expected.predicted_gain)
    assert record["reason_family"] == expected.reason_family
    assert record["ledger_position"] == 0
    stored = store.snapshot_for(UUID(state["episode_id"]))
    assert stored is not None and str(stored.snapshot_id) == record["snapshot_id"]
    for support, context in expected.contexts.items():
        assert stored.snapshot.context(support).values == context.values


# --- Approval -------------------------------------------------------------------------------


def test_approval_names_the_approver_and_the_exact_artifact(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    bandit = load_game_help_bandit("SIN")
    first = store.register_draft(bandit, now=NOW)
    assert store.register_draft(bandit, now=NOW) == first
    assert first.approval_status == "draft"
    with pytest.raises(GameHelpBanditStoreError, match="ARTIFACT_NOT_REGISTERED"):
        store.approve(subject="SIN", artifact_sha256="f" * 64, approved_by="me", now=NOW)
    with pytest.raises(GameHelpBanditStoreError, match="APPROVER_REQUIRED"):
        store.approve(
            subject="SIN", artifact_sha256=first.artifact_sha256, approved_by=" ", now=NOW
        )
    approved = store.approve(
        subject="SIN", artifact_sha256=first.artifact_sha256, approved_by="me", now=NOW
    )
    row = session.get(ModelVersionModel, approved.model_version_id)
    assert (row.approval_status, row.approved_by, row.model_role) == (
        "approved",
        "me",
        "support_policy",
    )
    assert row.feature_definition_version == "area-bandit-context-v1"
    assert row.metrics_json["parameters"]["game"]["failed_round_weight"] == 0.5
    assert store.approved("SIN").ledger_position == 0
    assert store.approved("MAT") is None


def test_a_changed_design_is_a_new_artifact_that_retires_the_old_one(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    old = _approve(store, load_game_help_bandit("MAT"))
    state, _ = _play(store, session, learner, ["succeeded"])
    parameters = load_game_help_bandit("MAT").parameters()
    parameters["game"]["failed_round_weight"] = 0.25
    new = _approve(store, GameHelpBandit.from_parameters(parameters))
    assert new.artifact_sha256 != old.artifact_sha256
    assert session.get(ModelVersionModel, old.model_version_id).approval_status == "retired"
    assert store.approved("MAT").model_version_id == new.model_version_id
    assert learn_from_episode(store, state, now=NOW) == "artifact_replaced"


# --- Shared learning ------------------------------------------------------------------------


def test_a_valid_proposed_episode_teaches_the_bandit_once(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    approved = _approve(store, load_game_help_bandit("MAT"))
    before = store.approved("MAT").bandit.parameters()
    state, choice = _play(
        store,
        session,
        learner,
        ["failed", "succeeded"],
    )
    assert learn_from_episode(store, state, now=NOW) == "applied"
    assert learn_from_episode(store, state, now=NOW) == "already_applied"
    rows = store.ledger(approved.model_version_id)
    assert {(e.support, e.role, e.score, e.weight) for _, e, _ in rows} == {
        (choice.order[0], "failed_round", 0.0, 0.5),
        (choice.order[1], "credited", 1.0, 1.0),
    }
    assert [position for position, _, _ in rows] == [1, 2]
    current = store.approved("MAT")
    assert current.ledger_position == 2
    assert current.bandit.parameters() != before
    assert store.replay_matches(approved.model_version_id)


def test_baseline_and_invalid_episodes_teach_nothing(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    approved = _approve(store, load_game_help_bandit("MAT"))
    baseline = _episode([("visual_guidance", "succeeded")], condition="baseline")
    _run(session, learner, baseline)
    assert learn_from_episode(store, baseline, now=NOW) == "baseline_condition"
    invalid, _ = _play(
        store,
        session,
        learner,
        ["failed", "succeeded"],
        valid=False,
    )
    assert learn_from_episode(store, invalid, now=NOW) == "not_valid"
    nothing, _ = _play(store, session, learner, ["failed"], True)
    assert learn_from_episode(store, nothing, now=NOW) == "nothing_to_credit"
    assert store.ledger(approved.model_version_id) == ()
    assert store.approved("MAT").ledger_position == 0


def test_two_children_finishing_together_both_teach_it(engine) -> None:
    with Session(engine) as setup:
        store = SqlAlchemyGameHelpBanditStore(setup)
        learner = _learner(setup)
        approved = _approve(store, load_game_help_bandit("MAT"))
        first, _ = _play(store, setup, learner, ["succeeded"])
        second, _ = _play(
            store,
            setup,
            learner,
            ["failed", "succeeded"],
        )
        setup.commit()

    with Session(engine) as one, Session(engine) as two:
        late = SqlAlchemyGameHelpBanditStore(two)
        stale = late.approved("MAT")
        assert stale.ledger_position == 0
        assert learn_from_episode(SqlAlchemyGameHelpBanditStore(one), first, now=NOW) == "applied"
        one.commit()
        assert learn_from_episode(late, second, now=NOW) == "applied"
        two.commit()

    with Session(engine) as check:
        store = SqlAlchemyGameHelpBanditStore(check)
        rows = store.ledger(approved.model_version_id)
        assert [position for position, _, _ in rows] == [1, 2, 3]
        assert {e.episode_id for _, e, _ in rows} == {first["episode_id"], second["episode_id"]}
        assert store.approved("MAT").ledger_position == 3
        assert store.replay_matches(approved.model_version_id)


def test_the_database_refuses_a_second_update_at_the_same_place(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    approved = _approve(store, load_game_help_bandit("MAT"))
    state, choice = _play(store, session, learner, ["succeeded"])
    learn_from_episode(store, state, now=NOW)
    session.commit()
    session.add(
        GameHelpBanditLedgerModel(
            model_version_id=approved.model_version_id,
            position=1,
            episode_id=UUID(state["episode_id"]),
            snapshot_id=choice.snapshot_id,
            help_type="step_by_step_guidance",
            role="credited",
            score=1.0,
            weight=1.0,
            credit_rule_version="weighted-round-credit-v1",
            applied_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# --- Replay and audit -----------------------------------------------------------------------


def test_the_state_is_always_the_artifact_plus_the_ledger(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    approved = _approve(store, load_game_help_bandit("MAT"))
    history: list[dict] = []
    for outcomes, correct in (
        (["failed", "succeeded"], True),
        (["succeeded"], False),
        (["succeeded"], True),
    ):
        state, _ = _play(store, session, learner, outcomes, correct, history=history)
        assert learn_from_episode(store, state, now=NOW) == "applied"
        history.append(state)
    assert store.replay_matches(approved.model_version_id)
    assert (
        store.rebuild(approved.model_version_id).parameters()
        == store.approved("MAT").bandit.parameters()
    )

    session.execute(
        update(GameHelpBanditLedgerModel)
        .where(GameHelpBanditLedgerModel.position == 1)
        .values(score=0.25, weight=0.75)
    )
    assert not store.replay_matches(approved.model_version_id)
    state_row = session.get(GameHelpBanditStateModel, approved.model_version_id)
    state_row.parameters_json = {**state_row.parameters_json, "ridge": 2.0}
    session.flush()
    with pytest.raises(GameHelpBanditStoreError, match="STATE_HASH_MISMATCH"):
        store.approved("MAT")


def test_a_snapshot_can_be_recomputed_from_its_inputs(session) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    learner = _learner(session)
    _approve(store, load_game_help_bandit("MAT"))
    earlier = _episode([("visual_guidance", "failed"), ("step_by_step_guidance", "succeeded")])
    _run(session, learner, earlier)
    state, choice = _play(store, session, learner, ["succeeded"], history=[earlier])
    bandit = load_game_help_bandit("MAT")
    assert store.snapshot_matches_its_inputs(choice.snapshot_id, bandit)

    run = session.get(LearningFlowEpisodeRunModel, UUID(earlier["episode_id"]))
    run.state_json = _episode([("visual_guidance", "succeeded")]) | {
        "episode_id": earlier["episode_id"]
    }
    session.flush()
    assert not store.snapshot_matches_its_inputs(choice.snapshot_id, bandit)
    snapshot = session.scalar(select(GameHelpBanditSnapshotModel))
    assert snapshot.episode_id == UUID(state["episode_id"])


# --- Migration and the approval command -----------------------------------------------------


def test_bandit_tables_migrate_up_and_down(tmp_path: Path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.sqlite'}"
    engine = sqlite_engine(database_url)
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["learners"]])
    # The stamped historical database predates display_name; current ORM metadata includes it.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE learners DROP COLUMN display_name"))
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.config import get_settings

    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "gam_20261118_01")
    upgraded = sqlite_engine(database_url)
    assert GAME_TABLES <= set(inspect(upgraded).get_table_names())
    upgraded.dispose()

    command.downgrade(config, "gam_20261022_01")
    restored = sqlite_engine(database_url)
    assert GAME_TABLES.isdisjoint(inspect(restored).get_table_names())
    assert "learning_flow_support_rounds" in inspect(restored).get_table_names()
    restored.dispose()
    get_settings.cache_clear()


def test_the_approval_command_registers_then_approves_the_exact_artifact(engine, capsys) -> None:
    def factory():
        return Session(engine)

    assert approve_game_help_bandit.main(["--subject", "ENG"], session_factory=factory) == 0
    status, sha256 = capsys.readouterr().out.split()[1:]
    assert status == "draft"
    assert (
        approve_game_help_bandit.main(
            ["--subject", "ENG", "--approve", "0" * 64, "--approved-by", "me"],
            session_factory=factory,
        )
        == 1
    )
    assert "nothing approved" in capsys.readouterr().err
    assert (
        approve_game_help_bandit.main(
            ["--subject", "ENG", "--approve", sha256, "--approved-by", "me"],
            session_factory=factory,
        )
        == 0
    )
    assert capsys.readouterr().out.split()[1:] == ["approved", sha256]
    with Session(engine) as check:
        assert SqlAlchemyGameHelpBanditStore(check).approved("ENG").artifact_sha256 == sha256
