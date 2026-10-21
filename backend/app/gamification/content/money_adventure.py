"""Grade 5 money activities using exact integer cents and stylised public tokens."""
from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-MAT-10"
UNIVERSAL_SKILL_ID = "MAT-MON"
PACKAGE_VERSION = "g5-mat-money-adventure-v1"
CATALOGUE_VERSION = "g5-mat-money-misconceptions-v1"
FEATURE_VERSION = "g5-mat-money-features-v1"
MAPPING_VERSION = "g5-mat-money-source-mapping-v1"
MODEL_VERSION = "g5-mat-money-authored-probabilistic-v1"
POLICY_VERSION = "g5-mat-money-deterministic-support-v1"
SCORING_VERSION = "g5-mat-money-trace-scoring-v1"
EQUIVALENCE_VERSION = "g5-mat-money-parallel-v1"
Chapter = Literal["money_recognition", "money_calculation", "little_shop"]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill("G5-MAT-MONEY-DENOMINATION-01", "money_recognition", "කාසි හා නෝට්ටු හඳුනා ගනිමු", "easy", "currency_recognition"),
    AtomicSkill("G5-MAT-MONEY-COMPOSE-01", "money_recognition", "මුදලක් සාදමු", "easy_medium", "amount_construction"),
    AtomicSkill("G5-MAT-MONEY-ADD-01", "money_calculation", "මුදල් එකතු කරමු", "medium", "money_arithmetic"),
    AtomicSkill("G5-MAT-MONEY-SUBTRACT-01", "money_calculation", "මුදල් අඩු කරමු", "medium_hard", "money_arithmetic"),
    AtomicSkill("G5-MAT-MONEY-SHOP-01", "little_shop", "වෙළඳසැලේ ගණනය", "hard", "shopping_calculation"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
DENOMINATIONS = (
    ("coin-1", "coin", 100), ("coin-2", "coin", 200),
    ("coin-5", "coin", 500), ("coin-10", "coin", 1000),
    ("note-20", "note", 2000), ("note-50", "note", 5000),
    ("note-100", "note", 10000), ("note-500", "note", 50000),
    ("note-1000", "note", 100000), ("note-5000", "note", 500000),
)
DENOMINATION_BY_ID = {row[0]: row for row in DENOMINATIONS}
PRODUCTS = (
    ("lime-1kg", "දෙහි 1 kg", 16500),
    ("papaya-1kg", "පැපොල් 1 kg", 26000),
    ("sugar-1kg", "සීනි 1 kg", 24200),
)
MISCONCEPTIONS = (
    "denomination_misidentified", "coin_note_classification_error", "incorrect_value_ordering",
    "running_total_overshoot", "invalid_denomination_combination", "rupee_cent_columns_reversed",
    "misaligned_money_values", "hundred_cents_treated_as_ten", "failed_to_carry",
    "carried_without_removing_cents", "subtracted_without_borrowing", "borrowed_incorrect_cents",
    "rupee_column_not_reduced", "incorrect_price_quantity", "incorrect_shopping_operation",
    "incorrect_change_direction", "correct_result_invalid_working", "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class MoneyItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Literal["unsupported_before", "unsupported_after"]
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _integer(value: object, maximum: int = 10_000_000) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("MONEY_VALUE_OUT_OF_RANGE")
    return value


def split_money(total_in_cents: int) -> tuple[int, int]:
    _integer(total_in_cents)
    return divmod(total_in_cents, 100)


def normalize_money(rupees: int, cents: int) -> tuple[int, int]:
    _integer(rupees); _integer(cents)
    carry, remainder = divmod(cents, 100)
    return rupees + carry, remainder


def format_money(total_in_cents: int) -> str:
    rupees, cents = split_money(total_in_cents)
    return f"{rupees}.{cents:02d}"


def canonical_arithmetic(operation: str, left: int, right: int) -> dict[str, object]:
    _integer(left); _integer(right)
    left_r, left_c = split_money(left); right_r, right_c = split_money(right)
    if operation == "add":
        cent_work = left_c + right_c
        exchange = cent_work >= 100
        exchanged = cent_work // 100
        result_c = cent_work % 100
        result_r = left_r + right_r + exchanged
        steps = [
            f"cents:{left_c}+{right_c}={cent_work}",
            f"carry:{exchanged}",
            f"cents-result:{result_c}",
            f"rupees:{left_r}+{right_r}+{exchanged}={result_r}",
        ]
    elif operation == "subtract":
        if left < right:
            raise ValueError("NEGATIVE_MONEY")
        exchanged = 1 if left_c < right_c else 0
        exchange = exchanged == 1
        adjusted_r = left_r - exchanged
        adjusted_c = left_c + 100 * exchanged
        result_c = adjusted_c - right_c
        result_r = adjusted_r - right_r
        cent_work = adjusted_c
        steps = [
            f"borrow:{exchanged}",
            f"adjust:{left_r}->{adjusted_r}:{left_c}->{adjusted_c}",
            f"cents:{adjusted_c}-{right_c}={result_c}",
            f"rupees:{adjusted_r}-{right_r}={result_r}",
        ]
    else:
        raise ValueError("INVALID_MONEY_OPERATION")
    result = result_r * 100 + result_c
    return {
        "operation": operation,
        "left_amount_in_cents": left,
        "right_amount_in_cents": right,
        "cent_subtotal_or_adjustment": cent_work,
        "carried_or_borrowed_rupees": exchanged,
        "exchange_used": exchange,
        "working_steps": steps,
        "result_in_cents": result,
        "result_rupees": result_r,
        "result_cents": result_c,
    }


def denomination_total(selected: list[str]) -> int:
    try:
        return sum(DENOMINATION_BY_ID[value][2] for value in selected)
    except KeyError as error:
        raise ValueError("UNKNOWN_DENOMINATION") from error


def _construction(target: int) -> list[str]:
    remaining = target
    selected: list[str] = []
    for denomination_id, _, value in reversed(DENOMINATIONS):
        while value <= remaining:
            selected.append(denomination_id)
            remaining -= value
    if remaining:
        raise ValueError("IMPOSSIBLE_TARGET")
    return selected


def shopping_totals(product_ids: list[str], quantities: list[int]) -> tuple[list[int], int]:
    product_map = {row[0]: row[2] for row in PRODUCTS}
    if len(product_ids) != len(quantities) or not product_ids or len(set(product_ids)) != len(product_ids):
        raise ValueError("AMBIGUOUS_SHOPPING_PROBLEM")
    line_totals = []
    for product_id, quantity in zip(product_ids, quantities, strict=True):
        if product_id not in product_map or type(quantity) is not int or not 1 <= quantity <= 10:
            raise ValueError("INVALID_SHOPPING_QUANTITY")
        line_totals.append(product_map[product_id] * quantity)
    return line_totals, sum(line_totals)


def _rng(skill_id: str, role: str, seed: int) -> random.Random:
    digest = hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


SIMPLER_DENOMINATION_COUNT = 4


def generate_simpler_item(
    skill_id: str, *, seed: int, than: Mapping[str, object] | None = None
) -> MoneyItem:
    """The same money skill with fewer coins and notes, smaller amounts, or no carrying."""
    # The easiest settings of the skill, so the failed game is not needed to make it easier.
    del than

    return generate_item(skill_id, role="unsupported_before", seed=seed, simpler=True)


def generate_item(skill_id: str, *, role: str, seed: int, simpler: bool = False) -> MoneyItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("MONEY_ITEM_REQUEST_INVALID")
    skill, rng = SKILLS[skill_id], _rng(skill_id, role, seed)
    if skill.response_kind == "currency_recognition":
        rows = DENOMINATIONS
        if simpler:
            rows = tuple(sorted(rng.sample(DENOMINATIONS, SIMPLER_DENOMINATION_COUNT), key=lambda row: row[2]))
        tokens = [{"denomination_id": row[0], "currency_type": row[1], "value_in_cents": row[2]} for row in rows]
        rng.shuffle(tokens)
        prompt = "කාසි සහ නෝට්ටු නිවැරදි තැන්වල තබා කුඩා අගයෙන් විශාල අගයට පෙළගස්වන්න."
        game: dict[str, object] = {"tokens": tokens}
    elif skill.response_kind == "amount_construction":
        target = rng.choice((1500, 2500, 3000) if simpler else (7600, 8700, 12500, 18500))
        prompt = f"රුපියල් {format_money(target)} මුදල පසුම්බියට සාදන්න."
        game = {"target_in_cents": target, "denominations": [row[0] for row in DENOMINATIONS[:7]]}
    elif skill.response_kind == "money_arithmetic":
        operation = "add" if skill_id.endswith("ADD-01") else "subtract"
        pairs = ((16575, 24250), (32860, 17655)) if operation == "add" else ((50000, 16575), (73025, 24860))
        if simpler:
            # Whole rupees with no carrying or exchanging between places.
            pairs = ((12000, 24000), (31000, 15000)) if operation == "add" else ((50000, 20000), (75000, 32000))
        left, right = rng.choice(pairs)
        prompt = f"රුපියල් {format_money(left)} {('සහ' if operation == 'add' else 'න්')} රුපියල් {format_money(right)} {('එකතු කරන්න.' if operation == 'add' else 'අඩු කරන්න.')}"
        game = {"operation": operation, "left_amount_in_cents": left, "right_amount_in_cents": right}
    else:
        scenario = rng.choice(("total", "change"))
        selected = ["lime-1kg", "papaya-1kg"] if scenario == "total" else ["lime-1kg", "papaya-1kg", "sugar-1kg"]
        quantities = [2, 1] if scenario == "total" else [1, 1, 1]
        if simpler:
            # One of each of two products, and no change to work out.
            scenario, selected, quantities = "total", ["lime-1kg", "papaya-1kg"], [1, 1]
        line_totals, total = shopping_totals(selected, quantities)
        paid = total if scenario == "total" else 100000
        prompt = "මිල වගුව බලන්න. ඉල්ලූ ප්‍රමාණවල මුළු මිල සහ ඉතිරි මුදල සොයන්න."
        game = {
            "problem_id": f"shop-{scenario}",
            "products": [{"product_id": row[0], "name_si": row[1], "unit_price_in_cents": row[2]} for row in PRODUCTS],
            "selected_products": selected,
            "quantities": quantities,
            "amount_paid_in_cents": paid,
            "requires_change": paid > total,
            "line_count": len(line_totals),
        }
    game["response_kind"] = skill.response_kind
    revision = f"{skill_id}:{role}{':simpler' if simpler else ''}:{seed % 100000}@v1"
    return MoneyItem(f"{skill_id}:{role}", revision, f"{skill_id}:parallel-v1", skill_id, skill.chapter, role, prompt, (), "constructed-response", {}, game)


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    kind = str(game["response_kind"])
    if kind == "currency_recognition":
        # The item's own tokens, smallest value first (every denomination, or fewer in the simpler version).
        shown = {str(token["denomination_id"]) for token in game["tokens"]}  # type: ignore[union-attr]
        placements = [
            {"denomination_id": row[0], "currency_type": row[1], "value_in_cents": row[2], "ordered_position": index}
            for index, row in enumerate(row for row in DENOMINATIONS if row[0] in shown)
        ]
        return {"kind": kind, "denomination_id": "all", "currency_type": "mixed", "value_in_cents": 0, "ordered_position": 10, "placements": placements}
    if kind == "amount_construction":
        target = int(game["target_in_cents"]); selected = _construction(target)
        counts = {value: selected.count(value) for value in sorted(set(selected))}
        return {"kind": kind, "target_in_cents": target, "selected_denominations": selected, "denomination_counts": counts, "constructed_total_in_cents": target}
    if kind == "money_arithmetic":
        return {"kind": kind, **canonical_arithmetic(str(game["operation"]), int(game["left_amount_in_cents"]), int(game["right_amount_in_cents"]))}
    selected = [str(value) for value in game["selected_products"]]  # type: ignore[index]
    quantities = [int(value) for value in game["quantities"]]  # type: ignore[index]
    line_totals, total = shopping_totals(selected, quantities)
    prices = {row[0]: row[2] for row in PRODUCTS}
    paid = int(game["amount_paid_in_cents"]); change = paid - total
    steps = [f"line:{product_id}:{prices[product_id]}x{quantity}={line_total}" for product_id, quantity, line_total in zip(selected, quantities, line_totals, strict=True)]
    steps.extend((f"total:{'+'.join(map(str, line_totals))}={total}", f"change:{paid}-{total}={change}"))
    return {
        "kind": kind, "problem_id": str(game["problem_id"]), "selected_products": selected,
        "quantities": quantities, "unit_prices_in_cents": [prices[value] for value in selected],
        "line_totals_in_cents": line_totals, "working_steps": steps, "total_in_cents": total,
        "amount_paid_in_cents": paid, "change_in_cents": change,
        "contextual_answer": f"pay:{total}:change:{change}",
    }


def _strict(response: Mapping[str, object], expected: Mapping[str, object]) -> None:
    if set(response) != set(expected):
        raise ValueError("MALFORMED_MONEY_RESPONSE")


def validate_constructed_response(item: Mapping[str, object] | MoneyItem, response: Mapping[str, object]) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, MoneyItem) else item["game_data"]
    assert isinstance(game, Mapping)
    expected = correct_response(game); kind = str(game["response_kind"])
    if response.get("kind") != kind:
        raise ValueError("WRONG_RESPONSE_KIND")
    _strict(response, expected)
    normalized = dict(response)
    focus = "denominations"
    if kind == "currency_recognition":
        placements = response.get("placements")
        if not isinstance(placements, list): raise ValueError("INVALID_PLACEMENTS")
        types_ok = all(isinstance(row, Mapping) and DENOMINATION_BY_ID.get(str(row.get("denomination_id")), (None, None, None))[1] == row.get("currency_type") for row in placements)
        values_ok = all(isinstance(row, Mapping) and DENOMINATION_BY_ID.get(str(row.get("denomination_id")), (None, None, None))[2] == row.get("value_in_cents") for row in placements)
        if not types_ok: error = "coin_note_classification_error"
        elif not values_ok: error = "denomination_misidentified"
        else: error = "incorrect_value_ordering"
    elif kind == "amount_construction":
        selected = response.get("selected_denominations")
        if not isinstance(selected, list) or not all(isinstance(value, str) for value in selected): raise ValueError("INVALID_DENOMINATIONS")
        actual_total = denomination_total(selected)
        counts = {value: selected.count(value) for value in sorted(set(selected))}
        target = int(game["target_in_cents"])
        normalized = {**normalized, "denomination_counts": counts, "constructed_total_in_cents": actual_total}
        correct = response.get("target_in_cents") == target and response.get("constructed_total_in_cents") == actual_total == target and response.get("denomination_counts") == counts
        normalized["_feedback_column"] = "total"
        return correct, "correct" if correct else ("running_total_overshoot" if actual_total > target else "invalid_denomination_combination"), normalized
    elif kind == "money_arithmetic":
        for key in ("left_amount_in_cents", "right_amount_in_cents", "cent_subtotal_or_adjustment", "carried_or_borrowed_rupees", "result_in_cents", "result_rupees", "result_cents"):
            _integer(response[key])
        operation = str(game["operation"]); focus = "cents"
        if response.get("exchange_used") != expected["exchange_used"]: error = "failed_to_carry" if operation == "add" else "subtracted_without_borrowing"
        elif response.get("carried_or_borrowed_rupees") != expected["carried_or_borrowed_rupees"]: error = "hundred_cents_treated_as_ten" if operation == "add" else "borrowed_incorrect_cents"
        elif response.get("cent_subtotal_or_adjustment") != expected["cent_subtotal_or_adjustment"]: error = "carried_without_removing_cents" if operation == "add" else "borrowed_incorrect_cents"
        elif response.get("result_rupees") != expected["result_rupees"]: error = "rupee_column_not_reduced" if operation == "subtract" else "misaligned_money_values"; focus = "rupees"
        elif response.get("working_steps") != expected["working_steps"]: error = "correct_result_invalid_working"
        else: error = "misaligned_money_values"
    else:
        line_totals = response.get("line_totals_in_cents")
        if not isinstance(line_totals, list) or any(type(value) is not int for value in line_totals): raise ValueError("INVALID_LINE_TOTALS")
        focus = "shop"
        if response.get("selected_products") != expected["selected_products"] or response.get("quantities") != expected["quantities"]: error = "incorrect_shopping_operation"
        elif line_totals != expected["line_totals_in_cents"]: error = "incorrect_price_quantity"
        elif response.get("change_in_cents") != expected["change_in_cents"]: error = "incorrect_change_direction"
        elif response.get("working_steps") != expected["working_steps"]: error = "correct_result_invalid_working"
        else: error = "incorrect_shopping_operation"
    correct = normalized == expected
    normalized["_feedback_column"] = focus
    return correct, "correct" if correct else error, normalized


def infer_belief(error_code: str, *, sparse: bool = False, evidence_quality: float = .8) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(.72, max(.2, evidence_quality * .72))
    other = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else other for name in MISCONCEPTIONS}
    return {"probabilities": probabilities, "predicted_label": primary, "confidence": probabilities[primary], "fallback_used": sparse}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    del skill_id, seed
    return {"selected_action": "visual_guidance", "condition": condition, "propensity": 1.0, "policy_version": POLICY_VERSION, "eligible_actions": list(SCAFFOLDS), "belief_label": belief.get("predicted_label")}


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    kind = game["response_kind"]
    if scaffold_type == "visual_guidance":
        return {
            "currency_recognition": ["කාසි/නෝට්ටු තැටිය සහ සසඳන අගයන් දෙක බලන්න."],
            "amount_construction": ["ඉලක්කය සහ දැනට ඇති එකතුව සසඳන්න."],
            "money_arithmetic": ["පළමුව සත තීරුව බලන්න."],
            "shopping_calculation": ["ඉල්ලූ භාණ්ඩ පේළිය එහි ගණනය පේළියට සම්බන්ධ කරන්න."],
        }[str(kind)]
    if kind == "currency_recognition": return ["කාසි සහ නෝට්ටු තැටි දෙක හඳුනා ගනිමු.", "එක් එක් අගය සසඳමු.", "කුඩා අගයෙන් විශාල අගයට නැවත පෙළගස්වමු."]
    if kind == "amount_construction": return ["ඉල්ලූ මුදල බලමු.", "එක් මුදල් කොටසක් පසුම්බියට දමා එකතුව යාවත්කාලීන කරමු.", "ඉලක්කය ලැබෙන තුරු ඉදිරියට යමු."]
    if kind == "money_arithmetic": return ["රුපියල් සහ සත නිවැරදි තීරුවල තබමු.", "පළමුව සත තීරුව විසඳමු.", "සත 100 ⇄ රුපියල් 1 හුවමාරුව පෙන්වමු.", "රුපියල් තීරුව සහ අවසාන මුදල පුරවමු."]
    return ["ඉල්ලූ භාණ්ඩ පේළි තෝරමු.", "මිල × ප්‍රමාණය ලෙස එක් එක් පේළිය ගණනය කරමු.", "පේළි එකතු කර මුළු මිල සොයමු.", "ගෙවූ මුදලෙන් මුළු මිල අඩු කර ඉතිරිය සොයමු."]


def package_hash() -> str:
    return hashlib.sha256(json.dumps({"version": PACKAGE_VERSION, "skills": list(SKILLS), "misconceptions": MISCONCEPTIONS}, sort_keys=True).encode()).hexdigest()
