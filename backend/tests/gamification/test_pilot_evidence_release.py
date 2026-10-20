"""When a scored answer may reach a model, and the difficulty it carries.

A scored answer is released (`model_ingestion_eligible`) only in the `pilot` environment, and only for
a learner whose research consent is on record. Every answer carries easy, medium or hard.
"""

import importlib
import inspect
import pkgutil
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.gamification.application as application_package
from app.gamification.application.consent_gate import RESEARCH_CONSENT_PURPOSE
from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
    LocalProbeGateway,
    RecordingEvidencePublisher,
)
from app.gamification.application.number_world_flow import evidence_difficulty
from app.gamification.application.records import ConsentDecision
from app.gamification.content.division_adventure import correct_response
from app.gamification.infrastructure.db.consent_store import (
    CONSENT_CONTRACT,
    SqlAlchemyConsentStore,
)
from app.gamification.infrastructure.db.learning_flow_store import SqlAlchemyLearningFlowStore
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

LEARNER = UUID("00000000-0000-4000-8000-000000000771")
AREA = "G5-AREA-MAT-08"  # division
SKILL = "G5-MAT-DIV-WRITTEN-01"
SUMMARY = {
    "move_count": 8, "correction_count": 0, "first_action_ms": 100, "active_time_ms": 700,
    "attempt_count": 1, "working_cell_count": 10, "bring_down_count": 1,
}


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(UTC)
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si", created_at=now, updated_at=now))
        db.commit()
        yield db


def research_consent(db: Session, *, granted: bool = True, expires_at: datetime | None = None) -> None:
    SqlAlchemyConsentStore(db).record(
        ConsentDecision(
            learner_id=LEARNER, purpose=RESEARCH_CONSENT_PURPOSE, granted=granted,
            consent_version="test-v1", decided_at=datetime.now(UTC), expires_at=expires_at,
            contract_version=CONSENT_CONTRACT,
        )
    )


def play_division(
    db: Session, environment: str, *, allow_draft: bool = True, publisher: object | None = None
) -> list[dict[str, object]]:
    """One whole episode of the game's real division flow; returns the answers a recorder saw.

    Pass the game's real outbox publisher to write the answers into the database instead.
    """
    recorder = RecordingEvidencePublisher()
    publisher = publisher or recorder
    flow = LearningFlowOrchestrator(
        SqlAlchemyLearningFlowStore(db),
        probe_gateway=LocalProbeGateway(),
        evidence_publisher=publisher,
        camera_consent=SqlAlchemyConsentStore(db),
    )
    opened = flow.open_episode(
        learner_id=LEARNER, session_id=uuid4(), grade=5, medium="si", condition="proposed",
        environment=environment, allow_draft=allow_draft, area_id=AREA, atomic_skill_id=SKILL,
        idempotency_key=f"open-{uuid4()}",
    )
    episode = UUID(opened["episode_id"])

    def answer(role: str) -> dict[str, object]:
        item = next(row for row in flow.reconstruct(episode)["state"]["presentations"] if row["role"] == role)
        response = correct_response(item["game_data"])
        response.update(
            presentation_id=item["presentation_id"], item_revision_id=item["revision_id"],
            interaction_version="constructed-response-v1",
        )
        return response

    before = answer("unsupported_before")
    before["working_steps"] = [{**step} for step in before["working_steps"]]
    before["working_steps"][0]["quotient_digit"] = (before["working_steps"][0]["quotient_digit"] + 1) % 10
    supported = flow.submit_before(
        episode, option_id=None, constructed_response=before, response_time_ms=800,
        interaction_summary=SUMMARY, idempotency_key=f"b-{uuid4()}",
    )
    manifest = supported["support"]["game_manifest"]
    flow.complete_support(
        episode, duration_ms=1200, steps_viewed=3, manifest_revision_id=manifest["revision_id"],
        grouped_count=0, group_sizes=(),
        interaction_summary={
            "completed": True, "renderer_id": manifest["renderer_id"],
            "parallel_example_id": manifest["parallel_example_id"], "support_actions": 3,
        },
        idempotency_key=f"c-{uuid4()}",
    )
    flow.withdraw_support(
        episode, request_id=uuid4(), support_revision_id=supported["support"]["revision_id"],
        manifest_revision_id=manifest["revision_id"], all_support_removed=True,
        answer_revealing_state_cleared=True, input_handlers_cleared=True, idempotency_key=f"w-{uuid4()}",
    )
    flow.present_after(episode, idempotency_key=f"p-{uuid4()}")
    flow.submit_after(
        episode, option_id=None, constructed_response=answer("unsupported_after"),
        response_time_ms=750, idempotency_key=f"a-{uuid4()}",
    )
    return recorder.records


