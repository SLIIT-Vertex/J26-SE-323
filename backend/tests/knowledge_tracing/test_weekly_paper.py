"""Weekly paper generation end to end: planner, layout, PDF, storage and database."""

import io
from collections.abc import Iterator
from contextlib import contextmanager
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
    NotEligibleYetError,
    PaperNotFoundError,
    PaperRequest,
    PaperService,
    next_paper_date,
    week_start_for,
)
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.application.weekly_batch import generate_weekly_batch
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
# A week runs Saturday to Friday. 2026-10-17 is a Saturday.
SATURDAY = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)  # Saturday 09:30 in Sri Lanka
THURSDAY = SATURDAY + timedelta(days=5)
NEXT_SATURDAY = SATURDAY + timedelta(days=7)
MONDAY = SATURDAY  # (kept so the helpers below read naturally: "the day the week starts")
WEDNESDAY = THURSDAY
NEXT_WEEK = NEXT_SATURDAY


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


def service(world: dict, now: datetime = MONDAY, min_days: int = 7) -> PaperService:
    db = world["db"]
    model = get_knowledge_model()
    mastery = MasteryService(SqlAlchemyMasteryRepository(db), model, SPEC, lambda: now)
    planner = PaperPlanner(SqlAlchemyPaperInputRepository(db), mastery, model, SPEC, now=lambda: now)
    return PaperService(
        SqlAlchemyPaperRepository(db),
        planner,
        world["questions"],
        world["papers"],
        lambda: now,
        min_days_after_joining=min_days,
    )


# Children in these tests joined long ago, so the one-week waiting rule is not in the way,
# except in the tests that are about that rule.
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)


def learner(world: dict, language: str = "si", joined: datetime = LONG_AGO) -> UUID:
    row = LearnerModel(id=uuid4(), grade=5, preferred_language=language, created_at=joined)
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


def test_the_week_starts_on_saturday_in_sri_lanka_time() -> None:
    friday_before = datetime(2026, 10, 16, 18, 29, tzinfo=UTC)  # Friday 23:59 in Sri Lanka
    saturday_00_00 = datetime(2026, 10, 16, 18, 30, tzinfo=UTC)  # Saturday 00:00 in Sri Lanka
    friday_last = datetime(2026, 10, 23, 18, 29, tzinfo=UTC)  # the next Friday 23:59

    assert week_start_for(friday_before).isoformat() == "2026-10-10"
    assert week_start_for(saturday_00_00).isoformat() == "2026-10-17"
    assert week_start_for(friday_last).isoformat() == "2026-10-17"
    assert week_start_for(friday_last + timedelta(minutes=1)).isoformat() == "2026-10-24"


@pytest.mark.parametrize("days", range(7))
def test_every_day_of_the_week_belongs_to_the_same_saturday(days: int) -> None:
    moment = SATURDAY + timedelta(days=days)

    assert week_start_for(moment).isoformat() == "2026-10-17"
    assert week_start_for(moment).weekday() == 5  # always a Saturday


def test_the_next_paper_date_is_the_following_saturday() -> None:
    assert next_paper_date(week_start_for(THURSDAY)).isoformat() == "2026-10-24"


# ---- generation -----------------------------------------------------------------------------


def test_a_new_learner_gets_a_diagnostic_paper_that_is_a_valid_pdf(world: dict) -> None:
    learner_id = learner(world)

    result = service(world).generate_weekly(learner_id)

    assert result.created
    paper = result.paper
    assert paper.mode == "diagnostic"
    assert paper.status == "generated"
    assert len(paper.token) == 12
    assert paper.week_start.isoformat() == "2026-10-17"
    assert 1 <= paper.page_count <= 4
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

    first = service(world, SATURDAY).generate_weekly(learner_id)
    again = service(world, THURSDAY).generate_weekly(learner_id, PaperRequest(max_questions=5))

    assert first.created and not again.created
    assert again.paper.id == first.paper.id
    count = world["db"].scalar(select(func.count()).select_from(PaperModel))
    assert count == 1
    assert len(world["papers"].list("papers/")) == 1


