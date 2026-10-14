"""The Alembic history must be one straight line: unique revision ids and a single head.

Two branches that both add a migration with the same id are silently shadowed (one is never
applied), which is easy to miss after a rebase.
"""

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).parents[1]
VERSIONS = BACKEND / "alembic" / "versions"


def test_every_revision_id_is_unique() -> None:
    ids: dict[str, list[str]] = {}
    for path in VERSIONS.glob("*.py"):
        match = re.search(r'^revision\s*:?[^=]*=\s*"([^"]+)"', path.read_text(), re.MULTILINE)
        assert match, f"{path.name} has no revision id"
        ids.setdefault(match.group(1), []).append(path.name)

    duplicates = {rev: files for rev, files in ids.items() if len(files) > 1}
    assert not duplicates, f"revision ids used by more than one file: {duplicates}"


def test_there_is_exactly_one_head() -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))

    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, f"migration branches need merging: {heads}"
