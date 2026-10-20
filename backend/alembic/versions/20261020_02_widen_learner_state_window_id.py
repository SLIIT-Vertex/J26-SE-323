"""Widen learner_skill_states.window_id to 64 bits.

The game records each scored answer with the scoring time in milliseconds as the window id
(about 1.8e12), which does not fit a 32-bit PostgreSQL integer.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261020_02"
down_revision: str | None = "20261019_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("learner_skill_states") as batch:
        batch.alter_column(
            "window_id",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("learner_skill_states") as batch:
        batch.alter_column(
            "window_id",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
