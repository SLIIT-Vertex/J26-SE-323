"""Delete a learner's cancelled papers from the database (testing and demos).

    python -m scripts.delete_cancelled_papers --dry-run          # the shared development learner: only count
    python -m scripts.delete_cancelled_papers
    python -m scripts.delete_cancelled_papers <learner-uuid>

Papers get cancelled when you make another one in the same week (scripts.redo_paper, or the cancel call).
The app no longer lists them, but the rows stay in the database. This removes them for good, with the page
photo records and the marking records that belong to them.

It does NOT remove the answers already saved in the child's history, so the model's estimates do not change
(use `scripts.redo_paper --purge` if you also want a paper's answers forgotten). Photo files on disk stay.
Live papers are never touched. Development databases only.
"""

import argparse
import sys
from uuid import UUID

from sqlalchemy import delete, func, select

from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    GradedAnswerModel,
    PaperItemModel,
    PaperModel,
    PaperSubmissionModel,
)
from app.shared.database.session import SessionLocal

DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"  # the learner the game and the papers share


def delete_cancelled_papers(session, learner_id: UUID, *, dry_run: bool = False) -> dict[str, int]:
    """Remove the learner's cancelled papers. Returns what was (or would be) removed."""
    paper_ids = select(PaperModel.id).where(PaperModel.learner_id == learner_id, PaperModel.status == "cancelled")
    item_ids = select(PaperItemModel.id).where(PaperItemModel.paper_id.in_(paper_ids))
    submission_ids = select(PaperSubmissionModel.id).where(PaperSubmissionModel.paper_id.in_(paper_ids))

    def count(statement) -> int:
        return session.scalar(select(func.count()).select_from(statement.subquery())) or 0

    found = {
        "papers": count(paper_ids),
        "questions on them": count(item_ids),
        "photo records": count(submission_ids),
        "marked answers": count(select(GradedAnswerModel.id).where(GradedAnswerModel.submission_id.in_(submission_ids))),
        "answers still in the history": session.scalar(
            select(func.count()).select_from(AttemptModel).where(AttemptModel.paper_item_id.in_(item_ids))
        )
        or 0,
    }
    if dry_run or not found["papers"]:
        return found
    # the order the database needs: marking records, photo records, the paper's questions, then the paper
    # (the questions are deleted here rather than left to the database's cascade, so it works the same everywhere)
    session.execute(delete(GradedAnswerModel).where(GradedAnswerModel.paper_item_id.in_(item_ids)))
    session.execute(delete(GradedAnswerModel).where(GradedAnswerModel.submission_id.in_(submission_ids)))
    session.execute(delete(PaperSubmissionModel).where(PaperSubmissionModel.paper_id.in_(paper_ids)))
    session.execute(delete(PaperItemModel).where(PaperItemModel.paper_id.in_(paper_ids)))
    session.execute(delete(PaperModel).where(PaperModel.id.in_(paper_ids)))
    session.commit()
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner_id", nargs="?", type=UUID, default=UUID(DEFAULT_LEARNER_ID))
    parser.add_argument("--dry-run", action="store_true", help="only count what would be removed")
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        found = delete_cancelled_papers(session, args.learner_id, dry_run=args.dry_run)

    if not found["papers"]:
        print("this learner has no cancelled papers: nothing to remove")
        return 0
    print(("would remove" if args.dry_run else "removed") + ":")
    for name, number in found.items():
        print(f"  {name}: {number}")
    if found["answers still in the history"]:
        print("(those saved answers stay in the child's history; scripts.redo_paper --purge forgets a paper's answers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
