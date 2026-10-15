"""The planner end to end on an in-memory database: attempts in, a paper plan out."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
    MasteryService,
)
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.application.paper_selection import PaperParams
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    QuestionModel,
    QuestionVariantModel,
    SkillModel,
)
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.flush()
        for index, code in enumerate(SPEC.skills):
            for k, level in enumerate(("easy", "medium", "hard", "medium")):
                qid = f"{index + 1}.{k + 1}"
                db.add(QuestionModel(id=qid, skill_code=code, difficulty=level, est_seconds=90))
                db.flush()
                for language in ("si", "ta"):
                    db.add(
                        QuestionVariantModel(
                            question_id=qid,
                            language=language,
                            image_key=f"questions/{qid}-{language}.png",
                            image_width_px=945,
                            image_height_px=300,
                            answer_key_raw="1",
                        )
                    )
        db.commit()
        yield db


def planner(session: Session, now: datetime = NOW) -> PaperPlanner:
    model = get_knowledge_model()
    mastery = MasteryService(SqlAlchemyMasteryRepository(session), model, SPEC, lambda: now)
    return PaperPlanner(SqlAlchemyPaperInputRepository(session), mastery, model, SPEC, now=lambda: now)


def add_learner(session: Session, language: str = "si") -> UUID:
    learner = LearnerModel(id=uuid4(), grade=5, preferred_language=language)
    session.add(learner)
    session.commit()
    return learner.id


def add_attempts(
    session: Session,
    learner: UUID,
    code: str,
    outcomes: list[bool],
    *,
    source: int = 1,
    days_ago: int = 60,
    start: int = 0,
) -> None:
    index = SPEC.skills.index(code)
    for n, correct in enumerate(outcomes):
        session.add(
            AttemptModel(
                learner_id=learner,
                question_id=f"{index + 1}.{(start + n) % 4 + 1}",
                language="si",
                source=source,
                correct=correct,
                penalty=0.1 if source == 1 else 0.08,
                answered_at=NOW - timedelta(days=days_ago, minutes=-n),
            )
        )
    session.commit()


def test_a_new_learner_gets_a_diagnostic_paper(session: Session) -> None:
    learner = add_learner(session)

    selection = planner(session).plan(learner, PaperParams(seed=1))

    assert selection.mode == "diagnostic"
    assert selection.questions
    assert all(q.role == "diagnostic" for q in selection.questions)
    assert len(selection.unknown_skills) == 30


def test_a_learner_with_history_gets_a_practice_paper_with_all_three_groups(
    session: Session,
) -> None:
    learner = add_learner(session)
    weak = SPEC.skills[:6]
    for code in weak:
        add_attempts(session, learner, code, [False, False, False, True, False, False])
    for code in SPEC.skills[6:12]:  # strong, game only: should be verified on paper
        add_attempts(session, learner, code, [True] * 8, days_ago=40)
    for code in SPEC.skills[12:20]:  # some more known skills so practice mode applies
        add_attempts(session, learner, code, [True, True, False, True], days_ago=45)

    selection = planner(session).plan(learner, PaperParams(seed=2))

    assert selection.mode == "practice"
    assert selection.method == "cp_sat"
    roles = {q.role for q in selection.questions}
    assert "weak" in roles

    # The weak list is the learner's lowest known skills, as the model sees them. (The model is
    # optimistic about skills that were practised a lot, so wrong answers alone do not make a
    # skill "weak"; the weak list is therefore chosen by rank when few skills fall below 0.60.)
    snapshot = planner(session).mastery.current(learner)
    known = {s.code: s.mastery for s in snapshot.skills if s.mastery is not None}
    weak_values = [known[c] for c in selection.weak_skills]
    others = [v for c, v in known.items() if c not in selection.weak_skills]
    assert len(selection.weak_skills) >= 5
    assert max(weak_values) <= min(others) or max(weak_values) < 0.70  # hysteresis can keep one

    # Skills that did well in the game and have no paper answers are to be verified on paper.
    expected_verify = set(SPEC.skills[6:12]) - set(selection.weak_skills)
    assert expected_verify <= set(selection.verify_skills)
    assert {q.skill_code for q in selection.questions} & set(selection.verify_skills)


def test_questions_answered_in_the_last_30_days_are_not_offered_again(session: Session) -> None:
    learner = add_learner(session)
    for code in SPEC.skills[:20]:
        add_attempts(session, learner, code, [False, True, False, False], days_ago=60)
    # question 1.1 was answered yesterday
    add_attempts(session, learner, SPEC.skills[0], [False], days_ago=1, start=0)

    selection = planner(session).plan(learner, PaperParams(seed=1))

    assert "1.1" not in {q.question_id for q in selection.questions}


def test_the_learners_language_picks_the_question_images(session: Session) -> None:
    learner = add_learner(session, language="ta")
    # remove the Tamil version of every question of the first skill
    for k in range(4):
        variant = session.get(QuestionVariantModel, (f"1.{k + 1}", "ta"))
        session.delete(variant)
    session.commit()

    selection = planner(session).plan(learner, PaperParams(seed=1, mode="diagnostic"))

    assert SPEC.skills[0] in selection.skipped_skills
    assert SPEC.skills[0] not in selection.diagnostic_skills


def test_the_requested_language_overrides_the_learners(session: Session) -> None:
    learner = add_learner(session, language="ta")
    for k in range(4):
        session.delete(session.get(QuestionVariantModel, (f"1.{k + 1}", "ta")))
    session.commit()

    selection = planner(session).plan(
        learner, PaperParams(seed=1, mode="diagnostic"), language="si"
    )

    assert SPEC.skills[0] in selection.diagnostic_skills


def test_an_unknown_learner_is_reported(session: Session) -> None:
    with pytest.raises(LearnerNotFoundError):
        planner(session).plan(uuid4(), PaperParams())


def test_the_same_inputs_give_the_same_paper(session: Session) -> None:
    learner = add_learner(session)
    for code in SPEC.skills[:20]:
        add_attempts(session, learner, code, [False, True, False, True, False], days_ago=50)

    first = planner(session).plan(learner, PaperParams(seed=9))
    second = planner(session).plan(learner, PaperParams(seed=9))

    assert [q.question_id for q in first.questions] == [q.question_id for q in second.questions]


def test_paper_answers_count_towards_verification(session: Session) -> None:
    learner = add_learner(session)
    code = SPEC.skills[6]
    add_attempts(session, learner, code, [True] * 6, source=1, days_ago=50)
    add_attempts(session, learner, code, [True, True, True], source=0, days_ago=45)  # paper-proven
    for other in SPEC.skills[:6] + SPEC.skills[7:20]:
        add_attempts(session, learner, other, [False, True, False, True], days_ago=50)

    selection = planner(session).plan(learner, PaperParams(seed=1))

    assert code not in selection.verify_skills
