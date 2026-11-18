"""Descriptive model checks from the child's own stored games. Simulated learners are reported separately."""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from math import sqrt

from app.gamification.application.research_dashboard.explain import area_title
from app.gamification.application.research_dashboard.glossary import EXCLUSIONS
from app.gamification.modeling.support_selection.game_bandit import (
    PROVISIONAL_FAILED_ROUND_WEIGHT,
    PROVISIONAL_UNINFORMED_PRECISION,
    load_help_order_expert_data,
    loop_credit,
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


def model_check(question, rule, values, *, reference, reference_label, reference_count=None):
    """The one deterministic accuracy test for a learned model.

    The model passes when, with at least ``MIN_SESSIONS`` games behind both numbers, the lower end
    of its 95% Wilson range is above the reference rate. Fewer games is "not enough data", never
    a pass or a fail.
    """

    n = len(values)
    interval = wilson(sum(values), n)
    enough = n >= MIN_SESSIONS and (reference_count is None or reference_count >= MIN_SESSIONS)
    if not enough or reference is None or interval is None:
        status = "not_enough_data"
    else:
        status = "passing" if interval[0] > reference else "not_passing"
    return {
        "question": question,
        "rule": rule,
        "value": sum(values) / n if n else None,
        "interval": interval,
        "count": n,
        "minimum": MIN_SESSIONS,
        "reference": reference,
        "reference_label": reference_label,
        "reference_count": reference_count,
        "status": status,
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


def _help_order_values() -> dict[str, float]:
    """The help-order bandit's provisional settings, as the expert data and the code set them."""

    try:
        gains, _families, _hashes = load_help_order_expert_data()
    except (OSError, ValueError):
        gains = {}
    return {
        "prior_strength": float(gains.get("prior_strength", 8)),  # type: ignore[arg-type]
        "own_success_rate_gain": float(gains.get("own_success_rate_gain", 0.3)),  # type: ignore[arg-type]
        "failed_round_weight": PROVISIONAL_FAILED_ROUND_WEIGHT,
        "uninformed_precision": PROVISIONAL_UNINFORMED_PRECISION,
    }


def _number(value: float) -> str:
    return f"{value:g}"


def accuracy_report(runs, *, all_runs=None, help_order=None):
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
    agreement, brier, bins, chance = [], [], defaultdict(list), []
    for model, observed in pairs:
        probabilities = model["probabilities"]
        chance.append(1 / max(1, len(probabilities)))
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
    learned, errors, bias = [], [], []
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
        mode = decision.get("support_selection_mode")
        if mode in {"learned_post_withdrawal_preference", "bandit_greedy"}:
            learned.append(success)
        winner, failed = loop_credit(s)
        # The help-order bandit's prediction for the help the fair test credits, against the gain.
        predicted = dict(decision.get("predicted_gain") or {}).get(winner)
        gain = (s.get("measurement") or {}).get("raw_independence_gain")
        if mode == "bandit_greedy" and predicted is not None and gain is not None:
            errors.append(abs(float(gain) - float(predicted)))
            bias.append(float(gain) - float(predicted))
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
    values = _help_order_values()
    proposed = [int(is_independent(s)) for s in valid if s.get("condition") == "proposed"]
    baseline = [int(is_independent(s)) for s in valid if s.get("condition") == "baseline"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "minimum_sessions": MIN_SESSIONS,
        "purpose": "How we check that each part is doing its job, and how well it is doing so far.",
        "models": [
            {
                "name": "Probabilistic Misconception",
                "subtitle": "Why did the child get it wrong?",
                "kind": "model",
                "check": model_check(
                    "Does the predicted reason match the child's next mistake?",
                    "Working when, over at least 20 games, the predicted reason matches the "
                    "child's next unaided mistake more often than guessing: the low end of the "
                    "95% range must be above the guessing rate.",
                    agreement,
                    reference=sum(chance) / len(chance) if chance else None,
                    reference_label="guessing",
                ),
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
                ],
                "calibration": calibration,
                "parameters": [
                    (
                        "Each reason's chance is the expert likelihood of the answer's mistake, times "
                        "one plus how often that mistake appeared in the last five unaided answers."
                    ),
                    (
                        "A reading is unsure when the top reason is below 40%, the top two are within "
                        "10 points, the answer carried too little evidence, or, in eight games, the "
                        "answer's own evidence points to no listed reason."
                    ),
                    (
                        "Only the mistake in the answer carries weight; the other factors are recorded "
                        "but switched off."
                    ),
                    (
                        "The tables are provisional expert assumptions taken from the earlier rules, "
                        "not yet reviewed by a teacher."
                    ),
                ],
                "settings": [
                    setting(
                        "Top reason must reach",
                        "40%",
                        "Replayed stored answers with each value; compared agreement, calibration "
                        "and how many readings change.",
                        tried=["30%", "40%", "50%"],
                        replay="top_probability_below",
                    ),
                    setting(
                        "Top two must differ by",
                        "10 points",
                        "Replayed stored answers with each value.",
                        tried=["5", "10", "20"],
                        replay="top_two_margin_below",
                    ),
                    setting(
                        "Answers remembered",
                        "5",
                        "Replayed stored answers with each window, from the same earlier answers.",
                        tried=["3", "5", "8"],
                        replay="prior_window",
                    ),
                    setting(
                        "Factor weights",
                        "Mistake 1, others 0",
                        "Fixed: the other factors are recorded for later study.",
                    ),
                    setting(
                        "Expert tables",
                        "expert-model-data-v1",
                        "Provisional expert assumptions, not yet reviewed by a teacher.",
                    ),
                ],
            },
            {
                "name": "Contextual Support Selection",
                "subtitle": "Which help should come first, and in what order?",
                "kind": "model",
                "check": model_check(
                    "Does the chosen help leave the child able to do it alone?",
                    "Working when, over at least 20 games in each group, children helped in the "
                    "model's order solve the fresh question alone more often than children given "
                    "the fixed order: the low end of the 95% range must be above the fixed-order "
                    "rate.",
                    proposed,
                    reference=sum(baseline) / len(baseline) if baseline else None,
                    reference_label="fixed order",
                    reference_count=len(baseline),
                ),
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
                        "The child can do it alone after a help chosen from earlier results.",
                        "Count independent successes after orders chosen from earlier results: "
                        "the help-order model's, or an earlier rule's learned preference.",
                        learned,
                        tile=True,
                    ),
                    metric(
                        "prediction-error",
                        "Prediction error",
                        "Smaller is better.",
                        "For the help the fair test credits, the measured gain minus the gain the "
                        "help-order model predicted, without its sign.",
                        errors,
                        unit="score",
                    ),
                    metric(
                        "prediction-bias",
                        "Prediction bias",
                        "Near 0 is best; below 0 means the model expected more than it saw.",
                        "The same difference with its sign: measured minus predicted gain.",
                        bias,
                        unit="gain",
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
                    (
                        "A LinUCB model run greedily: it always puts the help with the highest "
                        "predicted gain first and never tries a help just to learn."
                    ),
                    (
                        "It starts from provisional expert gains and learns from every valid fair "
                        "test in the study: the help that ended the help at full weight, helps that "
                        "failed while shown at half weight."
                    ),
                    (
                        "A child's own independent successes with a help raise its predicted gain "
                        "for that child."
                    ),
                ],
                "settings": [
                    setting(
                        "Expert start worth",
                        f"{_number(values['prior_strength'])} games",
                        "Replayed the stored decisions with each value; counted changed first helps.",
                        tried=["4", "8", "16"],
                        replay="prior_strength",
                    ),
                    setting(
                        "Own success weight",
                        _number(values["own_success_rate_gain"]),
                        "Replayed the stored decisions with each value.",
                        tried=["0", "0.15", "0.3"],
                        replay="own_success_rate_gain",
                    ),
                    setting(
                        "Failed round weight",
                        _number(values["failed_round_weight"]),
                        "Replayed the stored ledger with each weight.",
                        tried=["0", "0.25", "0.5", "1"],
                        replay="failed_round_weight",
                    ),
                    setting(
                        "Unknown features start fixed",
                        _number(values["uninformed_precision"]),
                        "How slowly features the expert data says nothing about may move; "
                        "replayed with each value.",
                        tried=["10", "100", "1000"],
                        replay="uninformed_precision",
                    ),
                ],
                "evidence": list((help_order or {}).get("subjects") or []),
                "honesty": "The model never explores: every recorded choice was its best guess. "
                "Comparing the proposed and fixed orders is the main test.",
            },
            {
                "name": "Independence Gain",
                "subtitle": "After the help is taken away, can the child do it alone?",
                # A before/after score difference, not a learned model: it has no accuracy test.
                "kind": "measurement",
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
