from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.grading.keys import to_key
from app.knowledge_tracing.application.grading.types import KeyPart
from app.knowledge_tracing.infrastructure.db.models import QuestionPartModel


class SqlAlchemyAnswerKeyRepository:
    """Reads answer keys. Nothing here is ever returned by an API."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def key(self, question_id: str, language: str) -> list[KeyPart]:
        parts = self.session.scalars(
            select(QuestionPartModel)
            .where(
                QuestionPartModel.question_id == question_id,
                QuestionPartModel.language == language,
            )
            .order_by(QuestionPartModel.part_no)
        ).all()
        return to_key(parts)

    def keys(self, question_ids: list[str], language: str) -> dict[str, list[KeyPart]]:
        if not question_ids:
            return {}
        parts = self.session.scalars(
            select(QuestionPartModel)
            .where(
                QuestionPartModel.question_id.in_(question_ids),
                QuestionPartModel.language == language,
            )
            .order_by(QuestionPartModel.question_id, QuestionPartModel.part_no)
        ).all()
        grouped: dict[str, list] = {}
        for part in parts:
            grouped.setdefault(part.question_id, []).append(part)
        return {question_id: to_key(rows) for question_id, rows in grouped.items()}
