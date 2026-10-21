"""Explanations built from the decision's stored inputs, never from guessed outcomes."""

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache

from app.gamification.application.research_glossary import (
    FAMILY_NAMES,
    MODE_NAMES,
    TYPE_NAMES,
    plain_status,
    reason_name,
)
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY


@lru_cache
def area_titles():
    return json.loads(
        (GAMIFICATION_DATA_DIRECTORY / "research-dashboard/area_titles.json").read_text(encoding="utf-8")
    )


def resolved_area(state):
    if state.get("area_id"):
        return str(state["area_id"])
    if str(state.get("skill_id", "")).startswith("G5-MAT-C03-"):
        return "G5-AREA-MAT-05"
    return "earlier-game"


def research_subject(state):
    return "ENG" if "-ENG-" in str(state.get("area_id", "")) else "MAT"


def area_title(area_id):
    row = area_titles().get(str(area_id), {"title": "Learning game", "english": "Learning game"})
    return row["title"] if row["title"] == row["english"] else f"{row['title']} · {row['english']}"


def english_title(area_id):
    row = area_titles().get(str(area_id), {})
    return str(row.get("english") or row.get("title") or "Learning game")


def name(support):
    return TYPE_NAMES.get(str(support), "Help")


def explain_model1(model1, subject="MAT"):
    if not isinstance(model1, Mapping):
        return None
    probabilities = {key: float(value) for key, value in model1["probabilities"].items()}
    label = max(probabilities, key=probabilities.get)
    top = probabilities[label]
    prior = model1.get("prior_counts") or {}
    count, size = prior.get(label, 0), model1.get("prior_sample_size", 0)
    likelihood = model1.get("likelihood") or probabilities
    why = "The game noticed a mistake in the child's answer. Other reasons remain possible."
    if model1.get("fallback_used"):
        why = "There was too little evidence in this answer to name one reason confidently."
    history_effect = (
        (
            f"This mistake appeared {count} of the last {size} times on this skill. "
            f"Confidence changed from {likelihood[label]:.0%} to {top:.0%}."
        )
        if count
        else "No matching earlier mistake changed this estimate."
    )
    return {
        "headline": f"Most likely reason: {reason_name(label, subject)} ({top:.0%} sure)",
        "why": why,
        "history_effect": history_effect,
        "uncertain": bool(model1.get("low_confidence") or model1.get("fallback_used")),
        "reasons": [
            {"code": code, "label": reason_name(code, subject), "probability": probability}
            for code, probability in sorted(
                probabilities.items(), key=lambda row: row[1], reverse=True
            )
        ],
        "inputs": {
            "answer": model1.get("constructed_response"),
            "error_code": model1.get("structured_error_code"),
        },
        "assumptions": [
            "One answer cannot prove why a mistake happened.",
            "At most five earlier answers influence the estimate.",
        ],
    }


def explain_model2(state):
    record = state.get("model2")
    if not isinstance(record, Mapping) or not record.get("support_order"):
        return None
    order = list(record["support_order"])
    history = dict(
        (record.get("learner_activity_support_preference") or {}).get("by_support") or {}
    )
    mode = str(record.get("support_selection_mode"))
    reading = record.get("learning_state_input") or {}
    # Said only when how the child seemed in this game actually changed the help.
    state_sentence = ""
    if reading.get("changed_first_help"):
        state_sentence = (
            f"During this game the child seemed {plain_status(reading.get('state')).lower()}, "
            "so a shorter first task was chosen."
        )
    elif reading.get("changed_order"):
        state_sentence = (
            f"During this game the child seemed {plain_status(reading.get('state')).lower()}, "
            "so a solved example moved earlier."
        )
    family = str(record.get("reason_family") or "unclear")
    steps = [
        f"Likely reason: {FAMILY_NAMES.get(family, FAMILY_NAMES['unclear'])}.",
        "This child's earlier fair tests guide which help to try first."
        if history
        else "There is no earlier fair test on this skill yet.",
        *([state_sentence] if state_sentence else []),
    ]
    if mode == "baseline_fixed_order":
        steps = [
            "The comparison group uses the subject's fixed help order.",
            "Past results do not change this order.",
        ]
    return {
        "headline": f"First help: {name(order[0])}",
        "why": MODE_NAMES.get(mode, "The recorded help choice") + ".",
        "steps": steps,
        "order": order,
        "mode": mode,
        "reason_family": family,
        "matched_pattern": "",
        "subject_order": [],
        "history": history,
        "learning_state_sentence": state_sentence,
        "legacy_shared_credit": record.get("order_policy_version") == "support-order-v2",
        "history_note": "This older decision counted every help that was tried. New games credit only the help that succeeded."
        if record.get("order_policy_version") == "support-order-v2"
        else "Only the successful help receives the later independent result. Earlier failed help is counted separately.",
        "assumptions": [
            "Only the help that succeeded receives the later independent result.",
            "Earlier failed help is counted separately.",
            "Two independent successes outweigh how the child seemed in one game.",
        ],
    }


