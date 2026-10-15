"""The result report of one weekly paper: what the child got wrong, for the parent.

Built only from questions whose marking is final. A question still waiting for the parent is
not shown (its result is not known yet), and no answer is given for it.

The report is the ONE place the answer key leaves the server, by the project owner's choice:
the correct answers come as a separate list at the end, by question number, and only for
questions the child got wrong or left blank. They are never put next to the question.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID

from app.knowledge_tracing.application.grading.types import KeyPart
from app.knowledge_tracing.application.paper_generation import PaperNotFoundError, next_paper_date
from app.knowledge_tracing.application.retention import photos_available, photos_expire_at
from app.knowledge_tracing.domain.paper import Paper, PaperItem
from app.knowledge_tracing.domain.submission import FINAL_STATUSES, GradedPart, Submission
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)

# Pages that have marked questions to show (a needs_review page is partly marked).
SHOWN_STATUSES = (*FINAL_STATUSES, "needs_review")

# (English name, Sinhala name or None) by skill code
SkillNames = Callable[[], dict[str, tuple[str, str | None]]]


@dataclass(frozen=True, slots=True)
class WrittenPart:
    part_no: int
    label: str | None
    text: str | None  # what the parent confirmed, or what was read; None = nothing written


@dataclass(frozen=True, slots=True)
class Mistake:
    paper_item_id: UUID
    submission_id: UUID
    position: int
    question_id: str
    skill_code: str
    skill_name: str
    skill_name_si: str | None
    result: str  # wrong | blank
    written: tuple[WrittenPart, ...]
    picture_available: bool


@dataclass(frozen=True, slots=True)
class CorrectAnswer:
    part_no: int
    label: str | None
    answer: str


@dataclass(frozen=True, slots=True)
class AnswerListEntry:
    position: int
    answers: tuple[CorrectAnswer, ...]


@dataclass(frozen=True, slots=True)
class SkillResult:
    skill_code: str
    name: str
    name_si: str | None
    correct: int
    wrong: int
    blank: int


@dataclass(frozen=True, slots=True)
class ReportSummary:
    questions: int  # questions on the printed paper
    marked: int  # questions with a final result
    correct: int
    wrong: int
    blank: int
    waiting_for_parent: int
    not_uploaded: int  # questions on pages that have no usable photo yet


@dataclass(frozen=True, slots=True)
class Report:
    paper: Paper
    pages_total: int
    pages_marked: int
    complete: bool
    summary: ReportSummary
    skills: tuple[SkillResult, ...]
    mistakes: tuple[Mistake, ...]
    answer_list: tuple[AnswerListEntry, ...]
    next_paper: date
    photos_kept_until: datetime | None
    first_viewed_pages: tuple[int, ...] = field(default=())


class PaperStore:
    """The slice of the paper repository the report needs (typed loosely on purpose)."""


class ReportService:
    def __init__(
        self,
        submissions: SqlAlchemySubmissionRepository,
        papers,
        answer_keys,
        skill_names: SkillNames,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.submissions = submissions
        self.papers = papers
        self.answer_keys = answer_keys
        self.skill_names = skill_names
        self.now = now

    def build(self, paper_id: UUID, *, mark_viewed: bool = True) -> Report:
        paper: Paper | None = self.papers.get(paper_id)
        if paper is None:
            raise PaperNotFoundError(paper_id)
        items: list[PaperItem] = self.papers.items(paper_id)
        current: list[Submission] = self.submissions.current_for_paper(paper_id)
        # A page still waiting for the parent has marked questions too: those are shown, and the
        # waiting ones are counted as waiting (they are not "missing photos").
        final = {s.page: s for s in current if s.status in SHOWN_STATUSES}

        parts_by_item: dict[UUID, list[GradedPart]] = {}
        for submission in final.values():
            for part in self.submissions.parts(submission.id):
                parts_by_item.setdefault(part.paper_item_id, []).append(part)

        names = self.skill_names()
        keys = self.answer_keys.keys([i.question_id for i in items], paper.language)

        correct = wrong = blank = waiting = not_uploaded = 0
        per_skill: dict[str, list[int]] = {}
        mistakes: list[Mistake] = []
        answer_list: list[AnswerListEntry] = []
        now = self.now()

        for item in sorted(items, key=lambda i: i.position):
            parts = parts_by_item.get(item.id)
            if item.page not in final or not parts:
                if item.page not in final:
                    not_uploaded += 1
                else:
                    waiting += 1
                continue
            if any(not p.is_final for p in parts):
                waiting += 1
                continue

            statuses = [p.final_status for p in parts]
            if all(s == "correct" for s in statuses):
                result = "correct"
            elif all(s == "blank" for s in statuses):
                result = "blank"
            else:
                result = "wrong"
            counts = per_skill.setdefault(item.skill_code, [0, 0, 0])
            if result == "correct":
                correct += 1
                counts[0] += 1
                continue
            if result == "wrong":
                wrong += 1
                counts[1] += 1
            else:
                blank += 1
                counts[2] += 1

            submission = final[item.page]
            english, sinhala = names.get(item.skill_code, (item.skill_code, None))
            key_by_no = {k.part_no: k for k in keys.get(item.question_id, [])}
            mistakes.append(
                Mistake(
                    paper_item_id=item.id,
                    submission_id=submission.id,
                    position=item.position,
                    question_id=item.question_id,
                    skill_code=item.skill_code,
                    skill_name=english,
                    skill_name_si=sinhala,
                    result=result,
                    written=tuple(
                        WrittenPart(
                            p.part_no,
                            key_by_no[p.part_no].label if p.part_no in key_by_no else None,
                            (p.read_selected or p.read_text or None) if p.final_status != "blank" else None,
                        )
                        for p in sorted(parts, key=lambda p: p.part_no)
                    ),
                    picture_available=photos_available(submission, now),
                )
            )
            answer_list.append(
                AnswerListEntry(
                    item.position,
                    tuple(
                        CorrectAnswer(k.part_no, k.label, _show(k))
                        for k in sorted(key_by_no.values(), key=lambda k: k.part_no)
                    ),
                )
            )

        marked = correct + wrong + blank
        if mark_viewed and marked:
            # Opening a report with something to see starts the 7-day clock for those pages.
            self.submissions.mark_report_viewed([s.id for s in final.values()], now)
            current = self.submissions.current_for_paper(paper_id)

        skills = tuple(
            SkillResult(
                code,
                names.get(code, (code, None))[0],
                names.get(code, (code, None))[1],
                c, w, b,
            )
            for code, (c, w, b) in sorted(per_skill.items())
        )
        kept = [
            photos_expire_at(s)
            for s in current
            if s.status in SHOWN_STATUSES and s.files_deleted_at is None
        ]
        return Report(
            paper=paper,
            pages_total=paper.page_count,
            pages_marked=len(final),
            complete=(
                len(final) == paper.page_count
                and waiting == 0
                and all(s.status in FINAL_STATUSES for s in final.values())
            ),
            summary=ReportSummary(len(items), marked, correct, wrong, blank, waiting, not_uploaded),
            skills=skills,
            mistakes=tuple(mistakes),
            answer_list=tuple(answer_list),
            next_paper=next_paper_date(paper.week_start),
            photos_kept_until=min(kept) if kept else None,
        )


def _show(key: KeyPart) -> str:
    """One correct answer as text. A part judged only by an instruction shows the task."""
    if key.alternatives:
        return " / ".join(key.alternatives)
    return key.instruction or ""
