import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import torch
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.api import mastery_router
from app.knowledge_tracing.api.mastery_router import get_estimator, get_mastery_service
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.domain.feature_spec import FeatureSpec, load_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    MasterySnapshotModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.ml.model import MindBridgeDKT
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel

BACKEND = Path(__file__).parents[2]
SPEC_PATH = BACKEND.parent / "shared" / "feature_spec.json"
WEIGHTS = BACKEND / "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
GOLDEN = BACKEND / "tests/knowledge_tracing/fixtures/golden_history.json"
START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
LEARNER = UUID("11111111-1111-1111-1111-111111111111")


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture(scope="module")
def spec() -> FeatureSpec:
    return load_feature_spec(str(SPEC_PATH))


@pytest.fixture(scope="module")
def estimator(spec: FeatureSpec) -> KnowledgeModel:
    torch.manual_seed(0)
    return KnowledgeModel(MindBridgeDKT(num_skills=len(spec.skills)), spec, "test-model")


@pytest.fixture
def engine(spec: FeatureSpec) -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si"))
        for index, code in enumerate(spec.skills):
            db.add(
                SkillModel(
                    code=code, sort_index=index, area=code[:3], name_en=f"Skill {code}",
                    name_si=f"සිංහල {code}",
                )
            )
        db.flush()
        for index, code in enumerate(spec.skills):
            db.add(QuestionModel(id=f"q{index}", skill_code=code, difficulty="medium"))
        db.flush()
        for index in range(len(spec.skills)):
            db.add(
                QuestionVariantModel(
                    question_id=f"q{index}", language="si", image_key=f"k{index}",
                    image_width_px=10, image_height_px=10, answer_key_raw="1",
                )
            )
        db.commit()
    return engine


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(
    engine: Engine, estimator: KnowledgeModel, spec: FeatureSpec, clock: Clock
) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def override_service() -> Iterator[MasteryService]:
        with Session(engine) as session:
            yield MasteryService(SqlAlchemyMasteryRepository(session), estimator, spec, clock)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_mastery_service] = override_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_attempts(
    engine: Engine, answers: list[tuple[int, bool, int]], learner: UUID = LEARNER
) -> None:
    """answers: (skill index, correct, source), oldest first."""
    with Session(engine) as session:
        base = session.scalar(
            select(func.count()).select_from(AttemptModel).where(AttemptModel.learner_id == learner)
        )
        for number, (skill, correct, source) in enumerate(answers, start=base or 0):
            session.add(
                AttemptModel(
                    learner_id=learner,
                    question_id=f"q{skill}",
                    language="si",
                    source=source,
                    correct=correct,
                    penalty=0.08 if source == 0 else 0.1,
                    answered_at=START + timedelta(minutes=number),
                    paper_item_id=uuid4() if source == 0 else None,
                )
            )
        session.commit()


def snapshots(engine: Engine) -> list[MasterySnapshotModel]:
    with Session(engine) as session:
        return list(session.scalars(select(MasterySnapshotModel).order_by(MasterySnapshotModel.id)))


def url(learner: UUID = LEARNER) -> str:
    return f"/api/v1/learners/{learner}/mastery"


def known(body: dict) -> dict[str, float]:
    return {s["code"]: s["mastery"] for s in body["skills"] if s["mastery"] is not None}


# --- reading mastery ------------------------------------------------------------------------


def test_a_new_learner_has_thirty_unknown_skills(client: TestClient, engine: Engine) -> None:
    response = client.get(url())

    assert response.status_code == 200
    body = response.json()
    assert len(body["skills"]) == 30
    assert all(s["mastery"] is None and s["attempts"] == 0 for s in body["skills"])
    assert body["n_attempts"] == 0
    assert body["model_version"] == "test-model"
    assert "medium-difficulty paper question" in body["definition"]
    assert len(snapshots(engine)) == 1


def test_skills_come_in_model_order_with_area_and_names(
    client: TestClient, spec: FeatureSpec
) -> None:
    skills = client.get(url()).json()["skills"]

    assert [s["code"] for s in skills] == list(spec.skills)
    assert skills[0]["area"] == "APT"
    assert skills[29]["area"] == "ENV"
    assert skills[0]["name_en"] == "Skill APT-PAT"
    assert skills[0]["name_si"] == "සිංහල APT-PAT"


def test_a_skill_needs_three_answers_to_show_a_number(client: TestClient, engine: Engine) -> None:
    add_attempts(engine, [(3, True, 1), (3, False, 1), (3, True, 0), (5, True, 1), (5, True, 1)])

    by_code = {s["code"]: s for s in client.get(url()).json()["skills"]}

    assert by_code["APT-LOG"]["attempts"] == 3
    assert by_code["APT-LOG"]["mastery"] is not None
    assert by_code["APT-VIS"]["attempts"] == 2
    assert by_code["APT-VIS"]["mastery"] is None


def test_the_api_returns_what_the_model_computes(
    client: TestClient, engine: Engine, estimator: KnowledgeModel
) -> None:
    answers = [(n % 4, n % 3 != 0, n % 2) for n in range(40)]
    add_attempts(engine, answers)
    with Session(engine) as session:
        history = SqlAlchemyMasteryRepository(session).history(LEARNER, 140)

    body = client.get(url()).json()

    assert body["n_attempts"] == 40
    assert known(body) == {m.code: m.mastery for m in estimator.mastery(history) if m.mastery}


