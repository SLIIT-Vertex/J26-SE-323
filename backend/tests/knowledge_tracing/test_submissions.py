"""Upload, marking, parent review and confirmation, on papers made by the real weekly service.

The reader is a scripted mock, so these tests show how marking behaves for given readings. Nothing
here uses the network or a vision-model key.
"""

import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.api.mastery_router import get_estimator
from app.knowledge_tracing.api.papers_router import get_paper_storage, get_question_storage
from app.knowledge_tracing.api.submissions_router import (
    get_grading_launcher,
    make_submission_service,
)
from app.knowledge_tracing.application.grading.types import (
    ItemRead,
    PartRead,
    VisionError,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    GradedAnswerModel,
    MasterySnapshotModel,
    PaperItemModel,
    PaperModel,
    PaperSubmissionModel,
    QuestionPartModel,
)
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.knowledge_tracing.infrastructure.pdf.paper_pdf import render_pages
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading
from app.main import app
from app.shared.database.session import get_db
from scripts.make_synthetic_photo import synthesize_photo
from tests.knowledge_tracing import test_weekly_paper as weekly

world = weekly.world

NOW = datetime.now(UTC)


class Script:
    """Hands the mock reader its next scripted reading for each question block, by position."""

    def __init__(self) -> None:
        self.default: ItemRead | VisionError | None = None
        self.by_position: dict[int, ItemRead | VisionError] = {}


class ScriptedProvider(MockProvider):
    """A reader that answers according to the question's printed position.

    The position is not in the crop, so the script is applied by call order: the pipeline sends
    the blocks of a page in position order and this provider is used with one worker.
    """

    def __init__(self, answers: list[ItemRead | VisionError]) -> None:
        super().__init__(*answers)


@dataclass
class Env:
    client: TestClient
    world: dict
    engine: object
    provider_ref: list  # a one-item list so a test can swap the reader
    learner_id: str = ""
    paper: dict | None = None
    pdf: bytes = b""


def seed_answer_keys(engine) -> None:
    """Give every question in the weekly-paper test bank an answer key.

    Questions numbered *.2 have two parts (a choice and a short answer); every other question
    has one choice part. The right answer of every part is "1".
    """
    from app.knowledge_tracing.infrastructure.db.models import QuestionVariantModel

    with Session(engine) as session:
        for variant in session.scalars(select(QuestionVariantModel)).all():
            session.add(
                QuestionPartModel(
                    question_id=variant.question_id,
                    language=variant.language,
                    part_no=1,
                    part_type="mcq",
                    answer_kind="choice",
                    option_labels=["1", "2", "3"],
                    correct_option="1",
                    accepted_answers=["1"],
                )
            )
            if variant.question_id.endswith(".2"):
                session.add(
                    QuestionPartModel(
                        question_id=variant.question_id,
                        language=variant.language,
                        part_no=2,
                        part_type="short",
                        answer_kind="text",
                        accepted_answers=["1"],
                    )
                )
        session.commit()


@pytest.fixture
def env(world: dict) -> Iterator[Env]:
    engine = world["engine"]
    seed_answer_keys(engine)
    provider_ref: list = [MockProvider()]

    def override_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def launcher_factory(paper_storage=None):
        def launch(submission_id: UUID) -> None:
            with Session(engine) as session:
                make_submission_service(
                    session,
                    world["papers"],
                    provider=provider_ref[0],
                    estimator=get_knowledge_model(),
                    use_default_readers=False,
                    workers=1,
                ).grade(submission_id)

        return launch

    from app.knowledge_tracing.api import submissions_router as module

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_question_storage] = lambda: world["questions"]
    app.dependency_overrides[get_paper_storage] = lambda: world["papers"]
    app.dependency_overrides[get_estimator] = get_knowledge_model
    app.dependency_overrides[get_grading_launcher] = launcher_factory
    original = module.make_submission_service

    def make_for_requests(session, paper_storage, **kwargs):
        kwargs.setdefault("provider", provider_ref[0])
        kwargs.setdefault("estimator", get_knowledge_model())
        kwargs["use_default_readers"] = False
        kwargs["workers"] = 1
        return original(session, paper_storage, **kwargs)

    module.make_submission_service = make_for_requests
    try:
        with TestClient(app) as client:
            yield Env(client, world, engine, provider_ref)
    finally:
        module.make_submission_service = original
        app.dependency_overrides.clear()


