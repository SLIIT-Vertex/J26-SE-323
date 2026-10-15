"""Marking that was interrupted by a server restart.

Pages are marked in the background of the server process. If the server stops while a page is
"grading", nothing will ever finish it. At startup NOTHING can still be running (marking lives in
this process), so every page in "grading" is put back to "uploaded" and marked again, however
recently it started. `stuck_after` stays as a parameter for a caller that runs beside live
workers; the startup hook passes zero.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)

logger = logging.getLogger("mindbridge.recovery")

STUCK_AFTER = timedelta(minutes=5)  # for callers that run while other workers are live
AT_STARTUP = timedelta(0)


def recover_stuck_grading(
    submissions: SqlAlchemySubmissionRepository,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    stuck_after: timedelta = STUCK_AFTER,
) -> list[UUID]:
    """Reset pages stuck in "grading" and return their ids, so the caller can mark them again."""
    ids = submissions.reset_stuck_grading(now() - stuck_after)
    if ids:
        logger.warning("%d page(s) were stuck in grading and were set back to uploaded", len(ids))
    return ids
