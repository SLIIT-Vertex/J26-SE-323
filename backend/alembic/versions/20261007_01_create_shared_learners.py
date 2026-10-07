"""Create the shared learner table and enable pgvector."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261007_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "learners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("preferred_language", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("grade IN (4, 5)", name="ck_learners_grade"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("learners")