def test_unknown_learner_is_404(client: TestClient) -> None:
    assert client.get(url(uuid4())).status_code == 404
    assert client.post(url(uuid4()) + "/recompute").status_code == 404


# --- recompute and debounce -----------------------------------------------------------------


def test_a_second_read_reuses_the_snapshot(client: TestClient, engine: Engine) -> None:
    first = client.get(url()).json()
    second = client.get(url()).json()

    assert second == first
    assert len(snapshots(engine)) == 1


def test_new_answers_are_picked_up_after_the_debounce_interval(
    client: TestClient, engine: Engine, clock: Clock
) -> None:
    client.get(url())
    add_attempts(engine, [(2, True, 1)] * 4)

    clock.advance(10)
    assert client.get(url()).json()["n_attempts"] == 0  # too soon: the cached snapshot
    assert len(snapshots(engine)) == 1

    clock.advance(25)
    refreshed = client.get(url()).json()
    assert refreshed["n_attempts"] == 4
    assert len(snapshots(engine)) == 2
    assert {s["code"]: s["attempts"] for s in refreshed["skills"]}["APT-DIR"] == 4


def test_nothing_new_means_no_new_snapshot_even_when_old(
    client: TestClient, engine: Engine, clock: Clock
) -> None:
    add_attempts(engine, [(1, True, 1)] * 3)
    client.get(url())

    clock.advance(3600)
    client.get(url())

    assert len(snapshots(engine)) == 1


def test_recompute_makes_a_fresh_snapshot_but_not_in_a_tight_loop(
    client: TestClient, engine: Engine, clock: Clock
) -> None:
    client.get(url())

    clock.advance(1)
    assert client.post(url() + "/recompute").status_code == 200
    assert len(snapshots(engine)) == 1  # a moment ago: reused

    clock.advance(10)
    forced = client.post(url() + "/recompute")
    assert forced.status_code == 200
    assert len(snapshots(engine)) == 2


def test_snapshots_record_version_and_attempt_count(
    client: TestClient, engine: Engine
) -> None:
    add_attempts(engine, [(0, True, 1)] * 5)
    client.get(url())

    [snapshot] = snapshots(engine)

    assert snapshot.model_version == "test-model"
    assert snapshot.n_attempts == 5
    assert len(snapshot.skills) == 30
    assert snapshot.skills[0] == {"code": "APT-PAT", "mastery": snapshot.skills[0]["mastery"],
                                  "attempts": 5}


# --- when the model is not there ------------------------------------------------------------


def test_mastery_is_503_when_the_weights_are_missing(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing() -> KnowledgeModel:
        raise FileNotFoundError("weights")

    def override_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(mastery_router, "get_knowledge_model", missing)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get(url())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert get_estimator is not None


def test_the_server_still_starts_without_the_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    def missing() -> KnowledgeModel:
        raise FileNotFoundError("weights")

    monkeypatch.setattr(main, "get_knowledge_model", missing)

    with TestClient(app) as test_client:
        assert test_client.get("/api/v1/health").json() == {"status": "ok"}


# --- the whole path with the real weights ---------------------------------------------------


def test_golden_histories_give_the_notebook_numbers_through_the_api(
    engine: Engine, spec: FeatureSpec, clock: Clock
) -> None:
    """Attempts in the database -> history loader -> trained model -> HTTP response."""
    if not (WEIGHTS.is_file() and GOLDEN.is_file()):
        pytest.skip("trained weights or golden fixture missing")
    real = KnowledgeModel.load(WEIGHTS, spec)
    student = json.loads(GOLDEN.read_text(encoding="utf-8"))[1]
    learner = uuid4()
    with Session(engine) as session:
        session.add(LearnerModel(id=learner, grade=5, preferred_language="si"))
        session.commit()
    with Session(engine) as session:
        for number, (skill, correct, source, penalty) in enumerate(
            zip(student["skills"], student["corrects"], student["sources"], student["penalties"],
                strict=True)
        ):
            session.add(
                AttemptModel(
                    learner_id=learner, question_id=f"q{skill}", language="si", source=source,
                    correct=bool(correct), penalty=penalty,
                    answered_at=START + timedelta(minutes=number),
                    paper_item_id=uuid4() if source == 0 else None,
                )
            )
        session.commit()

    def override_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def override_service() -> Iterator[MasteryService]:
        with Session(engine) as session:
            yield MasteryService(SqlAlchemyMasteryRepository(session), real, spec, clock)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_mastery_service] = override_service
    try:
        with TestClient(app) as test_client:
            body = test_client.get(url(learner)).json()
    finally:
        app.dependency_overrides.clear()

    assert body["model_version"].startswith("dkt-v2.1-")
    for code, expected in student["expected"].items():
        got = next(s["mastery"] for s in body["skills"] if s["code"] == code)
        assert (expected is None) == (got is None), code
        if expected is not None:
            assert abs(expected - got) < 1.5e-3, f"{code}: notebook {expected}, api {got}"
