"""Alembic revisions must be unique and end at the intentional module heads.

Research modules deliberately branch from the shared learner migration. Duplicate IDs still
silently shadow a migration after a rebase, while an unexpected head usually means a module's
chain was split accidentally.
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
        match = re.search(
            r'^revision\s*:?[^=]*=\s*"([^"]+)"',
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        assert match, f"{path.name} has no revision id"
        ids.setdefault(match.group(1), []).append(path.name)

    duplicates = {rev: files for rev, files in ids.items() if len(files) > 1}
    assert not duplicates, f"revision ids used by more than one file: {duplicates}"


def test_only_the_intentional_module_heads_exist() -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))

    heads = ScriptDirectory.from_config(config).get_heads()

    assert set(heads) == {
        "curr_20261015_01",
        "gam_20261017_07",
        "20261018_01",  # knowledge tracing, grading, and learner state
    }
