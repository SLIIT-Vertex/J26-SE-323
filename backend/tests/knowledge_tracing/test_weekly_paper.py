"""Weekly paper generation end to end: planner, layout, PDF, storage and database."""

import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.api.mastery_router import get_estimator
from app.knowledge_tracing.api.papers_router import get_paper_storage, get_question_storage
from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
    MasteryService,
)
from app.knowledge_tracing.application.paper_generation import (
    PaperNotFoundError,
    PaperRequest,
    PaperService,
    week_start_for,
)
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    PaperItemModel,
    PaperModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.knowledge_tracing.infrastructure.storage import LocalStorage
from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()
MONDAY = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)  # a Monday, 09:30 in Sri Lanka
WEDNESDAY = MONDAY + timedelta(days=2)
NEXT_WEEK = MONDAY + timedelta(days=7)


def question_png(label: str) -> bytes:
    image = Image.new("RGB", (900, 330), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([6, 6, 893, 323], outline="black", width=3)
    draw.text((30, 30), f"question {label}", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


SAMPLE_PNG = question_png("sample")


@pytest.fixture
def world(tmp_path: Path) -> Iterator[dict]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    questions = LocalStorage(tmp_path / "questions")
    papers = LocalStorage(tmp_path / "papers")
    with Session(engine) as db:
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.flush()
        for index, code in enumerate(SPEC.skills):
            for k, level in enumerate(("easy", "medium", "hard", "medium", "easy", "hard")):
                qid = f"{index + 1}.{k + 1}"
                db.add(QuestionModel(id=qid, skill_code=code, difficulty=level, est_seconds=90))
                db.flush()
                for language in ("si", "ta"):
                    key = f"questions/{qid}-{language}.png"
                    questions.put(key, SAMPLE_PNG)
                    db.add(
                        QuestionVariantModel(
                            question_id=qid,
                            language=language,
                            image_key=key,
                            image_width_px=900,
                            image_height_px=330,
                            answer_key_raw="1",
                        )
                    )
        db.commit()
        yield {"engine": engine, "db": db, "questions": questions, "papers": papers}


def service(world: dict, now: datetime = MONDAY) -> PaperService:
    db = world["db"]
    model = get_knowledge_model()
    mastery = MasteryService(SqlAlchemyMasteryRepository(db), model, SPEC, lambda: now)
    planner = PaperPlanner(SqlAlchemyPaperInputRepository(db), mastery, model, SPEC, now=lambda: now)
    return PaperService(
        SqlAlchemyPaperRepository(db), planner, world["questions"], world["papers"], lambda: now
    )


def learner(world: dict, language: str = "si") -> UUID:
    row = LearnerModel(id=uuid4(), grade=5, preferred_language=language)
    world["db"].add(row)
    world["db"].commit()
    return row.id


def give_history(world: dict, learner_id: UUID, skills: int = 22) -> None:
    db = world["db"]
    n = 0
    for index, code in enumerate(SPEC.skills[:skills]):
        for j in range(5):
            db.add(
                AttemptModel(
                    learner_id=learner_id,
                    question_id=f"{index + 1}.{j % 6 + 1}",
                    language="si",
                    source=1,
                    correct=(index + j) % 3 != 0,
                    penalty=0.1,
                    answered_at=MONDAY - timedelta(days=60, minutes=-n),
                )
            )
            n += 1
    db.commit()


# ---- week -----------------------------------------------------------------------------------


def test_the_week_starts_on_monday_in_sri_lanka_time() -> None:
    sunday_late_utc = datetime(2026, 10, 11, 19, 0, tzinfo=UTC)  # Monday 00:30 in Sri Lanka
    sunday_early_utc = datetime(2026, 10, 11, 17, 0, tzinfo=UTC)  # Sunday 22:30 in Sri Lanka

    assert week_start_for(sunday_late_utc).isoformat() == "2026-10-12"
    assert week_start_for(sunday_early_utc).isoformat() == "2026-10-05"
    assert week_start_for(WEDNESDAY).isoformat() == "2026-10-12"


# ---- generation -----------------------------------------------------------------------------


def test_a_new_learner_gets_a_diagnostic_paper_that_is_a_valid_pdf(world: dict) -> None:
    learner_id = learner(world)

    result = service(world).generate_weekly(learner_id)

    assert result.created
    paper = result.paper
    assert paper.mode == "diagnostic"
    assert paper.status == "generated"
    assert len(paper.token) == 12
    assert paper.week_start.isoformat() == "2026-10-12"
    assert 1 <= paper.page_count <= 3
    assert paper.pdf_key == f"papers/{paper.id}.pdf"

    data = world["papers"].get(paper.pdf_key)
    document = pdfium.PdfDocument(data)
    assert len(document) == paper.page_count
    document.close()

    assert [i.position for i in result.items] == list(range(1, len(result.items) + 1))
    assert all(i.role == "diagnostic" for i in result.items)
    assert all(0 <= i.block_x <= 1 and 0 <= i.block_y <= 1 for i in result.items)
    assert paper.params["question_count"] == len(result.items)


def test_a_paper_for_a_learner_with_history_is_a_practice_paper(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)

    result = service(world).generate_weekly(learner_id, PaperRequest(seed=3))

    assert result.paper.mode == "practice"
    assert result.paper.mastery_snapshot_id is not None
    assert result.paper.model_version.startswith("dkt-v2.1-")
    roles = {i.role for i in result.items}
    assert roles <= {"weak", "strong", "verify", "unknown"}
    assert result.paper.params["requested"]["seed"] == 3


def test_asking_again_in_the_same_week_returns_the_same_paper(world: dict) -> None:
    learner_id = learner(world)

    first = service(world, MONDAY).generate_weekly(learner_id)
    again = service(world, WEDNESDAY).generate_weekly(learner_id, PaperRequest(max_questions=5))

    assert first.created and not again.created
    assert again.paper.id == first.paper.id
    count = world["db"].scalar(select(func.count()).select_from(PaperModel))
    assert count == 1
    assert len(world["papers"].list("papers/")) == 1


def test_a_new_week_gets_a_new_paper_without_repeating_questions(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)

    week1 = service(world, MONDAY).generate_weekly(learner_id, PaperRequest(seed=1))
    week2 = service(world, NEXT_WEEK).generate_weekly(learner_id, PaperRequest(seed=1))

    assert week2.created
    assert week2.paper.id != week1.paper.id
    assert week2.paper.week_start > week1.paper.week_start
    first = {i.question_id for i in week1.items}
    second = {i.question_id for i in week2.items}
    assert not first & second  # questions on the last 3 papers are not repeated


def test_a_cancelled_paper_lets_the_week_have_a_new_one(world: dict) -> None:
    learner_id = learner(world)
    svc = service(world)
    first = svc.generate_weekly(learner_id)

    svc.cancel(first.paper.id)
    second = svc.generate_weekly(learner_id)

    assert second.created
    assert second.paper.id != first.paper.id
    assert second.paper.token != first.paper.token


def test_the_learners_language_chooses_the_printed_images(world: dict) -> None:
    learner_id = learner(world, language="ta")

    result = service(world).generate_weekly(learner_id)

    assert result.paper.language == "ta"
    assert {i.language for i in result.items} == {"ta"}


def test_the_requested_size_is_respected(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)

    result = service(world).generate_weekly(
        learner_id, PaperRequest(max_questions=6, max_minutes=12, max_pages=1, seed=2)
    )

    assert len(result.items) <= 6
    assert result.paper.page_count == 1
    assert result.paper.estimated_minutes <= 12


def test_a_missing_question_image_stops_the_paper_and_stores_nothing(world: dict) -> None:
    learner_id = learner(world)
    for key in world["questions"].list("questions/"):
        world["questions"].delete(key)

    with pytest.raises(Exception, match="cannot read the image"):
        service(world).generate_weekly(learner_id)

    assert world["db"].scalar(select(func.count()).select_from(PaperModel)) == 0
    assert world["papers"].list("papers/") == []


def test_an_unknown_learner_is_reported(world: dict) -> None:
    with pytest.raises(LearnerNotFoundError):
        service(world).generate_weekly(uuid4())


def test_the_paper_pdf_and_items_can_be_read_back(world: dict) -> None:
    learner_id = learner(world)
    svc = service(world)
    made = svc.generate_weekly(learner_id)

    paper, data = svc.pdf(made.paper.id)
    fetched = svc.get(made.paper.id)

    assert data.startswith(b"%PDF")
    assert paper.token == made.paper.token
    assert len(fetched.items) == len(made.items)
    with pytest.raises(PaperNotFoundError):
        svc.get(uuid4())


def test_paper_items_are_stored_with_their_page_position(world: dict) -> None:
    learner_id = learner(world)
    made = service(world).generate_weekly(learner_id, PaperRequest(max_pages=3))

    rows = world["db"].scalars(
        select(PaperItemModel).where(PaperItemModel.paper_id == made.paper.id)
    ).all()

    assert len(rows) == len(made.items) > 0
    assert {r.page for r in rows} <= set(range(1, made.paper.page_count + 1))
    assert all(r.answer_boxes is None for r in rows)  # the images already hold the answer space


# ---- API ------------------------------------------------------------------------------------


@pytest.fixture
def client(world: dict) -> Iterator[TestClient]:
    engine = world["engine"]

    def override_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_question_storage] = lambda: world["questions"]
    app.dependency_overrides[get_paper_storage] = lambda: world["papers"]
    app.dependency_overrides[get_estimator] = get_knowledge_model
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def api_learner(world: dict, language: str = "si") -> str:
    return str(learner(world, language))


def test_api_creates_then_returns_the_same_weekly_paper(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)

    first = client.post(f"/api/v1/learners/{learner_id}/papers")
    second = client.post(f"/api/v1/learners/{learner_id}/papers")

    assert first.status_code == 201
    assert second.status_code == 200
    body = first.json()
    assert body["paper_id"] == second.json()["paper_id"]
    assert len(body["code"]) == 12
    assert body["mode"] == "diagnostic"
    assert body["question_count"] == len(body["items"]) > 0
    assert body["pdf_url"].endswith(f"/papers/{body['paper_id']}/pdf")


def test_api_serves_the_pdf(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)
    created = client.post(f"/api/v1/learners/{learner_id}/papers").json()

    response = client.get(created["pdf_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert created["code"] in response.headers["content-disposition"]


def test_api_lists_and_reads_papers(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)
    created = client.post(f"/api/v1/learners/{learner_id}/papers").json()

    listed = client.get(f"/api/v1/learners/{learner_id}/papers").json()
    single = client.get(f"/api/v1/papers/{created['paper_id']}").json()

    assert [p["paper_id"] for p in listed] == [created["paper_id"]]
    assert single["items"] and single["code"] == created["code"]
    assert listed[0]["items"] is None


def test_api_accepts_a_custom_size(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)

    response = client.post(
        f"/api/v1/learners/{learner_id}/papers",
        json={"max_questions": 6, "max_minutes": 10, "max_pages": 1},
    )

    assert response.status_code == 201
    assert response.json()["question_count"] <= 6
    assert response.json()["page_count"] == 1


@pytest.mark.parametrize(
    "body",
    [{"max_questions": 0}, {"max_pages": 9}, {"mode": "hard"}, {"language": "en"}, {"x": 1}],
)
def test_api_rejects_bad_requests(world: dict, client: TestClient, body: dict) -> None:
    learner_id = api_learner(world)

    response = client.post(f"/api/v1/learners/{learner_id}/papers", json=body)

    assert response.status_code == 422


def test_api_unknown_learner_and_paper(world: dict, client: TestClient) -> None:
    missing = uuid4()

    assert client.post(f"/api/v1/learners/{missing}/papers").status_code == 404
    assert client.get(f"/api/v1/papers/{missing}").status_code == 404
    assert client.get(f"/api/v1/papers/{missing}/pdf").status_code == 404
    assert client.post(f"/api/v1/papers/{missing}/cancel").status_code == 404


def test_api_cancel_frees_the_week(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)
    first = client.post(f"/api/v1/learners/{learner_id}/papers").json()

    cancelled = client.post(f"/api/v1/papers/{first['paper_id']}/cancel")
    second = client.post(f"/api/v1/learners/{learner_id}/papers")

    assert cancelled.json()["status"] == "cancelled"
    assert second.status_code == 201
    assert second.json()["paper_id"] != first["paper_id"]


def test_the_api_never_returns_the_answer_key(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)
    body = client.post(f"/api/v1/learners/{learner_id}/papers").json()
    text = str(body).lower()

    for forbidden in ("correct_option", "accepted_answers", "answer_key", "instruction"):
        assert forbidden not in text
