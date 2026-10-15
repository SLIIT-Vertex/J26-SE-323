"""The parent's result report and how long the child's photos are kept."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.retention import (
    KEEP_AFTER_UPLOAD,
    KEEP_AFTER_VIEW,
    RetentionService,
    photos_available,
    photos_expire_at,
)
from app.knowledge_tracing.domain.submission import Submission
from app.knowledge_tracing.infrastructure.db.models import (
    GradedAnswerModel,
    PaperSubmissionModel,
)
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading
from tests.knowledge_tracing import test_submissions as ts

world = ts.world
env = ts.env

DAY = timedelta(days=1)
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def submission_at(uploaded: datetime, viewed: datetime | None = None, deleted: datetime | None = None):
    return Submission(uuid4(), uuid4(), 1, "k", "graded", None, None, True, uploaded, viewed, deleted)


# ---- the rule ---------------------------------------------------------------------------------


def test_never_opened_photos_go_30_days_after_the_upload() -> None:
    assert photos_expire_at(submission_at(T0)) == T0 + KEEP_AFTER_UPLOAD == T0 + 30 * DAY


def test_after_the_report_is_opened_they_get_one_more_week() -> None:
    opened_day_2 = submission_at(T0, viewed=T0 + 2 * DAY)

    assert photos_expire_at(opened_day_2) == T0 + 2 * DAY + KEEP_AFTER_VIEW == T0 + 9 * DAY


def test_one_more_week_never_goes_past_the_30_days() -> None:
    opened_day_28 = submission_at(T0, viewed=T0 + 28 * DAY)

    assert photos_expire_at(opened_day_28) == T0 + 30 * DAY


def test_a_time_without_a_zone_is_taken_as_utc() -> None:
    naive = submission_at(datetime(2026, 11, 1, 9, 0))

    assert photos_expire_at(naive) == T0 + 30 * DAY


def test_availability_follows_the_deadline_and_the_deleted_mark() -> None:
    page = submission_at(T0, viewed=T0 + DAY)

    assert photos_available(page, T0 + 7 * DAY)
    assert not photos_available(page, T0 + 8 * DAY)
    assert not photos_available(submission_at(T0, deleted=T0 + DAY), T0 + 2 * DAY)


# ---- a marked page with some mistakes ---------------------------------------------------------


def mixed_page(env: ts.Env) -> tuple[str, list]:
    """Question 1 wrong, question 2 blank, the rest right. Returns the submission and the page."""
    ts.start(env)
    on_page = ts.keys_on_page(env, 1)
    assert len(on_page) >= 3
    outcomes = {1: "wrong", 2: "blank"}
    env.provider_ref[0] = MockProvider(
        *ts.answers_for(env, 1, lambda position: outcomes.get(position, "right"))
    )
    return ts.upload(env, 1).json()["submission_id"], on_page


def report(env: ts.Env, **query: str) -> dict:
    assert env.paper is not None
    response = env.client.get(f"/api/v1/papers/{env.paper['paper_id']}/report", params=query)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_report_lists_what_the_child_got_wrong_and_the_answers_separately(env: ts.Env) -> None:
    _, on_page = mixed_page(env)

    body = report(env)

    assert body["summary"]["marked"] == len(on_page)
    assert body["summary"]["correct"] == len(on_page) - 2
    assert (body["summary"]["wrong"], body["summary"]["blank"]) == (1, 1)
    assert [(m["position"], m["result"]) for m in body["mistakes"]] == [(1, "wrong"), (2, "blank")]
    wrong = body["mistakes"][0]
    assert wrong["written"][0]["text"] == "3"  # what the child marked
    assert wrong["skill_name"]  # a name, not only a code
    assert body["mistakes"][1]["written"][0]["text"] is None  # nothing written

    # the correct answers are a separate list, by question number, not inside the mistakes
    assert [a["position"] for a in body["answer_list"]] == [1, 2]
    assert body["answer_list"][0]["answers"][0]["answer"] == "1"
    for mistake in body["mistakes"]:
        assert "answer" not in str(mistake).replace("answers", "")
        assert "correct_answer" not in mistake


def test_questions_the_child_got_right_are_not_in_the_report_lists(env: ts.Env) -> None:
    _, on_page = mixed_page(env)

    body = report(env)

    positions = {m["position"] for m in body["mistakes"]} | {a["position"] for a in body["answer_list"]}
    assert positions == {1, 2}  # nothing else, and no answers for what was right
    assert sum(s["correct"] for s in body["skills"]) == len(on_page) - 2
    assert sum(s["wrong"] + s["blank"] for s in body["skills"]) == 2


def test_questions_waiting_for_the_parent_show_neither_result_nor_answer(env: ts.Env) -> None:
    ts.start(env)
    on_page = ts.keys_on_page(env, 1)
    readings = ts.answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("3", 0.2)] * len(on_page[0][2]))  # the reader was unsure
    env.provider_ref[0] = MockProvider(*readings)
    ts.upload(env, 1)

    body = report(env)

    assert body["summary"]["waiting_for_parent"] == 1
    assert body["mistakes"] == []
    assert body["answer_list"] == []  # no answer is given for an undecided question
    assert body["complete"] is False


def test_pages_without_a_photo_are_counted_not_guessed(env: ts.Env) -> None:
    ts.start(env, questions=9)
    assert env.paper is not None and env.paper["page_count"] >= 2
    env.provider_ref[0] = MockProvider(*ts.answers_for(env, 1, lambda _: "right"))
    ts.upload(env, 1)

    body = report(env)

    assert body["pages_marked"] == 1 and body["pages_total"] == env.paper["page_count"]
    assert body["summary"]["not_uploaded"] > 0
    assert body["complete"] is False


def test_a_fully_marked_paper_is_complete(env: ts.Env) -> None:
    ts.start(env)
    env.provider_ref[0] = MockProvider(*ts.answers_for(env, 1, lambda _: "right"))
    ts.upload(env, 1)

    body = report(env)

    assert env.paper is not None
    if env.paper["page_count"] == 1:
        assert body["complete"] is True
    assert body["summary"]["wrong"] == 0
    assert body["next_paper_date"] == env.paper["next_paper_date"]


def test_the_report_after_a_parents_decision_uses_what_the_parent_said(env: ts.Env) -> None:
    ts.start(env)
    on_page = ts.keys_on_page(env, 1)
    readings = ts.answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = ts.upload(env, 1).json()["submission_id"]
    waiting = ts.submission(env, sub)["review_items"]
    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "2"} for r in waiting
    ]
    env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})

    body = report(env)

    assert body["mistakes"][0]["position"] == on_page[0][0]
    assert body["mistakes"][0]["written"][0]["text"] == "2"


def test_the_report_of_an_unknown_paper_is_not_found(env: ts.Env) -> None:
    assert env.client.get(f"/api/v1/papers/{uuid4()}/report").status_code == 404


def test_the_review_screen_still_has_no_answers_even_with_the_report_in_place(env: ts.Env) -> None:
    ts.start(env)
    on_page = ts.keys_on_page(env, 1)
    readings = ts.answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("3", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)

    review = str(ts.submission(env, ts.upload(env, 1).json()["submission_id"]))

    assert "answer_list" not in review and "correct_answer" not in review


# ---- the 7-day timer and the pictures ---------------------------------------------------------


def stored(env: ts.Env, submission_id: str) -> PaperSubmissionModel:
    with Session(env.engine) as session:
        row = session.get(PaperSubmissionModel, UUID(submission_id))
        assert row is not None
        session.expunge(row)
        return row


def test_opening_the_report_starts_the_seven_day_timer_but_peeking_does_not(env: ts.Env) -> None:
    sub, _ = mixed_page(env)

    report(env, peek="true")
    assert stored(env, sub).report_viewed_at is None

    body = report(env)
    row = stored(env, sub)
    assert row.report_viewed_at is not None
    assert body["photos_kept_until"] is not None
    kept_until = datetime.fromisoformat(body["photos_kept_until"])
    assert kept_until.replace(tzinfo=UTC) - row.report_viewed_at.replace(tzinfo=UTC) == KEEP_AFTER_VIEW


def test_the_first_view_is_never_moved(env: ts.Env) -> None:
    sub, _ = mixed_page(env)
    report(env)
    first = stored(env, sub).report_viewed_at

    report(env)

    assert stored(env, sub).report_viewed_at == first


def test_a_report_with_nothing_to_see_does_not_start_the_timer(env: ts.Env) -> None:
    ts.start(env)  # nothing uploaded

    report(env)

    with Session(env.engine) as session:
        assert session.scalars(select(PaperSubmissionModel.report_viewed_at)).all() == []


def test_the_pictures_are_served_until_their_time_is_up(env: ts.Env) -> None:
    sub, _ = mixed_page(env)
    body = report(env)
    picture = body["mistakes"][0]
    assert picture["picture_available"] is True

    served = env.client.get(picture["picture_url"])
    assert served.status_code == 200 and served.content.startswith(b"\x89PNG")

    # 31 days later the files may still be there, but they are no longer shown or served
    with Session(env.engine) as session:
        session.execute(
            update(PaperSubmissionModel)
            .where(PaperSubmissionModel.id == UUID(sub))
            .values(uploaded_at=datetime.now(UTC) - 31 * DAY)
        )
        session.commit()
    later = report(env, peek="true")
    assert later["mistakes"][0]["picture_available"] is False
    assert later["mistakes"][0]["picture_url"] is None
    assert env.client.get(picture["picture_url"]).status_code == 410
    assert later["mistakes"][0]["written"][0]["text"] == "3"  # the text part survives


def test_an_answer_cannot_be_decided_once_its_photos_are_gone(env: ts.Env) -> None:
    ts.start(env)
    on_page = ts.keys_on_page(env, 1)
    readings = ts.answers_for(env, 1, lambda _: "right")
    readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))
    env.provider_ref[0] = MockProvider(*readings)
    sub = ts.upload(env, 1).json()["submission_id"]
    waiting = ts.submission(env, sub)["review_items"]
    with Session(env.engine) as session:
        session.execute(
            update(PaperSubmissionModel)
            .where(PaperSubmissionModel.id == UUID(sub))
            .values(uploaded_at=datetime.now(UTC) - 40 * DAY)
        )
        session.commit()

    decisions = [
        {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1"} for r in waiting
    ]
    response = env.client.post(f"/api/v1/submissions/{sub}/confirm", json={"decisions": decisions})

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "photos_removed"


# ---- the cleanup ------------------------------------------------------------------------------


def sweep(env: ts.Env, when: datetime, dry_run: bool = False):
    with Session(env.engine) as session:
        return RetentionService(
            SqlAlchemySubmissionRepository(session), env.world["papers"], lambda: when
        ).sweep(dry_run=dry_run)


def files_of(env: ts.Env, submission_id: str) -> list[str]:
    return env.world["papers"].list(f"submissions/{submission_id}/")


def test_nothing_is_deleted_before_the_time(env: ts.Env) -> None:
    sub, _ = mixed_page(env)

    result = sweep(env, datetime.now(UTC) + 29 * DAY)

    assert (result.submissions, result.files) == (0, 0)
    assert files_of(env, sub)


def test_photos_are_deleted_after_30_days(env: ts.Env) -> None:
    sub, _ = mixed_page(env)
    before = files_of(env, sub)
    assert any(k.endswith("photo.jpg") for k in before)

    result = sweep(env, datetime.now(UTC) + 31 * DAY)

    assert result.submissions == 1 and result.files == len(before)
    assert files_of(env, sub) == []
    assert stored(env, sub).files_deleted_at is not None
    with Session(env.engine) as session:
        keys = session.scalars(
            select(GradedAnswerModel.crop_key).where(GradedAnswerModel.submission_id == UUID(sub))
        ).all()
        assert keys and all(k is None for k in keys)  # no pointer to a deleted file is kept


def test_photos_are_deleted_a_week_after_the_report_was_opened(env: ts.Env) -> None:
    sub, _ = mixed_page(env)
    report(env)  # opened now

    too_early = sweep(env, datetime.now(UTC) + 6 * DAY)
    assert too_early.submissions == 0 and files_of(env, sub)

    result = sweep(env, datetime.now(UTC) + 8 * DAY)
    assert result.submissions == 1
    assert files_of(env, sub) == []


def test_a_dry_run_deletes_nothing(env: ts.Env) -> None:
    sub, _ = mixed_page(env)
    count = len(files_of(env, sub))

    result = sweep(env, datetime.now(UTC) + 31 * DAY, dry_run=True)

    assert result.submissions == 1 and result.files == count
    assert len(files_of(env, sub)) == count
    assert stored(env, sub).files_deleted_at is None


def test_running_the_cleanup_twice_does_nothing_more(env: ts.Env) -> None:
    mixed_page(env)
    when = datetime.now(UTC) + 31 * DAY
    sweep(env, when)

    again = sweep(env, when)

    assert (again.submissions, again.files) == (0, 0)


def test_the_marking_and_the_report_text_outlive_the_photos(env: ts.Env) -> None:
    sub, on_page = mixed_page(env)
    sweep(env, datetime.now(UTC) + 31 * DAY)

    with Session(env.engine) as session:
        # the sweep ran "in the future": make the data look that old too
        session.execute(
            update(PaperSubmissionModel)
            .where(PaperSubmissionModel.id == UUID(sub))
            .values(uploaded_at=datetime.now(UTC) - 31 * DAY)
        )
        session.commit()
    body = report(env, peek="true")

    assert body["summary"]["marked"] == len(on_page)
    assert body["mistakes"][0]["picture_available"] is False
    assert body["answer_list"]  # the answers list does not depend on the pictures


def test_files_that_cannot_be_deleted_are_tried_again_next_time(
    env: ts.Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, _ = mixed_page(env)
    storage = env.world["papers"]
    original = storage.delete

    def failing(key: str) -> None:
        raise OSError("disk busy")

    monkeypatch.setattr(storage, "delete", failing)
    first = sweep(env, datetime.now(UTC) + 31 * DAY)
    assert first.submissions == 0
    assert stored(env, sub).files_deleted_at is None  # not claimed as gone

    monkeypatch.setattr(storage, "delete", original)
    second = sweep(env, datetime.now(UTC) + 31 * DAY)
    assert second.submissions == 1
