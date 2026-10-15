"""Make this week's paper for every learner. Schedule it for Saturday morning.

    python -m scripts.generate_weekly_papers             # every learner
    python -m scripts.generate_weekly_papers --dry-run   # only list who would get a paper

A week runs Saturday to Friday (Sri Lanka time). A learner who already has this week's paper is
skipped, so running the script again, or on another day, never makes a second paper. A learner who
joined less than PAPER_MIN_DAYS_AFTER_JOINING days ago is skipped too. Children normally get their
paper by pressing the button in the app; this script only makes papers ahead of time.

Exit status: 0 when every learner has a paper, 1 if any learner failed (so a scheduler can alert).
"""

import argparse
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.knowledge_tracing.api.papers_router import make_paper_service
from app.knowledge_tracing.application.paper_generation import (
    PaperRequest,
    PaperService,
    next_paper_date,
    week_start_for,
)
from app.knowledge_tracing.application.weekly_batch import generate_weekly_batch
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.knowledge_tracing.infrastructure.storage import create_paper_storage, create_storage
from app.shared.database.session import SessionLocal
from app.shared.learner.model import LearnerModel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="list learners, make nothing")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--minutes", type=int, default=35)
    parser.add_argument("--pages", type=int, default=4)
    args = parser.parse_args()

    now = datetime.now(UTC)
    week = week_start_for(now)
    print(f"week: {week} (Saturday) to {next_paper_date(week)} (next paper)")

    with SessionLocal() as session:
        learner_ids = list(session.scalars(select(LearnerModel.id).order_by(LearnerModel.created_at)))
    print(f"learners: {len(learner_ids)}")
    if args.dry_run:
        return 0

    settings = get_settings()
    model = get_knowledge_model()
    question_storage = create_storage(settings)
    paper_storage = create_paper_storage(settings)

    @contextmanager
    def scope() -> Iterator[PaperService]:
        with SessionLocal() as session:
            yield make_paper_service(session, model, question_storage, paper_storage)

    request = PaperRequest(
        max_questions=args.questions, max_minutes=args.minutes, max_pages=args.pages
    )
    result = generate_weekly_batch(learner_ids, scope, request)

    print(f"made: {len(result.created)}   already had one: {len(result.already_had)}   "
          f"not eligible yet: {len(result.not_eligible)}   failed: {len(result.failed)}")
    for learner_id, reason in result.failed:
        print(f"  FAILED {learner_id}: {reason}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
