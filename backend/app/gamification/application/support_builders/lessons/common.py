"""What a mathematics lesson says about one item, and the small helpers every area shares.

A lesson is written from the item's own numbers: the steps a teacher would say at the board, the
answer in words, a few obvious hints that stop short of the answer, and the same problem seen
another way. A diagnosis compares the child's failed answer with the right one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

Game = Mapping[str, object]
Solution = Mapping[str, object]


@dataclass(frozen=True)
class Lesson:
    # The full worked solution, one short sentence per step, with the item's numbers.
    steps: tuple[str, ...]
    # The answer, said the way the board shows it.
    answer: str
    # Obvious hints for the child's own attempt: the first moves, never the final answer.
    hints: tuple[str, ...] = ()
    # The same problem from another angle: expanded, drawn, or as repeated addition.
    another_view: tuple[str, ...] = ()


@dataclass(frozen=True)
class Diagnosis:
    # What the child gave, in words.
    you_did: str
    # Which step went wrong, and what that step should have been.
    went_wrong: str
    # A skill of this area that repairs that step, when the area has one.
    prerequisite_skill_id: str | None = None


LessonFn = Callable[[Game, Solution], Lesson | None]
DiagnoseFn = Callable[[Game, Solution, Mapping[str, object]], Diagnosis | None]

# Place names from the ones place leftwards, as the games label their columns.
PLACES = ("එකක", "දහය", "සියය", "දහස", "දසදහස", "ලක්ෂ")


def num(value: int) -> str:
    """A whole number with a space between thousands: 1 000, 34 527."""

    text = str(value)
    if len(text.lstrip("-")) < 4:
        return text
    return f"{value:,}".replace(",", " ")


def digits_of(value: int, width: int | None = None) -> list[int]:
    text = str(value).rjust(width or 0, "0")
    return [int(digit) for digit in text]


def column_addition(addends: Sequence[int]) -> tuple[list[str], int]:
    """Column-by-column working for an addition, from the ones place, with every carry."""

    width = len(str(sum(addends)))
    lines: list[str] = []
    carry = 0
    carries = 0
    for place in range(width):
        column = [(value // 10**place) % 10 for value in addends if value >= 10**place or place == 0]
        total = sum(column) + carry
        if not column and not carry:
            break
        parts = " + ".join(str(digit) for digit in column) or "0"
        name = PLACES[place] if place < len(PLACES) else f"{10**place}"
        carried = f" + ගෙන ආ {carry}" if carry else ""
        # What the column's total is worth: 12 tens are 12 × 10 = 120.
        worth = f" ({total} {name} = {total} × {num(10**place)} = {num(total * 10**place)})" if place else ""
        if total >= 10 and place < width - 1:
            lines.append(
                f"{name} තීරුව: {parts}{carried} = {total}{worth} → {total % 10} ලියා {total // 10} ක් "
                f"{PLACES[place + 1] if place + 1 < len(PLACES) else 'ඊළඟ'} තීරුවට ගෙන යන්න."
            )
            carries += 1
        else:
            lines.append(f"{name} තීරුව: {parts}{carried} = {total}{worth} → {total} ලියන්න.")
        carry = total // 10
    return lines, carries


def column_subtraction(minuend: int, subtrahend: int) -> list[str]:
    """Column-by-column working for a subtraction, from the ones place, with every exchange."""

    width = len(str(minuend))
    top = digits_of(minuend, width)[::-1]
    bottom = digits_of(subtrahend, width)[::-1]
    lines: list[str] = []
    for place in range(width):
        name = PLACES[place] if place < len(PLACES) else f"{10**place}"
        if top[place] < bottom[place]:
            lender = place + 1
            # Borrow through zeros: each zero becomes 9 on the way.
            while lender < width and top[lender] == 0:
                lender += 1
            top[lender] -= 1
            for middle in range(place + 1, lender):
                top[middle] = 9
            lines.append(
                f"{name} තීරුවේ {top[place]} න් {bottom[place]} අඩු කළ නොහැක. "
                f"{PLACES[lender]} තීරුවෙන් 1 ක් ණයට ගන්න (1 {PLACES[place + 1]} = {name} 10);"
                f" {name} තීරුව {top[place]} + 10 = {top[place] + 10} වේ."
            )
            top[place] += 10
        diff = top[place] - bottom[place]
        worth = f" ({diff} × {num(10**place)} = {num(diff * 10**place)})" if place else ""
        lines.append(f"{name} තීරුව: {top[place]} − {bottom[place]} = {diff}{worth}.")
    return lines


def expanded(value: int) -> str:
    """``3 472 = 3000 + 400 + 70 + 2``, leaving out the zero places."""

    text = str(value)
    terms = [
        str(int(digit) * 10 ** (len(text) - index - 1))
        for index, digit in enumerate(text)
        if digit != "0"
    ]
    return f"{num(value)} = " + (" + ".join(terms) if terms else "0")


def cents_text(cents: int) -> str:
    return f"රු. {cents // 100}.{cents % 100:02d}"


def first_mismatch(given: Sequence[object], wanted: Sequence[object]) -> int | None:
    for index, (left, right) in enumerate(zip(given, wanted, strict=False)):
        if left != right:
            return index
    if len(given) != len(wanted):
        return min(len(given), len(wanted))
    return None


def as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def int_list(value: object) -> list[int]:
    if not isinstance(value, list | tuple):
        return []
    return [number for number in (as_int(item) for item in value) if number is not None]
