"""A game answer can carry its own skill and difficulty, so the game does not need the paper bank.

The game has its own questions, so its answers cannot point at a row of the paper question bank.
They arrive with the skill (one of the 30) and the difficulty. Everything that reads attempts (the
history the model sees, the mastery, the paper planner) must count them like any other answer.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()
LEARNER = UUID("22222222-2222-2222-2222-222222222222")
FRACTIONS, PATTERNS = "MAT-FRC", "APT-PAT"


@pytest.fixture
def engine() -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si"))
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.flush()
        db.add(QuestionModel(id="1.1", skill_code=PATTERNS, difficulty="easy"))
        db.flush()
        db.add(
            QuestionVariantModel(
                question_id="1.1",
                language="si",
                image_key="questions/1.1-si.png",
                image_width_px=100,
                image_height_px=100,
                answer_key_raw="1",
            )
        )
        db.commit()
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db:
        yield db


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def game_body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "learner_id": str(LEARNER),
        "skill_code": FRACTIONS,
        "difficulty": "easy",
        "language": "si",
        "correct": True,
        "time_ms": 9_000,
        "hints": 0,
        "answered_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def stored(engine: Engine) -> list[AttemptModel]:
    with Session(engine) as db:
        return list(db.scalars(select(AttemptModel).order_by(AttemptModel.id)))


# ---- POST /attempts with a skill and a difficulty -----------------------------------------------


def test_a_game_answer_with_its_own_skill_is_stored_as_digital(
    client: TestClient, engine: Engine
) -> None:
    response = client.post("/api/v1/attempts", json=game_body())

    assert response.status_code == 201, response.text
    [row] = stored(engine)
    assert row.question_id is None
    assert (row.skill_code, row.difficulty) == (FRACTIONS, "easy")
    assert row.source == 1  # the server decides: this is a game answer
    assert 0.0 < row.penalty < 1.0  # computed from the time and the hints, as for a bank answer


@pytest.mark.parametrize(
    "overrides",
    [
        {"question_id": "1.1"},  # both forms
        {"skill_code": None, "difficulty": None},  # neither form
        {"difficulty": None},  # a skill without a difficulty
        {"skill_code": None},  # a difficulty without a skill
        {"difficulty": "introductory"},  # not one of easy, medium, hard
        {"skill_code": "fractions"},  # not shaped like a skill code
    ],
)
def test_an_answer_must_use_exactly_one_form(
    client: TestClient, engine: Engine, overrides: dict[str, object]
) -> None:
    body = game_body(**overrides)
    body = {key: value for key, value in body.items() if value is not None}

    response = client.post("/api/v1/attempts", json=body)

    assert response.status_code == 422
    assert stored(engine) == []


def test_a_skill_that_is_not_one_of_the_30_is_refused(
    client: TestClient, engine: Engine
) -> None:
    response = client.post("/api/v1/attempts", json=game_body(skill_code="ZZZ-ZZZ"))

    assert response.status_code == 422
    assert "skill" in response.text.lower()
    assert stored(engine) == []


def test_a_question_of_the_bank_still_works_as_before(
    client: TestClient, engine: Engine
) -> None:
    body = {
        "learner_id": str(LEARNER),
        "question_id": "1.1",
        "language": "si",
        "correct": False,
        "answered_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    }

    response = client.post("/api/v1/attempts", json=body)

    assert response.status_code == 201
    [row] = stored(engine)
    assert row.question_id == "1.1" and row.skill_code is None and row.difficulty is None


def test_a_repeated_key_returns_the_same_answer_and_a_different_skill_is_a_conflict(
    client: TestClient, engine: Engine
) -> None:
    headers = {"Idempotency-Key": "game:abc"}

    first = client.post("/api/v1/attempts", json=game_body(), headers=headers)
    again = client.post("/api/v1/attempts", json=game_body(), headers=headers)
    other = client.post(
        "/api/v1/attempts", json=game_body(skill_code=PATTERNS), headers=headers
    )

    assert first.status_code == 201 and again.status_code == 200
    assert first.json() == again.json()
    assert other.status_code == 409  # the same key for a different skill is a different answer
    assert len(stored(engine)) == 1


def test_the_database_refuses_an_answer_with_no_question_and_no_skill(
    session: Session,
) -> None:
    session.add(
        AttemptModel(
            learner_id=LEARNER,
            language="si",
            source=1,
            correct=True,
            penalty=0.1,
            answered_at=datetime.now(UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


# ---- what reads the answers counts them -----------------------------------------------------------


def add_game_answers(
    session: Session, code: str, outcomes: list[bool], *, minutes_ago: int = 600
) -> None:
    for n, correct in enumerate(outcomes):
        session.add(
            AttemptModel(
                learner_id=LEARNER,
                skill_code=code,
                difficulty="easy",
                language="si",
                source=1,
                correct=correct,
                time_ms=9_000,
                hints=0,
                penalty=0.08,
                answered_at=datetime.now(UTC) - timedelta(minutes=minutes_ago - n),
            )
        )
    session.commit()


def test_the_history_the_model_reads_includes_game_answers_in_time_order(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    session.add(
        AttemptModel(
            learner_id=LEARNER, question_id="1.1", language="si", source=0, correct=True,
            penalty=0.08, answered_at=now - timedelta(minutes=30),
        )
    )
    session.commit()
    add_game_answers(session, FRACTIONS, [True, False], minutes_ago=60)

    history = SqlAlchemyAttemptRepository(session).history(LEARNER)

    assert [(h.skill_code, h.difficulty, h.source) for h in history] == [
        (FRACTIONS, "easy", 1),
        (FRACTIONS, "easy", 1),
        (PATTERNS, "easy", 0),  # the bank answer takes its skill and level from its question
    ]
    assert [h.question_id for h in history] == [None, None, "1.1"]
    assert history[0].skill_index == SPEC.skills.index(FRACTIONS)


def test_three_game_answers_are_enough_for_the_model_to_give_a_mastery(
    session: Session,
) -> None:
    add_game_answers(session, FRACTIONS, [True, True, False])
    service = MasteryService(
        SqlAlchemyMasteryRepository(session), get_knowledge_model(), SPEC
    )

    snapshot = service.recompute(LEARNER)

    by_skill = {s.code: s for s in snapshot.skills}
    assert snapshot.n_attempts == 3
    assert by_skill[FRACTIONS].attempts == 3
    assert by_skill[FRACTIONS].mastery is not None  # three answers: a number, not "unknown"
    assert by_skill[PATTERNS].mastery is None  # nothing answered here yet


def test_the_paper_planner_counts_game_answers_by_skill(session: Session) -> None:
    add_game_answers(session, FRACTIONS, [True] * 5 + [False])
    session.add(
        AttemptModel(
            learner_id=LEARNER, question_id="1.1", language="si", source=0, correct=True,
            penalty=0.08, answered_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    session.commit()

    activity = SqlAlchemyPaperInputRepository(session).skill_activity(LEARNER)

    assert (activity[FRACTIONS].digital_attempts, activity[FRACTIONS].digital_correct) == (6, 5)
    assert activity[FRACTIONS].paper_attempts == 0
    assert activity[PATTERNS].paper_attempts == 1


def test_a_game_answer_never_removes_a_bank_question_from_the_next_paper(
    session: Session,
) -> None:
    """Game answers have no bank question, so there is nothing to exclude (and no None to trip on)."""
    add_game_answers(session, FRACTIONS, [True, True, True])
    repository = SqlAlchemyPaperInputRepository(session)

    recent = repository.recently_answered(LEARNER, datetime.now(UTC) - timedelta(days=30))

    assert recent == set()


def test_a_second_learner_does_not_see_the_first_learners_game_answers(session: Session) -> None:
    other = uuid4()
    session.add(LearnerModel(id=other, grade=5, preferred_language="si"))
    session.commit()
    add_game_answers(session, FRACTIONS, [True, True, True])

    assert SqlAlchemyAttemptRepository(session).history(other) == []


# ---- the migration ------------------------------------------------------------------------------------


def test_the_migration_goes_back_only_when_no_game_answer_would_be_lost() -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    from tests.knowledge_tracing import test_schema as schema

    migrations = [schema._load_migration(path) for path in schema.MIGRATIONS]
    mine = migrations[-1]
    assert mine.revision == "20261019_01"
    engine = schema._sqlite_engine()
    LearnerModel.__table__.create(engine)
    learner = str(LEARNER).replace("-", "")
    now = "2026-10-01 09:00:00"
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for migration in migrations:
                migration.upgrade()
        connection.execute(
            text("INSERT INTO learners (id, grade, preferred_language) VALUES (:id, 5, 'si')"),
            {"id": learner},
        )
        connection.execute(
            text("INSERT INTO skills (code, sort_index, area, name_en) VALUES ('MAT-FRC', 9, 'MAT', 'F')")
        )
        connection.execute(
            text("INSERT INTO questions (id, skill_code, difficulty) VALUES ('2.1', 'MAT-FRC', 'easy')")
        )
        base = (
            "INSERT INTO attempts (learner_id, {cols}, language, source, correct, penalty, answered_at) "
            "VALUES (:l, {vals}, 'si', :s, 1, 0.1, :t)"
        )
        connection.execute(
            text(base.format(cols="question_id", vals="'2.1'")), {"l": learner, "s": 0, "t": now}
        )
        connection.execute(
            text(base.format(cols="skill_code, difficulty", vals="'MAT-FRC', 'easy'")),
            {"l": learner, "s": 1, "t": now},
        )

        with Operations.context(context), pytest.raises(RuntimeError, match="no bank question"):
            mine.downgrade()  # one answer has no bank question: it must not be dropped quietly
        assert connection.execute(text("SELECT COUNT(*) FROM attempts")).scalar() == 2

        connection.execute(text("DELETE FROM attempts WHERE question_id IS NULL"))
        with Operations.context(context):
            mine.downgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("attempts")}
        assert "skill_code" not in columns and "difficulty" not in columns
        assert connection.execute(text("SELECT COUNT(*) FROM attempts")).scalar() == 1  # the paper answer
