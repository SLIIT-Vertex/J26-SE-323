"""Combines the parts of one question into one result. Pure.

    all parts correct                                  -> correct
    every part blank                                   -> blank   (blank is not wrong: no attempt)
    any part wrong, or some blank while others answered -> wrong
    any part waiting for the parent                    -> pending_review

One attempt is recorded per question, and it is correct only if every part is correct. The part
results are kept for feedback ("2 of 3 right").
"""

from collections.abc import Sequence

from app.knowledge_tracing.application.grading.types import PartGrade, QuestionGrade


def combine_parts(parts: Sequence[PartGrade]) -> QuestionGrade:
    ordered = tuple(sorted(parts, key=lambda p: p.part_no))
    correct = sum(p.status == "correct" for p in ordered)

    if any(p.needs_review for p in ordered):
        status = "pending_review"
    elif ordered and all(p.status == "correct" for p in ordered):
        status = "correct"
    elif ordered and all(p.status == "blank" for p in ordered):
        status = "blank"
    else:
        status = "wrong"
    return QuestionGrade(status, ordered, correct, len(ordered))


def provisional_status(parts: Sequence[PartGrade]) -> str:
    """The result the question would have if the parent confirms the automatic readings.

    Used only to show progress ("2 of 3 so far"); it is never stored as a final result.
    """
    settled = [p for p in parts if not p.needs_review]
    if not settled or len(settled) < len(parts):
        return "pending_review"
    return combine_parts(settled).status
