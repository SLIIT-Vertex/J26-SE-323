"""Let a game answer be saved with a skill and a difficulty instead of a bank question.

The game has its own questions, so its answers cannot point at a row of the paper question bank.
They carry the skill and the difficulty directly. Paper answers still always point at their bank
question, and every answer must have one form or the other.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261019_01"
down_revision: str | None = "20261018_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempts") as batch:
        batch.alter_column("question_id", existing_type=sa.String(length=16), nullable=True)
        batch.add_column(sa.Column("skill_code", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("difficulty", sa.String(length=6), nullable=True))
        batch.create_foreign_key("fk_attempts_skill_code_skills", "skills", ["skill_code"], ["code"])
        batch.create_check_constraint(
            "ck_attempts_difficulty",
            "difficulty IS NULL OR difficulty IN ('easy', 'medium', 'hard')",
        )
        batch.create_check_constraint(
            "ck_attempts_question_or_skill",
            "question_id IS NOT NULL OR (skill_code IS NOT NULL AND difficulty IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    without_question = bind.execute(
        sa.text("SELECT COUNT(*) FROM attempts WHERE question_id IS NULL")
    ).scalar()
    if without_question:
        # Answers with no bank question cannot be kept in the old shape. Never delete them silently.
        raise RuntimeError(
            f"{without_question} attempts have no bank question; remove or export them first"
        )
    with op.batch_alter_table("attempts") as batch:
        batch.drop_constraint("ck_attempts_question_or_skill", type_="check")
        batch.drop_constraint("ck_attempts_difficulty", type_="check")
        batch.drop_constraint("fk_attempts_skill_code_skills", type_="foreignkey")
        batch.drop_column("difficulty")
        batch.drop_column("skill_code")
        batch.alter_column("question_id", existing_type=sa.String(length=16), nullable=False)
