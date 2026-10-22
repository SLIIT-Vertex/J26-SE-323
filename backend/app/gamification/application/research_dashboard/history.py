"""Each model's history for one child: what it decided in every game, what changed, what did not.

Built only from the stored games, oldest to newest, so each entry reflects what the model knew at
that moment. A game still being played appears straight away and fills in as it goes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from app.gamification.application.research_dashboard.accuracy import is_independent, wilson
from app.gamification.application.research_dashboard.explain import (
    english_title,
    help_rounds,
    name,
    research_subject,
    resolved_area,
)
from app.gamification.application.research_dashboard.glossary import (
    EXCLUSIONS,
    FAMILY_NAMES,
    MODE_NAMES,
    plain_status,
    reason_name,
)
from app.gamification.application.research_dashboard.play_status import STATUS_LABELS, play_status
from app.gamification.modeling.support_selection.support_order import (
    SUBJECT_ORDERS,
    credited_support,
    rank_support_history,
    subject_of,
)

MODELS = ("misconception", "support", "gain")
TERMINAL = {"completed", "invalidated"}
HELP_CHIP = {
    "visual_guidance": "Visual hint",
    "step_by_step_guidance": "Guided questions",
    "conceptual_reexplanation": "Explain again",
    "simpler_same_game": "Easier first",
    "prerequisite_repair": "Practise skill",
    "worked_parallel_example": "Solved example",
}


def model_history(
    runs: Sequence[Mapping[str, object]], model: str, *, now: datetime | None = None
) -> list[dict[str, object]]:
    if model not in MODELS:
        raise ValueError("UNKNOWN_MODEL")
    moment = now or datetime.now(UTC)
    ordered = _ordered(runs)
    builder = {"misconception": _misconception, "support": _support, "gain": _gain}[model]
    entries: list[dict[str, object]] = []
    by_skill: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for run in ordered:
        state = _state(run)
        skill = str(state.get("skill_id"))
        entries.append({**_meta(run, moment), **builder(run, by_skill[skill])})
        by_skill[skill].append(run)
    return list(reversed(entries))


def model_series(
    runs: Sequence[Mapping[str, object]], model: str, *, now: datetime | None = None
) -> dict[str, object]:
    """Chart series from the same oldest-to-newest walk as model history."""

    if model not in MODELS:
        raise ValueError("UNKNOWN_MODEL")
    moment = now or datetime.now(UTC)
    ordered = _ordered(runs)
    return {
        "misconception": _misconception_series,
        "support": _support_series,
        "gain": _gain_series,
    }[model](ordered, moment)


def _ordered(runs: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return sorted(
        (run for run in runs if not _state(run).get("seed_source") and _played(run)),
        key=_started,
    )


# Probabilistic Misconception ----------------------------------------------------------------------


def _misconception(run, earlier):
    state = _state(run)
    subject = research_subject(state)
    model1 = state.get("model1")
    before = _attempt(state, "unsupported_before")
    if not isinstance(model1, Mapping):
        if before is None:
            return _entry("Waiting for the first answer.", [], ["Nothing estimated yet."])
        return _entry(
            "Right at the first try: no reason needed.",
            [],
            [
                "No mistake, so no reason was estimated.",
                "This right answer still counts in the memory of the last five answers on this skill.",
            ],
        )
    posterior = {k: float(v) for k, v in dict(model1["probabilities"]).items()}
    likelihood = {k: float(v) for k, v in dict(model1.get("likelihood") or posterior).items()}
    top = str(model1.get("top_hypothesis") or model1.get("predicted_label"))
    alone_top = max(likelihood, key=likelihood.get)
    changed, unchanged, chips = [], [], []
    noticed = reason_name(model1.get("structured_error_code"), subject)
    unchanged.append(f"The game noticed this mistake: {noticed.lower()}.")
    counts = dict(model1.get("prior_counts") or {})
    window = list(model1.get("prior_window") or [])
    same = int(counts.get(top, 0))
    if model1.get("learner_prior_used"):
        changed.append(
            f"Earlier answers changed how sure it is: {_pct(likelihood.get(top))} from this answer "
            f"alone → {_pct(posterior[top])} after counting {same} of the last {len(window)} "
            "answers with the same mistake."
        )
        chips.append(
            _chip(
                {
                    "kind": "confidence",
                    "from": round(float(likelihood.get(top) or 0), 4),
                    "to": round(posterior[top], 4),
                },
                f"Confidence {_pct(likelihood.get(top))} → {_pct(posterior[top])}",
            )
        )
        if alone_top != top:
            changed.append(
                f"History changed the most likely reason from "
                f"{reason_name(alone_top, subject).lower()} to {reason_name(top, subject).lower()}."
            )
    else:
        unchanged.append(
            "No earlier mistake of this kind on this skill, so the estimate comes from this answer alone."
        )
    previous = next(
        (
            _state(r)["model1"]
            for r in reversed(earlier)
            if isinstance(_state(r).get("model1"), Mapping)
        ),
        None,
    )
    if previous is not None:
        last = str(previous.get("top_hypothesis") or previous.get("predicted_label"))
        if last == top:
            unchanged.append(
                f"Same most likely reason as last time on this skill ({reason_name(top, subject).lower()})."
            )
        else:
            changed.append(
                f"Most likely reason changed since last time: {reason_name(last, subject).lower()} → "
                f"{reason_name(top, subject).lower()}."
            )
            chips.append(
                _chip(
                    {
                        "kind": "reason",
                        "from": _three(reason_name(last, subject)),
                        "to": _three(reason_name(top, subject)),
                    },
                    f"Reason changed: {_three(reason_name(last, subject))} → {_three(reason_name(top, subject))}",
                )
            )
    else:
        unchanged.append("First estimate for this skill.")
    if model1.get("low_confidence") or model1.get("fallback_used"):
        unchanged.append(
            "Marked as unsure, so the help choice treats the reason as “not sure yet”."
        )
    ranked = sorted(posterior.items(), key=lambda item: item[1], reverse=True)[:3]
    return _entry(
        f"Most likely reason: {reason_name(top, subject)} ({_pct(posterior[top])})",
        changed,
        unchanged,
        values=[
            {"label": reason_name(key, subject), "value": _pct(value)} for key, value in ranked
        ],
        chips=chips,
    )


# Contextual Support Selection ---------------------------------------------------------------------


def _support(run, earlier):
    state = _state(run)
    model2 = state.get("model2")
    if not isinstance(model2, Mapping) or not model2.get("support_order"):
        if _attempt(state, "unsupported_before") is None:
            return _entry("Waiting for the first answer.", [], ["No help chosen yet."])
        return _entry(
            "No help needed.",
            [],
            [
                "The child was right at the first try, so no help was chosen and nothing was learned."
            ],
        )
    area = resolved_area(state)
    order = [str(value) for value in model2["support_order"]]
    mode = str(model2.get("support_selection_mode"))
    changed, unchanged, chips = [], [], []
    family = str(model2.get("reason_family") or "unclear")
    unchanged.extend(_help_given(state))
    if mode == "baseline_fixed_order":
        unchanged.append("Comparison group: the fixed help order was used.")
    else:
        unchanged.append(
            f"Likely reason: {FAMILY_NAMES.get(family, FAMILY_NAMES['unclear']).lower()}."
        )
        changed.append(f"Why {name(order[0])} came first: {MODE_NAMES.get(mode, mode).lower()}.")
    last = next(
        (
            _state(r)["model2"]
            for r in reversed(earlier)
            if isinstance(_state(r).get("model2"), Mapping)
            and _state(r)["model2"].get("support_order")
        ),
        None,
    )
    if last is not None:
        last_first = str(last["support_order"][0])
        if last_first == order[0]:
            unchanged.append(f"Same first help as last time on this skill ({name(order[0])}).")
        else:
            changed.append(
                f"First help changed since last time: {name(last_first)} → {name(order[0])}."
            )
            chips.append(
                _chip(
                    {"kind": "first_help", "from": last_first, "to": order[0]},
                    f"First help: {_help_chip(last_first)} → {_help_chip(order[0])}",
                )
            )
    # What this game did to the child's record.
    completed = [_state(r) for r in earlier if r["status"] == "completed"]
    subject_order = (
        SUBJECT_ORDERS[subject_of(area)] if area.startswith("G5-AREA-") else SUBJECT_ORDERS["MAT"]
    )
    before_rank = rank_support_history(completed, order=subject_order)
    if run["status"] not in TERMINAL:
        unchanged.append("The game is still being played; the record changes when it ends.")
    elif run["status"] == "invalidated":
        unchanged.append("The game was not finished, so the record was not changed.")
    elif state.get("condition") != "proposed":
        unchanged.append("Comparison-group games never change the record.")
    else:
        after_rank = rank_support_history([*completed, state], order=subject_order)
        winner, failed = credited_support(state)
        record_chip = None
        for support in sorted(set(before_rank.by_support) | set(after_rank.by_support)):
            old = before_rank.by_support.get(support)
            new = after_rank.by_support.get(support)
            if old == new:
                continue
            changed.append(f"{name(support)}: {_record(old)} → {_record(new)}.")
            if record_chip is None or support == winner:
                record_chip = _chip(
                    {
                        "kind": "record",
                        "help": support,
                        "from": _ratio(old),
                        "to": _ratio(new),
                    },
                    f"Record {_ratio(old)} → {_ratio(new)}",
                )
        if record_chip is not None:
            chips.append(record_chip)
        if winner:
            chips.append(_chip({"kind": "learned", "help": winner}, "Learned: credit recorded"))
        if winner is None and not failed:
            unchanged.append("No help type earned credit in this game.")
        if before_rank.preferred == after_rank.preferred:
            unchanged.append(
                f"Best help for this child on this skill stays {name(after_rank.preferred)}."
                if after_rank.preferred
                else "No best help for this child on this skill yet."
            )
        else:
            changed.append(
                f"Best help for this child on this skill: {name(before_rank.preferred) if before_rank.preferred else 'none yet'} "
                f"→ {name(after_rank.preferred)}."
            )
    return _entry(
        f"First help: {name(order[0])}",
        changed,
        unchanged,
        values=[
            {"label": f"{index + 1}.", "value": name(value)} for index, value in enumerate(order)
        ],
        chips=chips,
    )


def _help_given(state) -> list[str]:
    """What the child actually saw, which can be fewer helps than the planned order."""

    rounds = help_rounds(state)
    lines = []
    for stage_phase, label in (
        ("measured", "Help given"),
        ("follow_up", "More help after the try alone"),
    ):
        given = [
            f"{name(row.get('scaffold_type'))} ({plain_status(row.get('outcome')).lower()})"
            for phase, row in rounds
            if phase == stage_phase
        ]
        if given:
            lines.append(f"{label}: {' → '.join(given)}.")
    return lines


# Independence Gain ----------------------------------------------------------------------------------


def _gain(run, _earlier):
    state = _state(run)
    before = _attempt(state, "unsupported_before")
    after = _attempt(state, "unsupported_after")
    measurement = state.get("measurement")
    if before is None:
        return _entry("Waiting for the first answer.", [], ["Nothing measured yet."])
    if not isinstance(measurement, Mapping):
        if before.get("correct"):
            return _entry(
                "Right at the first try: nothing to measure.",
                [],
                ["Gain is only measured when help was needed."],
            )
        if run["status"] == "invalidated":
            return _entry(
                "Not measured: the game was not finished.",
                [],
                ["An unfinished game is never used to judge help."],
            )
        return _entry(
            "Waiting for the try alone after help.",
            [],
            ["The measurement appears once the fresh question is answered."],
        )
    raw = measurement.get("raw_independence_gain")
    raw = raw if raw is not None else state.get("raw_independence_gain")
    if raw is None:
        return _entry(
            "Not measured: the try alone after help is missing.",
            [],
            ["Without both answers there is no gain to report."],
        )
    gain = Decimal(str(raw))
    changed, unchanged, chips = [], [], []
    fair = state.get("validity") == "valid"
    if fair:
        unchanged.append(
            "Fair test: help was fully removed and the fresh question was new to the child."
        )
    else:
        reasons = [
            EXCLUSIONS.get(code, "A fair-test requirement was not met")
            for code in measurement.get("exclusion_reasons") or state.get("exclusion_reasons") or []
        ]
        unchanged.append(
            "Not a fair test: " + ("; ".join(reasons) or "a requirement was not met") + "."
        )
    alone = bool(after and after.get("correct")) and fair and gain > 0
    chips.append(
        _chip(
            {
                "kind": "gain",
                "value": 1 if alone else 0,
                "before": bool(before.get("correct")),
                "after": bool(after.get("correct")) if after is not None else None,
            },
            "Could do it alone" if alone else "Still needed help",
        )
    )
    updates = list(state.get("policy_updates") or [])
    if updates:
        winner, _failed = credited_support(state)
        changed.append(
            "Contextual Support Selection learned from this result"
            + (f" (credit to {name(winner)})." if winner else " (no help type earned credit).")
        )
    elif state.get("condition") != "proposed":
        unchanged.append("Comparison group: measured, but nothing was learned from it.")
    else:
        unchanged.append("Not used for learning, because it was not a fair test.")
    return _entry(
        f"Gain {_signed(gain)}: {_mark(before)} before help → {_mark(after)} alone after help",
        changed,
        unchanged,
        values=[
            {"label": "Before help", "value": _mark(before)},
            {"label": "Alone after help", "value": _mark(after)},
            {"label": "Gain", "value": _signed(gain)},
        ],
        chips=chips,
    )


# Shared -------------------------------------------------------------------------------------------


def _meta(run, now: datetime) -> dict[str, object]:
    state = _state(run)
    area = resolved_area(state)
    status = play_status(run, now)
    return {
        "episode_id": str(state.get("episode_id")),
        "area_id": area,
        "game": english_title(area),
        "skill_id": str(state.get("skill_id")),
        "played_at": _started(run),
        "status": STATUS_LABELS[status],
        "play_status": status,
        "in_progress": status == "live",
        "comparison_group": state.get("condition") == "baseline",
    }


def _entry(headline, changed, unchanged, *, values=None, chips=None) -> dict[str, object]:
    chosen = list(chips or [])[:2]
    return {
        "headline": headline,
        "changed": changed,
        "unchanged": unchanged,
        "values": values or [],
        "changes": [chip["change"] for chip in chosen],
        "changed_short": [chip["text"] for chip in chosen],
    }


def _played(run) -> bool:
    """A game counts once the child has answered, or while it is being played."""

    state = _state(run)
    return run["status"] != "invalidated" or _attempt(state, "unsupported_before") is not None


def _started(run) -> str:
    events = _state(run).get("events") or []
    if events:
        return str(events[0].get("occurred_at"))
    return (
        run["updated_at"].isoformat()
        if hasattr(run["updated_at"], "isoformat")
        else str(run["updated_at"])
    )


def _attempt(state, role):
    return next((row for row in state.get("attempts") or [] if row.get("role") == role), None)


def _record(row) -> str:
    if not row:
        return "no record"
    return f"alone afterwards {row['independent_successes']} of {row['episodes']} times"


def _pct(value) -> str:
    return f"{round(float(value or 0) * 100)}%"


def _signed(value: Decimal) -> str:
    return f"+{value.normalize()}" if value > 0 else str(value.normalize())


def _mark(attempt) -> str:
    if attempt is None:
        return "not answered"
    return "right" if attempt.get("correct") else "wrong"


def _state(run) -> Mapping[str, object]:
    return run["state"]


def _chip(change: dict[str, object], text: str) -> dict[str, object]:
    return {"change": change, "text": " ".join(text.split()[:10])}


def _three(label: str) -> str:
    return " ".join(label.split()[:3])


def _help_chip(code: str) -> str:
    return HELP_CHIP.get(code, "Help")


def _ratio(row) -> str:
    if not row:
        return "0/0"
    return f"{int(row['independent_successes'])}/{int(row['episodes'])}"


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _short_game(title: str) -> str:
    words = title.split()
    return words[-1] if len(words) > 1 else title


def _short_reason(label: str) -> str:
    words = label.split()
    chosen = " ".join(words[-2:] if len(words) > 2 else words)
    return chosen[:1].upper() + chosen[1:]


def _episode_id(run) -> str:
    return str(_state(run).get("episode_id"))


def _order(run) -> list[str]:
    model2 = _state(run).get("model2")
    if not isinstance(model2, Mapping):
        return []
    return [str(value) for value in model2.get("support_order") or []]


def _subject_order(state):
    area = resolved_area(state)
    subject = subject_of(area) if str(area).startswith("G5-AREA-") else "MAT"
    return SUBJECT_ORDERS[subject]


# Series ------------------------------------------------------------------------------------------------


def _misconception_series(ordered, _now) -> dict[str, object]:
    points = []
    seen: dict[str, set[str]] = defaultdict(set)
    with_history: list[float] = []
    without: list[float] = []
    for run in ordered:
        state = _state(run)
        model1 = state.get("model1")
        if not isinstance(model1, Mapping) or not model1.get("probabilities"):
            continue
        posterior = {k: float(v) for k, v in dict(model1["probabilities"]).items()}
        top = str(model1.get("top_hypothesis") or model1.get("predicted_label") or "")
        if top not in posterior:
            top = max(posterior, key=posterior.get)
        subject = research_subject(state)
        skill = str(state.get("skill_id"))
        confidence = posterior[top]
        used = bool(model1.get("learner_prior_used"))
        label = reason_name(top, subject)
        points.append(
            {
                "episode_id": _episode_id(run),
                "at": _started(run),
                "game": english_title(resolved_area(state)),
                "confidence": round(confidence, 4),
                "repeat_reason": top in seen[skill],
                "used_history": used,
                "reason": label,
            }
        )
        (with_history if used else without).append(confidence)
        seen[skill].add(top)
    counts: dict[str, int] = defaultdict(int)
    for point in points:
        counts[str(point["reason"])] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top_reason = (
        {"label": ranked[0][0], "count": ranked[0][1]} if ranked else {"label": "", "count": 0}
    )
    recent = [
        {
            "episode_id": point["episode_id"],
            "game_short": _short_game(str(point["game"])),
            "reason_short": _short_reason(str(point["reason"])),
            "confidence": point["confidence"],
        }
        for point in reversed(points[-8:])
    ]
    return {
        "kpis": {
            "analysed": len(points),
            "top_reason": top_reason,
            "mean_confidence": _mean([float(point["confidence"]) for point in points]),
        },
        "points": points,
        "top_reasons": [{"label": label, "count": count} for label, count in ranked[:5]],
        "memory": {
            "with_history": {"count": len(with_history), "mean": _mean(with_history)},
            "without": {"count": len(without), "mean": _mean(without)},
        },
        "recent": recent,
    }


def _support_outcome(run, now: datetime) -> str:
    status = play_status(run, now)
    if status == "live":
        return "live"
    if status in {"abandoned", "invalid"}:
        return "abandoned"
    state = _state(run)
    if state.get("condition") == "baseline":
        return "comparison"
    if is_independent(state):
        return "alone"
    return "not_alone"


def _support_series(ordered, now: datetime) -> dict[str, object]:
    points = []
    drivers = {"reason": 0, "history": 0, "fixed": 0}
    first_worked: list[int] = []
    by_skill: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for run in ordered:
        state = _state(run)
        order = _order(run)
        status = play_status(run, now)
        if order or status in {"live", "abandoned"}:
            points.append(
                {
                    "episode_id": _episode_id(run),
                    "at": _started(run),
                    "first_help": order[0] if order else None,
                    "outcome": _support_outcome(run, now),
                }
            )
        if order:
            mode = str((_state(run).get("model2") or {}).get("support_selection_mode"))  # type: ignore[union-attr]
            if mode == "baseline_fixed_order" or state.get("condition") == "baseline":
                drivers["fixed"] += 1
            elif mode == "learned_post_withdrawal_preference":
                drivers["history"] += 1
            else:
                drivers["reason"] += 1
        if run["status"] == "completed":
            by_skill[str(state.get("skill_id"))].append(state)
            loop = (
                state.get("support_loop") if isinstance(state.get("support_loop"), Mapping) else {}
            )
            if loop.get("stop_reason"):
                rounds = loop.get("rounds") or []
                first_worked.append(
                    int(len(rounds) == 1 and loop.get("stop_reason") == "supported_success")
                )
    worked, skills_with_best = _worked(by_skill)
    recent = []
    for run in reversed(ordered):
        order = _order(run)
        if not order:
            continue
        after = _attempt(_state(run), "unsupported_after")
        recent.append(
            {
                "episode_id": _episode_id(run),
                "order": order[:3],
                "after": bool(after.get("correct")) if after is not None else None,
            }
        )
        if len(recent) == 8:
            break
    return {
        "kpis": {
            "sessions": sum(1 for run in ordered if _order(run)),
            "first_help_worked": {
                "value": round(sum(first_worked) / len(first_worked), 4) if first_worked else 0,
                "count": len(first_worked),
            },
            "skills_with_best_help": skills_with_best,
        },
        "points": points,
        "worked": worked,
        "preference": _preference(ordered),
        "drivers": drivers,
        "recent": recent,
    }


def _preference(ordered) -> list[dict[str, object]]:
    """Every help, most to least preferred, ranked the way the support model ranks its history."""

    order = tuple(dict.fromkeys(help for subject in SUBJECT_ORDERS.values() for help in subject))
    states = [_state(run) for run in ordered if run["status"] == "completed"]
    by_support = rank_support_history(states, order=order).by_support
    rows = []
    for index, support in enumerate(order):
        row = by_support.get(support) or {}
        credited = int(row.get("episodes", 0))
        successes = int(row.get("independent_successes", 0))
        failed = int(row.get("did_not_help", 0))
        rows.append(
            {
                "help": support,
                "successes": successes,
                "credited": credited,
                "did_not_help": failed,
                "rate": round(successes / credited, 4) if credited else None,
                "tried": bool(credited or failed),
                # Same tie-breaks as the model: success rate, mean gain, fewer failed rounds,
                # then the subject's default order.
                "_score": (
                    bool(credited or failed),
                    successes / credited if credited else -1.0,
                    float(row.get("mean_independence_gain", 0)),
                    -failed,
                    -index,
                ),
            }
        )
    rows.sort(key=lambda row: row["_score"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        del row["_score"]
        row["rank"] = rank
    return rows


def _worked(by_skill: dict[str, list[Mapping[str, object]]]):
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    best_skill_size = -1
    star = None
    skills = 0
    for states in by_skill.values():
        if not states:
            continue
        ranking = rank_support_history(states, order=_subject_order(states[-1]))
        if ranking.preferred:
            skills += 1
            if len(states) > best_skill_size:
                best_skill_size = len(states)
                star = ranking.preferred
        for support, row in ranking.by_support.items():
            totals[support][0] += int(row["independent_successes"])
            totals[support][1] += int(row["episodes"])
    rows = [
        {
            "help": support,
            "successes": successes,
            "credited": credited,
            "star": support == star,
        }
        for support, (successes, credited) in sorted(totals.items())
        if credited
    ]
    return rows, skills


def _gain_series(ordered, _now) -> dict[str, object]:
    points = []
    successes = 0
    grid = {"wrong_then_right": 0, "wrong_then_wrong": 0, "right_first": 0}
    by_game: dict[str, list[int]] = defaultdict(list)
    eligible = 0
    fair = 0
    for run in ordered:
        state = _state(run)
        before = _attempt(state, "unsupported_before")
        after = _attempt(state, "unsupported_after")
        if (
            run["status"] == "completed"
            and before
            and before.get("correct")
            and not state.get("support_loop")
        ):
            grid["right_first"] += 1
        measurement = (
            state.get("measurement") if isinstance(state.get("measurement"), Mapping) else None
        )
        if run["status"] != "completed" or measurement is None:
            continue
        if state.get("validity") in {"valid", "invalid"} or run["status"] == "invalidated":
            eligible += 1
        if state.get("validity") != "valid":
            if before and not before.get("correct") and after is not None:
                pass
            continue
        fair += 1
        alone = is_independent(state)
        successes += int(alone)
        band = wilson(successes, fair) or [0.0, 1.0]
        rate = successes / fair
        gain_bit = 1 if alone else 0
        low = min(band[0], rate)
        high = max(band[1], rate)
        points.append(
            {
                "episode_id": _episode_id(run),
                "at": _started(run),
                "gain": gain_bit,
                "running_rate": round(rate, 4),
                "low": round(low, 4),
                "high": round(high, 4),
            }
        )
        game = english_title(resolved_area(state))
        by_game[game].append(gain_bit)
        if before and not before.get("correct"):
            grid["wrong_then_right" if alone else "wrong_then_wrong"] += 1
    fair_runs = []
    for run in ordered:
        state = _state(run)
        if (
            run["status"] == "completed"
            and state.get("validity") == "valid"
            and isinstance(state.get("measurement"), Mapping)
        ):
            fair_runs.append(run)
    recent = []
    for run in reversed(fair_runs[-8:]):
        state = _state(run)
        before = _attempt(state, "unsupported_before")
        after = _attempt(state, "unsupported_after")
        alone = is_independent(state)
        recent.append(
            {
                "episode_id": _episode_id(run),
                "before": bool(before and before.get("correct")),
                "after": bool(after.get("correct")) if after is not None else None,
                "gain": 1 if alone else 0,
            }
        )
    return {
        "kpis": {
            "fair_tests": fair,
            "alone": {"value": _mean([float(point["gain"]) for point in points]), "count": fair},
            "fair_rate": round(fair / eligible, 4) if eligible else None,
        },
        "points": points,
        "grid": grid,
        "by_game": [{"game": game, "points": marks} for game, marks in by_game.items()],
        "recent": recent,
    }
