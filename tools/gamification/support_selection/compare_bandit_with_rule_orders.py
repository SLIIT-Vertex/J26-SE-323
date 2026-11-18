"""Compare the expert-initialised help-order bandit with the frozen rule-based orders.

With no history the bandit must reproduce today's order exactly; that is tested. With a history,
today's rules and the bandit learn differently, so this reports how often they agree on the first
help for each frozen history pattern and subject. Sinhala is compared with the order its packages
deliver. The bandit has learned nothing here: only the child's own record moves it.

    PYTHONPATH=backend python3 tools/gamification/support_selection/compare_bandit_with_rule_orders.py
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from app.gamification.modeling.support_selection.game_bandit import load_game_help_bandit

ROOT = Path(__file__).resolve().parents[3]
ORDERS = ROOT / "backend" / "tests" / "gamification" / "fixtures" / "rule_based_support_orders.json"
SUBJECTS = ("MAT", "ENG", "SIN")


def first_help_agreement(orders: dict[str, object]) -> dict[str, dict[str, dict[str, int]]]:
    """Per subject and history pattern: decisions compared and first helps that agree."""

    bandits = {subject: load_game_help_bandit(subject) for subject in SUBJECTS}
    result: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"decisions": 0, "same_first_help": 0})
    )
    for decision in orders["decisions"]:  # type: ignore[union-attr]
        if decision["condition"] != "proposed" or decision["helps"] != "all_eligible":
            continue
        subject = decision["subject"]
        bandit = bandits[subject]
        chosen = bandit.order(
            model1_label=decision["model1_label"],
            model1_uncertain=decision["model1_uncertain"],
            learning_state_input=orders["learning_state_readings"][decision["learning_state"]],  # type: ignore[index]
            history=orders["histories"][subject][decision["history"]],  # type: ignore[index]
            eligible=orders["eligible_helps"][subject]["helps"],  # type: ignore[index]
            renderable=decision["renderable"],
        )
        source = decision["delivered"] if subject == "SIN" else decision["decision"]
        row = result[subject][decision["history"]]
        row["decisions"] += 1
        row["same_first_help"] += int(chosen.first == source["support_order"][0])
    return {subject: dict(rows) for subject, rows in result.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the counts as JSON")
    arguments = parser.parse_args()
    agreement = first_help_agreement(json.loads(ORDERS.read_text(encoding="utf-8")))
    if arguments.json:
        print(json.dumps(agreement, indent=2, sort_keys=True))
        return 0
    histories = sorted({name for rows in agreement.values() for name in rows})
    print(f"{'history':34}" + "".join(f"{subject:>14}" for subject in SUBJECTS))
    for name in histories:
        cells = []
        for subject in SUBJECTS:
            row = agreement[subject][name]
            cells.append(f"{row['same_first_help']}/{row['decisions']}".rjust(14))
        print(f"{name:34}" + "".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