def test_a_new_week_gets_a_new_paper_without_repeating_questions(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)

    week1 = service(world, SATURDAY).generate_weekly(learner_id, PaperRequest(seed=1))
    week2 = service(world, NEXT_SATURDAY).generate_weekly(learner_id, PaperRequest(seed=1))

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
    assert "dropped_questions" in result.paper.params  # layout drops are always recorded


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


def api_learner(world: dict, language: str = "si", joined: datetime = LONG_AGO) -> str:
    return str(learner(world, language, joined))


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


# ---- the paper of the week stays until the next Saturday --------------------------------------


def test_the_paper_stays_the_paper_of_the_week_until_the_next_saturday(world: dict) -> None:
    learner_id = learner(world)
    made = service(world, SATURDAY).generate_weekly(learner_id)

    for day in range(7):  # Saturday ... Friday
        moment = SATURDAY + timedelta(days=day)
        again = service(world, moment).generate_weekly(learner_id)
        assert again.paper.id == made.paper.id
        assert not again.created
    next_week = service(world, SATURDAY + timedelta(days=7)).generate_weekly(learner_id)
    assert next_week.created
    assert next_week.paper.id != made.paper.id
    assert next_week.paper.week_start.isoformat() == "2026-10-24"


def test_current_returns_this_weeks_paper_without_making_one(world: dict) -> None:
    learner_id = learner(world)
    svc = service(world, SATURDAY)

    assert svc.current(learner_id) is None
    assert world["db"].scalar(select(func.count()).select_from(PaperModel)) == 0
    made = svc.generate_weekly(learner_id)
    assert svc.current(learner_id).paper.id == made.paper.id  # type: ignore[union-attr]
    assert service(world, NEXT_SATURDAY).current(learner_id) is None  # the new week has none yet


# ---- the Saturday batch -------------------------------------------------------------------------


def batch_scope(world: dict, now: datetime):
    @contextmanager
    def scope() -> Iterator[PaperService]:
        yield service(world, now)

    return scope


def test_the_batch_makes_a_paper_for_every_learner_once(world: dict) -> None:
    ids = [learner(world) for _ in range(3)]
    scope = batch_scope(world, SATURDAY)

    first = generate_weekly_batch(ids, scope)
    second = generate_weekly_batch(ids, scope)  # run again the same week

    assert len(first.created) == 3 and not first.failed and first.ok
    assert second.created == [] and len(second.already_had) == 3
    assert world["db"].scalar(select(func.count()).select_from(PaperModel)) == 3
    codes = [p.qr_token for p in world["db"].scalars(select(PaperModel))]
    assert len(set(codes)) == 3  # every child's paper has its own code


def test_one_failing_learner_does_not_stop_the_rest(world: dict) -> None:
    good_a, good_b = learner(world), learner(world)
    unknown = uuid4()  # no such learner

    result = generate_weekly_batch([good_a, unknown, good_b], batch_scope(world, SATURDAY))

    assert result.created == [good_a, good_b]
    assert [learner_id for learner_id, _ in result.failed] == [unknown]
    assert not result.ok
    assert result.total == 3


def test_the_batch_after_a_new_saturday_makes_new_papers(world: dict) -> None:
    ids = [learner(world), learner(world)]

    generate_weekly_batch(ids, batch_scope(world, SATURDAY))
    later = generate_weekly_batch(ids, batch_scope(world, NEXT_SATURDAY))

    assert len(later.created) == 2
    assert world["db"].scalar(select(func.count()).select_from(PaperModel)) == 4


