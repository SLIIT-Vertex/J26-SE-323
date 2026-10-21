"""Composition of the Learning State module's published provider for in-process consumers."""

from app.learner_state.application.support_need import StoredSupportNeedProvider
from app.learner_state.infrastructure.db.repository import SqlAlchemyLearnerSkillStateRepository


def stored_learning_state_provider(session):
    return StoredSupportNeedProvider(SqlAlchemyLearnerSkillStateRepository(session))
