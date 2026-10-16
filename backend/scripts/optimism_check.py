"""How optimistic is the model for a child who gets almost everything wrong?

Simulates many children who answered 6 questions of ONE skill and got exactly 1 right (the right
one is at a random position, the source is random: game or paper, and the game penalty is drawn
from the golden histories). Prints the minimum, median and maximum mastery of that skill.

    python -m scripts.optimism_check --students 1000 --seed 2026
"""

import argparse
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel

GOLDEN = Path(__file__).resolve().parents[1] / "tests/knowledge_tracing/fixtures/golden_history.json"


def digital_penalties() -> list[float]:
    students = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return sorted(
        {p for s in students for p, src in zip(s["penalties"], s["sources"], strict=True) if int(src) == 1}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--answers", type=int, default=6)
    parser.add_argument("--correct", type=int, default=1)
    args = parser.parse_args()

    spec = get_feature_spec()
    model = KnowledgeModel.load(get_settings().model_weights_path, spec)
    rng = random.Random(args.seed)
    penalties = digital_penalties()
    values: list[float] = []
    for _ in range(args.students):
        skill = rng.randrange(len(spec.skills))
        right = set(rng.sample(range(args.answers), args.correct))
        history = []
        for n in range(args.answers):
            source = rng.choice((0, 1))
            history.append(
                HistoryItem(
                    attempt_id=n,
                    question_id="sim",
                    language="si",
                    skill_code=spec.skills[skill],
                    skill_index=skill,
                    difficulty="medium",
                    correct=n in right,
                    source=source,
                    penalty=spec.paper_penalty if source == 0 else rng.choice(penalties),
                    answered_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
        mastery = next(m.mastery for m in model.mastery(history) if m.code == spec.skills[skill])
        if mastery is not None:
            values.append(mastery)

    print(f"model {model.version}; {len(values)} simulated children, "
          f"{args.correct} correct out of {args.answers} in one skill")
    print(f"mastery  min {min(values):.3f}   median {statistics.median(values):.3f}   "
          f"max {max(values):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
