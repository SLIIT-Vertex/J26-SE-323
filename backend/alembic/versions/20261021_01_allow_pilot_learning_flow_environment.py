"""Allow the `pilot` environment on durable learning-flow episodes.

Only a pilot episode can release a child's answers to the models, and only with research consent.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gam_20261021_01"
down_revision: str | None = "gam_20261020_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "learning_flow_episode_runs"
CONSTRAINT = "ck_learning_flow_runs_environment"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(CONSTRAINT, type_="check")
        batch.create_check_constraint(CONSTRAINT, "environment IN ('development', 'test', 'pilot')")


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint(CONSTRAINT, type_="check")
        batch.create_check_constraint(CONSTRAINT, "environment IN ('development', 'test')")
