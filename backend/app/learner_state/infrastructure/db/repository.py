from uuid import UUID

from sqlalchemy.orm import Session

from app.learner_state.application.support_need import LearnerSkillState
from app.learner_state.infrastructure.db.models import LearnerSkillStateModel

_STATE_FIELDS = (
    "session_id",
    "window_id",
    "observed_at",
    "confusion_state",
    "confusion_support_need",
    "confusion_temporal_score",
    "disengagement_state",
    "disengagement_support_need",
    "recommended_action",
    "support_need",
)


def _to_domain(model: LearnerSkillStateModel) -> LearnerSkillState:
    return LearnerSkillState(
        learner_id=model.learner_id,
        skill_id=model.skill_id,
        **{name: getattr(model, name) for name in _STATE_FIELDS},
    )


class SqlAlchemyLearnerSkillStateRepository:
    """Keeps one row per (learner_id, skill_id), overwritten by each new window."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, state: LearnerSkillState) -> None:
        model = self.session.get(LearnerSkillStateModel, (state.learner_id, state.skill_id))

        if model is None:
            model = LearnerSkillStateModel(learner_id=state.learner_id, skill_id=state.skill_id)
            self.session.add(model)

        for name in _STATE_FIELDS:
            setattr(model, name, getattr(state, name))

        self.session.commit()

    def get(self, learner_id: UUID, skill_id: str) -> LearnerSkillState | None:
        model = self.session.get(LearnerSkillStateModel, (learner_id, skill_id))
        return _to_domain(model) if model else None
