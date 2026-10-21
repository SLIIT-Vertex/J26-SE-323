"""Reads the game's new answers right before the knowledge model is asked.

Without this, the game's answers sit in its outbox until someone runs
`python -m scripts.ingest_game_evidence`. With `GAME_EVIDENCE_AUTO_READ=true`, asking for a learner's
mastery or making their weekly paper first reads that learner's new game answers, so what the model
shows is up to date. It is the same reader and the same rules as the script (the game's release flag,
the skill check, difficulty), and a record is never saved twice.

It never breaks the request it runs in: if anything goes wrong it logs a warning and the request
carries on with the answers the model already has.
"""

import logging
import time
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.knowledge_tracing.application.attempts import AttemptService
from app.knowledge_tracing.application.game_evidence import (
    GameEvidenceIngestor,
    checked_skills,
    load_crosswalk,
    load_game_skill_map,
)
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import SqlAlchemyAttemptRepository
from app.knowledge_tracing.infrastructure.db.game_evidence_repository import OutboxEvidenceSource
from app.knowledge_tracing.infrastructure.db.mastery_repository import SqlAlchemyMasteryRepository
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.session import get_db

log = logging.getLogger(__name__)

# One page load asks for several things at once; reading the outbox once every few seconds is enough.
MIN_SECONDS_BETWEEN_READS = 3.0
_last_read: dict[UUID, float] = {}


def read_new_game_answers(
    session: Session,
    learner_id: UUID,
    *,
    settings: Settings | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Save this learner's new, usable game answers; return how many were saved. 0 when switched off."""
    settings = settings or get_settings()
    if not settings.game_evidence_auto_read:
        return 0
    now = clock()
    last = _last_read.get(learner_id)
    if last is not None and now - last < MIN_SECONDS_BETWEEN_READS:
        return 0
    _last_read[learner_id] = now

    try:
        source = OutboxEvidenceSource(session, learner_id)
        if not source.available():
            return 0  # the game's tables are not in this database
        spec = get_feature_spec()
        skill_map = load_game_skill_map()
        repository = SqlAlchemyAttemptRepository(session)
        report = GameEvidenceIngestor(
            source,
            AttemptService(repository, spec),
            repository.learner_language,
            spec,
            checked_skills(load_crosswalk(), skill_map),
            include_development=settings.game_evidence_include_development,
            sub_skills=skill_map.sub_skills,
        ).run()
        if report.ingested:
            # new answers: show them now, not after the usual short wait before a recompute
            MasteryService(SqlAlchemyMasteryRepository(session), get_knowledge_model(), spec).refresh(learner_id)
        return report.ingested
    except Exception:
        log.warning("could not read the game's new answers for %s; carrying on without", learner_id, exc_info=True)
        session.rollback()
        return 0


def sync_game_answers(learner_id: UUID, session: Annotated[Session, Depends(get_db)]) -> None:
    """A route dependency: read the learner's new game answers before the route runs."""
    read_new_game_answers(session, learner_id)