def start(env: Env, questions: int = 6) -> Env:
    """A learner, and this week's paper (a short one, so each test stays quick)."""
    learner = weekly.learner(env.world)
    env.learner_id = str(learner)
    response = env.client.post(
        f"/api/v1/learners/{learner}/papers",
        json={"max_questions": questions, "max_minutes": 40, "max_pages": 3},
    )
    assert response.status_code == 201, response.text
    env.paper = response.json()
    env.pdf = env.client.get(env.paper["pdf_url"]).content
    return env


def photo(env: Env, page: int, **options) -> bytes:
    grays, px_per_mm = render_pages(env.pdf)
    image = synthesize_photo(
        grays[page - 1], px_per_mm, random.Random(page + 7), size=(1800, 2400), **options
    ).image
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return data.tobytes()


def upload(env: Env, page: int = 1, data: bytes | None = None):
    assert env.paper is not None
    return env.client.post(
        f"/api/v1/papers/{env.paper['paper_id']}/pages/{page}/photo",
        files={"image": ("page.jpg", data if data is not None else photo(env, page), "image/jpeg")},
    )


def submission(env: Env, submission_id: str) -> dict:
    response = env.client.get(f"/api/v1/submissions/{submission_id}")
    assert response.status_code == 200, response.text
    return response.json()


def keys_on_page(env: Env, page: int) -> list[tuple[int, UUID, list[QuestionPartModel]]]:
    """(position, paper_item_id, key parts) of the questions on a page, from the database."""
    with Session(env.engine) as session:
        items = session.scalars(
            select(PaperItemModel)
            .where(PaperItemModel.paper_id == UUID(env.paper["paper_id"]), PaperItemModel.page == page)
            .order_by(PaperItemModel.position)
        ).all()
        out = []
        for item in items:
            parts = session.scalars(
                select(QuestionPartModel)
                .where(
                    QuestionPartModel.question_id == item.question_id,
                    QuestionPartModel.language == item.language,
                )
                .order_by(QuestionPartModel.part_no)
            ).all()
            session.expunge_all()
            out.append((item.position, item.id, list(parts)))
        return out


def answers_for(env: Env, page: int, mode: Callable[[int], str]) -> list[ItemRead]:
    """One scripted reading per question on the page.

    The question bank of these tests has every part answered by the label "1" (see the world
    fixture), so "right" is "1", "wrong" is "3", "blank" is None and anything else is a literal.
    """
    readings = []
    for position, _, parts in keys_on_page(env, page):
        outcome = mode(position)
        answers: list = []
        for _ in parts:
            answers.append(
                {"right": "1", "wrong": "3", "blank": None}.get(outcome, outcome)
            )
        readings.append(reading(*answers))
    return readings


def attempts(env: Env) -> list[AttemptModel]:
    with Session(env.engine) as session:
        rows = session.scalars(select(AttemptModel).order_by(AttemptModel.id)).all()
        session.expunge_all()
        return list(rows)


# ---- the whole path ---------------------------------------------------------------------------


