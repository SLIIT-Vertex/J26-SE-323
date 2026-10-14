import importlib.util
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.learner_state.infrastructure.db.models import LearnerSkillStateModel
from app.shared.learner.model import LearnerModel

MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "20261014_01_create_learner_state_tables.py"
)


def test_migration_matches_the_model() -> None:
    """Running this migration must produce exactly the learner-state table the model describes."""
    spec = importlib.util.spec_from_file_location("learner_state_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    expected = MetaData()
    LearnerModel.__table__.to_metadata(expected)
    LearnerSkillStateModel.__table__.to_metadata(expected)

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    LearnerModel.__table__.create(engine)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        assert "learner_skill_states" in inspect(connection).get_table_names()
        assert compare_metadata(context, expected) == []

        with Operations.context(context):
            migration.downgrade()
        assert "learner_skill_states" not in inspect(connection).get_table_names()
