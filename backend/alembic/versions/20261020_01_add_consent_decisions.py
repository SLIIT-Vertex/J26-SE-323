"""Add current purpose-specific consent decisions, such as learner-state camera use."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gam_20261020_01"
down_revision: str | None = "gam_20261017_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent_decisions",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"]),
        sa.PrimaryKeyConstraint("learner_id", "purpose"),
    )


def downgrade() -> None:
    op.drop_table("consent_decisions")
