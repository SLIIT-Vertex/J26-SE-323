"""Replay parameter changes on stored inputs. Never invent counterfactual outcomes."""

from datetime import UTC, datetime

from app.gamification.application.research_dashboard.accuracy import prediction_pairs
from app.gamification.modeling.misconception_inference.learner_prior import apply_learner_prior
from app.gamification.modeling.support_selection.support_order import (
    choose_support_order,
    subject_of,
)


def replay_report(runs, learner_id):
    states = [
        run["state"]
        for run in runs
        if run["status"] in {"completed", "invalidated"} and not run["state"].get("seed_source")
    ]
    states.sort(
        key=lambda state: str(
            (state.get("model1") or {}).get("created_at")
            or (state.get("events") or [{}])[0].get("occurred_at", "")
        )
    )
    pairs = prediction_pairs(states)
    caps = []
    for cap in (0.6, 0.72, 0.8):
        correct, scores = [], []
        for model, observed in pairs:
            likelihood = dict(model.get("likelihood") or model["probabilities"])
            primary = str(model.get("structured_error_code"))
            if not model.get("fallback_used") and primary in likelihood and len(likelihood) > 1:
                confidence = min(cap, max(0.2, float(likelihood[primary]) / 0.72 * cap))
                likelihood = {
                    key: confidence if key == primary else (1 - confidence) / (len(likelihood) - 1)
                    for key in likelihood
                }
            replayed = apply_learner_prior(
                {**model, "probabilities": likelihood}, model.get("prior_window") or []
            )
            p = replayed["probabilities"]
            correct.append(int(max(p, key=p.get) == observed))
            scores.append(sum((p.get(k, 0) - int(k == observed)) ** 2 for k in set(p) | {observed}))
        caps.append(
            {
                "confidence_cap": cap,
                "count": len(correct),
                "agreement": sum(correct) / len(correct) if len(correct) >= 20 else None,
                "brier": sum(scores) / len(scores) if len(scores) >= 30 else None,
            }
        )
    thresholds = []
    for threshold in (1, 2, 3):
        changed, checked = 0, 0
        for index, state in enumerate(states):
            model = state.get("model2") or {}
            if not model.get("support_order"):
                continue
            # Only games completed before this decision can enter the replay history.
            decided_at = str(model.get("created_at", ""))
            history = [
                prior
                for prior in states[:index]
                if prior.get("status") == "completed"
                and prior.get("skill_id") == state.get("skill_id")
                and str((prior.get("events") or [{}])[-1].get("occurred_at", "")) < decided_at
            ]
            belief = state.get("model1") or {}
            replayed = choose_support_order(
                subject=subject_of(state["area_id"]),
                condition=state["condition"],
                model1_label=belief.get("top_hypothesis") or belief.get("predicted_label"),
                model1_uncertain=any(
                    belief.get(k) for k in ("low_confidence", "abstained", "fallback_used")
                ),
                eligible=model["eligible_actions"],
                renderable=model.get("renderable_actions") or model["eligible_actions"],
                history=history,
                learning_state_input=model.get("learning_state_input"),
                preference_threshold=threshold,
            )
            checked += 1
            changed += int(replayed.first != model["support_order"][0])
        thresholds.append(
            {"success_threshold": threshold, "checked": checked, "changed_first_choices": changed}
        )
    return {
        "learner_id": str(learner_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "confidence_caps": caps,
        "preference_thresholds": thresholds,
        "note": "These replays show sensitivity to settings. Changed help choices have no observed alternative outcome.",
    }
