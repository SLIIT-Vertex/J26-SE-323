"""Show what this week's paper for a learner really contains, next to what the model thinks of each skill.

    python -m scripts.show_paper_mix                    # the shared development learner
    python -m scripts.show_paper_mix <learner-uuid>

For a demo: after the paper is made (in the app or through /docs), this shows that the questions went to
the skills the model finds weak (and a few to confirm strong ones). Read only.
"""

import argparse
import sys
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.application.paper_generation import week_start_for
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.mastery_repository import SqlAlchemyMasteryRepository
from app.knowledge_tracing.infrastructure.db.paper_repository import SqlAlchemyPaperRepository
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.session import SessionLocal

DEFAULT_LEARNER_ID = "00000000-0000-4000-8000-000000000721"
BAR = 20


def _bar(value: float | None) -> str:
    return "." * BAR if value is None else "#" * round(value * BAR) + "-" * (BAR - round(value * BAR))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("learner_id", nargs="?", type=UUID, default=UUID(DEFAULT_LEARNER_ID))
    args = parser.parse_args(argv)

    spec = get_feature_spec()
    with SessionLocal() as session:
        papers = SqlAlchemyPaperRepository(session)
        paper = papers.find_for_week(args.learner_id, week_start_for(datetime.now(UTC)))
        if paper is None:
            print("no paper has been made for this learner this week", file=sys.stderr)
            return 1
        items = papers.items(paper.id)
        snapshot = MasteryService(SqlAlchemyMasteryRepository(session), get_knowledge_model(), spec).current(
            args.learner_id
        )

    mastery = {skill.code: skill for skill in snapshot.skills}
    per_skill = Counter(item.skill_code for item in items)
    roles = {item.skill_code: item.role for item in items}
    print(f"paper {paper.token}: {paper.mode}, {len(items)} questions on {paper.page_count} page(s), "
          f"about {paper.estimated_minutes:.0f} min\n")
    print(f"{'skill':8} {'seen':>4}  {'mastery':>7}  {'':{BAR}}  {'role':10} {'questions':>9}")
    for code, count in sorted(per_skill.items(), key=lambda pair: (-pair[1], pair[0])):
        skill = mastery[code]
        value = "not yet" if skill.mastery is None else f"{skill.mastery:.2f}"
        print(f"{code:8} {skill.attempts:>4}  {value:>7}  {_bar(skill.mastery)}  {roles[code]:10} {count:>9}")
    mix = Counter(item.role for item in items)
    print("\nby role: " + ", ".join(f"{n} {role}" for role, n in mix.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
