"""Let a repeated game request return the same attempt instead of creating a duplicate."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261014_02"
down_revision: str | None = "20261014_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempts") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch.create_unique_constraint("uq_attempts_idempotency_key", ["idempotency_key"])


def downgrade() -> None:
    with op.batch_alter_table("attempts") as batch:
        batch.drop_constraint("uq_attempts_idempotency_key", type_="unique")
        batch.drop_column("idempotency_key")