# ---- who may release an answer to a model ---------------------------------------------------------------


@pytest.mark.parametrize("environment", ["development", "test"])
def test_development_and_test_answers_are_never_released_even_with_consent(session, environment) -> None:
    research_consent(session)

    records = play_division(session, environment)

    assert len(records) == 2
    assert all(record["model_ingestion_eligible"] is False for record in records)


def test_a_pilot_answer_without_research_consent_is_not_released(session) -> None:
    records = play_division(session, "pilot")

    assert len(records) == 2
    assert all(record["model_ingestion_eligible"] is False for record in records)


def test_a_pilot_answer_with_research_consent_is_released(session) -> None:
    research_consent(session)

    records = play_division(session, "pilot")

    assert len(records) == 2
    assert all(record["model_ingestion_eligible"] is True for record in records)
    assert all(record["environment"] == "pilot" for record in records)


def test_withdrawn_or_expired_consent_releases_nothing(session) -> None:
    research_consent(session, granted=False)
    assert all(r["model_ingestion_eligible"] is False for r in play_division(session, "pilot"))

    research_consent(session, expires_at=datetime.now(UTC) - timedelta(days=1))
    assert all(r["model_ingestion_eligible"] is False for r in play_division(session, "pilot"))


def test_camera_consent_is_not_research_consent(session) -> None:
    SqlAlchemyConsentStore(session).record(
        ConsentDecision(
            learner_id=LEARNER, purpose="learner_state_camera", granted=True, consent_version="test-v1",
            decided_at=datetime.now(UTC), expires_at=None, contract_version=CONSENT_CONTRACT,
        )
    )

    assert all(r["model_ingestion_eligible"] is False for r in play_division(session, "pilot"))


def test_the_pilot_still_needs_the_explicit_draft_opt_in(session) -> None:
    research_consent(session)

    with pytest.raises(LearningFlowOrchestrationError):
        play_division(session, "pilot", allow_draft=False)


def test_other_environments_are_still_refused(session) -> None:
    with pytest.raises(LearningFlowOrchestrationError):
        play_division(session, "production")


# ---- the difficulty every answer carries ------------------------------------------------------------------


def test_every_published_answer_has_a_difficulty_the_model_can_use(session) -> None:
    records = play_division(session, "development")

    for record in records:
        assert record["difficulty"] in {"easy", "medium", "hard"}
        assert record["difficulty_source"] in {"declared", "default_unlabelled"}
        assert record["difficulty_mapping_version"] == "gamification-skill-level-v1"


@pytest.mark.parametrize(
    ("level", "band"),
    [("easy", "easy"), ("easy_medium", "medium"), ("easy-medium", "medium"), ("medium", "medium"),
     ("medium_hard", "medium"), ("medium-hard", "medium"), ("hard", "hard"), (" Hard ", "hard"),
     ("easy-to-hard", "medium"), ("easy_to_hard", "medium")],
)
def test_a_declared_level_becomes_one_of_the_three_bands(level, band) -> None:
    skill = type("Skill", (), {"difficulty": level})()

    assert evidence_difficulty(skill) == (band, "declared")


@pytest.mark.parametrize("skill", [object(), type("Skill", (), {"difficulty": None})(),
                                   type("Skill", (), {"difficulty": "unheard-of"})(), None])
def test_a_skill_without_a_known_level_gets_the_neutral_band_and_says_so(skill) -> None:
    assert evidence_difficulty(skill) == ("medium", "default_unlabelled")


def test_every_skill_of_every_game_flow_maps_to_a_band() -> None:
    """If a game adds a level word we do not know, it is called out here instead of reaching a model."""
    unknown: list[str] = []
    for info in pkgutil.iter_modules(application_package.__path__):
        if not info.name.endswith("_flow"):
            continue
        module = importlib.import_module(f"app.gamification.application.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__ or not hasattr(cls, "skills"):
                continue
            for skill_id, skill in cls.skills.items():
                level = getattr(skill, "difficulty", None)
                if level is not None and evidence_difficulty(skill)[1] != "declared":
                    unknown.append(f"{cls.__name__} {skill_id}: {level!r}")
    assert not unknown, unknown
