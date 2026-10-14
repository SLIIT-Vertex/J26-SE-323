from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.attempts import AttemptService
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
LEARNER = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def engine() -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si"))
        db.add(SkillModel(code="APT-PAT", sort_index=0, area="APT", name_en="Patterns"))
        db.add(SkillModel(code="MAT-FRC", sort_index=9, area="MAT", name_en="Fractions"))
        db.flush()
        db.add(QuestionModel(id="1.1", skill_code="APT-PAT", difficulty="easy"))
        db.add(QuestionModel(id="2.1", skill_code="MAT-FRC", difficulty="hard"))
        db.flush()
        for question_id, language in [("1.1", "si"), ("1.1", "ta"), ("2.1", "si")]:
            db.add(
                QuestionVariantModel(
                    question_id=question_id,
                    language=language,
                    image_key=f"questions/{question_id}-{language}.png",
                    image_width_px=100,
                    image_height_px=100,
                    answer_key_raw="1",
                )
            )
        db.commit()
    return engine


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "learner_id": str(LEARNER),
        "question_id": "1.1",
        "language": "si",
        "correct": True,
        "time_ms": 14_000,
        "hints": 1,
        "answered_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def rows(engine: Engine) -> list[AttemptModel]:
    with Session(engine) as session:
        return list(session.scalars(select(AttemptModel).order_by(AttemptModel.id)))


# --- POST /attempts -------------------------------------------------------------------------


def test_a_game_answer_is_stored_as_digital_with_a_computed_penalty(
    client: TestClient, engine: Engine
) -> None:
    response = client.post("/api/v1/attempts", json=body())

    assert response.status_code == 201
    assert set(response.json()) == {"attempt_id"}
    [row] = rows(engine)
    assert row.id == response.json()["attempt_id"]
    assert row.source == 1
    assert row.correct is True
    assert row.language == "si"
    assert row.penalty == pytest.approx(0.6 * (1 / 3) + 0.4 * (14_000 / 180_000))


def test_time_and_hints_are_optional(client: TestClient, engine: Engine) -> None:
    payload = body()
    del payload["time_ms"], payload["hints"]

    assert client.post("/api/v1/attempts", json=payload).status_code == 201
    [row] = rows(engine)
    assert row.time_ms is None and row.hints is None
    assert row.penalty == pytest.approx(0.4 * 12_000 / 180_000)


def test_tamil_version_can_be_answered(client: TestClient) -> None:
    assert client.post("/api/v1/attempts", json=body(language="ta")).status_code == 201


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        ({"learner_id": str(uuid4())}, 404),
        ({"question_id": "9.9"}, 404),
        ({"question_id": "2.1", "language": "ta"}, 422),  # 2.1 has no Tamil version here
        ({"language": "en"}, 422),
        ({"time_ms": 600_001}, 422),
        ({"time_ms": -1}, 422),
        ({"hints": 11}, 422),
        ({"hints": -1}, 422),
        ({"answered_at": "2026-10-01T09:00:00"}, 422),  # no time zone
        ({"answered_at": "not a date"}, 422),
        ({"correct": "maybe"}, 422),
        ({"source": 0}, 422),  # the client cannot choose the source
        ({"penalty": 0.0}, 422),  # nor the penalty
    ],
)
def test_bad_requests_are_rejected_and_nothing_is_stored(
    client: TestClient, engine: Engine, overrides: dict[str, object], status: int
) -> None:
    response = client.post("/api/v1/attempts", json=body(**overrides))

    assert response.status_code == status, response.text
    assert rows(engine) == []


def test_an_answer_from_the_future_is_rejected(client: TestClient, engine: Engine) -> None:
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    response = client.post("/api/v1/attempts", json=body(answered_at=future))

    assert response.status_code == 422
    assert rows(engine) == []


def test_a_little_clock_drift_is_tolerated(client: TestClient) -> None:
    soon = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()

    assert client.post("/api/v1/attempts", json=body(answered_at=soon)).status_code == 201


