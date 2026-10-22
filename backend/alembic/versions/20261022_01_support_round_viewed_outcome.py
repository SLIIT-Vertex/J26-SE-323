"""Allow a support round to end as watched: mathematics visual guidance is a demonstration only."""

from alembic import op

revision = "gam_20261022_01"
down_revision = "gam_20261021_03"
branch_labels = None
depends_on = None

TABLE = "learning_flow_support_rounds"
NAME = "ck_learning_flow_support_round_outcome"


def upgrade():
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(
            NAME, "outcome IS NULL OR outcome IN ('succeeded', 'failed', 'viewed')"
        )


def downgrade():
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, "outcome IS NULL OR outcome IN ('succeeded', 'failed')")
