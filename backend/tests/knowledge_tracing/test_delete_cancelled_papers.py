"""scripts.delete_cancelled_papers: remove replaced papers for good, and nothing else."""

from uuid import uuid4

from sqlalchemy import func, select

from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    GradedAnswerModel,
    PaperItemModel,
    PaperModel,
    PaperSubmissionModel,
)
from knowledge_tracing import test_weekly_paper as weekly
from knowledge_tracing.test_weekly_paper import MONDAY, give_history, learner, service
from scripts.delete_cancelled_papers import delete_cancelled_papers

world = weekly.world  # the weekly-paper test world (a question bank, storage and a database), reused


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def mark_page_one(world: dict, paper_id) -> None:
    """What uploading and grading leave behind: a photo record, a marked answer, a saved answer."""
    db = world["db"]
    item = db.scalars(select(PaperItemModel).where(PaperItemModel.paper_id == paper_id)).first()
    submission = PaperSubmissionModel(id=uuid4(), paper_id=paper_id, page=1, image_key="photos/x.jpg", status="graded")
    db.add(submission)
    db.flush()
    db.add(
        GradedAnswerModel(
            id=uuid4(), submission_id=submission.id, paper_item_id=item.id, vision_provider="mock",
            vision_model="mock", prompt_version="v1", auto_status="wrong",
        )
    )
    db.add(
        AttemptModel(
            learner_id=db.get(PaperModel, paper_id).learner_id, question_id=item.question_id, language="si",
            source=0, correct=False, penalty=0.08, answered_at=MONDAY, paper_item_id=item.id,
        )
    )
    db.commit()


def test_cancelled_papers_go_with_their_photo_and_marking_records(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    old = svc.generate_weekly(learner_id).paper
    mark_page_one(world, old.id)
    svc.cancel(old.id)
    live = svc.generate_weekly(learner_id).paper
    db = world["db"]

    found = delete_cancelled_papers(db, learner_id)

    assert found["papers"] == 1 and found["photo records"] == 1 and found["marked answers"] == 1
    assert db.get(PaperModel, old.id) is None
    assert count(db, PaperSubmissionModel) == 0 and count(db, GradedAnswerModel) == 0
    assert not db.scalars(select(PaperItemModel).where(PaperItemModel.paper_id == old.id)).all()
    assert db.get(PaperModel, live.id) is not None  # the live paper is never touched
    assert db.scalars(select(PaperItemModel).where(PaperItemModel.paper_id == live.id)).all()


def test_the_childs_saved_answers_stay_so_the_estimates_do_not_change(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    old = svc.generate_weekly(learner_id).paper
    mark_page_one(world, old.id)
    svc.cancel(old.id)
    db = world["db"]
    before = count(db, AttemptModel)

    found = delete_cancelled_papers(db, learner_id)

    assert found["answers still in the history"] == 1
    assert count(db, AttemptModel) == before


def test_a_dry_run_changes_nothing(world: dict) -> None:
    learner_id = learner(world)
    svc = service(world)
    old = svc.generate_weekly(learner_id).paper
    svc.cancel(old.id)
    db = world["db"]

    found = delete_cancelled_papers(db, learner_id, dry_run=True)

    assert found["papers"] == 1 and db.get(PaperModel, old.id) is not None


def test_another_learners_cancelled_papers_are_left_alone(world: dict) -> None:
    mine, theirs = learner(world), learner(world)
    svc = service(world)
    for who in (mine, theirs):
        svc.cancel(svc.generate_weekly(who).paper.id)
    db = world["db"]

    delete_cancelled_papers(db, mine)

    assert [p.learner_id for p in db.scalars(select(PaperModel)).all()] == [theirs]
