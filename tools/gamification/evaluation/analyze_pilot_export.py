"""Analysis of a research export. Synthetic and authorized inputs only. No pilot claim."""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

ALLOWED_PROVENANCE = {"synthetic", "authorized"}


def analyze_export(document: Mapping[str, object]) -> dict[str, object]:
    provenance = document.get("provenance")
    if provenance not in ALLOWED_PROVENANCE:
        raise ValueError(
            "analysis refuses inputs without synthetic or authorized provenance"
        )
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("analysis requires rows")
    typed = [row for row in rows if isinstance(row, dict)]
    return {
        "header": (
            f"{str(provenance).upper()} INPUTS. This table is not a pilot result "
            "and not educational effectiveness."
        ),
        "provenance": provenance,
        "ancova": _ancova(typed),
        "independence_gain_ci": _paired_interval(typed),
        "mixed_effects": {
            "status": "placeholder",
            "grouping": "learner_id",
            "note": "A mixed model is not fitted in this engineering script.",
        },
        "attrition": _attrition(typed),
    }


def _ancova(rows: list[dict[str, object]]) -> dict[str, float]:
    """Ordinary least squares: post = b0 + b1 * pre + b2 * proposed_arm."""

    design = []
    outcome = []
    for row in rows:
        proposed = 1.0 if row.get("arm") == "proposed_misconception_ig_policy" else 0.0
        pre = float(row["pre_test"])
        design.append((1.0, pre, proposed))
        outcome.append(float(row["post_test"]))
    coefficients = _least_squares(design, outcome)
    return {
        "intercept": coefficients[0],
        "pre_test": coefficients[1],
        "proposed_arm": coefficients[2],
    }


def _least_squares(
    design: list[tuple[float, float, float]], outcome: list[float]
) -> tuple[float, float, float]:
    width = 3
    gram = [[0.0 for _ in range(width)] for _ in range(width)]
    moment = [0.0 for _ in range(width)]
    for row, target in zip(design, outcome, strict=True):
        for left in range(width):
            moment[left] += row[left] * target
            for right in range(width):
                gram[left][right] += row[left] * row[right]
    return _solve(gram, moment)


def _solve(
    matrix: list[list[float]], target: list[float]
) -> tuple[float, float, float]:
    size = len(target)
    working = [row[:] + [target[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(working[index][column]))
        working[column], working[pivot] = working[pivot], working[column]
        scale = working[column][column]
        if abs(scale) < 1e-12:
            raise ValueError("ANCOVA design is singular")
        for index in range(column, size + 1):
            working[column][index] /= scale
        for row in range(size):
            if row == column:
                continue
            factor = working[row][column]
            for index in range(column, size + 1):
                working[row][index] -= factor * working[column][index]
    solved = [working[index][size] for index in range(size)]
    return solved[0], solved[1], solved[2]


def _paired_interval(rows: list[dict[str, object]]) -> dict[str, float | int]:
    gains = [float(row["independence_gain"]) for row in rows]
    count = len(gains)
    mean = sum(gains) / count
    variance = sum((value - mean) ** 2 for value in gains) / max(count - 1, 1)
    margin = 1.96 * math.sqrt(variance / count) if count else 0.0
    return {
        "n": count,
        "mean": mean,
        "ci95_low": mean - margin,
        "ci95_high": mean + margin,
    }


def _attrition(rows: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"assigned": 0, "completed": 0}
    )
    for row in rows:
        arm = str(row.get("arm"))
        counts[arm]["assigned"] += 1
        if row.get("completed") is True:
            counts[arm]["completed"] += 1
    return dict(counts)


def main() -> None:
    document = json.loads(sys.stdin.read())
    print(json.dumps(analyze_export(document), indent=2))


if __name__ == "__main__":
    main()
