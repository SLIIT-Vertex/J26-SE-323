"""The real answer of a help item, in words the child sees on the game board.

Help stages show the answer: tinted while the child still plays, fully filled in a worked
example. The before and after items never carry this; only help stages do.

The solution payload names things by token (``w-8d…``) or by value (``45``). This module turns
it into readable lines and into ``marks``: the labels on the board that the phone tints.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.gamification.application.support_builders.context import SupportBuildContext

RevealMode = Literal["tint", "filled"]

# Payload fields that record how the child played, not what the answer is.
_IGNORED_KEYS = frozenset(
    {
        "kind",
        "command_token",
        "command_id",
        "interaction_trace",
        "interaction_version",
        "revisions",
        "invalid_drop_count",
        "tap_alternative_used",
        "sequence",
        "round_id",
        "adjustment_actions",
        "presentation_id",
        "item_revision_id",
        "combined",
    }
)
# Fields of a board entry that hold its visible label, best first.
_LABEL_HINTS = ("text_en", "word_en", "label_en", "name_en", "text", "label", "word", "name")
_SINHALA_HINTS = ("text_si", "word_si", "label_si", "name_si", "translation_si")
# A picture card has no words; its picture key ("plant-buds") still names it.
_PICTURE_HINTS = ("visual_key",)
# An opaque board token (``t-30fadd2609c2``) means nothing to a child and is never shown.
_OPAQUE = re.compile(r"^[a-z]+-[0-9a-f]{8,}$")


def answer_reveal(
    context: SupportBuildContext, record: Mapping[str, object], mode: RevealMode
) -> dict[str, object] | None:
    """The answer of one help item, or ``None`` when its game has no solution to show."""

    solution = context.source.support_solution(record).get("correct_response")
    if not isinstance(solution, Mapping):
        return None
    game = context.source.support_activity(record)["game"]
    labels = _board_labels(game)
    given = game if isinstance(game, Mapping) else {}
    lines = _lines(solution, labels, given)
    if not lines:
        return None
    marks = sorted({mark for line in lines for mark in line.split(" → ")})
    # Mathematics help says its answer in words, in the lesson; the raw payload lines
    # ("3434 → 2") would only confuse a child, so only the board highlights remain.
    if context.subject == "MAT":
        return {"mode": mode, "lines": [], "marks": marks}
    return {"mode": mode, "lines": lines, "marks": marks}


def _board_labels(game: object) -> dict[str, str]:
    """Every token on the board, with the label the child reads for it."""

    labels: dict[str, str] = {}

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            label = _label(value)
            if label is not None:
                for key, token in value.items():
                    if isinstance(token, str) and key.endswith(("_token", "_id")):
                        labels.setdefault(token, label)
            for item in value.values():
                walk(item)
        elif isinstance(value, list | tuple):
            for item in value:
                walk(item)

    walk(game)
    return labels


def _label(entry: Mapping[str, object]) -> str | None:
    for hints in (_LABEL_HINTS, _SINHALA_HINTS):
        for hint in hints:
            text = entry.get(hint)
            if isinstance(text, str) and text.strip():
                return text.strip()
    for hint in _PICTURE_HINTS:
        text = entry.get(hint)
        if isinstance(text, str) and text.strip():
            return text.strip().replace("-", " ").replace("_", " ")
    return None


def _lines(
    solution: Mapping[str, object], labels: Mapping[str, str], given: Mapping[str, object]
) -> list[str]:
    lines: list[str] = []
    scalars: list[str] = []
    for key, value in solution.items():
        # A value the board already states (the two numbers to multiply) is not the answer.
        if key in _IGNORED_KEYS or given.get(key) == value:
            continue
        if isinstance(value, list) and value and all(isinstance(row, Mapping) for row in value):
            for row in value:
                parts = [
                    _readable(part, labels)
                    for name, part in row.items()
                    if name not in _IGNORED_KEYS
                ]
                text = " → ".join(dict.fromkeys(part for part in parts if part))
                if text:
                    lines.append(text)
        elif isinstance(value, Mapping):
            lines.extend(_lines(value, labels, {}))
        else:
            text = _readable(value, labels)
            if text:
                scalars.append(text)
    # A single value (a total, a product) or a short list of digits reads as one answer line.
    # Beside matched pairs, a lone number only counts how the child played, so it is left out.
    if scalars and not lines:
        lines.append(" → ".join(dict.fromkeys(scalars)))
    return lines


def _readable(value: object, labels: Mapping[str, str]) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, str):
        if value in labels:
            return labels[value]
        return "" if _OPAQUE.match(value) else value.replace("_", " ")
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple):
        return " ".join(_readable(item, labels) for item in value if not isinstance(item, Mapping))
    return ""
