"""How much does the constant paper penalty matter?

Paper answers have no per-question time or hints, so they get a constant penalty (0.08).
This script takes the golden histories, sets every PAPER attempt's penalty to 0.0, 0.08 and
0.12, recomputes mastery, and prints the largest change per skill. A change above 0.05
anywhere means the missing paper time/hints matter and the team should decide whether to
collect them.

    python -m scripts.penalty_sensitivity                  # the 3 golden histories
    python -m scripts.penalty_sensitivity --students 100   # 100 simulated histories, summary only
"""

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.knowledge_tracing.domain.attempt import HistoryItem
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.ml.service import KnowledgeModel

GOLDEN = Path(__file__).resolve().parents[1] / "tests/knowledge_tracing/fixtures/golden_history.json"
PENALTIES = (0.0, 0.08, 0.12)
BASELINE = 0.08
THRESHOLD = 0.05


def history_from(student: dict, spec, paper_penalty: float) -> list[HistoryItem]:
    items = []
    rows = zip(
        student["skills"], student["corrects"], student["sources"], student["penalties"],
        strict=True,
    )
    for number, (skill, correct, source, penalty) in enumerate(rows):
        items.append(
            HistoryItem(
                attempt_id=number,
                question_id="golden",
                language="si",
                skill_code=spec.skills[skill],
                skill_index=skill,
                difficulty="medium",
                correct=bool(correct),
                source=int(source),
                penalty=paper_penalty if int(source) == 0 else penalty,
                answered_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    return items


def simulate_students(count: int, seed: int, spec) -> list[dict]:
    """Histories of 60-140 answers: each child has an ability per skill, 70% of answers come
    from the game (with a game penalty drawn from the golden histories) and 30% from paper."""
    rng = random.Random(seed)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    game_penalties = sorted(
        {p for g in golden for p, s in zip(g["penalties"], g["sources"], strict=True) if int(s) == 1}
    )
    students = []
    for _ in range(count):
        base = rng.uniform(0.25, 0.85)
        ability = [min(0.97, max(0.03, rng.gauss(base, 0.15))) for _ in spec.skills]
        skills, corrects, sources, penalties = [], [], [], []
        for _ in range(rng.randint(60, 140)):
            skill = rng.randrange(len(spec.skills))
            source = 1 if rng.random() < 0.7 else 0
            skills.append(skill)
            corrects.append(1 if rng.random() < ability[skill] else 0)
            sources.append(source)
            penalties.append(rng.choice(game_penalties) if source == 1 else BASELINE)
        students.append(
            {"skills": skills, "corrects": corrects, "sources": sources, "penalties": penalties}
        )
    return students


def summary(spec, model, students: list[dict]) -> int:
    changes: list[float] = []
    for student in students:
        by_penalty = {
            penalty: {m.code: m.mastery for m in model.mastery(history_from(student, spec, penalty))}
            for penalty in PENALTIES
        }
        for code in spec.skills:
            values = [by_penalty[p][code] for p in PENALTIES]
            if all(v is not None for v in values):
                changes.append(max(values) - min(values))
    changes.sort()
    over = sum(1 for c in changes if c > THRESHOLD)
    print(f"model {model.version}; {len(students)} simulated students, {len(changes)} skill values")
    print(
        f"change in mastery when the paper penalty is 0.0 / 0.08 / 0.12: "
        f"median {changes[len(changes) // 2]:.3f}  95th percentile {changes[int(len(changes) * 0.95)]:.3f}"
        f"  max {changes[-1]:.3f}  (threshold {THRESHOLD})"
    )
    print(f"values above the threshold: {over} of {len(changes)} ({100 * over / len(changes):.2f}%)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=0, help="simulate this many students")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    spec = get_feature_spec()
    model = KnowledgeModel.load(get_settings().model_weights_path, spec)
    if args.students:
        return summary(spec, model, simulate_students(args.students, args.seed, spec))
    students = json.loads(GOLDEN.read_text(encoding="utf-8"))

    print(f"model {model.version}; paper penalties compared: {PENALTIES}; baseline {BASELINE}\n")
    worst_overall = 0.0
    for number, student in enumerate(students, start=1):
        paper_answers = sum(1 for s in student["sources"] if int(s) == 0)
        by_penalty = {
            penalty: {m.code: m.mastery for m in model.mastery(history_from(student, spec, penalty))}
            for penalty in PENALTIES
        }
        print(f"student {number}: {len(student['skills'])} attempts, {paper_answers} on paper")
        print(f"  {'skill':9} " + " ".join(f"{p:>6}" for p in PENALTIES) + "   max change")
        for code in spec.skills:
            values = [by_penalty[p][code] for p in PENALTIES]
            if any(v is None for v in values):
                continue
            change = max(values) - min(values)
            worst_overall = max(worst_overall, change)
            flag = "  <-- above threshold" if change > THRESHOLD else ""
            print(f"  {code:9} " + " ".join(f"{v:6.3f}" for v in values) + f"   {change:6.3f}{flag}")
        print()

    print(f"largest change in any skill: {worst_overall:.3f} (threshold {THRESHOLD})")
    if worst_overall > THRESHOLD:
        print("The constant paper penalty matters: decide whether to collect paper time/hints.")
    else:
        print("The constant paper penalty (0.08) is a safe simplification on these histories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
