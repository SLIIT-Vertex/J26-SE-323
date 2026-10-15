"""Delete the photos and crops of answered pages that are older than the retention time.

    python -m scripts.delete_old_photos --dry-run   # show how many would go, delete nothing
    python -m scripts.delete_old_photos             # delete, then print how many

The retention time is PHOTO_RETENTION_DAYS in .env (default 30): photos older than that are
removed, counted from the upload. A page whose result report was opened more than 7 days ago is
removed sooner, as agreed with the project owner. An expired picture is never served even before
this script runs; the script makes the deletion real.

Run it once a day (Windows Task Scheduler on a laptop, a scheduled job in production).
Exit status 0 on success, 1 if some file could not be deleted.
"""

import argparse
import sys
from datetime import timedelta

from app.config import get_settings
from app.knowledge_tracing.application.retention import RetentionService
from app.knowledge_tracing.infrastructure.db.submission_repository import (
    SqlAlchemySubmissionRepository,
)
from app.knowledge_tracing.infrastructure.storage import create_paper_storage
from app.shared.database.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would be deleted")
    args = parser.parse_args()

    settings = get_settings()
    storage = create_paper_storage(settings)
    with SessionLocal() as session:
        service = RetentionService(
            SqlAlchemySubmissionRepository(session),
            storage,
            keep_after_upload=timedelta(days=settings.photo_retention_days),
        )
        result = service.sweep(dry_run=args.dry_run)
        remaining = len(service.due()) if not args.dry_run else result.submissions
    verb = "would delete" if args.dry_run else "deleted"
    print(
        f"{verb} {result.files} photo/crop files from {result.submissions} pages "
        f"(retention {settings.photo_retention_days} days)"
    )
    return 1 if remaining and not args.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
