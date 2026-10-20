"""Benchmark metrics with explicit denominators; small slices are flagged, never hidden."""

import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import median

SMALL_SLICE = 10


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    language: str
    category: str
    gold_status: str
    gold_skill_id: str | None
    predicted_status: str
    predicted_skill_id: str | None
    ranking: tuple[str, ...]
    top_score: float
    margin: float
    vetoed: bool
    seconds: float

    @property
    def gold_label(self) -> str:
        return (
            self.gold_skill_id
            if self.gold_status == "MATCHED" and self.gold_skill_id
            else self.gold_status
        )

    @property
    def predicted_label(self) -> str:
        return (
            self.predicted_skill_id
            if self.predicted_status == "MATCHED" and self.predicted_skill_id
            else self.predicted_status
        )

    @property
    def skill_labelled(self) -> bool:
        return self.gold_status == "MATCHED" and self.gold_skill_id is not None

    @property
    def correct_match(self) -> bool:
        return (
            self.predicted_status == "MATCHED"
            and self.skill_labelled
            and self.predicted_skill_id == self.gold_skill_id
        )

    @property
    def false_confident_match(self) -> bool:
        return self.predicted_status == "MATCHED" and not self.correct_match


def macro_f1(outcomes: Sequence[CaseOutcome]) -> float:
    labels = {item.gold_label for item in outcomes} | {item.predicted_label for item in outcomes}
    scores = []
    for label in labels:
        tp = sum(item.gold_label == label and item.predicted_label == label for item in outcomes)
        fp = sum(item.gold_label != label and item.predicted_label == label for item in outcomes)
        fn = sum(item.gold_label == label and item.predicted_label != label for item in outcomes)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores) if scores else 0.0


def _rate(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "count": numerator,
        "of": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def summarize(outcomes: Sequence[CaseOutcome]) -> dict[str, object]:
    labelled = [item for item in outcomes if item.skill_labelled]
    matches = [item for item in outcomes if item.predicted_status == "MATCHED"]
    false_confident = [item for item in outcomes if item.false_confident_match]
    return {
        "cases": len(outcomes),
        "small_slice_warning": len(outcomes) < SMALL_SLICE,
        "top_1_accuracy": _rate(
            sum(item.ranking[:1] == (item.gold_skill_id,) for item in labelled), len(labelled)
        ),
        "top_3_accuracy": _rate(
            sum(item.gold_skill_id in item.ranking[:3] for item in labelled), len(labelled)
        ),
        "confirmed_match_coverage": _rate(
            sum(item.correct_match for item in labelled), len(labelled)
        ),
        "false_confident_matches": {
            **_rate(len(false_confident), len(outcomes)),
            "among_confirmed": _rate(len(false_confident), len(matches)),
            "case_ids": [item.case_id for item in false_confident],
        },
        "clarification_rate": _rate(
            sum(item.predicted_status == "AMBIGUOUS" for item in outcomes), len(outcomes)
        ),
        "status_accuracy": _rate(
            sum(item.predicted_status == item.gold_status for item in outcomes), len(outcomes)
        ),
        "macro_f1": macro_f1(outcomes),
        "evidence_vetoes": sum(item.vetoed for item in outcomes),
    }


def sliced(
    outcomes: Sequence[CaseOutcome], key: Callable[[CaseOutcome], str]
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[CaseOutcome]] = defaultdict(list)
    for item in outcomes:
        groups[key(item)].append(item)
    return {name: summarize(items) for name, items in sorted(groups.items())}


def bootstrap_intervals(
    outcomes: Sequence[CaseOutcome], *, resamples: int = 2000, seed: int = 20261021
) -> dict[str, tuple[float, float]]:
    """95% percentile intervals from case-level resampling (groups are single cases or pairs)."""

    rng = random.Random(seed)
    values: dict[str, list[float]] = defaultdict(list)
    for _ in range(resamples):
        sample = [outcomes[rng.randrange(len(outcomes))] for _ in outcomes]
        labelled = [item for item in sample if item.skill_labelled]
        values["confirmed_match_coverage"].append(
            sum(item.correct_match for item in labelled) / len(labelled) if labelled else 0.0
        )
        values["false_confident_match_rate"].append(
            sum(item.false_confident_match for item in sample) / len(sample)
        )
        values["macro_f1"].append(macro_f1(sample))
    intervals = {}
    for name, series in values.items():
        series.sort()
        intervals[name] = (series[int(0.025 * len(series))], series[int(0.975 * len(series)) - 1])
    return intervals


def latency(seconds: Sequence[float]) -> dict[str, float]:
    ordered = sorted(seconds)
    if not ordered:
        return {}
    return {
        "p50_ms": median(ordered) * 1000,
        "p95_ms": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] * 1000,
        "max_ms": ordered[-1] * 1000,
        "queries": len(ordered),
    }
