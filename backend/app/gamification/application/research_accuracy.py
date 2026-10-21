"""Descriptive model checks from the child's own stored games. Simulated learners are reported separately."""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from math import sqrt

from app.gamification.application.research_explain import area_title
from app.gamification.application.research_glossary import EXCLUSIONS
from app.gamification.modeling.misconception_inference.learner_prior import PRIOR_CAP
from app.gamification.modeling.support_selection.support_order import (
    LEAD_BY_REASON,
    credited_support,
)

MIN_SESSIONS = 20
CALIBRATION_PAIRS = 30


def wilson(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    z, p = 1.959963984540054, successes / count
    centre = (p + z * z / (2 * count)) / (1 + z * z / count)
    margin = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    return [max(0, centre - margin), min(1, centre + margin)]


def metric(
    key,
    title,
    good,
    method,
    values,
    *,
    threshold=MIN_SESSIONS,
    unit="rate",
    technical=None,
    tile=False,
):
    """One measured value. Small samples are shown, with how much they can be trusted."""

    n = len(values)
    value = sum(values) / n if n else None
    if not n:
        meaning = "No game has produced this measurement yet."
    elif n < threshold:
        meaning = (
            f"Based on {n} games. That is a small number, so treat it as an early sign; "
            f"the reporting threshold is {threshold} games, not a guarantee of accuracy."
        )
    else:
        meaning = f"Based on {n} games."
    return {
        "key": key,
        "title": title,
        "good": good,
        "method": method,
        "count": n,
        "minimum": threshold,
        "value": value,
        "unit": unit,
        "small_sample": 0 < n < threshold,
        "tile": tile,
        "meaning": meaning,
        "interval": wilson(sum(values), n) if n and unit == "rate" else None,
        "technical": technical or {},
    }


def setting(name, value, how, *, tried=None, replay=None):
    """One model parameter, the values compared for it, and how they were compared."""

    return {"name": name, "value": value, "how": how, "tried": tried or [], "replay": replay}


def _plain_exclusions(codes: Counter) -> Counter:
    merged: Counter = Counter()
    for code, n in codes.items():
        merged[EXCLUSIONS.get(code, "A fair-test requirement was not met")] += n
    return merged


def is_independent(state):
    m = state.get("measurement") or {}
    return (
        state.get("validity") == "valid"
        and float(m.get("after_maximum", 0)) > 0
        and float(m.get("after_earned", 0)) == float(m["after_maximum"])
    )


def prediction_pairs(states):
    """Pair each prediction with the next wrong unsupported answer on the same skill."""
    by_skill = defaultdict(list)
    for state in states:
        by_skill[state.get("skill_id")].append(state)
    pairs = []
    for skill_states in by_skill.values():
        pending = []
        for state in skill_states:
            for attempt in state.get("attempts") or []:
                if (
                    attempt.get("role") not in {"unsupported_before", "unsupported_after"}
                    or attempt.get("assistance_state", "none") != "none"
                ):
                    continue
                code = attempt.get("structured_error_code")
                if not attempt.get("correct") and code:
                    pairs.extend((model, str(code)) for model in pending)
                    pending = []
                if attempt.get("role") == "unsupported_before" and state.get("model1"):
                    pending.append(state["model1"])
    return pairs


def accuracy_report(runs, *, all_runs=None):
    states = [
        r["state"]
        for r in runs
        if r["status"] in {"completed", "invalidated"} and not r["state"].get("seed_source")
    ]
    states.sort(
        key=lambda s: str(
            (s.get("model1") or {}).get("created_at")
            or (s.get("events") or [{}])[0].get("occurred_at", "")
        )
    )
    helped = [s for s in states if s.get("support_loop") or s.get("scaffold_exposure")]
    measured = [s for s in helped if s.get("measurement")]
    valid = [s for s in measured if s.get("validity") == "valid"]
    pairs = prediction_pairs(states)
    agreement, brier, bins = [], [], defaultdict(list)
    for model, observed in pairs:
        probabilities = model["probabilities"]
        top = max(probabilities, key=lambda k: float(probabilities[k]))
        agreement.append(int(top == observed))
        classes = set(probabilities) | {observed}
        brier.append(
            sum((float(probabilities.get(k, 0)) - int(k == observed)) ** 2 for k in classes)
        )
        confidence = float(probabilities[top])
        bins[min(3, int(confidence * 4))].append((confidence, int(top == observed)))
    calibration = (
        [
            {
                "from": i / 4,
                "to": (i + 1) / 4,
                "count": len(rows),
                "confidence": sum(v[0] for v in rows) / len(rows),
                "agreement": sum(v[1] for v in rows) / len(rows),
            }
            for i, rows in sorted(bins.items())
        ]
        if len(pairs) >= CALIBRATION_PAIRS
        else []
    )
    conditions = {}
    for condition in ("proposed", "baseline"):
        sample = [s for s in valid if s.get("condition") == condition]
        conditions[condition] = {
            "success": metric(
                condition,
                "Could do it alone",
                "More independent successes are better.",
                "Correct fresh answers after help was removed.",
                [int(is_independent(s)) for s in sample],
            ),
            "gain": metric(
                condition + "-gain",
                "Average gain",
                "A larger gain means more improvement.",
                "After score minus before score.",
                [
                    float(s["measurement"]["raw_independence_gain"])
                    for s in sample
                    if s["measurement"].get("raw_independence_gain") is not None
                ],
                unit="gain",
            ),
        }
    intervals = [row["success"]["interval"] for row in conditions.values()]
    comparison = "One of the two groups has no measured game yet, so they cannot be compared."
    if all(intervals):
        comparison = (
            "The uncertainty ranges overlap; there is not enough evidence to say one order is better."
            if max(i[0] for i in intervals) <= min(i[1] for i in intervals)
            else "The observed ranges do not overlap. This comparison alone does not prove that the help caused the difference."
        )
    matched, other, learned = [], [], []
    first = []
    rates = defaultdict(lambda: defaultdict(list))
    for s in helped:
        loop, decision = s.get("support_loop") or {}, s.get("model2") or {}
        rounds = loop.get("rounds") or []
        if loop.get("stop_reason"):
            first.append(int(len(rounds) == 1 and loop["stop_reason"] == "supported_success"))
        if s not in valid:
            continue
        success = int(is_independent(s))
        if decision.get("support_selection_mode") == "learned_post_withdrawal_preference":
            learned.append(success)
        if decision.get("reason_family") in LEAD_BY_REASON:
            first_choice = (decision.get("support_order") or [None])[0]
            (
                matched if first_choice == LEAD_BY_REASON[decision["reason_family"]] else other
            ).append(success)
        winner, failed = credited_support(s)
        for support in failed:
            rates[s.get("skill_id")][support].append(0)
        if winner:
            rates[s.get("skill_id")][winner].append(success)
    regrets = []
    for s in valid:
        chosen = ((s.get("model2") or {}).get("support_order") or [None])[0]
        skill_rates = rates[s.get("skill_id")]
        if chosen and chosen in skill_rates:
            averages = {k: sum(v) / len(v) for k, v in skill_rates.items()}
            regrets.append(max(averages.values()) - averages[chosen])
    exclusions = Counter(
        code
        for s in helped
        for code in (s.get("measurement") or {}).get(
            "exclusion_reasons", s.get("exclusion_reasons") or []
        )
    )
    leakage = 0
    repeat = []
    last_by_skill = {}
    for s in valid:
        skill = s.get("skill_id")
        value = int(is_independent(s))
        if skill in last_by_skill:
            repeat.append(int(value == last_by_skill[skill]))
        last_by_skill[skill] = value
    for s in measured:
        after = next(
            (p for p in s.get("presentations") or [] if p.get("role") == "unsupported_after"), {}
        )
        revision = after.get("revision_id")
        seen = {
            stage.get("item", {}).get("revision_id")
            for r in (s.get("support_loop") or {}).get("rounds") or []
            for stage in r.get("stages") or []
            if isinstance(stage.get("item"), dict)
        }
        leakage += int(bool(revision) and revision in seen)
    # Only genuinely unassisted answers can inform before/after difficulty matching.
    item_samples = defaultdict(lambda: defaultdict(list))
    for run in all_runs if all_runs is not None else runs:
        s = run["state"]
        if (
            run["status"] != "completed"
            or s.get("seed_source")
            or s.get("support_loop")
            or s.get("scaffold_exposure")
        ):
            continue
        for attempt in s.get("attempts") or []:
            if attempt.get("role") in {"unsupported_before", "unsupported_after"}:
                item_samples[s.get("area_id")][attempt["role"]].append(
                    int(bool(attempt.get("correct")))
                )
    matching = []
    for area, roles in item_samples.items():
        before, after = roles["unsupported_before"], roles["unsupported_after"]
        enough = min(len(before), len(after)) > 0
        gap = abs(sum(before) / len(before) - sum(after) / len(after)) if enough else None
        matching.append(
            {
                "area_id": area,
                "area_title": area_title(area),
                "before_count": len(before),
                "after_count": len(after),
                "gap": gap,
                "flagged": gap is not None and gap > 0.15,
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "minimum_sessions": MIN_SESSIONS,
        "purpose": "How we check that each part is doing its job, and how well it is doing so far.",
        "models": [
            {
                "name": "Probabilistic Misconception",
                "subtitle": "Why did the child get it wrong?",
                "metrics": [
                    metric(
                        "agreement",
                        "Reason confirmed later",
                        "The predicted reason matches a later mistake.",
                        "Compare the prediction with the next wrong unsupported answer on this skill.",
                        agreement,
                        tile=True,
                    ),
                    metric(
                        "calibration",
                        "Confidence accuracy",
                        "Smaller scores mean more accurate probabilities.",
                        "Compare the full probability estimate with the next observed mistake.",
                        brier,
                        threshold=CALIBRATION_PAIRS,
                        unit="score",
                        tile=True,
                    ),
                    metric(
                        "reason-help",
                        "Help matched to reason worked",
                        "The child succeeds alone after help.",
                        "Compare reason-led help with other first choices; this describes a pattern, not a cause.",
                        matched,
                    ),
                    metric(
                        "other-help",
                        "Other first help worked",
                        "The child succeeds alone after help.",
                        "Use other first help choices as a descriptive comparison.",
                        other,
                    ),
                ],
                "calibration": calibration,
                "parameters": [
                    "Answer evidence is capped at 72% and floored at 20% before history is applied.",
                    "Only five earlier answers can influence a new estimate.",
                    "A cap avoids certainty from one answer. A floor keeps some weight on a detected mistake.",
                    "These are provisional settings, not proven optimal values.",
                ],
                "settings": [
                    setting(
                        "Evidence cap",
                        "72%",
                        "Replayed stored answers with each cap; compared agreement and calibration.",
                        tried=["60%", "72%", "80%"],
                        replay="confidence_caps",
                    ),
                    setting("Evidence floor", "20%", "Keeps some weight on a detected mistake."),
                    setting(
                        "Answers remembered",
                        str(PRIOR_CAP),
                        "Only the latest answers without help shape the estimate.",
                    ),
                ],
            },
            {
                "name": "Contextual Support Selection",
                "subtitle": "Which help should come first, and in what order?",
                "metrics": [
                    metric(
                        "first",
                        "First help worked",
                        "Fewer rounds may mean the first choice was useful.",
                        "Count completed help loops that succeeded in the first round.",
                        first,
                        tile=True,
                    ),
                    metric(
                        "preference",
                        "Learned help worked",
                        "The child can do it alone after a familiar help choice.",
                        "Count independent successes after choices based on earlier results.",
                        learned,
                        tile=True,
                    ),
                    metric(
                        "regret",
                        "Gap from the best recorded help",
                        "A smaller gap is better.",
                        "Compare the first chosen help with the best recorded help for that skill; failed rounds count as failures.",
                        regrets,
                        unit="score",
                    ),
                ],
                "conditions": conditions,
                "comparison": comparison,
                "parameters": [
                    "Two earlier independent successes outweigh how the child seems in one game.",
                    "Rank by independent success, average gain, fewer failed rounds, then subject order.",
                ],
                "settings": [
                    setting(
                        "Successes before a help is trusted",
                        "2",
                        "Replayed past decisions with each value; counted changed first choices.",
                        tried=["1", "2", "3"],
                        replay="preference_thresholds",
                    ),
                    setting(
                        "Ranking order",
                        "Alone → gain → fewer rounds",
                        "Fixed rule, compared against the fixed-order group.",
                    ),
                ],
                "honesty": "The policy uses fixed rules without random exploration. Comparing the proposed and fixed orders is the main test.",
            },
            {
                "name": "Independence Gain",
                "subtitle": "After the help is taken away, can the child do it alone?",
                "metrics": [
                    metric(
                        "fair",
                        "Fair-test rate",
                        "Every measured game passes all fairness checks.",
                        "Count valid games among valid and invalid help sessions.",
                        [
                            int(s.get("validity") == "valid")
                            for s in helped
                            if s.get("validity") in {"valid", "invalid"}
                            or s.get("status") == "invalidated"
                        ],
                        tile=True,
                    ),
                    metric(
                        "repeat",
                        "Repeat consistency",
                        "Similar games on the same skill give consistent results.",
                        "Compare consecutive valid games on each skill.",
                        repeat,
                        tile=True,
                    ),
                ],
                "leakage": {"count": leakage, "checked": len(measured)},
                "matching": matching,
                # Codes without a plain name share one sentence, so rows are merged by sentence.
                "exclusions": [
                    {"reason": reason, "count": n}
                    for reason, n in _plain_exclusions(exclusions).most_common()
                ],
                "parameters": [
                    "One question before and one after gives limited evidence.",
                    "Question difficulty is compared once both question groups have answers without help.",
                ],
                "settings": [
                    setting(
                        "Questions before / after help",
                        "1 + 1",
                        "Both answered without help, on the same skill.",
                    ),
                    setting(
                        "Fairness checks",
                        "All must pass",
                        "Same skill, scoring and question type; a failing game is left out.",
                    ),
                    setting(
                        "Allowed difficulty gap",
                        "15 points",
                        "Before and after questions are flagged if their success rates differ more.",
                    ),
                ],
            },
        ],
    }


def present_simulation(simulation: dict | None) -> dict | None:
    """Mark the one headline metric and its reference tick on each simulated model."""

    if not isinstance(simulation, dict):
        return simulation
    models = []
    for model in simulation.get("models") or []:
        if not isinstance(model, dict):
            models.append(model)
            continue
        updated = dict(model)
        name = str(model.get("name"))
        metrics = list(model.get("metrics") or [])
        if name == "Probabilistic Misconception":
            updated["headline"] = "Found the true kind of mistake"
            updated["reference"] = {"value": 0.2, "label": "guessing"}
        elif name == "Contextual Support Selection":
            updated["headline"] = "First help was the one that really works (proposed)"
            comparison = next(
                (
                    row
                    for row in metrics
                    if "comparison group" in str(row.get("title", ""))
                    and str(row.get("title", "")).startswith("First help")
                ),
                None,
            )
            updated["reference"] = {
                "value": None if comparison is None else comparison.get("value"),
                "label": "fixed order",
            }
        elif name == "Independence Gain":
            updated["headline"] = "Measured gain agrees with real learning"
            updated["reference"] = {"value": None, "label": None}
        models.append(updated)
    return {**simulation, "models": models}
