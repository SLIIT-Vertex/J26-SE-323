"""Store every computed mastery vector so progress over time can be shown."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261015_01"
down_revision: str | None = "20261014_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
big_int = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "mastery_snapshots",
        sa.Column("id", big_int, autoincrement=True, nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("n_attempts", sa.Integer(), nullable=False),
        sa.Column("skills", json_type, nullable=False),
        sa.CheckConstraint("n_attempts >= 0", name="ck_mastery_snapshots_n_attempts"),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mastery_snapshots_latest", "mastery_snapshots", ["learner_id", "computed_at"]
    )


def downgrade() -> None:
    op.drop_table("mastery_snapshots")
