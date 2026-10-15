"""How long a child's photos are kept, and removing them when the time is up.

The rule (agreed with the project owner):

* A page's photo and its question crops are kept for at most 30 days after the upload.
* Once the parent has opened the result report that shows the page, they are kept for 7 more days,
  and no longer than the 30 days.

So the deadline is the earlier of  upload + 30 days  and  first report view + 7 days.

The deadline is enforced when pictures are read (an expired picture is never served, even if the
cleanup has not run yet) and by a daily cleanup that really deletes the files.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.knowledge_tracing.domain.submission import Submission
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.knowledge_tracing.infrastructure.storage.base import StorageBackend

logger = logging.getLogger("mindbridge.retention")

KEEP_AFTER_UPLOAD = timedelta(days=30)
KEEP_AFTER_VIEW = timedelta(days=7)


def aware(moment: datetime) -> datetime:
    """Some databases drop the time zone; everything is UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def photos_expire_at(submission: Submission) -> datetime:
    deadline = aware(submission.uploaded_at) + KEEP_AFTER_UPLOAD
    if submission.report_viewed_at is not None:
        deadline = min(deadline, aware(submission.report_viewed_at) + KEEP_AFTER_VIEW)
    return deadline


def photos_available(submission: Submission, now: datetime) -> bool:
    """False once the files were removed or their time is up (whether or not they are gone yet)."""
    return submission.files_deleted_at is None and now < photos_expire_at(submission)


@dataclass(frozen=True, slots=True)
class SweepResult:
    submissions: int
    files: int

    def __str__(self) -> str:
        return f"{self.submissions} pages cleared, {self.files} files deleted"


class RetentionService:
    def __init__(
        self,
        submissions: SqlAlchemySubmissionRepository,
        storage: StorageBackend,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.submissions = submissions
        self.storage = storage
        self.now = now

    def due(self) -> list[Submission]:
        now = self.now()
        return [s for s in self.submissions.with_files() if now >= photos_expire_at(s)]

    def sweep(self, *, dry_run: bool = False) -> SweepResult:
        """Delete the photo and crops of every page whose time is up."""
        pages = files = 0
        for submission in self.due():
            prefix = f"submissions/{submission.id}/"
            keys = self.storage.list(prefix)
            if dry_run:
                pages += 1
                files += len(keys)
                continue
            failed = False
            for key in keys:
                try:
                    self.storage.delete(key)
                    files += 1
                except Exception:
                    failed = True
                    logger.warning("could not delete %s", key, exc_info=True)
            if failed:
                continue  # try again at the next sweep; do not claim it is gone
            self.submissions.mark_files_deleted(submission.id, self.now())
            pages += 1
        return SweepResult(pages, files)
