"""Give a DEMO learner a prepared answer history: strong skills, weak skills and in-between ones.

    python -m scripts.seed_demo_history --create
    python -m scripts.seed_demo_history --learner-id <uuid> --create

For showing the model to a panel: a child who is strong in some skills and weak in others, so the weekly
paper visibly leans on the weak ones. The answers are saved as game answers (source = game), the same
way the game's answers are saved when they are read from its outbox. Say so when you show it: the history
was prepared in advance; in real use it builds up as the child plays.

16 skills get at least 3 answers, so the learner is no longer "new": the paper planner builds a practice
paper (not the one-question-per-skill diagnostic paper) and weights it by what the model estimates.

Safe to run again (every answer has a fixed key, so nothing is saved twice). Development databases only.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.knowledge_tracing.application.attempts import AttemptService, DigitalAttemptCommand
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import SqlAlchemyAttemptRepository
from app.shared.database.session import SessionLocal
from app.shared.learner.model import LearnerModel

DEMO_LEARNER_ID = "00000000-0000-4000-8000-000000000801"

# skill -> answers, in order ("1" right, "0" wrong). The model is careful: about 10 right answers in a
# row are needed before a skill stops looking weak, and a handful of wrong ones make it clearly weak.
STRONG = "111111111111"  # 12 of 12
WEAK = "010000"  # 1 of 6
MIXED = "110110"  # 4 of 6
HISTORY = {
    # strong
    "MAT-NUM": STRONG,
    "MAT-OPS": STRONG,
    "MAT-MON": STRONG,
    "LAN-VOC": STRONG,
    "ENV-BIO": STRONG,
    # weak
    "MAT-FRC": WEAK,
    "MAT-TIM": WEAK,
    "MAT-GEO": WEAK,
    "MAT-MAS": WEAK,
    "LAN-AGR": WEAK,
    "APT-PAT": WEAK,
    # in between
    "MAT-LEN": MIXED,
    "MAT-DAT": MIXED,
    "LAN-CMP": MIXED,
    "ENV-PHY": MIXED,
    "ENV-HLT": MIXED,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--learner-id", type=UUID, default=UUID(DEMO_LEARNER_ID))
    parser.add_argument("--create", action="store_true", help="create the learner if it does not exist")
    parser.add_argument("--language", choices=("si", "ta"), default="si")
    args = parser.parse_args(argv)

    spec = get_feature_spec()
    unknown = sorted(set(HISTORY) - set(spec.skills))
    if unknown:
        print(f"not skills of ours: {unknown}", file=sys.stderr)
        return 2

    now = datetime.now(UTC)
    with SessionLocal() as session:
        learner = session.get(LearnerModel, args.learner_id)
        if learner is None:
            if not args.create:
                print(f"no learner {args.learner_id} here; add --create to make it", file=sys.stderr)
                return 1
            joined = now - timedelta(days=14)
            session.add(LearnerModel(id=args.learner_id, grade=5, preferred_language=args.language,
                                     created_at=joined, updated_at=joined))
            session.commit()
            print(f"created learner {args.learner_id}")

        repository = SqlAlchemyAttemptRepository(session)
        service = AttemptService(repository, spec)
        saved = already = 0
        total = sum(len(pattern) for pattern in HISTORY.values())
        step = 0
        for skill, pattern in HISTORY.items():
            for number, mark in enumerate(pattern):
                step += 1
                _, created = service.log_digital_attempt(
                    DigitalAttemptCommand(
                        learner_id=args.learner_id,
                        language=args.language,
                        correct=mark == "1",
                        answered_at=now - timedelta(minutes=(total - step) * 3 + 5),  # in the past, in order
                        question_id=None,
                        skill_code=skill,
                        difficulty="medium",
                        time_ms=8_000 + 700 * (number % 5),
                        hints=0,
                        idempotency_key=f"demo-history:{args.learner_id}:{skill}:{number}",
                    )
                )
                saved += created
                already += not created
    print(f"saved {saved} answers ({already} were already there) across {len(HISTORY)} skills")
    print("next:  python -m scripts.show_mastery", args.learner_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
