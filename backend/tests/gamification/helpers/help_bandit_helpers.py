"""Approve the expert-initialised help-order bandits in a test database, as the researcher would."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.game_help_bandit_store import (
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.modeling.support_selection.game_bandit import load_game_help_bandit


def approve_expert_start(session: Session, *subjects: str) -> None:
    store = SqlAlchemyGameHelpBanditStore(session)
    now = datetime.now(UTC)
    for subject in subjects or ("MAT", "ENG", "SIN"):
        draft = store.register_draft(load_game_help_bandit(subject), now=now)
        store.approve(
            subject=subject, artifact_sha256=draft.artifact_sha256, approved_by="test", now=now
        )
    session.commit()
