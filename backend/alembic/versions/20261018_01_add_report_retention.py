"""Track when a result report was first seen and when a page's photos were removed."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261018_01"
down_revision: str | None = "20261017_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("paper_submissions") as batch:
        batch.add_column(sa.Column("report_viewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("files_deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("paper_submissions") as batch:
        batch.drop_column("files_deleted_at")
        batch.drop_column("report_viewed_at")
