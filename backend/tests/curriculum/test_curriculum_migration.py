from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from alembic import command
from app.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_TABLES = {
    "curriculum_sources",
    "curriculum_chunks",
    "curriculum_chunk_embeddings",
}


def test_curriculum_branch_is_independent_of_the_gamification_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    (curriculum_head,) = script.get_revisions("curriculum@head")
    assert curriculum_head.revision == "curr_20261015_01"
    assert curriculum_head.down_revision == "20261007_01"
    assert set(curriculum_head.branch_labels or ()) == {"curriculum"}
    assert curriculum_head.revision in script.get_heads()
    for head in set(script.get_heads()) - {curriculum_head.revision}:
        ancestors = {revision.revision for revision in script.iterate_revisions(head, "base")}
        assert curriculum_head.revision not in ancestors


def test_curriculum_migration_upgrades_and_downgrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'curriculum-migration.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.stamp(config, "20261007_01")
    command.upgrade(config, "curriculum@head")

    engine = create_engine(database_url)
    assert CURRICULUM_TABLES <= set(inspect(engine).get_table_names())
    embedding_columns = {
        column["name"] for column in inspect(engine).get_columns("curriculum_chunk_embeddings")
    }
    assert embedding_columns == {"chunk_id", "model_name", "model_revision", "vector"}
    source_columns = {
        column["name"] for column in inspect(engine).get_columns("curriculum_sources")
    }
    assert "source_document_sha256" in source_columns
    engine.dispose()

    command.downgrade(config, "20261007_01")
    downgraded = create_engine(database_url)
    assert CURRICULUM_TABLES.isdisjoint(inspect(downgraded).get_table_names())
    downgraded.dispose()

    command.upgrade(config, "curriculum@head")
    reupgraded = create_engine(database_url)
    assert CURRICULUM_TABLES <= set(inspect(reupgraded).get_table_names())
    reupgraded.dispose()
    get_settings.cache_clear()


def test_postgres_embedding_column_is_pgvector() -> None:
    source = (BACKEND_ROOT / "alembic/versions/20261015_01_create_curriculum_tables.py").read_text()
    assert "vector(384)" in source
    assert 'branch_labels: str | Sequence[str] | None = ("curriculum",)' in source