def explain_rounds(state):
    loop = state.get("support_loop") or {}
    result = []
    for index, row in enumerate(loop.get("rounds") or []):
        outcome = row.get("outcome")
        rule = (
            "The child managed it with help. The help is then removed."
            if outcome == "succeeded"
            else "This help was not enough, so the next help was tried."
            if outcome == "failed" and index < len(loop["rounds"]) - 1
            else "All available help was tried. The child next tries alone."
            if outcome == "failed"
            else "The child is still trying this help."
        )
        stages = row.get("stages") or []
        result.append(
            {
                "round_number": row.get("round_number"),
                "scaffold_type": row.get("scaffold_type"),
                "name": name(row.get("scaffold_type")),
                "stages": [stage.get("kind") for stage in stages],
                "what_child_saw": [cue for stage in stages for cue in stage.get("cues_si") or []],
                "attempts": [
                    {"correct": bool(a.get("correct")), "error": a.get("structured_error_code")}
                    for a in row.get("attempts") or []
                ],
                "outcome": outcome,
                "outcome_label": plain_status(outcome),
                "rule": rule,
                "opened_at": row.get("opened_at"),
                "closed_at": row.get("closed_at"),
            }
        )
    return result


def explain_model3(state):
    measurement = state.get("measurement")
    status = str(state.get("policy_update_status"))
    if not isinstance(measurement, Mapping):
        if status == "not_authorized_no_support":
            return {
                "headline": "Right first time",
                "why": "No help was needed, so there is no before-and-after help result.",
                "checks": [],
                "policy": plain_status(status),
            }
        return None
    before, after = measurement.get("before_earned"), measurement.get("after_earned")
    gain = measurement.get("raw_independence_gain", state.get("raw_independence_gain"))
    withdrawal = state.get("withdrawal") or {}
    items = {item.get("role"): item for item in state.get("presentations") or []}
    first, last = items.get("unsupported_before", {}), items.get("unsupported_after", {})
    checks = [
        (
            "Both questions test the same skill",
            bool(first) and first.get("skill_id") == last.get("skill_id"),
        ),
        (
            "Both questions have a matching difficulty",
            bool(first.get("parallel_family_id"))
            and first.get("parallel_family_id") == last.get("parallel_family_id"),
        ),
        (
            "The second question was fresh",
            bool(last) and first.get("revision_id") != last.get("revision_id"),
        ),
        (
            "Every trace of help was removed",
            all(
                withdrawal.get(flag)
                for flag in (
                    "all_support_removed",
                    "answer_revealing_state_cleared",
                    "input_handlers_cleared",
                )
            ),
        ),
        (
            "No issue made this an unfair test",
            measurement.get("valid", state.get("validity") == "valid") is True
            and not measurement.get("exclusion_reasons"),
        ),
    ]
    return {
        "headline": f"Independence gain {gain if gain is not None else 'not measured'}",
        "why": "One question before help and one fresh question after help. One game gives only a small piece of evidence.",
        "basis": "1 question before, 1 after",
        "before": before,
        "after": after,
        "checks": [{"name": label, "passed": bool(passed)} for label, passed in checks],
        "policy": plain_status(status),
        "policy_updates": state.get("policy_updates") or [],
        "formula": "After score minus before score",
    }


def episode_summary(run: Mapping[str, object]) -> dict[str, object]:
    state = run["state"]
    assert isinstance(state, Mapping)
    attempts = {str(row.get("role")): row for row in state.get("attempts") or []}
    model2 = state.get("model2") if isinstance(state.get("model2"), Mapping) else {}
    loop = state.get("support_loop") if isinstance(state.get("support_loop"), Mapping) else {}
    measurement = state.get("measurement") if isinstance(state.get("measurement"), Mapping) else {}
    events: Sequence[Mapping[str, object]] = state.get("events") or []  # type: ignore[assignment]
    return {
        "episode_id": state.get("episode_id"),
        "skill_id": state.get("skill_id"),
        "area_id": resolved_area(state),
        "condition": state.get("condition"),
        "area_title": area_title(resolved_area(state)),
        "status_label": plain_status(run["status"]),
        "status": run["status"],
        "seeded": state.get("seed_source") is not None,
        "started_at": events[0].get("occurred_at") if events else None,
        "updated_at": run["updated_at"].isoformat() if run.get("updated_at") else None,  # type: ignore[union-attr]
        "before_correct": attempts.get("unsupported_before", {}).get("correct"),
        "after_correct": attempts.get("unsupported_after", {}).get("correct"),
        "help_types": list(loop.get("types_used") or []),
        "selection_mode": model2.get("support_selection_mode") if model2 else None,
        "first_help": (next(iter(model2.get("support_order") or [None])) if model2 else None),
        "gain": (measurement.get("raw_independence_gain") if measurement else None)
        or state.get("raw_independence_gain"),
        "policy_update_status": state.get("policy_update_status"),
        "last_event": events[-1].get("event_type") if events else None,
    }
