"""How sensitive the games' help-order bandit is to its provisional settings.

Each replay starts again from the expert data with one setting changed, applies the stored ledger
in its recorded order and, at every stored decision, ranks the helps that decision scored from
their stored context vectors. It counts the decisions whose first help would have changed. It
never invents an outcome: a help that was not given has no observation, and the replay only
re-weighs what was observed. At the approved settings it must reproduce every stored first help.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from app.gamification.modeling.support_selection.game_bandit import (
    GameHelpBandit,
    rank_by_gain,
)
from app.gamification.modeling.support_selection.game_bandit_ledger import (
    DecisionSnapshot,
    LedgerEntry,
)

# The values each provisional setting is replayed with; the approved value is among them.
SETTING_VALUES: Mapping[str, tuple[float, ...]] = {
    "prior_strength": (4.0, 8.0, 16.0),
    "own_success_rate_gain": (0.0, 0.15, 0.3),
    "failed_round_weight": (0.0, 0.25, 0.5, 1.0),
    "uninformed_precision": (10.0, 100.0, 1000.0),
}


@dataclass(frozen=True)
class StoredDecision:
    snapshot: DecisionSnapshot
    ledger_position: int
    first_help: str


def sensitivity(
    parameters: Mapping[str, object],
    gains: Mapping[str, object],
    families: Mapping[str, object],
    ledger: Sequence[tuple[LedgerEntry, DecisionSnapshot]],
    decisions: Sequence[StoredDecision],
) -> list[dict[str, object]]:
    """One row per setting value: decisions replayed and first helps that would change.

    ``gains`` and ``families`` are the checked expert data; they must be the files the approved
    artifact was built from.
    """

    approved = GameHelpBandit.from_parameters(parameters)
    settings = approved.settings
    if _start(approved, gains, families, {}).policy.parameters()["arms"] != parameters["arms"]:
        raise ValueError("the expert data no longer builds the approved artifact")
    rows = []
    for name, values in SETTING_VALUES.items():
        for value in values:
            start = _start(approved, gains, families, {name: value})
            weight = float(start.settings["failed_round_weight"])  # type: ignore[arg-type]
            changed = _replay(start, ledger, decisions, failed_round_weight=weight)
            rows.append(
                {
                    "setting": name,
                    "value": value,
                    "approved": value == float(settings[name]),  # type: ignore[arg-type]
                    "decisions": len(decisions),
                    "changed_first_helps": changed,
                }
            )
    return rows


def evidence(ledger: Sequence[LedgerEntry]) -> list[dict[str, object]]:
    """Per help type, the observations behind its predictions."""

    rows: dict[str, Counter[str]] = defaultdict(Counter)
    weights: dict[str, float] = defaultdict(float)
    for entry in ledger:
        if entry.role == "credited":
            rows[entry.support]["credited_success" if entry.score > 0 else "credited_zero"] += 1
        else:
            rows[entry.support]["failed_rounds"] += 1
            weights[entry.support] += entry.weight
    return [
        {
            "help": support,
            "credited_success": counts["credited_success"],
            "credited_zero": counts["credited_zero"],
            "failed_rounds": counts["failed_rounds"],
            "failed_round_weight": weights[support],
        }
        for support, counts in sorted(rows.items())
    ]


def _start(
    approved: GameHelpBandit,
    gains: Mapping[str, object],
    families: Mapping[str, object],
    change: Mapping[str, float],
) -> GameHelpBandit:
    settings = approved.settings
    varied = dict(gains)
    for name in ("prior_strength", "own_success_rate_gain"):
        varied[name] = change.get(name, settings[name])
    return GameHelpBandit.from_expert_data(
        approved.subject,
        varied,
        families,
        file_sha256=settings["file_sha256"],  # type: ignore[arg-type]
        failed_round_weight=float(
            change.get("failed_round_weight", settings["failed_round_weight"])  # type: ignore[arg-type]
        ),
        uninformed_precision=float(
            change.get("uninformed_precision", settings["uninformed_precision"])  # type: ignore[arg-type]
        ),
    )


def _replay(
    start: GameHelpBandit,
    ledger: Sequence[tuple[LedgerEntry, DecisionSnapshot]],
    decisions: Sequence[StoredDecision],
    *,
    failed_round_weight: float,
) -> int:
    arms = start.policy.parameters()["arms"]
    assert isinstance(arms, Mapping)
    matrix = {arm: np.array(state["A"], dtype=float) for arm, state in arms.items()}
    target = {arm: np.array(state["b"], dtype=float) for arm, state in arms.items()}
    solved: dict[str, np.ndarray] = {}
    tolerance = float(start.settings["tie_tolerance"])  # type: ignore[arg-type]
    applied, changed = 0, 0
    for decision in sorted(decisions, key=lambda d: d.ledger_position):
        while applied < decision.ledger_position:
            entry, snapshot = ledger[applied]
            weight = failed_round_weight if entry.role == "failed_round" else entry.weight
            if weight:
                x = _vector(snapshot, entry.support)
                matrix[entry.support] += weight * np.outer(x, x)
                target[entry.support] += weight * entry.score * x
                solved.pop(entry.support, None)
            applied += 1
        inputs = decision.snapshot.inputs
        cell = start.cells[
            (
                str(inputs["reason_family"]),
                bool(inputs["model1_uncertain"]),
                str(inputs["learning_state"]),
            )
        ]
        scored = decision.snapshot.vectors
        gains = {}
        for support in scored:
            if support not in solved:
                solved[support] = np.linalg.solve(matrix[support], target[support])
            gains[support] = float(_vector(decision.snapshot, support) @ solved[support])
        cell_order = [support for support in cell["order"] if support in scored]  # type: ignore[union-attr]
        changed += int(rank_by_gain(cell_order, gains, tolerance)[0] != decision.first_help)
    return changed


def _vector(snapshot: DecisionSnapshot, support: str) -> np.ndarray:
    return np.array(snapshot.context(support).values, dtype=float)
