"""Read the game's scored answers and save the usable ones as game answers for the model.

    python -m scripts.ingest_game_evidence --dry-run               # show what would be saved
    python -m scripts.ingest_game_evidence                         # save them
    python -m scripts.ingest_game_evidence --include-development   # local trial only (see below)

The game writes one record per scored answer into its outbox table. A record is used only when the
game marks it as eligible for models, its skill agrees with the skill crosswalk, and its fields are
complete. Everything else is skipped and counted, with the reason. Running it again is safe: an
answer that was already saved is recognised and not saved twice. The game's table is never changed.

Today every record the game writes is marked as a development record that must not reach a model,
so a normal run saves nothing. `--include-development` also accepts development and test records.
Use it only to try the whole flow on a local database: it puts a test child's answers into the
model's history.

Exit status 0 on success, 1 if the skill crosswalk cannot be read.
"""

import argparse
import sys
from pathlib import Path

from app.knowledge_tracing.application.attempts import AttemptService
from app.knowledge_tracing.application.game_evidence import (
    CrosswalkUnavailable,
    GameEvidenceIngestor,
    checked_skills,
    load_crosswalk,
    load_game_skill_map,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.game_evidence_repository import (
    OutboxEvidenceSource,
)
from app.shared.database.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report only, save nothing")
    parser.add_argument(
        "--include-development",
        action="store_true",
        help="also accept records marked as development or test (local trial only)",
    )
    parser.add_argument("--crosswalk", type=Path, help="the skill crosswalk file (default: the game's)")
    args = parser.parse_args()

    try:
        skill_map = load_game_skill_map()
        crosswalk = checked_skills(load_crosswalk(args.crosswalk), skill_map)
    except CrosswalkUnavailable as error:
        print(f"nothing was read: {error}", file=sys.stderr)
        return 1

    spec = get_feature_spec()
    with SessionLocal() as session:
        source = OutboxEvidenceSource(session)
        if not source.available():
            print(
                "nothing to read: this database has no game outbox table "
                "(learner_evidence_outbox). Run the game's migrations first."
            )
            return 0
        repository = SqlAlchemyAttemptRepository(session)
        ingestor = GameEvidenceIngestor(
            source,
            AttemptService(repository, spec),
            repository.learner_language,
            spec,
            crosswalk,
            include_development=args.include_development,
            sub_skills=skill_map.sub_skills,
        )
        report = ingestor.run(dry_run=args.dry_run)

    print("DRY RUN: nothing was saved" if args.dry_run else "done")
    print(report)
    if args.include_development and not args.dry_run and report.ingested:
        print("note: development records were included; use a local database only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
