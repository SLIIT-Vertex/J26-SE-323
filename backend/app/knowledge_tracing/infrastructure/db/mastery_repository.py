from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.mastery import MasterySnapshot, SkillEstimate
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.models import (
    AttemptModel,
    MasterySnapshotModel,
    SkillModel,
)
from app.shared.learner.model import LearnerModel


def _to_domain(model: MasterySnapshotModel) -> MasterySnapshot:
    return MasterySnapshot(
        id=model.id,
        learner_id=model.learner_id,
        computed_at=model.computed_at,
        model_version=model.model_version,
        n_attempts=model.n_attempts,
        skills=tuple(
            SkillEstimate(entry["code"], entry["mastery"], entry["attempts"])
            for entry in model.skills
        ),
    )


class SqlAlchemyMasteryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._attempts = SqlAlchemyAttemptRepository(session)

    def learner_exists(self, learner_id: UUID) -> bool:
        return self.session.get(LearnerModel, learner_id) is not None

    def count_attempts(self, learner_id: UUID) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(AttemptModel).where(
                    AttemptModel.learner_id == learner_id
                )
            )
            or 0
        )

    def latest_snapshot(self, learner_id: UUID) -> MasterySnapshot | None:
        model = self.session.scalars(
            select(MasterySnapshotModel)
            .where(MasterySnapshotModel.learner_id == learner_id)
            .order_by(MasterySnapshotModel.computed_at.desc(), MasterySnapshotModel.id.desc())
            .limit(1)
        ).first()
        return _to_domain(model) if model else None

    def add_snapshot(self, snapshot: MasterySnapshot) -> MasterySnapshot:
        model = MasterySnapshotModel(
            learner_id=snapshot.learner_id,
            computed_at=snapshot.computed_at,
            model_version=snapshot.model_version,
            n_attempts=snapshot.n_attempts,
            skills=[
                {"code": s.code, "mastery": s.mastery, "attempts": s.attempts}
                for s in snapshot.skills
            ],
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return _to_domain(model)

    def history(self, learner_id: UUID, limit: int | None) -> list[HistoryItem]:
        return self._attempts.history(learner_id, limit)

    def skill_catalog(self) -> dict[str, tuple[str, str, str | None]]:
        """code -> (area, English name, Sinhala name)."""
        rows = self.session.execute(
            select(SkillModel.code, SkillModel.area, SkillModel.name_en, SkillModel.name_si)
        ).all()
        return {code: (area, name_en, name_si) for code, area, name_en, name_si in rows}
