"""Allow the authored performance-triggered decision mode."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261014_03"
down_revision: str | None = "20261014_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_MODE = (
    "decision_mode IN ('deterministic_reference', 'shadow', 'learned', 'conservative_fallback')"
)
_NEW_MODE = (
    "decision_mode IN ('performance_triggered_fixed', 'deterministic_reference', "
    "'shadow', 'learned', 'conservative_fallback')"
)


def upgrade() -> None:
    with op.batch_alter_table("support_decisions") as batch:
        batch.drop_constraint("ck_support_decisions_mode", type_="check")
        batch.create_check_constraint("ck_support_decisions_mode", _NEW_MODE)


def downgrade() -> None:
    with op.batch_alter_table("support_decisions") as batch:
        batch.drop_constraint("ck_support_decisions_mode", type_="check")
        batch.create_check_constraint("ck_support_decisions_mode", _OLD_MODE)
