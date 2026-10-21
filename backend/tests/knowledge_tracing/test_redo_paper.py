"""scripts.redo_paper: clear this week's paper and make another, without losing anyone's answers by accident."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.knowledge_tracing.api import papers_router
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_generation import PaperRequest
from app.knowledge_tracing.infrastructure.db.mastery_repository import SqlAlchemyMasteryRepository
from app.knowledge_tracing.infrastructure.db.models import AttemptModel, PaperItemModel, PaperModel
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from knowledge_tracing import test_weekly_paper as weekly
from knowledge_tracing.test_weekly_paper import (
    MONDAY,
    SPEC,
    give_history,
    learner,
    service,
)
from scripts.redo_paper import PaperInUse, redo_paper

world = weekly.world  # the weekly-paper test world (a question bank, storage and a database), reused

REQUEST = PaperRequest(max_questions=8, max_pages=1, max_minutes=20, mode="practice")


def mastery_for(world: dict) -> MasteryService:
    return MasteryService(SqlAlchemyMasteryRepository(world["db"]), get_knowledge_model(), SPEC, lambda: MONDAY)


def mark_one_answer(world: dict, learner_id, paper_id) -> None:
    """What grading saves: a paper answer tied to one of the paper's items."""
    db = world["db"]
    item = db.scalars(select(PaperItemModel).where(PaperItemModel.paper_id == paper_id)).first()
    db.add(
        AttemptModel(
            learner_id=learner_id, question_id=item.question_id, language="si", source=0, correct=False,
            penalty=0.08, answered_at=MONDAY + timedelta(hours=1), paper_item_id=item.id,
        )
    )
    db.commit()


def test_it_cancels_the_old_paper_and_makes_a_new_one(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    first = svc.generate_weekly(learner_id)

    done = redo_paper(world["db"], svc, mastery_for(world), learner_id, REQUEST)

    assert done.cancelled is not None and done.cancelled.id == first.paper.id
    assert done.new.created and done.new.paper.id != first.paper.id
    assert done.new.paper.mode == "practice" and 1 <= len(done.new.items) <= 8
    old = world["db"].get(PaperModel, first.paper.id)
    assert old.status == "cancelled"  # kept in the history, not deleted


def test_with_no_paper_yet_it_just_makes_one(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)

    done = redo_paper(world["db"], service(world), mastery_for(world), learner_id, REQUEST)

    assert done.cancelled is None and done.removed_answers == 0 and done.new.created


def test_it_can_be_repeated_as_often_as_wanted(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    tokens = {svc.generate_weekly(learner_id).paper.token}

    for _ in range(3):
        tokens.add(redo_paper(world["db"], svc, mastery_for(world), learner_id, REQUEST).new.paper.token)

    assert len(tokens) == 4


def test_it_refuses_while_answers_from_the_paper_are_in_the_history(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    paper = svc.generate_weekly(learner_id).paper
    mark_one_answer(world, learner_id, paper.id)

    with pytest.raises(PaperInUse) as refused:
        redo_paper(world["db"], svc, mastery_for(world), learner_id, REQUEST)

    assert refused.value.answers == 1
    assert world["db"].get(PaperModel, paper.id).status != "cancelled"  # nothing was changed


def test_purge_forgets_those_answers_and_makes_the_new_paper(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    paper = svc.generate_weekly(learner_id).paper
    mark_one_answer(world, learner_id, paper.id)
    paper_answers = select(func.count()).select_from(AttemptModel).where(AttemptModel.source == 0)
    assert world["db"].scalar(paper_answers) == 1

    done = redo_paper(world["db"], svc, mastery_for(world), learner_id, REQUEST, purge=True)

    assert done.removed_answers == 1 and done.new.created
    assert world["db"].scalar(paper_answers) == 0  # the child's history no longer holds that answer
    games = select(func.count()).select_from(AttemptModel).where(AttemptModel.source == 1)
    assert world["db"].scalar(games) == 22 * 5  # and nothing else was touched


# ---- clearing only, and what the "Make this week's paper" button builds -----------------------------


def test_clearing_only_leaves_the_week_free_for_the_button(world: dict) -> None:
    learner_id = learner(world)
    give_history(world, learner_id)
    svc = service(world)
    svc.generate_weekly(learner_id)

    done = redo_paper(world["db"], svc, mastery_for(world), learner_id, REQUEST, make_new=False)

    assert done.cancelled is not None and done.new is None
    assert svc.current(learner_id) is None  # no live paper: the app shows the button again
    assert svc.availability(learner_id).state == "available"


client = weekly.client


@pytest.fixture
def default_mode(monkeypatch: pytest.MonkeyPatch):
    def set_(mode: str) -> None:
        settings = get_settings().model_copy(update={"paper_default_mode": mode})
        monkeypatch.setattr(papers_router, "get_settings", lambda: settings)

    return set_


def test_a_request_without_a_mode_gets_the_configured_default(world: dict, client, default_mode) -> None:
    learner_id = weekly.learner(world)
    give_history(world, learner_id, skills=5)  # too few skills known: "auto" would build a check-up

    default_mode("auto")
    assert client.post(f"/api/v1/learners/{learner_id}/papers").json()["mode"] == "diagnostic"

    client.post(f"/api/v1/papers/{client.get(f'/api/v1/learners/{learner_id}/papers/current').json()['paper_id']}/cancel")
    default_mode("practice")
    assert client.post(f"/api/v1/learners/{learner_id}/papers").json()["mode"] == "practice"


def test_a_mode_named_in_the_request_beats_the_default(world: dict, client, default_mode) -> None:
    learner_id = weekly.learner(world)
    give_history(world, learner_id, skills=5)
    default_mode("practice")

    assert client.post(f"/api/v1/learners/{learner_id}/papers", json={"mode": "diagnostic"}).json()["mode"] == "diagnostic"
