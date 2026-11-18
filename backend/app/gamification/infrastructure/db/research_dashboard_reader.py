"""Read-only queries behind the research dashboard."""

from __future__ import annotations

import logging
from collections import Counter
from uuid import UUID

from sqlalchemy import Uuid, bindparam, select, text
from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.game_help_bandit_store import (
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.infrastructure.db.learning_flow_store import digest
from app.gamification.infrastructure.db.models import (
    GameHelpBanditStateModel,
    LearningFlowEpisodeRunModel,
    LearningFlowSupportRoundModel,
    ModelVersionModel,
)
from app.shared.learner.model import LearnerModel

logger = logging.getLogger(__name__)


def _intact(row: LearningFlowEpisodeRunModel) -> bool:
    """The same integrity check the episode store applies before it trusts a row."""

    if digest(row.state_json) == row.state_sha256:
        return True
    logger.warning("research dashboard skipped episode %s: state hash mismatch", row.episode_id)
    return False


def _as_run(row: LearningFlowEpisodeRunModel) -> dict[str, object]:
    return {"state": dict(row.state_json), "status": row.status, "updated_at": row.updated_at}


class SqlAlchemyResearchDashboardReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def profile(self, learner_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LearnerModel, learner_id)
        if row is None:
            return None
        return {
            "learner_id": str(row.id),
            "display_name": row.display_name,
            "grade": row.grade,
            "language": row.preferred_language,
            "account_created": row.created_at.isoformat() if row.created_at else None,
        }

    def run_versions(self) -> tuple[tuple[str, str, str], ...]:
        """Every stored game's id, last update and status: enough to tell whether anything
        changed, without loading any game's state."""

        rows = self.session.execute(
            select(
                LearningFlowEpisodeRunModel.episode_id,
                LearningFlowEpisodeRunModel.updated_at,
                LearningFlowEpisodeRunModel.status,
            ).order_by(LearningFlowEpisodeRunModel.updated_at, LearningFlowEpisodeRunModel.episode_id)
        ).all()
        return tuple((str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def all_runs(self) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(LearningFlowEpisodeRunModel).order_by(LearningFlowEpisodeRunModel.updated_at)
        ).all()
        return [_as_run(row) for row in rows if _intact(row)]

    def runs(self, learner_id: UUID) -> list[dict[str, object]]:
        """Every episode of the learner, oldest first, with its status and last update."""

        rows = self.session.scalars(
            select(LearningFlowEpisodeRunModel)
            .where(LearningFlowEpisodeRunModel.learner_id == learner_id)
            .order_by(
                LearningFlowEpisodeRunModel.updated_at, LearningFlowEpisodeRunModel.episode_id
            )
        ).all()
        return [_as_run(row) for row in rows if _intact(row)]

    def run(self, episode_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LearningFlowEpisodeRunModel, episode_id)
        if row is None or not _intact(row):
            return None
        return _as_run(row)

    def help_order_ledger(self, episode_id: UUID) -> list[dict[str, object]]:
        """What one episode taught the help-order bandit, in applied order."""

        return SqlAlchemyGameHelpBanditStore(self.session).ledger_for_episode(episode_id)

    def help_order_version(self) -> tuple[tuple[str, str, str, int], ...]:
        """Every help-order artifact's approval and ledger position: enough to tell whether an
        approval changed, without loading any artifact."""

        rows = self.session.execute(
            select(
                ModelVersionModel.model_name,
                ModelVersionModel.artifact_sha256,
                ModelVersionModel.approval_status,
                GameHelpBanditStateModel.ledger_position,
            )
            .outerjoin(
                GameHelpBanditStateModel,
                GameHelpBanditStateModel.model_version_id == ModelVersionModel.id,
            )
            .where(ModelVersionModel.model_name.like("game-help-order-bandit:%"))
            .order_by(ModelVersionModel.model_name, ModelVersionModel.artifact_sha256)
        ).all()
        return tuple((str(r[0]), str(r[1]), str(r[2]), int(r[3] or 0)) for r in rows)

    def help_order_subjects(self) -> dict[str, dict[str, object]]:
        """Each subject's approved help-order bandit: its parameters, ledger and decisions."""

        store = SqlAlchemyGameHelpBanditStore(self.session)
        return {
            subject: {
                "parameters": parameters,
                "ledger": store.ledger_with_snapshots(model_version_id),
                "decisions": store.decisions(model_version_id),
            }
            for subject, (model_version_id, parameters) in store.approved_artifacts().items()
        }

    def round_counts(self, episode_ids: list[UUID]) -> Counter[UUID]:
        return Counter(
            self.session.scalars(
                select(LearningFlowSupportRoundModel.episode_id).where(
                    LearningFlowSupportRoundModel.episode_id.in_(episode_ids)
                )
            ).all()
        )

    def learner_state(self, learner_id: UUID) -> list[dict[str, object]]:
        """Learner State's latest result per broad skill. Plain SQL: the gamification module does
        not import another module's persistence model."""

        statement = text(
            "select skill_id, session_id, confusion_state, confusion_support_need, "
            "confusion_temporal_score, disengagement_state, disengagement_support_need, "
            "recommended_action, support_need, observed_at from learner_skill_states "
            "where learner_id = :learner order by skill_id"
        ).bindparams(bindparam("learner", type_=Uuid))
        return [
            dict(row) for row in self.session.execute(statement, {"learner": learner_id}).mappings()
        ]
