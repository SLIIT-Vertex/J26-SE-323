"""Show which questions this week's paper would contain for one learner (nothing is saved).

    python -m scripts.plan_paper <learner-uuid>
    python -m scripts.plan_paper <learner-uuid> --seed 3 --questions 12 --minutes 20 --pages 2
"""

import argparse
import sys
from uuid import UUID

from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.application.paper_selection import PaperParams
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.session import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner_id", type=UUID)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--questions", type=int, default=15)
    parser.add_argument("--minutes", type=int, default=25)
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--mode", choices=("auto", "practice", "diagnostic"), default="auto")
    parser.add_argument("--language", choices=("si", "ta"))
    parser.add_argument("--focus", nargs="*", default=[], help="skill codes to emphasise")
    args = parser.parse_args()

    spec = get_feature_spec()
    model = get_knowledge_model()
    with SessionLocal() as session:
        mastery = MasteryService(SqlAlchemyMasteryRepository(session), model, spec)
        planner = PaperPlanner(SqlAlchemyPaperInputRepository(session), mastery, model, spec)
        selection = planner.plan(
            args.learner_id,
            PaperParams(
                max_questions=args.questions, max_minutes=args.minutes, max_pages=args.pages,
                seed=args.seed, mode=args.mode, focus_skills=tuple(args.focus),
            ),
            language=args.language,
        )

    print(f"mode: {selection.mode}   solver: {selection.method}   "
          f"questions: {len(selection.questions)}   minutes: {selection.seconds / 60:.1f}   "
          f"height: {selection.height_mm:.0f} mm   value: {selection.total_value}")
    print(f"weak: {', '.join(selection.weak_skills) or '-'}")
    print(f"verify: {', '.join(selection.verify_skills) or '-'}")
    print(f"unknown skills: {len(selection.unknown_skills)}   skipped (no questions): "
          f"{', '.join(selection.skipped_skills) or '-'}")
    print()
    print(f"{'#':>2} {'question':9} {'skill':8} {'level':7} {'role':11} {'p':>5} {'value':>7} {'sec':>4}")
    for number, q in enumerate(selection.questions, start=1):
        p = "-" if q.predicted_p is None else f"{q.predicted_p:.2f}"
        print(f"{number:>2} {q.question_id:9} {q.skill_code:8} {q.difficulty:7} {q.role:11} "
              f"{p:>5} {q.value:>7.3f} {q.est_seconds:>4}")
    for note in selection.notes:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