def test_api_current_paper_and_next_paper_date(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)

    assert client.get(f"/api/v1/learners/{learner_id}/papers/current").status_code == 404
    created = client.post(f"/api/v1/learners/{learner_id}/papers").json()
    current = client.get(f"/api/v1/learners/{learner_id}/papers/current")

    assert current.status_code == 200
    assert current.json()["paper_id"] == created["paper_id"]
    from datetime import date

    start = date.fromisoformat(created["week_start"])
    assert start.weekday() == 5  # a Saturday
    assert date.fromisoformat(created["next_paper_date"]) == start + timedelta(days=7)


# ---- the one-week waiting rule and the button state ---------------------------------------------


def test_a_child_who_joined_a_week_ago_can_ask_for_a_paper(world: dict) -> None:
    joined = SATURDAY - timedelta(days=7)  # exactly one week before
    learner_id = learner(world, joined=joined)

    result = service(world, SATURDAY).generate_weekly(learner_id)

    assert result.created


def test_a_child_who_joined_less_than_a_week_ago_cannot_yet(world: dict) -> None:
    joined = SATURDAY - timedelta(days=6, hours=23)
    learner_id = learner(world, joined=joined)

    with pytest.raises(NotEligibleYetError) as caught:
        service(world, SATURDAY).generate_weekly(learner_id)

    assert caught.value.eligible_from == joined + timedelta(days=7)
    assert world["db"].scalar(select(func.count()).select_from(PaperModel)) == 0
    assert world["papers"].list("papers/") == []


def test_the_waiting_days_can_be_changed_or_switched_off(world: dict) -> None:
    just_joined = learner(world, joined=SATURDAY)

    assert service(world, SATURDAY, min_days=0).generate_weekly(just_joined).created
    other = learner(world, joined=SATURDAY - timedelta(days=2))
    assert service(world, SATURDAY, min_days=2).generate_weekly(other).created
    third = learner(world, joined=SATURDAY - timedelta(days=1))
    with pytest.raises(NotEligibleYetError):
        service(world, SATURDAY, min_days=2).generate_weekly(third)


def test_the_button_is_unavailable_then_available_then_a_paper(world: dict) -> None:
    joined = SATURDAY - timedelta(days=3)
    learner_id = learner(world, joined=joined)

    early = service(world, SATURDAY).availability(learner_id)
    assert early.state == "not_yet_eligible" and not early.can_generate
    assert early.days_until_eligible == 4
    assert early.eligible_from == joined + timedelta(days=7)
    assert early.paper is None

    eligible_day = SATURDAY + timedelta(days=4)
    ready = service(world, eligible_day).availability(learner_id)
    assert ready.state == "available" and ready.can_generate
    assert ready.days_until_eligible == 0

    service(world, eligible_day).generate_weekly(learner_id)
    done = service(world, eligible_day + timedelta(days=1)).availability(learner_id)
    assert done.state == "generated" and not done.can_generate
    assert done.paper is not None
    assert done.next_paper_date.isoformat() == "2026-10-24"  # clickable again that Saturday


def test_the_button_becomes_available_again_on_the_next_saturday(world: dict) -> None:
    learner_id = learner(world)
    service(world, SATURDAY).generate_weekly(learner_id)

    friday = service(world, SATURDAY + timedelta(days=6)).availability(learner_id)
    saturday = service(world, NEXT_SATURDAY).availability(learner_id)

    assert friday.state == "generated"
    assert saturday.state == "available" and saturday.paper is None


def test_a_paper_already_made_is_still_returned_after_the_rule_changes(world: dict) -> None:
    learner_id = learner(world, joined=SATURDAY - timedelta(days=30))
    made = service(world, SATURDAY, min_days=7).generate_weekly(learner_id)

    again = service(world, THURSDAY, min_days=60).generate_weekly(learner_id)

    assert again.paper.id == made.paper.id and not again.created


def test_availability_for_an_unknown_learner(world: dict) -> None:
    with pytest.raises(LearnerNotFoundError):
        service(world).availability(uuid4())


