import importlib.util
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, MetaData, create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    QuestionModel,
    QuestionPartModel,
    QuestionVariantModel,
    SkillModel,
)
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

VERSIONS = Path(__file__).parents[2] / "alembic" / "versions"
# The knowledge tracing migrations, oldest first.
MIGRATIONS = [
    VERSIONS / "20261013_01_create_knowledge_tracing_tables.py",
    VERSIONS / "20261014_02_add_attempt_idempotency_key.py",
    VERSIONS / "20261015_01_create_mastery_snapshots.py",
]
KT_TABLES = {
    "skills",
    "questions",
    "question_variants",
    "question_parts",
    "attempts",
    "mastery_snapshots",
}


def _sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


@pytest.fixture
def session() -> Iterator[Session]:
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(SkillModel(code="MAT-FRC", sort_index=9, area="MAT", name_en="Fractions"))
        db.flush()
        db.add(QuestionModel(id="3.41", skill_code="MAT-FRC", difficulty="medium"))
        db.flush()
        db.add(
            QuestionVariantModel(
                question_id="3.41",
                language="si",
                image_key="questions/3/3.41.png",
                image_width_px=800,
                image_height_px=400,
                content_hash="a" * 64,
                answer_key_raw="2",
            )
        )
        db.commit()
        yield db


def _attempt(db: Session, **overrides: object) -> AttemptModel:
    learner = LearnerModel(id=uuid4(), grade=5, preferred_language="si")
    db.add(learner)
    db.flush()
    values: dict[str, object] = {
        "learner_id": learner.id,
        "question_id": "3.41",
        "language": "si",
        "source": 1,
        "correct": True,
        "time_ms": 14000,
        "hints": 0,
        "penalty": 0.1,
        "answered_at": datetime.now(UTC),
    }
    values.update(overrides)
    return AttemptModel(**values)


def test_valid_rows_round_trip(session: Session) -> None:
    session.add(
        QuestionPartModel(
            question_id="3.41",
            language="si",
            part_no=1,
            part_type="mcq",
            answer_kind="choice",
            option_labels=["1", "2", "3"],
            correct_option="2",
        )
    )
    session.add(_attempt(session))
    session.commit()

    question = session.get(QuestionModel, "3.41")
    assert question is not None
    assert question.secondary_skill_codes == []
    assert question.active is True
    assert question.est_seconds == 60


@pytest.mark.parametrize(
    "build",
    [
        lambda: SkillModel(code="X-ONE", sort_index=30, area="MAT", name_en="x"),
        lambda: SkillModel(code="X-TWO", sort_index=1, area="ART", name_en="x"),
        lambda: SkillModel(code="MAT-DUP", sort_index=9, area="MAT", name_en="x"),
        lambda: QuestionModel(id="9.9", skill_code="MAT-FRC", difficulty="extreme"),
        lambda: QuestionModel(id="9.9", skill_code="NOPE-NOPE", difficulty="easy"),
        lambda: QuestionModel(id="9.9", skill_code="MAT-FRC", difficulty="easy", est_seconds=0),
        lambda: QuestionVariantModel(
            question_id="3.41",
            language="en",
            image_key="k",
            image_width_px=1,
            image_height_px=1,
            answer_key_raw="2",
        ),
        lambda: QuestionVariantModel(
            question_id="3.41",
            language="ta",
            image_key="k",
            image_width_px=1,
            image_height_px=1,
            content_hash="a" * 64,
            answer_key_raw="2",
        ),
        lambda: QuestionPartModel(
            question_id="3.41", language="si", part_no=1, part_type="mcq", option_labels=["1", "2"]
        ),
        lambda: QuestionPartModel(question_id="3.41", language="si", part_no=1, part_type="short"),
        lambda: QuestionPartModel(
            question_id="3.41",
            language="ta",
            part_no=1,
            part_type="short",
            accepted_answers=["x"],
        ),
    ],
    ids=[
        "skill-index-out-of-range",
        "skill-unknown-area",
        "skill-duplicate-index",
        "question-bad-difficulty",
        "question-unknown-skill",
        "question-zero-seconds",
        "variant-english-not-allowed",
        "variant-duplicate-image-hash",
        "mcq-without-correct-option",
        "short-without-answer-or-instruction",
        "part-without-variant",
    ],
)
def test_bad_rows_are_rejected(session: Session, build) -> None:
    session.add(build())
    with pytest.raises(IntegrityError):
        session.commit()


def test_short_part_may_be_instruction_only(session: Session) -> None:
    session.add(
        QuestionPartModel(
            question_id="3.41",
            language="si",
            part_no=1,
            part_type="short",
            answer_kind="instruction",
            instruction="color three boxes",
        )
    )
    session.commit()


@pytest.mark.parametrize(
    "overrides",
    [{"source": 2}, {"penalty": 1.5}, {"penalty": -0.1}, {"language": "en"}, {"question_id": "0.0"}],
    ids=["source", "penalty-high", "penalty-low", "language", "unknown-question"],
)
def test_bad_attempts_are_rejected(session: Session, overrides: dict[str, object]) -> None:
    session.add(_attempt(session, **overrides))
    with pytest.raises(IntegrityError):
        session.commit()


def test_a_paper_item_can_only_become_one_attempt(session: Session) -> None:
    paper_item = uuid4()
    session.add(_attempt(session, source=0, paper_item_id=paper_item))
    session.commit()
    session.add(_attempt(session, source=0, paper_item_id=paper_item))
    with pytest.raises(IntegrityError):
        session.commit()


def test_digital_attempts_do_not_need_a_paper_item(session: Session) -> None:
    session.add(_attempt(session))
    session.add(_attempt(session))
    session.commit()


def test_deleting_a_variant_removes_its_parts(session: Session) -> None:
    session.add(
        QuestionPartModel(
            question_id="3.41",
            language="si",
            part_no=1,
            part_type="short",
            accepted_answers=["x"],
        )
    )
    session.commit()
    session.delete(session.get(QuestionVariantModel, ("3.41", "si")))
    session.commit()
    assert session.query(QuestionPartModel).count() == 0


def _load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(f"kt_migration_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrations_match_the_models() -> None:
    """Running the knowledge tracing migrations must produce exactly the models' schema."""
    migrations = [_load_migration(path) for path in MIGRATIONS]

    engine = _sqlite_engine()
    LearnerModel.__table__.create(engine)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            for migration in migrations:
                migration.upgrade()

        assert KT_TABLES <= set(inspect(connection).get_table_names())
        # Compare only the tables this migration creates (plus learners); other
        # modules' tables in Base.metadata are created by their own migrations.
        expected = MetaData()
        for name in KT_TABLES | {"learners"}:
            Base.metadata.tables[name].to_metadata(expected)
        diff = compare_metadata(context, expected)
        assert diff == []

        with Operations.context(context):
            for migration in reversed(migrations):
                migration.downgrade()
        assert not KT_TABLES & set(inspect(connection).get_table_names())
