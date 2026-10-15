"""Add struggle-trigger reasons and the exposure budget columns."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "gam_20261014_02"
down_revision: str | None = "gam_20261013_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

_OLD_STATUS = (
    "delivery_status IN ('scheduled', 'presented', 'interacted', 'dismissed', "
    "'completed', 'failed')"
)
_NEW_STATUS = (
    "delivery_status IN ('scheduled', 'presented', 'interacted', 'dismissed', "
    "'completed', 'completed_over_budget', 'failed')"
)


def upgrade() -> None:
    op.add_column(
        "adaptive_episodes",
        sa.Column("trigger_reasons_json", json_type, nullable=True),
    )
    op.add_column(
        "adaptive_episodes",
        sa.Column("baseline_template", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "support_exposures",
        sa.Column("maximum_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "support_exposures",
        sa.Column("maximum_number_of_steps", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("support_exposures") as batch:
        batch.alter_column(
            "delivery_status",
            existing_type=sa.String(length=20),
            type_=sa.String(length=40),
            existing_nullable=False,
        )
        batch.drop_constraint("ck_support_exposures_status", type_="check")
        batch.create_check_constraint("ck_support_exposures_status", _NEW_STATUS)


def downgrade() -> None:
    with op.batch_alter_table("support_exposures") as batch:
        batch.drop_constraint("ck_support_exposures_status", type_="check")
        batch.create_check_constraint("ck_support_exposures_status", _OLD_STATUS)
        batch.alter_column(
            "delivery_status",
            existing_type=sa.String(length=40),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
    op.drop_column("support_exposures", "maximum_number_of_steps")
    op.drop_column("support_exposures", "maximum_duration_ms")
    op.drop_column("adaptive_episodes", "baseline_template")
    op.drop_column("adaptive_episodes", "trigger_reasons_json")