def test_the_batch_skips_children_who_are_not_eligible(world: dict) -> None:
    old = learner(world)
    new = learner(world, joined=SATURDAY - timedelta(days=2))

    result = generate_weekly_batch([old, new], batch_scope(world, SATURDAY))

    assert result.created == [old]
    assert result.not_eligible == [new]
    assert result.ok  # a child who has to wait is not a failure


def test_api_reports_the_button_state_and_refuses_too_early(world: dict, client: TestClient) -> None:
    joined = datetime.now(UTC) - timedelta(days=2)
    learner_id = api_learner(world, joined=joined)

    state = client.get(f"/api/v1/learners/{learner_id}/papers/availability").json()
    assert state["state"] == "not_yet_eligible"
    assert state["can_generate"] is False
    assert state["days_until_eligible"] in (4, 5)
    assert state["paper"] is None

    refused = client.post(f"/api/v1/learners/{learner_id}/papers")
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["code"] == "not_eligible_yet"
    assert "eligible_from" in detail


def test_api_button_flow_for_an_eligible_child(world: dict, client: TestClient) -> None:
    learner_id = api_learner(world)

    before = client.get(f"/api/v1/learners/{learner_id}/papers/availability").json()
    assert before["state"] == "available" and before["can_generate"] is True

    created = client.post(f"/api/v1/learners/{learner_id}/papers")
    assert created.status_code == 201

    after = client.get(f"/api/v1/learners/{learner_id}/papers/availability").json()
    assert after["state"] == "generated" and after["can_generate"] is False
    assert after["paper"]["paper_id"] == created.json()["paper_id"]
    assert after["next_paper_date"] == created.json()["next_paper_date"]


def test_api_availability_unknown_learner(world: dict, client: TestClient) -> None:
    assert client.get(f"/api/v1/learners/{uuid4()}/papers/availability").status_code == 404


# ---- diagnostic papers for children with no recorded activity --------------------------------


def test_a_child_with_no_activity_gets_a_diagnostic_paper(world: dict) -> None:
    learner_id = learner(world)  # joined long ago, never played

    result = service(world, SATURDAY).generate_weekly(learner_id)

    assert result.paper.mode == "diagnostic"
    assert {i.role for i in result.items} == {"diagnostic"}
    # one easy and one medium question for each skill covered
    per_skill: dict[str, set[str]] = {}
    for item in result.items:
        per_skill.setdefault(item.skill_code, set()).add(item.shown_difficulty)
    assert all(levels == {"easy", "medium"} for levels in per_skill.values())


def test_diagnostic_papers_move_on_to_new_skills_each_week(world: dict) -> None:
    learner_id = learner(world)
    seen: list[str] = []
    for week in range(5):
        when = SATURDAY + timedelta(days=7 * week)
        made = service(world, when).generate_weekly(learner_id, PaperRequest(seed=week))
        assert made.paper.mode == "diagnostic"
        skills = list(made.paper.params["diagnostic_skills"])
        assert skills, f"week {week} covered no skills"
        assert not set(skills) & set(seen), "a skill was asked about twice before all were covered"
        seen.extend(skills)

    assert seen == list(SPEC.skills[: len(seen)])  # APT first, then MAT, LAN, ENV, in order
    assert len(seen) >= 20


def test_after_all_skills_are_covered_the_walk_starts_again(world: dict) -> None:
    learner_id = learner(world)
    covered: set[str] = set()
    week = 0
    while len(covered) < len(SPEC.skills) and week < 12:
        when = SATURDAY + timedelta(days=7 * week)
        made = service(world, when).generate_weekly(learner_id)
        covered.update(made.paper.params["diagnostic_skills"])
        week += 1
    assert covered == set(SPEC.skills)

    again = service(world, SATURDAY + timedelta(days=7 * week)).generate_weekly(learner_id)

    assert again.paper.mode == "diagnostic"
    assert again.paper.params["diagnostic_skills"]  # the walk began again, not an error