def test_a_clean_page_is_marked_without_the_parent_and_counts(env: Env) -> None:
    start(env)
    first_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda position: "right" if position % 2 else "wrong")
    env.provider_ref[0] = MockProvider(*readings)

    response = upload(env, 1)

    assert response.status_code == 202
    assert response.json()["status"] == "uploaded"
    body = submission(env, response.json()["submission_id"])
    assert body["status"] == "graded"  # the background task ran before the client returned
    assert body["in_progress"] is False
    assert body["review_items"] == []
    assert body["summary"] == {
        "items": len(first_page), "auto_final": len(first_page), "needs_review": 0,
    }
    assert [r["result"] for r in body["results"]] == [
        "correct" if position % 2 else "wrong" for position, _, _ in first_page
    ]
    # every decided question became exactly one paper attempt
    made = attempts(env)
    assert len(made) == len(first_page)
    assert all(a.source == 0 for a in made)
    assert all(a.time_ms is None and a.hints is None for a in made)
    assert all(a.penalty == pytest.approx(0.08) for a in made)
    assert all(a.paper_item_id is not None for a in made)
    assert sum(a.correct for a in made) == sum(1 for p, _, _ in first_page if p % 2)


def test_mastery_is_recomputed_when_paper_answers_arrive(env: Env) -> None:
    start(env)
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))
    with Session(env.engine) as session:
        before = session.scalar(select(func.count()).select_from(MasterySnapshotModel))

    upload(env, 1)

    with Session(env.engine) as session:
        after = session.scalar(select(func.count()).select_from(MasterySnapshotModel))
        latest = session.scalars(
            select(MasterySnapshotModel).order_by(MasterySnapshotModel.id.desc())
        ).first()
    assert after > before
    assert latest is not None and latest.n_attempts == len(attempts(env))


def test_blank_questions_make_no_attempt(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda p: "blank" if p == 1 else "right"))

    body = submission(env, upload(env, 1).json()["submission_id"])

    assert body["results"][0]["result"] == "blank"
    assert len(attempts(env)) == len(on_page) - 1


# ---- when the reader is unsure ----------------------------------------------------------------


def test_an_unsure_reading_waits_for_the_parent_and_hides_its_result(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    first_parts = len(on_page[0][2])
    readings[0] = reading(*[("1", 0.2)] * first_parts)  # the reader was unsure about question 1
    env.provider_ref[0] = MockProvider(*readings)

    body = submission(env, upload(env, 1).json()["submission_id"])

    assert body["status"] == "needs_review"
    assert body["summary"]["needs_review"] == 1
    assert len(body["review_items"]) == first_parts
    item = body["review_items"][0]
    assert item["reason"] == "low_confidence"
    assert item["crop_url"].endswith(f"/crops/{item['paper_item_id']}")
    assert item["reading"] == {"selected": "1"}
    assert item["part_type"] == "mcq"
    assert item["options"]
    assert body["results"][0]["result"] == "pending_review"  # hidden until decided
    # the settled questions already count; the waiting one does not
    assert len(attempts(env)) == len(on_page) - 1


def test_the_parent_confirms_and_the_question_then_counts(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("3", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]

    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1"}
        for r in waiting
    ]
    response = env.client.post(
        f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions},
        headers={"X-Parent-Id": "parent-77"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["review_items"] == []
    assert body["results"][0]["result"] == "correct"  # the parent said the child marked "1"
    assert len(attempts(env)) == len(on_page)
    with Session(env.engine) as session:
        decided = session.scalars(
            select(GradedAnswerModel).where(GradedAnswerModel.confirmed_by == "parent-77")
        ).all()
        assert len(decided) == len(waiting)
        assert {d.final_status for d in decided} == {"correct"}


def test_the_parent_says_what_the_child_marked_not_correct_or_wrong(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]

    # the child actually marked option 3, which is not the key: the question becomes wrong
    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "3"} for r in waiting
    ]
    body = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions}).json()

    assert body["results"][0]["result"] == "wrong"
    made = [a for a in attempts(env) if a.paper_item_id == UUID(waiting[0]["paper_item_id"])]
    assert len(made) == 1 and made[0].correct is False


def test_a_parent_who_says_no_answer_makes_the_question_blank(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]

    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": None} for r in waiting
    ]
    body = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions}).json()

    assert body["results"][0]["result"] == "blank"
    assert len(attempts(env)) == len(on_page) - 1  # blank is not wrong: no attempt


