from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.answer_key import parse_answer_key
from app.knowledge_tracing.application.grading import PartRead, compare_part
from app.knowledge_tracing.application.question_import import (
    ImageInfo,
    ImportPlan,
    QuestionPlan,
    SkillPlan,
    VariantPlan,
)
from app.knowledge_tracing.infrastructure.db.answer_key_repository import (
    SqlAlchemyAnswerKeyRepository,
)
from app.knowledge_tracing.infrastructure.db.question_bank_writer import write_plan
from app.shared.database.base import Base


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        plan = ImportPlan(
            skills=[SkillPlan("MAT-OPS", 0, "MAT", "Operations", None, None)],
            questions=[
                QuestionPlan(
                    "1.2", "MAT-OPS", (), "easy", 90,
                    {
                        language: VariantPlan(
                            language,
                            ImageInfo(f"q/{language}.png", 400, 200, f"h-{language}"),
                            key,
                            tuple(parse_answer_key(key)),
                        )
                        for language, key in (("si", "2, ගස/රුක"), ("ta", "2, மரம்"))
                    },
                )
            ],
        )
        write_plan(db, plan)
        db.commit()
        yield db


def test_the_key_comes_back_in_part_order_for_each_language(session: Session) -> None:
    repository = SqlAlchemyAnswerKeyRepository(session)

    si = repository.key("1.2", "si")
    ta = repository.key("1.2", "ta")

    assert [p.part_no for p in si] == [1, 2]
    assert si[0].kind == "choice" and si[0].alternatives == ("2",)
    assert si[0].option_labels == ("1", "2", "3")
    assert si[1].alternatives == ("ගස", "රුක")
    assert ta[1].alternatives == ("மரம்",)


def test_a_stored_key_grades_a_reading(session: Session) -> None:
    key = SqlAlchemyAnswerKeyRepository(session).key("1.2", "ta")

    right = compare_part(PartRead(part=2, answer="மரம்", confidence=0.9), key[1])
    wrong = compare_part(PartRead(part=2, answer="ගස", confidence=0.9), key[1])

    assert right.status == "correct"
    assert wrong.status == "wrong"  # the Sinhala word is not an answer to the Tamil paper


def test_many_keys_at_once_and_unknown_questions(session: Session) -> None:
    repository = SqlAlchemyAnswerKeyRepository(session)

    keys = repository.keys(["1.2", "9.9"], "si")

    assert set(keys) == {"1.2"}
    assert repository.key("9.9", "si") == []
    assert repository.keys([], "si") == {}
