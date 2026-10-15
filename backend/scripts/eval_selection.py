"""Compares the knapsack (CP-SAT) paper selection with the greedy baseline.

For simulated learners with different mastery vectors it reports total value, paper size,
weak-skill coverage, verification coverage and run time for both solvers, so the gain of the
knapsack is a measured result and not an assumption.

    python -m scripts.eval_selection                    # 100 learners, questions from the database
    python -m scripts.eval_selection --source synthetic # no database needed
    python -m scripts.eval_selection --students 200 --seed 7 --out results.json

The learners are simulated: the mastery vectors and item probabilities are made up and are NOT
the output of the trained model. The result compares two ways of choosing questions, not how
well papers help real children.
"""

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass

import numpy as np

from app.knowledge_tracing.application.paper_selection import (
    DEFAULT_CONFIG,
    DIFFICULTIES,
    Candidate,
    NotEnoughQuestions,
    PaperParams,
    Selection,
    SkillState,
    classify_skills,
    layout_height_mm,
    select_questions,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec


@dataclass(slots=True)
class Student:
    states: list[SkillState]
    item_probs: np.ndarray


def simulate_student(rng: random.Random, skills: tuple[str, ...]) -> Student:
    """A made-up learner: 16 to 30 known skills with a spread of mastery and game history."""
    known = set(rng.sample(skills, rng.randint(16, 30)))
    profile = rng.choice(("weak", "mixed", "mixed", "strong"))
    centre = {"weak": 0.40, "mixed": 0.60, "strong": 0.80}[profile]
    states: list[SkillState] = []
    probs = np.zeros((len(skills), 3))
    for index, code in enumerate(skills):
        mastery: float | None = None
        digital_n = digital_ok = paper_n = 0
        if code in known:
            mastery = min(0.97, max(0.05, rng.gauss(centre, 0.2)))
            digital_n = rng.randint(3, 12)
            digital_ok = min(digital_n, round(digital_n * min(1.0, max(0.0, mastery + rng.gauss(0.1, 0.15)))))
            paper_n = rng.choice((0, 0, 1, 2, 3, 5))
        states.append(
            SkillState(
                code=code,
                area=code[:3],
                sort_index=index,
                mastery=mastery,
                digital_attempts=digital_n,
                digital_correct=digital_ok,
                paper_attempts=paper_n,
                was_weak=mastery is not None and mastery < 0.65 and rng.random() < 0.5,
            )
        )
        base = 0.5 if mastery is None else mastery
        probs[index] = np.clip([base + 0.15, base, base - 0.2], 0.02, 0.98)
    return Student(states, probs)


def synthetic_pool(rng: random.Random, skills: tuple[str, ...], per_skill: int = 11) -> list[Candidate]:
    pool: list[Candidate] = []
    for index, code in enumerate(skills):
        for k in range(per_skill):
            width, height = rng.choice((700, 945, 1200)), rng.randint(150, 900)
            pool.append(
                Candidate(
                    question_id=f"s{index}.{k}",
                    skill_code=code,
                    difficulty=rng.choice(DIFFICULTIES),
                    est_seconds=rng.choice((60, 90, 120, 150, 180, 270)),
                    height_mm=layout_height_mm(width, height),
                )
            )
    return pool


def database_pool(language: str) -> list[Candidate]:
    from app.knowledge_tracing.infrastructure.db.paper_input_repository import (
        SqlAlchemyPaperInputRepository,
    )
    from app.shared.database.session import SessionLocal

    with SessionLocal() as session:
        rows = SqlAlchemyPaperInputRepository(session).question_rows(language)
    return [
        Candidate(r.question_id, r.skill_code, r.difficulty, r.est_seconds,
                  layout_height_mm(r.width_px, r.height_px))
        for r in rows
    ]


def measure(selection: Selection, student: Student, elapsed_ms: float) -> dict[str, float]:
    groups = classify_skills(student.states)
    chosen = {q.skill_code for q in selection.questions}
    weak = set(groups.weak)
    verify = set(groups.verify)
    n = max(1, len(selection.questions))
    weak_questions = sum(q.skill_code in weak for q in selection.questions)
    unknown = set(groups.unknown)
    weak_side = sum(q.skill_code in weak or q.skill_code in unknown for q in selection.questions)
    by_code = {s.code: s for s in student.states}
    weakest = sorted(
        (c for c in weak if by_code[c].mastery is not None),
        key=lambda c: (by_code[c].mastery, by_code[c].sort_index),
    )[:3]
    return {
        "value": selection.total_value,
        "questions": len(selection.questions),
        "weakest3_covered": (
            sum(c in chosen for c in weakest) / len(weakest) if weakest else float("nan")
        ),
        "weak_skill_coverage": len(weak & chosen) / max(1, len(weak)),
        "weak_share": weak_questions / n,
        "weak_or_unknown_share": weak_side / n,
        "verify_coverage": len(verify & chosen) / max(1, len(verify)) if verify else float("nan"),
        "minutes": selection.seconds / 60,
        "ms": elapsed_ms,
    }


def run(students: int, seed: int, source: str, language: str) -> dict:
    spec = get_feature_spec()
    rng = random.Random(seed)
    pool = database_pool(language) if source == "db" else synthetic_pool(rng, spec.skills)
    if not pool:
        raise SystemExit("the question pool is empty: import the question bank first")

    rows = {"cp_sat": [], "greedy": []}
    knapsack_better = tie = knapsack_worse = skipped = 0
    for i in range(students):
        student = simulate_student(rng, spec.skills)
        params = PaperParams(seed=i, mode="practice")
        results = {}
        for solver in ("cp_sat", "greedy"):
            started = time.perf_counter()
            try:
                selection = select_questions(student.states, student.item_probs, pool, params,
                                             DEFAULT_CONFIG, solver=solver)
            except NotEnoughQuestions:
                results = {}
                break
            results[solver] = (selection, (time.perf_counter() - started) * 1000)
        if len(results) != 2:
            skipped += 1
            continue
        for solver, (selection, elapsed) in results.items():
            rows[solver].append(measure(selection, student, elapsed))
        a, b = results["cp_sat"][0].total_value, results["greedy"][0].total_value
        if a > b + 1e-6:
            knapsack_better += 1
        elif a < b - 1e-6:
            knapsack_worse += 1
        else:
            tie += 1

    def mean(solver: str, key: str) -> float:
        values = [r[key] for r in rows[solver] if r[key] == r[key]]  # drop NaN
        return statistics.fmean(values) if values else float("nan")

    keys = ["value", "questions", "weakest3_covered", "weak_skill_coverage", "weak_share",
            "weak_or_unknown_share", "verify_coverage", "minutes", "ms"]
    summary = {s: {k: round(mean(s, k), 4) for k in keys} for s in rows}
    gain = (summary["cp_sat"]["value"] / summary["greedy"]["value"] - 1) * 100 \
        if summary["greedy"]["value"] else float("nan")
    return {
        "students": students, "evaluated": len(rows["cp_sat"]), "skipped": skipped,
        "pool_questions": len(pool), "source": source, "seed": seed,
        "knapsack_better": knapsack_better, "tie": tie, "knapsack_worse": knapsack_worse,
        "value_gain_percent": round(gain, 2), "summary": summary,
    }


def print_report(result: dict) -> None:
    print(f"learners: {result['evaluated']} of {result['students']} "
          f"(pool: {result['pool_questions']} questions, source: {result['source']}, "
          f"seed: {result['seed']})")
    print(f"knapsack better: {result['knapsack_better']}   tie: {result['tie']}   "
          f"worse: {result['knapsack_worse']}   mean value gain: {result['value_gain_percent']}%")
    print(f"{'metric (mean)':26} {'knapsack':>10} {'greedy':>10}")
    labels = {
        "value": "total value",
        "questions": "questions",
        "weakest3_covered": "weakest 3 skills covered",
        "weak_skill_coverage": "all weak skills covered",
        "weak_share": "weak-skill question share",
        "weak_or_unknown_share": "weak+unknown share",
        "verify_coverage": "verify skills covered",
        "minutes": "minutes",
        "ms": "run time (ms)",
    }
    for key, label in labels.items():
        a = result["summary"]["cp_sat"][key]
        b = result["summary"]["greedy"][key]
        print(f"{label:26} {a:>10} {b:>10}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--source", choices=("db", "synthetic"), default="db")
    parser.add_argument("--language", choices=("si", "ta"), default="si")
    parser.add_argument("--out", help="write the result as JSON")
    args = parser.parse_args()

    result = run(args.students, args.seed, args.source, args.language)
    print_report(result)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, indent=2)
        print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
