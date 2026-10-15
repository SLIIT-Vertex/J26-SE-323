"""Synthetic baseline-versus-proposed comparison. Inputs are not learner evidence."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.gamification.modeling.synthetic.bandit_environment import run_bandit_simulation  # noqa: E402

BASELINE = "performance_triggered_fixed"
PROPOSED = "LinUCB"
ABLATION = "LinUCB_belief_ablated"


def build_report(*, seeds: int = 30) -> dict[str, object]:
    raw = run_bandit_simulation(seeds=seeds)
    mean_ig = raw["mean_valid_ig"]
    regret = raw["mean_cumulative_regret"]
    assert isinstance(mean_ig, dict) and isinstance(regret, dict)
    return {
        "header": "SYNTHETIC INPUTS. This is not a pilot result and not educational effectiveness.",
        "provenance": "synthetic",
        "seeds": raw["seeds"],
        "arms": {
            "baseline_performance_triggered": {
                "simulator_policy": BASELINE,
                "mean_valid_ig": mean_ig[BASELINE],
                "mean_cumulative_regret": regret[BASELINE],
            },
            "proposed_misconception_ig_policy": {
                "simulator_policy": PROPOSED,
                "mean_valid_ig": mean_ig[PROPOSED],
                "mean_cumulative_regret": regret[PROPOSED],
            },
        },
        "action_coverage": raw["action_coverage"],
        "fallback_rate": raw["fallback_rate"],
        "fallback_note": (
            "This synthetic environment always selects an eligible arm, so the fallback "
            "rate is zero. The application counter records conservative fallback separately."
        ),
        "per_misconception_mean_ig": raw["per_misconception_mean_ig"],
        "ablation_without_belief_context": {
            "simulator_policy": ABLATION,
            "mean_valid_ig": mean_ig[ABLATION],
            "mean_cumulative_regret": regret[ABLATION],
        },
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        str(report["header"]),
        "",
        f"Seeds: {report['seeds']}",
        "",
        "| Arm | Mean valid IG | Mean cumulative regret |",
        "| --- | --- | --- |",
    ]
    arms = report["arms"]
    assert isinstance(arms, dict)
    for name, row in arms.items():
        assert isinstance(row, dict)
        lines.append(
            f"| {name} | {row['mean_valid_ig']:.4f} | {row['mean_cumulative_regret']:.4f} |"
        )
    ablation = report["ablation_without_belief_context"]
    assert isinstance(ablation, dict)
    lines.extend(
        [
            "",
            "| Ablation without belief context | Mean valid IG | Mean cumulative regret |",
            "| --- | --- | --- |",
            (
                f"| {ablation['simulator_policy']} | {ablation['mean_valid_ig']:.4f} | "
                f"{ablation['mean_cumulative_regret']:.4f} |"
            ),
            "",
            "Action coverage, fallback rate, and per-misconception slices are in the JSON report.",
        ]
    )
    return "\n".join(lines) + "\n"


def synthetic_export(report: dict[str, object]) -> dict[str, object]:
    """A tiny analysis-shaped export derived from the synthetic arm means."""

    arms = report["arms"]
    assert isinstance(arms, dict)
    rows = []
    for index, (arm_key, row) in enumerate(arms.items()):
        assert isinstance(row, dict)
        gain = float(row["mean_valid_ig"])
        pre = 0.25 + index * 0.2
        rows.append(
            {
                "learner_id": f"synthetic-{index}",
                "arm": arm_key,
                "pre_test": pre,
                "post_test": min(1.0, max(0.0, pre + gain)),
                "independence_gain": gain,
                "completed": index == 0,
            }
        )
    rows.append(
        {
            "learner_id": "synthetic-held",
            "arm": "baseline_performance_triggered",
            "pre_test": 0.6,
            "post_test": 0.7,
            "independence_gain": 0.1,
            "completed": True,
        }
    )
    return {"provenance": "synthetic", "rows": rows}


def main() -> None:
    report = build_report()
    destination = ROOT / "tmp-synthetic-policy-comparison.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    main()
