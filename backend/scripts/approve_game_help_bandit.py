"""Register or approve a subject's expert-initialised help-order bandit for the games.

    python -m scripts.approve_game_help_bandit --subject MAT
    python -m scripts.approve_game_help_bandit --subject MAT \\
        --approve <artifact sha256> --approved-by "<researcher name>"

The first form registers the artifact built from the checked expert model data as a draft and
prints its SHA-256. The second approves that exact artifact: the hash must match what was
registered, so the approval names what was reviewed. Approving retires the subject's previous
artifact, and the new one starts learning from ledger position 0.

Until a subject has an approved artifact, its games give the proposed condition the subject's
fixed order. The approval covers the expert data, the context version, the failed-round weight,
the uninformed-feature precision and the credit rule; changing any of them makes a new artifact
that needs its own approval.
"""

import argparse
import sys
from datetime import UTC, datetime

from app.gamification.infrastructure.db.game_help_bandit_store import (
    GameHelpBanditStoreError,
    SqlAlchemyGameHelpBanditStore,
)
from app.gamification.modeling.support_selection.game_bandit import load_game_help_bandit
from app.shared.database.session import SessionLocal

SUBJECTS = ("MAT", "ENG", "SIN")


def main(argv: list[str] | None = None, *, session_factory=SessionLocal) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", required=True, choices=SUBJECTS)
    parser.add_argument("--approve", metavar="SHA256", help="approve this registered artifact")
    parser.add_argument("--approved-by", help="the researcher approving it")
    args = parser.parse_args(argv)
    if args.approve and not args.approved_by:
        parser.error("--approve needs --approved-by")

    now = datetime.now(UTC)
    with session_factory() as session:
        store = SqlAlchemyGameHelpBanditStore(session)
        try:
            draft = store.register_draft(load_game_help_bandit(args.subject), now=now)
            if args.approve:
                if args.approve != draft.artifact_sha256:
                    print(
                        f"{args.subject}: the artifact built now is {draft.artifact_sha256}, "
                        f"not {args.approve}; nothing approved",
                        file=sys.stderr,
                    )
                    session.rollback()
                    return 1
                draft = store.approve(
                    subject=args.subject,
                    artifact_sha256=args.approve,
                    approved_by=args.approved_by,
                    now=now,
                )
        except GameHelpBanditStoreError as error:
            session.rollback()
            print(f"{args.subject}: {error}", file=sys.stderr)
            return 1
        session.commit()
    print(f"{args.subject} {draft.approval_status} {draft.artifact_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
