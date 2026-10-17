"""Move durable learning-flow storage to stable domain table names."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gam_20261017_07"
down_revision: str | None = "gam_20261015_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_PREFIX = "phase" + "6"
SUFFIXES = (
    "episode_runs",
    "probe_reservations",
    "episode_events",
    "idempotency_receipts",
    "audit_events",
)


def _rename(source_prefix: str, destination_prefix: str) -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for suffix in SUFFIXES:
        source = f"{source_prefix}_{suffix}"
        destination = f"{destination_prefix}_{suffix}"
        if source in tables and destination not in tables:
            op.rename_table(source, destination)
            tables.remove(source)
            tables.add(destination)


def upgrade() -> None:
    _rename(LEGACY_PREFIX, "learning_flow")


def downgrade() -> None:
    _rename("learning_flow", LEGACY_PREFIX)
