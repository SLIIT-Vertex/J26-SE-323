"""This child's record with each help on a skill, read with the help-order bandit's credit rule.

A description for the research views, not a model: the bandit's own ranking is the predicted gain
recorded with each decision. Only valid proposed episodes count. The help the loop ended on
carries the fair test's result; a help that failed while shown is counted as not helping.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.gamification.modeling.support_selection.game_bandit import loop_credit


@dataclass(frozen=True)
class ChildRecord:
    # The help with the best record, if any help led to an independent success.
    preferred: str | None
    by_support: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def as_record(self) -> dict[str, object]:
        return {
            "basis": "valid_unsupported_after_outcomes",
            "supported_correctness_used": False,
            "preferred_support": self.preferred,
            "by_support": {key: dict(value) for key, value in self.by_support.items()},
        }


def child_record(history: Iterable[Mapping[str, object]], *, order: Sequence[str]) -> ChildRecord:
    """Per help: credited episodes, independent successes, mean gain and rounds it did not help.

    The best record is the highest independent-success rate, then the higher mean gain, then
    fewer rounds that did not help, then the subject's order.
    """

    stats: dict[str, dict[str, object]] = {}
    for state in history:
        if state.get("condition") != "proposed" or state.get("validity") != "valid":
            continue
        measurement = state.get("measurement")
        if not isinstance(measurement, Mapping):
            continue
        gain = measurement.get("raw_independence_gain", state.get("raw_independence_gain"))
        maximum = Decimal(str(measurement.get("after_maximum", 0)))
        if gain is None or maximum <= 0:
            continue
        winner, failed = loop_credit(state)
        credited = (winner,) if winner else ()
        for support in dict.fromkeys((*credited, *failed)):
            if support not in order:
                continue
            row = stats.setdefault(
                support,
                {"episodes": 0, "independent_successes": 0, "total_ig": Decimal(0), "did_not_help": 0},
            )
            row["did_not_help"] = int(row["did_not_help"]) + int(support in failed)  # type: ignore[call-overload]
            if support not in credited:
                continue
            row["episodes"] = int(row["episodes"]) + 1  # type: ignore[call-overload]
            row["independent_successes"] = int(row["independent_successes"]) + int(  # type: ignore[call-overload]
                Decimal(str(measurement.get("after_earned", 0))) == maximum
            )
            row["total_ig"] = Decimal(str(row["total_ig"])) + Decimal(str(gain))

    def score(support: str) -> tuple[Decimal, Decimal, int, int]:
        row = stats[support]
        episodes = int(row["episodes"])  # type: ignore[call-overload]
        return (
            Decimal(int(row["independent_successes"])) / episodes,  # type: ignore[call-overload]
            Decimal(str(row["total_ig"])) / episodes,
            -int(row["did_not_help"]),  # type: ignore[call-overload]
            -list(order).index(support),
        )

    successful = [support for support, row in stats.items() if row["independent_successes"]]
    return ChildRecord(
        preferred=max(successful, key=score) if successful else None,
        by_support={
            support: {
                "episodes": row["episodes"],
                "independent_successes": row["independent_successes"],
                "did_not_help": row["did_not_help"],
                "mean_independence_gain": str(
                    Decimal(str(row["total_ig"])) / int(row["episodes"])  # type: ignore[call-overload]
                )
                if row["episodes"]
                else "0",
            }
            for support, row in stats.items()
        },
    )
