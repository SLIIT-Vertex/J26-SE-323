"""Show what the model knows about one learner, and how that shapes this week's paper (nothing is saved
except the mastery snapshot the model keeps anyway).

    python -m scripts.show_mastery                      # the shared development learner
    python -m scripts.show_mastery <learner-uuid>
    python -m scripts.show_mastery --seed 3 --questions 12
    python -m scripts.show_mastery --mode practice      # force the weighting by weak skills (see below)

The planner builds a "diagnostic" paper (one question per skill) while more than 15 of the 30 skills have
fewer than 3 answers. Only a "practice" paper leans on weak skills. The game reaches 11 of the 30 skills,
so game answers alone keep the learner in diagnostic mode until paper answers add more skills; `--mode
practice` lets you see the weighting early.

One row per skill: how many answers the model has seen (game and paper), its estimate, and the part the
skill would play in the paper: `weak` skills get the most questions, `verify` skills a few to confirm a
high estimate, `unknown` skills (fewer than 3 answers) a few to learn about them, `strong` skills the least.
"""

import argparse
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy import func, select

from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_planning import PaperPlanner
from app.knowledge_tracing.application.paper_selection import PaperParams
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import SqlAlchemyMasteryRepository
from app.knowledge_tracing.infrastructure.db.models import AttemptModel
from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
    SqlAlchemyPaperInputRepository,
)
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.session import SessionLocal

DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"  # the learner the game and the papers share
BAR = 20


def _bar(value: float | None) -> str:
    if value is None:
        return "." * BAR
    filled = round(value * BAR)
    return "#" * filled + "-" * (BAR - filled)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner_id", nargs="?", type=UUID, default=UUID(DEFAULT_LEARNER_ID))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--minutes", type=int, default=35)
    parser.add_argument("--pages", type=int, default=4)
    parser.add_argument("--mode", choices=("auto", "practice", "diagnostic"), default="auto")
    args = parser.parse_args(argv)

    spec = get_feature_spec()
    model = get_knowledge_model()
    with SessionLocal() as session:
        mastery_service = MasteryService(SqlAlchemyMasteryRepository(session), model, spec)
        snapshot = mastery_service.recompute(args.learner_id)
        planner = PaperPlanner(SqlAlchemyPaperInputRepository(session), mastery_service, model, spec)
        selection = planner.plan(
            args.learner_id,
            PaperParams(
                max_questions=args.questions, max_minutes=args.minutes, max_pages=args.pages,
                seed=args.seed, mode=args.mode, focus_skills=(),
            ),
            language=None,
        )
        by_source = dict(
            session.execute(
                select(AttemptModel.source, func.count())
                .where(AttemptModel.learner_id == args.learner_id)
                .group_by(AttemptModel.source)
            ).all()
        )

    asked = Counter(question.skill_code for question in selection.questions)
    role_of = {question.skill_code: question.role for question in selection.questions}
    for code in selection.weak_skills:
        role_of.setdefault(code, "weak")
    for code in selection.verify_skills:
        role_of.setdefault(code, "verify")

    print(f"learner {args.learner_id}   model {snapshot.model_version}")
    print(f"answers seen: {by_source.get(1, 0)} from the game, {by_source.get(0, 0)} from paper\n")
    print(f"{'skill':8} {'seen':>4}  {'mastery':>7}  {'':{BAR}}  {'role in paper':13} {'questions':>9}")
    for skill in sorted(snapshot.skills, key=lambda s: (s.attempts == 0, -(s.attempts))):
        if skill.attempts == 0 and skill.code not in asked:
            continue
        value = "not yet" if skill.mastery is None else f"{skill.mastery:.2f}"
        role = role_of.get(skill.code, "-")
        print(f"{skill.code:8} {skill.attempts:>4}  {value:>7}  {_bar(skill.mastery)}  {role:13} {asked.get(skill.code, 0):>9}")
    untouched = sum(1 for s in snapshot.skills if s.attempts == 0 and s.code not in asked)
    if untouched:
        print(f"({untouched} more skills have no answers and no questions in this paper)")

    print(f"\nthe paper would hold {len(selection.questions)} questions, about {selection.seconds / 60:.0f} minutes "
          f"(mode: {selection.mode}, solver: {selection.method})")
    roles = Counter(question.role for question in selection.questions)
    print("  by role: " + ", ".join(f"{count} {role}" for role, count in roles.most_common()))
    if selection.weak_skills:
        print(f"  weak skills it leans on: {', '.join(selection.weak_skills)}")
    for note in selection.notes:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
