"""Model 2 help order for one multi-help episode.

Model 2 chooses the first help type and the order of the rest. The goal is the fresh unsupported
item after every trace of help is gone, so each subject's order is chosen for later independent
success, not for success while help is on screen.

1. The first type answers Model 1's reason for the difficulty (``LEAD_BY_REASON``). Model 1's
   labels are grouped into five kinds of difficulty, read differently for each subject.
2. The rest follow the subject's ``fallback_order``.

   Mathematics (``MATHEMATICS_ORDER``) starts with the lightest cue on the child's own task and
   only then changes the task, because help that leaves the child generating the answer transfers
   best to an item with no help at all:

   - ``visual_guidance``: the child still does all the reasoning; only the structure is shown.
   - ``step_by_step_guidance``: short questions narrow the reasoning; the child still answers.
   - ``conceptual_reexplanation``: the idea is said again from another angle, for a child whose
     cues did not land because the idea itself is not yet in place.
   - ``simpler_same_game``: the same skill with easier quantities, so the child can succeed on
     the same structure and then return to the failed difficulty.
   - ``prerequisite_repair``: leaves the skill for an earlier one. It costs the most time and its
     transfer is indirect, so it comes after every same-skill route.
   - ``worked_parallel_example``: a full solution of a different problem. It is the most
     answer-adjacent and the most passive, so it is the last resort before withdrawal.

   English (``ENGLISH_ORDER``) moves the simpler version up to second. The English games ask the
   child to retrieve a word's meaning and link it among several look-alike choices. When the
   picture cue has not worked, the load of the choices is usually what is in the way, and a
   successful link with fewer choices is the same retrieval the fresh item will ask for, after
   which the child returns to the full set. Guided questions and a re-explanation of the meaning
   follow. Prerequisite repair (back to the area's word-recognition skill) and the worked example
   (a different set linked in full) stay last for the same reasons as in Mathematics.

3. In the proposed condition, the type with the best record of valid post-withdrawal outcomes for
   this learner and skill moves to the front. Supported correctness is never that record.
4. The baseline condition keeps the fallback order unchanged: no reason, no history.

Types the area does not list, or that this episode cannot render, are skipped. Nothing outside the
shared support-type contract is ever returned.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from app.gamification.content.support_types import SUPPORT_TYPES, SupportType

ORDER_POLICY_VERSION = "support-order-v3"

MATHEMATICS_ORDER: tuple[SupportType, ...] = (
    "visual_guidance",
    "step_by_step_guidance",
    "conceptual_reexplanation",
    "simpler_same_game",
    "prerequisite_repair",
    "worked_parallel_example",
)
ENGLISH_ORDER: tuple[SupportType, ...] = (
    "visual_guidance",
    "simpler_same_game",
    "step_by_step_guidance",
    "conceptual_reexplanation",
    "prerequisite_repair",
    "worked_parallel_example",
)
assert set(MATHEMATICS_ORDER) == set(ENGLISH_ORDER) == set(SUPPORT_TYPES)

# Model 1's reason, grouped into the kind of difficulty it names.
LEAD_BY_REASON: dict[str, SupportType] = {
    # The child misread the structure: a place, a column, a scale, a direction, a net.
    "representation": "visual_guidance",
    # The child knows what to do but lost a step: carrying, exchanging, bringing down.
    "procedure": "step_by_step_guidance",
    # The child holds a wrong idea: two units or two operations treated as one.
    "relation": "conceptual_reexplanation",
    # A fact or an earlier skill underneath this one is missing.
    "prerequisite": "prerequisite_repair",
    # Model 1 could not name the reason with confidence: lower the load first.
    "unclear": "simpler_same_game",
}

# First matching family wins. Every label of every multi-help area is checked by a test.
_MATHEMATICS_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unclear", ("unknown", "other", "invalid_interaction", "correct_result_invalid")),
    (
        "prerequisite",
        (
            "_fact",
            "fact_",
            "recall",
            "incorrect_arithmetic",
            "incorrect_subtraction",
            "denomination",
            "misidentified",
            "classification",
            "counted",
            "count_off",
            "emoji",
            "duplicate",
            "omitted_emoji",
            "sinhala_digit_word",
            "confused_i_v_x",
            "instrument",
        ),
    ),
    (
        "procedure",
        (
            "carry",
            "carried",
            "borrow",
            "exchange",
            "regroup",
            "remainder",
            "brought_down",
            "omitted",
            "omits",
            "incomplete",
            "running_total",
            "overshoot",
            "overflow",
            "padding",
            "skips",
            "missing",
            "extra_digit",
            "concatenat",
            "copies",
            "reapplies",
            "inconsistent",
            "once_then",
            "unequal",
            "distribution",
            "partial_sums",
            "third_addend",
            "reset",
            "starts_from_left",
            "terms_out_of_order",
            "combination",
            "noncanonical",
            "wrong_symbol_order",
            "wrong_match",
            "matching",
            "incorrect_portion",
            "incorrect_quotient",
            "incorrect_kilometre",
            "grouping",
            "first_visible",
            "mechanical",
            "without_adding",
            "without_decreasing",
        ),
    ),
    (
        "relation",
        (
            "confus",
            "treated_as",
            "reverses",
            "counts_groups",
            "added_to",
            "price_quantity",
            "numerator",
            "_as_",
            "relationship",
            "conversion",
            "unit_",
            "operation",
            "uses_addition",
            "swapped",
            "whole",
            "base_100",
            "thousand",
            "hundred",
            "factor",
            "multiplier",
            "difference",
            "wrong_direction",
            "reversed",
            "subtracts",
            "assumed",
            "interpretation",
            "fraction",
            "ten_parts",
            "decimal_point",
            "selected_incorrectly",
            "has_vertices",
            "properties",
            "complement",
            "denominator",
        ),
    ),
    (
        "representation",
        (
            "place",
            "column",
            "align",
            "scale",
            "reading",
            "read",
            "hand",
            "minute_marks",
            "position",
            "reversal",
            "net",
            "shaded",
            "level",
            "plumb",
            "viewpoint",
            "screen",
            "axis",
            "compass",
            "direction",
            "label",
            "ordering",
            "order",
            "digit",
            "cells",
            "row",
            "parts",
            "midday",
            "tilted",
            "heavier",
            "flat_face",
            "zero",
            "section",
            "invalid_roman",
        ),
    ),
)
# Labels the patterns above would group wrongly.
_MATHEMATICS_OVERRIDES: dict[str, str] = {
    "exchanged_ten_counted_as_one": "relation",
    "counted_labels_not_intervals": "representation",
    "counts_places_from_wrong_direction": "representation",
    "first_visible_digit_only": "representation",
    "reversed_factors": "relation",
    "incorrect_conversion_factor": "relation",
    "incomplete_or_duplicate_matching": "procedure",
}


# English labels name a confusion between two words, a word and a picture, a word and a heading,
# or a step of an ordering game.
_ENGLISH_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unclear", ("unknown_or_other", "multiple_valid_response")),
    (
        # The word itself, its Sinhala meaning or its written form is not yet known: the area's
        # word-recognition skill comes first.
        "prerequisite",
        (
            "english_sinhala",
            "sinhala_",
            "plural",
            "singular",
            "_form_",
            "form_confusion",
            "ending",
            "spelling",
            "source_",
            "article_",
            "contraction",
            "apostrophe",
            "hyphen",
            "spacing",
            "capitalization",
            "punctuation",
        ),
    ),
    (
        # A step of an ordering or moving game was lost.
        "procedure",
        (
            "order",
            "omission",
            "incomplete",
            "stops_before",
            "origin_not_retained",
            "destination_ignored",
            "speaker_role",
        ),
    ),
    (
        # The word is known but placed under the wrong heading, function or meaning.
        "relation",
        (
            "heading",
            "category",
            "exemplar",
            "_link_",
            "function",
            "response",
            "polarity",
            "frame",
            "possession",
            "negation",
            "pronoun",
            "semantic",
            "sense",
            "context",
            "command",
            "treated_as",
            "concept",
            "exclusivity",
            "one_to_one",
            "overgeneralization",
            "selection",
            "plant_type",
            "shared_buildings",
        ),
    ),
    (
        # The picture, scene or look-alike word was misread: the remaining word-pair confusions.
        "representation",
        (
            "visual",
            "scene",
            "not_noticed",
            "detail",
            "ambiguity",
            "overreliance",
            "_vs_",
            "confusion",
        ),
    ),
)

_SUBJECT_PATTERNS = {"MAT": _MATHEMATICS_PATTERNS, "ENG": _ENGLISH_PATTERNS}
_SUBJECT_OVERRIDES: dict[str, dict[str, str]] = {"MAT": _MATHEMATICS_OVERRIDES, "ENG": {}}
SUBJECT_ORDERS: dict[str, tuple[SupportType, ...]] = {
    "MAT": MATHEMATICS_ORDER,
    "ENG": ENGLISH_ORDER,
}


def subject_of(area_id: str) -> str:
    """The subject code in a Grade 5 area id, such as ``MAT`` in ``G5-AREA-MAT-01``."""

    return area_id.split("-")[2]


def reason_family(label: str | None, *, subject: str = "MAT") -> str:
    """Group one Model 1 label into the kind of difficulty it names, for one subject."""

    return reason_family_match(label, subject=subject)[0]


def reason_family_match(label: str | None, *, subject: str = "MAT") -> tuple[str, str]:
    """The family of one Model 1 label and what decided it: ``override``, the matched pattern,
    or ``no_match``/``empty`` when the label falls back to ``unclear``."""

    text = (label or "").strip().lower()
    if not text:
        return "unclear", "empty"
    overrides = _SUBJECT_OVERRIDES[subject]
    if text in overrides:
        return overrides[text], "override"
    for family, patterns in _SUBJECT_PATTERNS[subject]:
        for pattern in patterns:
            if pattern in text:
                return family, pattern
    return "unclear", "no_match"


@dataclass(frozen=True)
class SupportHistoryRanking:
    preferred: SupportType | None
    by_support: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def as_record(self) -> dict[str, object]:
        return {
            "basis": "valid_unsupported_after_outcomes",
            "supported_correctness_used": False,
            "preferred_support": self.preferred,
            "by_support": {key: dict(value) for key, value in self.by_support.items()},
        }


def credited_support(state: Mapping[str, object]) -> tuple[str | None, tuple[str, ...]]:
    """The successful round earns credit; failed rounds never inherit its result."""
    loop = state.get("support_loop")
    if isinstance(loop, Mapping) and "rounds" in loop:
        rounds = loop.get("rounds") or []
        failed = tuple(
            dict.fromkeys(
                row.get("scaffold_type")
                for row in rounds
                if row.get("outcome") == "failed" and row.get("scaffold_type") in SUPPORT_TYPES
            )
        )
        winner = next(
            (
                row.get("scaffold_type")
                for row in rounds
                if row.get("outcome") in {"succeeded", "supported_success"}
            ),
            None,
        )
        if loop.get("stop_reason") == "order_exhausted":
            winner = None
        return (winner if winner in SUPPORT_TYPES else None), failed
    used = _types_used(state)
    return (used[0] if len(used) == 1 else None), ()


def learning_state_key(state: Mapping[str, object]) -> str:
    model2 = state.get("model2") or {}
    reading = model2.get("learning_state_input") or {}
    return str(reading.get("state", "not_available"))


def rank_support_history(
    history: Iterable[Mapping[str, object]],
    *,
    order: tuple[SupportType, ...] = MATHEMATICS_ORDER,
    learning_state: str | None = None,
    legacy: bool = False,
) -> SupportHistoryRanking:
    """Use valid proposed outcomes and give only the successful round their independent result."""
    stats = {}
    for state in history:
        if state.get("condition") != "proposed" or state.get("validity") != "valid":
            continue
        if learning_state is not None and learning_state_key(state) != learning_state:
            continue
        measurement = state.get("measurement")
        if not isinstance(measurement, Mapping):
            continue
        gain = measurement.get("raw_independence_gain", state.get("raw_independence_gain"))
        maximum = Decimal(str(measurement.get("after_maximum", 0)))
        if gain is None or maximum <= 0:
            continue
        winner, failed = credited_support(state)
        credited = _types_used(state) if legacy else ((winner,) if winner else ())
        for support in dict.fromkeys((*credited, *failed)):
            if support not in order:
                continue
            row = stats.setdefault(
                support,
                {
                    "episodes": 0,
                    "independent_successes": 0,
                    "total_ig": Decimal(0),
                    "did_not_help": 0,
                },
            )
            row["did_not_help"] += int(support in failed)
            if support not in credited:
                continue
            row["episodes"] += 1
            row["independent_successes"] += int(
                Decimal(str(measurement.get("after_earned", 0))) == maximum
            )
            row["total_ig"] += Decimal(str(gain))

    def score(support):
        row = stats[support]
        n = row["episodes"]
        return (
            Decimal(row["independent_successes"]) / n,
            row["total_ig"] / n,
            n if legacy else -row["did_not_help"],
            -order.index(support),
        )

    successful = [support for support, row in stats.items() if row["independent_successes"]]
    return SupportHistoryRanking(
        preferred=max(successful, key=score) if successful else None,
        by_support={
            support: {
                "episodes": row["episodes"],
                "independent_successes": row["independent_successes"],
                "did_not_help": row["did_not_help"],
                "mean_independence_gain": str(row["total_ig"] / row["episodes"])
                if row["episodes"]
                else "0",
            }
            for support, row in stats.items()
        },
    )


def _types_used(state: Mapping[str, object]) -> tuple[SupportType, ...]:
    loop = state.get("support_loop")
    if isinstance(loop, Mapping) and isinstance(loop.get("types_used"), list):
        used = loop["types_used"]
    else:
        # Episodes from before the multi-help loop delivered one type.
        model2 = state.get("model2")
        used = [model2.get("selected_action")] if isinstance(model2, Mapping) else []
    return tuple(value for value in used if value in SUPPORT_TYPES)


@dataclass(frozen=True)
class SupportOrderDecision:
    order: tuple[SupportType, ...]
    reason_family: str | None
    selection_mode: str
    history: SupportHistoryRanking
    learning_state_input: Mapping[str, object] = field(
        default_factory=lambda: {"status": "not_available", "reason": "NOT_FOUND"}
    )
    state_history: Mapping[str, object] = field(default_factory=dict)

    @property
    def first(self) -> SupportType:
        return self.order[0]

    def as_record(self) -> dict[str, object]:
        return {
            "order_policy_version": ORDER_POLICY_VERSION,
            "learning_state_input": dict(self.learning_state_input),
            "history_by_learning_state": dict(self.state_history),
            "support_order": list(self.order),
            "selected_action": self.first,
            "reason_family": self.reason_family,
            "support_selection_mode": self.selection_mode,
            "learner_activity_support_preference": self.history.as_record(),
        }


def choose_support_order(
    *,
    subject: str,
    condition: str,
    model1_label: str | None,
    model1_uncertain: bool,
    eligible: Collection[str],
    renderable: Collection[str],
    history: Iterable[Mapping[str, object]] = (),
    learning_state_input: Mapping[str, object] | None = None,
    preference_threshold: int = 2,
    policy_version: str = ORDER_POLICY_VERSION,
) -> SupportOrderDecision:
    """Choose this episode's help order. Raises ``ValueError`` when no type can be delivered."""

    fallback = SUBJECT_ORDERS[subject]
    available = [support for support in fallback if support in eligible and support in renderable]
    if not available:
        raise ValueError("NO_RENDERABLE_SUPPORT")
    if condition != "proposed":
        return SupportOrderDecision(
            order=tuple(available),
            reason_family=None,
            selection_mode="baseline_fixed_order",
            history=SupportHistoryRanking(preferred=None),
        )
    history = tuple(history)
    legacy = policy_version == "support-order-v2"
    family = "unclear" if model1_uncertain else reason_family(model1_label, subject=subject)
    reading = dict(learning_state_input or {"status": "not_available", "reason": "NOT_FOUND"})
    ranking = rank_support_history(history, order=fallback, legacy=legacy)
    state_ranking = rank_support_history(
        history, order=fallback, learning_state=str(reading.get("state"))
    )
    if (
        state_ranking.preferred
        and int(state_ranking.by_support[state_ranking.preferred]["independent_successes"])
        >= preference_threshold
    ):
        ranking = state_ranking
    lead = LEAD_BY_REASON[family]
    mode = "model1_reason_lead"
    if lead not in available:
        lead, mode = available[0], "model1_reason_lead_unrenderable_fallback"
    chosen = [lead, *(support for support in available if support != lead)]
    state_changed = False
    if not legacy and reading.get("status") == "available":
        state = reading.get("state")
        if state == "disengaged" or (state == "confused" and model1_uncertain):
            first = "simpler_same_game" if "simpler_same_game" in available else available[0]
            chosen = [first, *(support for support in chosen if support != first)]
            mode, state_changed = "learning_state_lead", True
        elif state == "confused" and "worked_parallel_example" in chosen:
            position = chosen.index("worked_parallel_example")
            chosen.remove("worked_parallel_example")
            chosen.insert(max(1, position - 2), "worked_parallel_example")
            state_changed = True
    preferred = ranking.preferred
    successes = int(ranking.by_support.get(preferred, {}).get("independent_successes", 0))
    if preferred in available and (
        not state_changed or successes >= preference_threshold or legacy
    ):
        chosen = [preferred, *(support for support in chosen if support != preferred)]
        mode = "learned_post_withdrawal_preference"
    reading["changed_first_help"] = chosen[0] != lead and mode == "learning_state_lead"
    reading["changed_order"] = state_changed and mode != "learned_post_withdrawal_preference"
    return SupportOrderDecision(
        order=tuple(chosen),
        reason_family=family,
        selection_mode=mode,
        history=ranking,
        learning_state_input=reading,
        state_history=state_ranking.as_record(),
    )
