import importlib.util
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.learner_state.infrastructure.db.models import LearnerSkillStateModel
from app.shared.learner.model import LearnerModel

VERSIONS = Path(__file__).parents[2] / "alembic" / "versions"
# The learner-state migrations, in order.
MIGRATIONS = (
    "20261014_01_create_learner_state_tables.py",
    "20261020_02_widen_learner_state_window_id.py",
)


def load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), VERSIONS / filename)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_migrations_match_the_model() -> None:
    """Running the learner-state migrations must produce exactly the table the model describes."""
    migrations = [load(name) for name in MIGRATIONS]

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
            for migration in migrations:
                migration.upgrade()

        assert "learner_skill_states" in inspect(connection).get_table_names()
        # Includes column types, so a 32-bit window_id would be reported.
        assert compare_metadata(context, expected) == []

        with Operations.context(context):
            for migration in reversed(migrations):
                migration.downgrade()
        assert "learner_skill_states" not in inspect(connection).get_table_names()


def test_window_id_holds_millisecond_timestamps() -> None:
    assert LearnerSkillStateModel.__table__.c.window_id.type.python_type is int
    assert type(LearnerSkillStateModel.__table__.c.window_id.type).__name__ == "BigInteger"
