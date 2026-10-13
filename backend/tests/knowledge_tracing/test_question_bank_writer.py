from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.answer_key import parse_answer_key
from app.knowledge_tracing.application.question_import import (
    ImageInfo,
    ImportIssue,
    ImportPlan,
    QuestionPlan,
    SkillPlan,
    VariantPlan,
)
from app.knowledge_tracing.infrastructure.db.models import (
    QuestionModel,
    QuestionPartModel,
    QuestionVariantModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.db.question_bank_writer import (
    SkillOrderConflict,
    write_plan,
)
from app.shared.database.base import Base


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def plan_with(key_si: str = "2, ගස", key_ta: str = "2, மரம்", skill_index: int = 0) -> ImportPlan:
    def variant(language: str, key: str) -> VariantPlan:
        image = ImageInfo(f"questions/{language}/1.2.png", 400, 200, f"hash-{language}")
        return VariantPlan(language, image, key, tuple(parse_answer_key(key)))

    return ImportPlan(
        skills=[
            SkillPlan("MAT-OPS", skill_index, "MAT", "Operations", "මූලික", "desc"),
            SkillPlan("MAT-FRC", 1, "MAT", "Fractions", None, None),
        ],
        questions=[
            QuestionPlan(
                "1.2",
                "MAT-OPS",
                ("MAT-FRC",),
                "hard",
                150,
                {"si": variant("si", key_si), "ta": variant("ta", key_ta)},
            )
        ],
    )


def test_plan_is_written(session: Session) -> None:
    counts = write_plan(session, plan_with())
    session.commit()

    assert counts == {"skills": 2, "questions": 1, "variants": 2, "parts": 4}
    question = session.get(QuestionModel, "1.2")
    assert question is not None
    assert (question.skill_code, question.difficulty, question.est_seconds) == (
        "MAT-OPS",
        "hard",
        150,
    )
    assert question.secondary_skill_codes == ["MAT-FRC"]
    parts = session.scalars(
        select(QuestionPartModel)
        .where(QuestionPartModel.language == "ta")
        .order_by(QuestionPartModel.part_no)
    ).all()
    assert [(p.part_type, p.correct_option, p.accepted_answers) for p in parts] == [
        ("mcq", "2", ["2"]),
        ("short", None, ["மரம்"]),
    ]


def test_importing_twice_updates_in_place(session: Session) -> None:
    write_plan(session, plan_with())
    session.commit()
    question = session.get(QuestionModel, "1.2")
    assert question is not None
    question.key_verified_by = "Teacher"
    session.commit()

    write_plan(session, plan_with(key_si="3, ගස්"))
    session.commit()

    assert session.query(QuestionModel).count() == 1
    assert session.query(SkillModel).count() == 2
    assert session.query(QuestionVariantModel).count() == 2
    assert session.query(QuestionPartModel).count() == 4
    si = session.get(QuestionVariantModel, ("1.2", "si"))
    assert si is not None
    assert si.answer_key_raw == "3, ගස්"
    session.refresh(question)
    assert question.key_verified_by == "Teacher"


def test_a_changed_skill_index_is_refused(session: Session) -> None:
    write_plan(session, plan_with())
    session.commit()

    with pytest.raises(SkillOrderConflict):
        write_plan(session, plan_with(skill_index=5))


def test_a_plan_with_errors_is_never_written(session: Session) -> None:
    plan = plan_with()
    plan.issues.append(ImportIssue("error", "answers-1.md", "bad line", 3))

    with pytest.raises(ValueError):
        write_plan(session, plan)
    assert session.query(QuestionModel).count() == 0
