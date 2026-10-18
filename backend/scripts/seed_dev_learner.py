"""Create the shared development learner, once.

    python -m scripts.seed_dev_learner
    python -m scripts.seed_dev_learner --joined-days-ago 14

There is no login or user management yet, so the game and the practice screens in the app share one
development learner (the same id, set by VITE_MOBILE_LEARNING_LEARNER_ID in the frontend). Both the
game's evidence and the paper answers point at this learner in the database, so it has to exist
before either can save anything.

Safe to run again: if the learner is already there, nothing is changed.

The weekly paper opens PAPER_MIN_DAYS_AFTER_JOINING days after a learner joined (7 by default).
For a learner created today, either set that to 0 in backend/.env while developing, or use
--joined-days-ago to record an earlier joining date for this test learner.

For development databases only: do not use it to create real children.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.shared.database.session import SessionLocal
from app.shared.learner.model import LearnerModel

# The same default as the frontend (features/papers/hooks.ts and the game's MobileLearningApp).
DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", default=DEFAULT_LEARNER_ID, help="the learner id (default: the shared one)")
    parser.add_argument("--grade", type=int, choices=(4, 5), default=5)
    parser.add_argument("--language", choices=("si", "ta"), default="si")
    parser.add_argument(
        "--joined-days-ago",
        type=int,
        default=0,
        metavar="DAYS",
        help="record this learner as having joined this many days ago (default: today)",
    )
    args = parser.parse_args()

    try:
        learner_id = UUID(args.id)
    except ValueError:
        print(f"not a valid learner id: {args.id!r}", file=sys.stderr)
        return 2
    if args.joined_days_ago < 0:
        print("--joined-days-ago cannot be negative", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        existing = session.get(LearnerModel, learner_id)
        if existing is not None:
            print(
                f"already exists, nothing changed: {learner_id} "
                f"(grade {existing.grade}, {existing.preferred_language})"
            )
            return 0
        joined = datetime.now(UTC) - timedelta(days=args.joined_days_ago)
        session.add(
            LearnerModel(
                id=learner_id,
                grade=args.grade,
                preferred_language=args.language,
                created_at=joined,
                updated_at=joined,
            )
        )
        session.commit()
    print(f"created {learner_id} (grade {args.grade}, {args.language}, joined {joined:%Y-%m-%d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