def test_the_same_idempotency_key_returns_the_same_attempt(
    client: TestClient, engine: Engine
) -> None:
    headers = {"Idempotency-Key": "game-session-42-q-7"}
    first = client.post("/api/v1/attempts", json=body(), headers=headers)
    second = client.post("/api/v1/attempts", json=body(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(rows(engine)) == 1


def test_an_idempotency_key_reused_for_another_answer_is_a_conflict(
    client: TestClient, engine: Engine
) -> None:
    headers = {"Idempotency-Key": "k1"}
    assert client.post("/api/v1/attempts", json=body(), headers=headers).status_code == 201

    other = client.post("/api/v1/attempts", json=body(question_id="2.1"), headers=headers)

    assert other.status_code == 409
    assert len(rows(engine)) == 1


def test_without_a_key_every_post_is_a_new_attempt(client: TestClient, engine: Engine) -> None:
    client.post("/api/v1/attempts", json=body())
    client.post("/api/v1/attempts", json=body())

    assert len(rows(engine)) == 2


# --- history --------------------------------------------------------------------------------


def add_attempt(
    engine: Engine,
    question_id: str,
    answered_at: datetime,
    *,
    source: int = 1,
    correct: bool = True,
    penalty: float = 0.1,
) -> int:
    with Session(engine) as session:
        model = AttemptModel(
            learner_id=LEARNER,
            question_id=question_id,
            language="si",
            source=source,
            correct=correct,
            penalty=penalty,
            answered_at=answered_at,
            paper_item_id=uuid4() if source == 0 else None,
        )
        session.add(model)
        session.commit()
        return model.id


def history(engine: Engine, limit: int | None = None):
    with Session(engine) as session:
        service = AttemptService(SqlAlchemyAttemptRepository(session), get_feature_spec())
        return service.history(LEARNER, limit)


def test_history_is_ordered_by_time_even_when_inserted_out_of_order(engine: Engine) -> None:
    late = add_attempt(engine, "1.1", T0 + timedelta(minutes=10))
    early = add_attempt(engine, "2.1", T0)
    middle = add_attempt(engine, "1.1", T0 + timedelta(minutes=5))

    assert [h.attempt_id for h in history(engine)] == [early, middle, late]


def test_equal_times_are_broken_by_id(engine: Engine) -> None:
    ids = [add_attempt(engine, "1.1", T0) for _ in range(4)]

    assert [h.attempt_id for h in history(engine)] == ids


def test_history_mixes_digital_and_paper(engine: Engine) -> None:
    add_attempt(engine, "1.1", T0, source=1)
    add_attempt(engine, "2.1", T0 + timedelta(minutes=1), source=0, penalty=0.08)

    items = history(engine)

    assert [i.source for i in items] == [1, 0]
    assert items[1].penalty == pytest.approx(0.08)


def test_history_carries_what_the_model_needs(engine: Engine) -> None:
    add_attempt(engine, "2.1", T0, correct=False)

    [item] = history(engine)

    assert (item.skill_code, item.skill_index, item.difficulty) == ("MAT-FRC", 9, "hard")
    assert item.correct is False
    assert item.question_id == "2.1"


def test_history_limit_keeps_the_latest_in_time_order(engine: Engine) -> None:
    ids = [add_attempt(engine, "1.1", T0 + timedelta(minutes=m)) for m in range(6)]

    recent = history(engine, limit=3)

    assert [h.attempt_id for h in recent] == ids[-3:]


def test_history_of_another_learner_is_not_included(engine: Engine) -> None:
    add_attempt(engine, "1.1", T0)
    with Session(engine) as session:
        other = LearnerModel(id=uuid4(), grade=4, preferred_language="ta")
        session.add(other)
        session.commit()
        other_id = other.id

    with Session(engine) as session:
        service = AttemptService(SqlAlchemyAttemptRepository(session), get_feature_spec())
        assert service.history(other_id) == []


def test_empty_history_is_an_empty_list(engine: Engine) -> None:
    assert history(engine) == []
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AttemptModel)) == 0