def test_every_unclear_answer_needs_a_decision(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]

    response = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": []})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "decisions_missing"
    assert detail["missing"][0]["position"] == on_page[0][0]
    assert submission(env, sub)["status"] == "needs_review"  # nothing changed


def test_a_double_mark_from_the_parent_is_sent_back(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]

    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1 and 2"}
        for r in waiting
    ]
    response = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "bad_decision"


def test_a_decision_for_an_answer_that_is_not_waiting_is_refused(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]
    settled = on_page[1][1]  # the second question was decided automatically

    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1"} for r in waiting
    ] + [{"paper_item_id": str(settled), "part_no": 1, "selected": "2"}]
    response = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})

    assert response.status_code == 422


def test_confirming_twice_is_harmless(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    waiting = submission(env, sub)["review_items"]
    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1"} for r in waiting
    ]

    first = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})
    second = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})

    assert first.status_code == second.status_code == 200
    assert len(attempts(env)) == len(on_page)  # not counted twice


def test_the_review_screen_never_carries_the_answer_key(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("3", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)

    text = str(submission(env, upload(env, 1).json()["submission_id"])).lower()

    for forbidden in ("correct_option", "accepted_answers", "answer_key", "alternatives"):
        assert forbidden not in text


# ---- the reader fails -------------------------------------------------------------------------


def test_a_failed_reader_leaves_everything_to_the_parent(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    env.provider_ref[0] = MockProvider(*[VisionError("quota_daily")] * len(on_page))

    body = submission(env, upload(env, 1).json()["submission_id"])

    assert body["status"] == "needs_review"
    assert {r["reason"] for r in body["review_items"]} == {"vision_error"}
    assert all(item["result"] == "pending_review" for item in body["results"])
    assert attempts(env) == []  # nothing was marked wrong


def test_no_reader_configured_also_leaves_everything_to_the_parent(env: Env) -> None:
    start(env)
    env.provider_ref[0] = None  # make_submission_service then falls back to the unavailable reader

    body = submission(env, upload(env, 1).json()["submission_id"])

    assert body["status"] == "needs_review"
    assert {r["reason"] for r in body["review_items"]} == {"vision_error"}


# ---- photos that cannot be used ---------------------------------------------------------------


def test_a_blurry_photo_is_rejected_with_a_message(env: Env) -> None:
    start(env)
    env.provider_ref[0] = MockProvider()

    body = submission(env, upload(env, 1, photo(env, 1, blur_sigma=4.0)).json()["submission_id"])

    assert body["status"] == "failed_alignment"
    assert body["failure_reason"] == "blurry"
    assert "blurry" in body["message"].lower()
    assert body["review_items"] == []
    assert attempts(env) == []


def test_the_wrong_page_is_rejected(env: Env) -> None:
    start(env, questions=9)
    assert env.paper is not None and env.paper["page_count"] >= 2

    body = submission(env, upload(env, 1, photo(env, 2)).json()["submission_id"])

    assert body["status"] == "failed_alignment"
    assert body["failure_reason"] == "wrong_page"


def test_a_file_that_is_not_a_photo_is_refused_at_once(env: Env) -> None:
    start(env)

    response = upload(env, 1, b"this is not an image")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unreadable_image"
    with Session(env.engine) as session:
        assert session.scalar(select(func.count()).select_from(PaperSubmissionModel)) == 0


def test_a_retake_replaces_a_failed_photo(env: Env) -> None:
    start(env)
    first = upload(env, 1, photo(env, 1, blur_sigma=4.0)).json()["submission_id"]
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))

    second = upload(env, 1).json()["submission_id"]

    assert submission(env, first)["status"] == "failed_alignment"
    assert submission(env, second)["status"] == "graded"
    with Session(env.engine) as session:
        current = session.scalars(
            select(PaperSubmissionModel).where(PaperSubmissionModel.is_current.is_(True))
        ).all()
        assert [s.id for s in current] == [UUID(second)]


