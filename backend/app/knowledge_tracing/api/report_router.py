"""The result report of a paper, for the app's results page."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.knowledge_tracing.application.paper_generation import PaperNotFoundError
from app.knowledge_tracing.application.report import Report, ReportService
from app.knowledge_tracing.infrastructure.db.answer_key_repository import (
    SqlAlchemyAnswerKeyRepository,
)
from app.knowledge_tracing.infrastructure.db.models import SkillModel
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.shared.database.session import get_db

router = APIRouter(tags=["report"])


class WrittenRead(BaseModel):
    part_no: int
    label: str | None
    text: str | None  # what the child wrote or marked; null means nothing


class MistakeRead(BaseModel):
    position: int
    question_id: str
    skill_code: str
    skill_name: str
    skill_name_si: str | None
    result: Literal["wrong", "blank"]
    written: list[WrittenRead]
    picture_available: bool
    # The question as photographed, with the child's writing. Null once the photo is removed.
    picture_url: str | None


class CorrectAnswerRead(BaseModel):
    part_no: int
    label: str | None
    answer: str


class ReportItemRead(BaseModel):
    position: int
    question_id: str
    skill_code: str
    result: Literal["correct", "wrong", "blank", "under_review", "not_uploaded"]
    # Set only for "wrong" and "blank". Null for correct items and for items under review.
    correct_answer_text: str | None


class AnswerListEntryRead(BaseModel):
    position: int
    answers: list[CorrectAnswerRead]


class SkillResultRead(BaseModel):
    skill_code: str
    name: str
    name_si: str | None
    correct: int
    wrong: int
    blank: int


class SummaryRead(BaseModel):
    questions: int
    marked: int
    correct: int
    wrong: int
    blank: int
    waiting_for_parent: int
    not_uploaded: int


class ReportRead(BaseModel):
    paper_id: UUID
    code: str
    week_start: date
    language: str
    pages_total: int
    pages_marked: int
    complete: bool
    summary: SummaryRead
    skills: list[SkillResultRead]
    items: list[ReportItemRead]
    mistakes: list[MistakeRead]
    # The correct answers, by question number, as a separate list (never next to the question).
    answer_list: list[AnswerListEntryRead]
    next_paper_date: date
    photos_kept_until: datetime | None


def get_report_service(session: Annotated[Session, Depends(get_db)]) -> ReportService:
    def skill_names() -> dict[str, tuple[str, str | None]]:
        rows = session.execute(
            select(SkillModel.code, SkillModel.name_en, SkillModel.name_si)
        ).all()
        return {code: (en, si) for code, en, si in rows}

    return ReportService(
        SqlAlchemySubmissionRepository(session),
        SqlAlchemyPaperRepository(session),
        SqlAlchemyAnswerKeyRepository(session),
        skill_names,
    )


def _to_read(report: Report) -> ReportRead:
    prefix = get_settings().api_v1_prefix
    return ReportRead(
        paper_id=report.paper.id,
        code=report.paper.token,
        week_start=report.paper.week_start,
        language=report.paper.language,
        pages_total=report.pages_total,
        pages_marked=report.pages_marked,
        complete=report.complete,
        summary=SummaryRead(
            questions=report.summary.questions,
            marked=report.summary.marked,
            correct=report.summary.correct,
            wrong=report.summary.wrong,
            blank=report.summary.blank,
            waiting_for_parent=report.summary.waiting_for_parent,
            not_uploaded=report.summary.not_uploaded,
        ),
        skills=[
            SkillResultRead(
                skill_code=s.skill_code,
                name=s.name,
                name_si=s.name_si,
                correct=s.correct,
                wrong=s.wrong,
                blank=s.blank,
            )
            for s in report.skills
        ],
        items=[
            ReportItemRead(
                position=i.position,
                question_id=i.question_id,
                skill_code=i.skill_code,
                result=i.result,  # type: ignore[arg-type]
                correct_answer_text=i.correct_answer_text,
            )
            for i in report.items
        ],
        mistakes=[
            MistakeRead(
                position=m.position,
                question_id=m.question_id,
                skill_code=m.skill_code,
                skill_name=m.skill_name,
                skill_name_si=m.skill_name_si,
                result=m.result,  # type: ignore[arg-type]
                written=[
                    WrittenRead(part_no=w.part_no, label=w.label, text=w.text) for w in m.written
                ],
                picture_available=m.picture_available,
                picture_url=(
                    f"{prefix}/submissions/{m.submission_id}/crops/{m.paper_item_id}"
                    if m.picture_available
                    else None
                ),
            )
            for m in report.mistakes
        ],
        answer_list=[
            AnswerListEntryRead(
                position=a.position,
                answers=[
                    CorrectAnswerRead(part_no=c.part_no, label=c.label, answer=c.answer)
                    for c in a.answers
                ],
            )
            for a in report.answer_list
        ],
        next_paper_date=report.next_paper,
        photos_kept_until=report.photos_kept_until,
    )


@router.get("/papers/{paper_id}/report", response_model=ReportRead)
def get_report(
    paper_id: UUID,
    service: Annotated[ReportService, Depends(get_report_service)],
    peek: Annotated[bool, Query(description="look without starting the 7-day photo timer")] = False,
) -> ReportRead:
    """What the child got wrong this week, with the correct answers as a separate list.

    Opening a report that shows something starts a 7-day timer for the photos of those pages
    (they are removed at the earlier of that and 30 days after the upload). `peek=true` reads the
    report without starting it.
    """
    try:
        return _to_read(service.build(paper_id, mark_viewed=not peek))
    except PaperNotFoundError as error:
        raise HTTPException(404, {"code": "not_found", "message": "Paper not found"}) from error
