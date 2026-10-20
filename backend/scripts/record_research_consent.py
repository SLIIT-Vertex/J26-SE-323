"""Record (or withdraw) a learner's research consent, so the pilot can release their game answers.

    python -m scripts.record_research_consent --learner-id <uuid>
    python -m scripts.record_research_consent --learner-id <uuid> --withdraw

The game releases a scored answer to the models only in the `pilot` environment, and only for a learner
whose research consent is on record (see `NumberWorldFlow._model_eligible`). Run this once the
guardian's written consent has been collected, outside the app. A newer decision replaces the older
one, so `--withdraw` stops the release for answers given from then on. Answers already read are not
changed by it.

There is no guardian login yet: this is how the team records a consent it already holds on paper.
"""

import argparse
import sys
from datetime import UTC, datetime
from uuid import UUID

from app.gamification.application.consent_gate import RESEARCH_CONSENT_PURPOSE
from app.gamification.application.records import ConsentDecision
from app.gamification.infrastructure.db.consent_store import (
    CONSENT_CONTRACT,
    SqlAlchemyConsentStore,
)
from app.shared.database.session import SessionLocal
from app.shared.learner.model import LearnerModel

RESEARCH_CONSENT_VERSION = "research-pilot-consent-v1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--learner-id", required=True, type=UUID)
    parser.add_argument("--withdraw", action="store_true", help="record that consent is withdrawn")
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if session.get(LearnerModel, args.learner_id) is None:
            print(f"no learner {args.learner_id} in this database", file=sys.stderr)
            return 1
        SqlAlchemyConsentStore(session).record(
            ConsentDecision(
                learner_id=args.learner_id,
                purpose=RESEARCH_CONSENT_PURPOSE,
                granted=not args.withdraw,
                consent_version=RESEARCH_CONSENT_VERSION,
                decided_at=datetime.now(UTC),
                expires_at=None,
                contract_version=CONSENT_CONTRACT,
            )
        )
    print(f"research consent {'withdrawn' if args.withdraw else 'recorded'} for {args.learner_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
