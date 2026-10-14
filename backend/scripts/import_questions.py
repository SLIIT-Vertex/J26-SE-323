"""Import the question bank (answers, skills, difficulty, S3 images) into the database.

    python -m scripts.import_questions            # check only: prints every problem, writes nothing
    python -m scripts.import_questions --apply    # write, only if there are no errors
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.knowledge_tracing.application.question_import import (
    ImportPlan,
    QuestionBankFiles,
    build_plan,
    load_files,
)
from app.knowledge_tracing.infrastructure.db.question_bank_writer import write_plan
from app.knowledge_tracing.infrastructure.storage import create_storage
from app.knowledge_tracing.infrastructure.storage.question_images import StorageImageSource
from app.shared.database.session import SessionLocal

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "question_bank"


def feature_spec_order(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    spec = json.loads(path.read_text(encoding="utf-8"))
    skills = spec.get("skills", [])
    return [s["code"] if isinstance(s, dict) else s for s in skills]


def prefetch_images(files: QuestionBankFiles, source: StorageImageSource) -> None:
    from app.knowledge_tracing.application.question_files import parse_answers

    pairs = [
        (language, entry.question_id)
        for (_, language), (_, text) in files.answers.items()
        for entry in parse_answers(text).entries.values()
    ]
    source.prefetch(pairs)


def print_report(plan: ImportPlan) -> None:
    for issue in plan.issues:
        print(issue)
    kinds = Counter(p.answer_kind for q in plan.questions for v in q.variants.values()
                    for p in v.parts)
    print()
    print(f"skills: {len(plan.skills)}   questions: {len(plan.questions)}   "
          f"variants: {sum(len(q.variants) for q in plan.questions)}   "
          f"parts: {sum(kinds.values())} {dict(kinds)}")
    print(f"errors: {len(plan.errors)}   warnings: {len(plan.warnings)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="question bank folder")
    parser.add_argument("--apply", action="store_true", help="write to the database")
    parser.add_argument("--workers", type=int, default=8, help="parallel image downloads")
    args = parser.parse_args()

    settings = get_settings()
    storage = create_storage(settings)
    print(f"storage: {settings.storage_backend}  prefix: {settings.s3_question_prefix!r}  "
          f"folder: {args.dir}")

    files = load_files(args.dir)
    source = StorageImageSource(storage, settings.s3_question_prefix, workers=args.workers)
    prefetch_images(files, source)
    order = feature_spec_order(Path(settings.feature_spec_path))
    plan = build_plan(files, source, order)
    print_report(plan)

    if not plan.ok:
        print("\nNothing was written: fix the errors above and run again.")
        return 1
    if not args.apply:
        print("\nCheck passed. Run again with --apply to write to the database.")
        return 0
    with SessionLocal() as session, session.begin():
        counts = write_plan(session, plan)
    print(f"\nWritten: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
