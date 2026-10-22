"""Clear this week's paper of a learner and make a new one (testing and demos).

    python -m scripts.redo_paper --clear --purge              # only clear it: the app shows the button again
    python -m scripts.redo_paper                              # the shared development learner
    python -m scripts.redo_paper <learner-uuid> --mode practice --questions 8 --pages 1 --minutes 20
    python -m scripts.redo_paper <learner-uuid> --purge       # also forget answers marked from the old paper

A learner gets one paper per week, and asking again returns the same one. This cancels this week's paper
(it stays in the history, marked cancelled), reads the game's newest answers if automatic reading is on,
and makes a new paper from what the model knows now, so you can try the paper as often as you like.

If nobody has started on the old paper, that is all. If pages were already photographed or answers were
saved from it, it stops and says so, because those answers are already part of the child's history. Then
choose: --keep-answers clears the paper and KEEPS those answers (the model keeps what it learned from
them), or --purge deletes them too (and the estimates are recomputed), so the child's history is as if that
paper had never been marked. The old page photos stay on disk. Development databases only.
"""

import argparse
import sys
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.api.game_sync import read_new_game_answers
from app.knowledge_tracing.api.mastery_router import get_estimator
from app.knowledge_tracing.api.papers_router import (
    get_paper_storage,
    get_question_storage,
    make_paper_service,
)
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_generation import (
    GeneratedPaper,
    PaperRequest,
    PaperService,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.domain.paper import Paper
from app.knowledge_tracing.infrastructure.db.mastery_repository import SqlAlchemyMasteryRepository
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    PaperItemModel,
    PaperSubmissionModel,
)
from app.shared.database.session import SessionLocal

DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"  # the learner the game and the papers share


class PaperInUse(Exception):
    """The old paper already has photos or saved answers, and --purge was not given."""

    def __init__(self, photos: int, answers: int) -> None:
        super().__init__(f"{photos} photo upload(s) and {answers} saved answer(s)")
        self.photos = photos
        self.answers = answers


@dataclass
class Redone:
    cancelled: Paper | None
    removed_answers: int
    new: GeneratedPaper | None  # None when only clearing


def redo_paper(
    db: Session,
    service: PaperService,
    mastery: MasteryService,
    learner_id: UUID,
    request: PaperRequest,
    *,
    purge: bool = False,
    keep_answers: bool = False,
    make_new: bool = True,
) -> Redone:
    cancelled: Paper | None = None
    removed = 0
    current = service.current(learner_id)
    if current is not None:
        paper = current.paper
        item_ids = select(PaperItemModel.id).where(PaperItemModel.paper_id == paper.id)
        photos = db.scalar(
            select(func.count()).select_from(PaperSubmissionModel).where(PaperSubmissionModel.paper_id == paper.id)
        )
        answers = db.scalar(select(func.count()).select_from(AttemptModel).where(AttemptModel.paper_item_id.in_(item_ids)))
        if (photos or answers) and not (purge or keep_answers):
            raise PaperInUse(photos or 0, answers or 0)
        if answers and purge and not keep_answers:  # only --purge deletes; --keep-answers never does
            db.execute(delete(AttemptModel).where(AttemptModel.paper_item_id.in_(item_ids)))
            db.commit()
            removed = answers
        service.cancel(paper.id)
        cancelled = paper
    if not make_new:
        return Redone(cancelled, removed, None)
    mastery.refresh(learner_id)  # the new paper is built from the estimates as they are now
    return Redone(cancelled, removed, service.generate_weekly(learner_id, request))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner_id", nargs="?", type=UUID, default=UUID(DEFAULT_LEARNER_ID))
    parser.add_argument("--mode", choices=("auto", "practice", "diagnostic"), default="auto")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--pages", type=int, default=4)
    parser.add_argument("--minutes", type=int, default=35)
    parser.add_argument("--language", choices=("si", "ta"))
    parser.add_argument("--purge", action="store_true", help="also delete answers already marked from the old paper")
    parser.add_argument(
        "--keep-answers", action="store_true",
        help="clear the paper even if it was already marked, and KEEP its answers in the child's history",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="only clear this week's paper; the app then shows the 'Make this week's paper' button again",
    )
    args = parser.parse_args(argv)

    request = PaperRequest(
        max_questions=args.questions, max_minutes=args.minutes, max_pages=args.pages,
        mode=args.mode, language=args.language,
    )
    with SessionLocal() as session:
        read_new_game_answers(session, args.learner_id)  # only does anything when automatic reading is on
        estimator = get_estimator()
        service = make_paper_service(session, estimator, get_question_storage(), get_paper_storage())
        mastery = MasteryService(SqlAlchemyMasteryRepository(session), estimator, get_feature_spec())
        try:
            done = redo_paper(
                session, service, mastery, args.learner_id, request, purge=args.purge,
                keep_answers=args.keep_answers, make_new=not args.clear
            )
        except PaperInUse as error:
            print(
                f"not changed: this week's paper already has {error}. Those answers are part of the child's "
                "history. Run again with --purge to delete them too, or use another learner.",
                file=sys.stderr,
            )
            return 1

    if done.cancelled is not None:
        print(f"cancelled the old paper {done.cancelled.token}"
              + (f" and deleted {done.removed_answers} marked answer(s)" if done.removed_answers else ""))
    if done.new is None:
        if done.cancelled is None:
            print("this learner has no paper this week: nothing to clear")
        print("the Practice tab now shows the 'Make this week's paper' button")
        return 0
    paper = done.new.paper
    print(f"new paper {paper.token}: {paper.mode}, {len(done.new.items)} questions on {paper.page_count} page(s), "
          f"about {paper.estimated_minutes:.0f} min")
    for item in done.new.items:
        print(f"  {item.position:>2}  page {item.page}  {item.skill_code:8} {item.shown_difficulty:7} {item.role}")
    print("open the Practice tab to see it; python -m scripts.show_paper_mix shows it with the estimates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