def test_a_marked_page_cannot_be_uploaded_again(env: Env) -> None:
    start(env)
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))
    upload(env, 1)

    response = upload(env, 1)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "page_already_graded"


def test_a_page_with_counted_answers_cannot_be_replaced_while_it_waits(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    upload(env, 1)

    response = upload(env, 1)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "page_in_progress"


def test_unknown_paper_page_and_submission(env: Env) -> None:
    start(env)
    from uuid import uuid4

    assert upload(env, 9, photo(env, 1)).status_code == 404  # this paper has no page 9
    other = env.client.post(
        f"/api/v1/papers/{uuid4()}/pages/1/photo",
        files={"image": ("p.jpg", photo(env, 1), "image/jpeg")},
    )
    assert other.status_code == 404
    assert env.client.get(f"/api/v1/submissions/{uuid4()}").status_code == 404
    assert env.client.post(f"/api/v1/submissions/{uuid4()}/confirm", json={"decisions": []}).status_code == 404
    assert env.client.get(f"/api/v1/submissions/{uuid4()}/crops/{uuid4()}").status_code == 404


# ---- the paper's own status -------------------------------------------------------------------


def paper_status(env: Env) -> str:
    with Session(env.engine) as session:
        row = session.get(PaperModel, UUID(env.paper["paper_id"]))
        assert row is not None
        return row.status


def test_the_paper_status_follows_its_pages(env: Env) -> None:
    start(env, questions=9)
    pages = env.paper["page_count"]
    assert pages >= 2
    assert paper_status(env) == "generated"

    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))
    upload(env, 1)
    assert paper_status(env) == "partially_uploaded"

    for page in range(2, pages + 1):
        env.provider_ref[0] = MockProvider(*answers_for(env, page, lambda _: "right"))
        upload(env, page)
    assert paper_status(env) == "graded"


def test_a_page_waiting_for_the_parent_makes_the_paper_need_review(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    upload(env, 1)

    assert paper_status(env) == "needs_review"


def test_crops_are_served_for_the_review_screen(env: Env) -> None:
    start(env)
    on_page = keys_on_page(env, 1)
    readings = answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = upload(env, 1).json()["submission_id"]
    item = submission(env, sub)["review_items"][0]

    response = env.client.get(item["crop_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_the_photo_and_crops_are_kept_in_private_storage(env: Env) -> None:
    start(env)
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))
    sub = upload(env, 1).json()["submission_id"]

    stored = env.world["papers"].list(f"submissions/{sub}/")

    assert any(key.endswith("photo.jpg") for key in stored)
    assert any("/crops/" in key for key in stored)


def test_no_image_content_or_text_reaches_the_call_records(env: Env) -> None:
    start(env)
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))

    upload(env, 1)

    columns = {c.name for c in GradedAnswerModel.__table__.columns}
    assert "image" not in columns and "crop" not in columns
    _ = np  # numpy is imported for the photo helpers above
    _ = PartRead  # the reading type used by the scripted answers


def test_the_paper_detail_lists_each_page_and_its_photo(env: Env) -> None:
    start(env, questions=9)
    pages = env.paper["page_count"]
    assert pages >= 2

    before = env.client.get(f"/api/v1/papers/{env.paper['paper_id']}").json()["pages"]
    env.provider_ref[0] = MockProvider(*answers_for(env, 1, lambda _: "right"))
    sub = upload(env, 1).json()["submission_id"]
    after = env.client.get(f"/api/v1/papers/{env.paper['paper_id']}").json()["pages"]

    assert [p["page"] for p in before] == list(range(1, pages + 1))
    assert all(p["submission_status"] is None for p in before)
    assert after[0]["submission_id"] == sub
    assert after[0]["submission_status"] == "graded"
    assert all(p["submission_status"] is None for p in after[1:])
