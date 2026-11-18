"""Replay setting changes on stored inputs. Never invent counterfactual outcomes.

Model 1: every stored wrong answer is read again by the area's expert-initialised Bayesian model
with one setting changed, from the same inputs and the same earlier answers, and compared with
the child's next unaided mistake. Model 2: the help-order replays come from the shared ledger
(``bandit_sensitivity``) and are passed in.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from functools import cache

from app.gamification.application.learning_flow_orchestration import GAME_FLOW_TYPES
from app.gamification.application.research_dashboard.accuracy import prediction_pairs
from app.gamification.modeling.misconception_inference.bayesian_model import (
    GAME_MODEL_VERSION,
    BayesianMisconceptionModel,
)
from app.gamification.modeling.misconception_inference.expert_tables import (
    load_game_misconception_model,
)
from app.gamification.modeling.misconception_inference.game_belief import learner_answer_window

# The values each Model 1 setting is replayed with; the approved value is among them.
MODEL1_SETTING_VALUES: Mapping[str, tuple[float, ...]] = {
    "top_probability_below": (0.3, 0.4, 0.5),
    "top_two_margin_below": (0.05, 0.1, 0.2),
    "prior_window": (3, 5, 8),
}
_TOLERANCE = 1e-9


def replay_report(runs, learner_id, *, help_order=None):
    finished = [
        run
        for run in runs
        if run["status"] in {"completed", "invalidated"} and not run["state"].get("seed_source")
    ]
    finished.sort(key=lambda run: _decided_at(run["state"]))
    readings = [reading for run in finished if (reading := _reading(run, finished)) is not None]
    rows = []
    for name, values in MODEL1_SETTING_VALUES.items():
        for value in values:
            replayed = {
                id(state): _belief(model, name, value, inputs) for state, model, inputs in readings
            }
            states = [
                {
                    **run["state"],
                    "model1": replayed.get(id(run["state"]), run["state"].get("model1")),
                }
                for run in finished
            ]
            pairs = prediction_pairs(states)
            correct = [int(_top(model["probabilities"]) == observed) for model, observed in pairs]
            scores = [
                sum(
                    (float(model["probabilities"].get(code, 0)) - int(code == observed)) ** 2
                    for code in set(model["probabilities"]) | {observed}
                )
                for model, observed in pairs
            ]
            stored = [state["model1"] for state, _, _ in readings]
            new = [replayed[id(state)] for state, _, _ in readings]
            approved = _approved(readings, name)
            rows.append(
                {
                    "setting": name,
                    "value": value,
                    "approved": approved is not None and value == approved,
                    "readings": len(readings),
                    "agreement": sum(correct) / len(correct) if len(correct) >= 20 else None,
                    "brier": sum(scores) / len(scores) if len(scores) >= 30 else None,
                    "pairs": len(correct),
                    "changed_reason": sum(
                        _top(a["probabilities"]) != _top(b["probabilities"])
                        for a, b in zip(stored, new, strict=True)
                    ),
                    "changed_uncertain": sum(
                        _uncertain(a) != _uncertain(b) for a, b in zip(stored, new, strict=True)
                    ),
                    "reproduced": sum(
                        _same(a["probabilities"], b["probabilities"])
                        for a, b in zip(stored, new, strict=True)
                        if a.get("model_version") == GAME_MODEL_VERSION
                    ),
                    "bayesian_readings": sum(
                        a.get("model_version") == GAME_MODEL_VERSION for a in stored
                    ),
                }
            )
    return {
        "learner_id": str(learner_id),
        "generated_at": datetime.now(UTC).isoformat(),
        "model1_settings": rows,
        "help_order_settings": list(help_order or []),
        "note": "These replays show sensitivity to settings. Changed choices have no observed "
        "alternative outcome: a help that was not given has no result, and a reason is only "
        "compared with the child's next real mistake.",
    }


def _reading(run, finished):
    """One stored wrong answer, the area's model and the inputs it was read from."""

    state = run["state"]
    model1 = state.get("model1")
    if not isinstance(model1, Mapping) or not model1.get("structured_error_code"):
        return None
    flow = _flows().get(str(state.get("area_id")))
    if flow is None or state.get("skill_id") not in flow.skills:
        return None
    decided = _decided_at(state)
    history = [
        other["state"]
        for other in finished
        if other["status"] == "completed"
        and other["state"].get("skill_id") == state.get("skill_id")
        and other["state"].get("episode_id") != state.get("episode_id")
        and _moment(other["updated_at"]) < decided
    ]
    inputs = {
        "skill_id": str(state["skill_id"]),
        "error_code": str(model1["structured_error_code"]),
        "response_time_ms": model1.get("response_time_ms"),
        "interaction_summary": model1.get("structured_response") or None,
        "history": history,
    }
    return state, _model(flow.area_id, tuple(flow.skills)), inputs


def _belief(model: BayesianMisconceptionModel, name: str, value: float, inputs):
    game = model.game
    assert game is not None
    varied = copy.copy(model)
    varied.game = replace(game, **{name: int(value) if name == "prior_window" else value})
    return varied.predict_game_belief(
        skill_id=inputs["skill_id"],
        error_code=inputs["error_code"],
        response_time_ms=inputs["response_time_ms"],
        interaction_summary=inputs["interaction_summary"],
        prior_window=learner_answer_window(inputs["history"], size=varied.game.prior_window),
    )


def _approved(readings, name: str) -> float | None:
    if not readings:
        return None
    game = readings[0][1].game
    return None if game is None else float(getattr(game, name))


@cache
def _flows():
    return {flow.area_id: flow for flow in GAME_FLOW_TYPES}


@cache
def _model(area_id: str, skills: tuple[str, ...]) -> BayesianMisconceptionModel:
    return load_game_misconception_model(area_id, skills)


def _decided_at(state) -> datetime:
    return _moment(
        (state.get("model1") or {}).get("created_at")
        or (state.get("model2") or {}).get("created_at")
        or (state.get("events") or [{}])[0].get("occurred_at")
    )


def _moment(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif value:
        moment = datetime.fromisoformat(str(value))
    else:
        return datetime.min.replace(tzinfo=UTC)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _top(probabilities: Mapping[str, object]) -> str:
    return max(probabilities, key=lambda code: float(probabilities[code]))  # type: ignore[arg-type]


def _same(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    return set(left) == set(right) and all(
        abs(float(left[code]) - float(right[code])) <= _TOLERANCE  # type: ignore[arg-type]
        for code in left
    )


def _uncertain(model1: Mapping[str, object]) -> bool:
    if "uncertain_because" in model1:
        return bool(model1["uncertain_because"])
    return any(model1.get(flag) for flag in ("low_confidence", "fallback_used", "abstained"))


__all__: Sequence[str] = ["MODEL1_SETTING_VALUES", "replay_report"]
