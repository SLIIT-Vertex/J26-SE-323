"""Persist the name provided at profile setup."""

import sqlalchemy as sa

from alembic import op

revision = "gam_20261021_03"
down_revision = "gam_20261021_02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("learners", sa.Column("display_name", sa.String(60), nullable=True))


def downgrade():
    op.drop_column("learners", "display_name")
