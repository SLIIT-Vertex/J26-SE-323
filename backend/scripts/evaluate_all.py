"""Reproduce every number of the knowledge-tracing evaluation in one command.

    python -m scripts.evaluate_all                                  # one seed (2026)
    python -m scripts.evaluate_all --seeds 11,22,33,44,55 --out ../research/evaluation.md

It runs, in this order:
  1. model check   - the PyTorch weights reproduce the Colab golden histories exactly
  2. selection     - CP-SAT knapsack vs greedy on simulated students, once per seed, with the
                     mean and spread over the seeds (scripts.eval_selection)
  3. penalty       - how much the constant paper penalty (0.08) moves mastery: the 3 golden
                     histories and 100 simulated students (scripts.penalty_sensitivity)
  4. optimism      - mastery of a child with 1 correct answer out of 6 (scripts.optimism_check)
and prints where the numbers that need outside data come from, so the report never quotes a
figure that has no source. The same figures are quoted in docs/bhs-kt/LIMITATIONS.md.
"""

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

EXTERNAL_TABLE = """| Figure | Where it comes from |
|---|---|
| Model AUC / accuracy on held-out students | Colab training notebook (simulated data) |
| Handwriting accuracy, hand-over rate | benchmark_vision.py on labelled photos (not yet collected) |
| Mastery vs real paper accuracy | real children's paper results (not yet collected) |"""

BACKEND = Path(__file__).resolve().parents[1]

# (key in the eval_selection summary, label, decimals)
SOLVER_ROWS = (
    ("value", "total value", 3),
    ("questions", "questions", 2),
    ("weak_or_unknown_share", "weak + unknown share", 3),
    ("weak_skill_coverage", "weak skills covered", 3),
    ("verify_coverage", "verify skills covered", 3),
    ("minutes", "minutes", 2),
    ("ms", "run time (ms)", 1),
)


def run(module: str, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def spread(values: list[float], digits: int) -> str:
    """mean (sd, min to max) over the seeds."""
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    mean, low, high = statistics.fmean(values), min(values), max(values)
    return f"{mean:.{digits}f} (sd {sd:.{digits}f}, {low:.{digits}f} to {high:.{digits}f})"


def selection_section(seeds: list[int], students: int, raw_out: Path) -> tuple[list[str], bool]:
    runs: list[dict] = []
    with tempfile.TemporaryDirectory() as folder:
        for seed in seeds:
            target = Path(folder) / f"seed_{seed}.json"
            args = ("--students", str(students), "--seed", str(seed), "--out", str(target))
            code, output = run("scripts.eval_selection", *args)
            if code != 0 or not target.exists():
                return [
                    f"eval_selection failed for seed {seed}:",
                    "```",
                    output.strip(),
                    "```",
                ], True
            runs.append(json.loads(target.read_text(encoding="utf-8")))

    worse = sum(r["knapsack_worse"] for r in runs)
    total = sum(r["evaluated"] for r in runs)
    lines = [
        (
            f"{len(seeds)} seed(s) ({', '.join(map(str, seeds))}), {students} simulated "
            f"students each, question pool {runs[0]['pool_questions']}. Values are mean "
            "(sd, min to max) over the seeds."
        ),
        "",
        "| Measure | Knapsack (CP-SAT) | Greedy |",
        "|---|---|---|",
    ]
    for key, label, digits in SOLVER_ROWS:
        cp = [r["summary"]["cp_sat"][key] for r in runs]
        greedy = [r["summary"]["greedy"][key] for r in runs]
        lines.append(f"| {label} | {spread(cp, digits)} | {spread(greedy, digits)} |")
    better = [float(r["knapsack_better"]) for r in runs]
    lines += [
        "",
        f"- Value gain of knapsack over greedy: {spread([r['value_gain_percent'] for r in runs], 2)} %",
        f"- Students where knapsack was better: {spread(better, 1)} of {students} per seed",
        (
            f"- Students where knapsack was worse than greedy: {worse} of {total} "
            "(the selector returns the better of the two, so this must be 0)"
        ),
    ]
    raw_out.write_text(
        json.dumps({"seeds": seeds, "students_per_seed": students, "runs": runs}, indent=2),
        encoding="utf-8",
    )
    lines.append(f"- Raw numbers per seed: `{raw_out.name}`")
    return lines, worse > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=100, help="students per seed")
    parser.add_argument("--seed", type=int, default=2026, help="one seed (without --seeds)")
    parser.add_argument("--seeds", help="several seeds, e.g. 11,22,33,44,55")
    parser.add_argument("--optimism-students", type=int, default=1000)
    parser.add_argument("--penalty-students", type=int, default=100)
    parser.add_argument("--out", help="write the report as markdown")
    parser.add_argument(
        "--selection-json",
        default=str(BACKEND.parent / "research" / "selection_eval.json"),
        help="where the raw selection numbers are written",
    )
    args = parser.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else [args.seed]
    first = str(seeds[0])

    stamp = f"{datetime.now(UTC):%Y-%m-%d %H:%M}"
    command = f"python -m scripts.evaluate_all --seeds {','.join(map(str, seeds))}"
    sections: list[str] = [
        "# Knowledge tracing - evaluation record",
        f"Run at {stamp} UTC. Reproduce with `{command}`.",
    ]
    failed = False

    code, output = run("pytest", "tests/knowledge_tracing/test_model_service.py", "-q")
    failed |= code != 0
    summary = output.strip().splitlines()[-1] if output.strip() else ""
    sections += ["## 1. Model reproduces Colab", f"{'PASS' if code == 0 else 'FAIL'} - {summary}"]

    lines, bad = selection_section(seeds, args.students, Path(args.selection_json))
    failed |= bad
    sections += ["## 2. Paper selection: knapsack vs greedy", "\n".join(lines)]

    code, output = run("scripts.penalty_sensitivity")
    failed |= code != 0
    golden = "\n".join(output.strip().splitlines()[-2:])
    code, output = run(
        "scripts.penalty_sensitivity", "--students", str(args.penalty_students), "--seed", first
    )
    failed |= code != 0
    simulated = "\n".join(output.strip().splitlines()[-3:])
    sections += [
        "## 3. Paper penalty sensitivity",
        "Mastery recomputed with a paper penalty of 0.0, 0.08 and 0.12 (threshold 0.05).",
        f"3 golden histories:\n\n```\n{golden}\n```",
        f"{args.penalty_students} simulated students (30% paper answers):\n\n```\n{simulated}\n```",
    ]

    code, output = run(
        "scripts.optimism_check", "--students", str(args.optimism_students), "--seed", first
    )
    failed |= code != 0
    sections += ["## 4. How optimistic is the model?", f"```\n{output.strip()}\n```"]

    sections += [
        "## 5. Numbers that come from outside this repository",
        EXTERNAL_TABLE,
        "See `docs/bhs-kt/LIMITATIONS.md` before quoting any of these.",
    ]

    text = "\n\n".join(sections) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written {args.out}")
    else:
        print(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
