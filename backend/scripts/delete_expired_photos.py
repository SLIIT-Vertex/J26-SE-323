"""Delete the photos and crops of pages whose retention time is up.

    python -m scripts.delete_expired_photos --dry-run   # list what would go, delete nothing
    python -m scripts.delete_expired_photos             # delete

A page's photo and crops are kept for at most 30 days after the upload, and for 7 days after the
parent first opened the result report that shows them (whichever comes first). Run this once a
day: Windows Task Scheduler on a laptop, a scheduled job (for example an AWS EventBridge rule) in
production. An expired picture is never served even before this runs; this makes the deletion real.

Exit status 0 on success.
"""

import argparse
import sys

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

    storage = create_paper_storage(get_settings())
    with SessionLocal() as session:
        service = RetentionService(SqlAlchemySubmissionRepository(session), storage)
        result = service.sweep(dry_run=args.dry_run)
    print(("would clear: " if args.dry_run else "cleared: ") + str(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
