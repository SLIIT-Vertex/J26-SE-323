"""Parser for the question bank's answer-key syntax (pure, no I/O).

One line of key becomes one or more parts, in the order the child answers them:

    a, b, c            three parts
    ans1/ans2          alternatives of one part (a slash between digits is a fraction)
    i. x, ii. y        optional labels in front of parts
    80,004             a comma inside a number does not split
    "color 3 boxes"    straight double quotes: an instruction to the grader
    \\,                 a literal comma inside one answer
"""

import re
from dataclasses import dataclass

CHOICE_TOKENS = {"1", "2", "3", "4", "i", "ii", "iii", "iv"}
ROMAN_ORDER = ["i", "ii", "iii", "iv"]
DIGIT_ORDER = ["1", "2", "3", "4"]

_COMMA_PLACEHOLDER = "\x00"
_LABEL_DOT = re.compile(r"^\(?\s*([ivxIVX]{1,4}|\d{1,2}|[A-Za-z])\s*\)?\s*\.\s*(?!\d)(\S.*)$", re.DOTALL)
_LABEL_PAREN = re.compile(r"^\(\s*([ivxIVX]{1,4})\s*\)\s*(\S.*)$", re.DOTALL)
_ALTERNATIVE_SLASH = re.compile(r"(?<!\d)/|/(?!\d)")
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")


class AnswerKeyError(ValueError):
    """The key line cannot be understood."""


@dataclass(frozen=True)
class ParsedPart:
    part_no: int
    answer_kind: str  # choice | number | text | instruction
    part_type: str  # mcq | short
    alternatives: tuple[str, ...]  # raw accepted answers; empty for an instruction-only part
    instruction: str | None = None
    label: str | None = None
    option_labels: tuple[str, ...] | None = None
    correct_option: str | None = None


def parse_answer_key(raw: str) -> list[ParsedPart]:
    text = raw.strip()
    if not text:
        raise AnswerKeyError("the answer key is empty")
    pieces = _split_parts(text)
    return [_parse_part(piece, number) for number, piece in enumerate(pieces, start=1)]


def _split_parts(text: str) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    in_quote = False
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and text[i + 1 : i + 2] == ",":
            current.append(_COMMA_PLACEHOLDER)
            i += 2
            continue
        if char == '"':
            in_quote = not in_quote
        if char == "," and not in_quote and not _is_thousand_separator(text, i):
            pieces.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    if in_quote:
        raise AnswerKeyError('unbalanced double quote (") in the answer key')
    pieces.append("".join(current))
    return pieces


def _is_thousand_separator(text: str, index: int) -> bool:
    """digit , exactly three digits, then not a digit."""
    if index == 0 or not text[index - 1].isdigit():
        return False
    following = text[index + 1 : index + 4]
    if len(following) != 3 or not following.isdigit():
        return False
    return not text[index + 4 : index + 5].isdigit()


def _parse_part(piece: str, part_no: int) -> ParsedPart:
    text = piece.strip()
    instructions = re.findall(r'"([^"]*)"', text)
    text = re.sub(r'"[^"]*"', " ", text).strip()
    instruction = "; ".join(i.strip() for i in instructions if i.strip()) or None

    label: str | None = None
    for pattern in (_LABEL_DOT, _LABEL_PAREN):
        match = pattern.match(text)
        if match:
            label, text = match.group(1), match.group(2).strip()
            break

    answer = text.replace(_COMMA_PLACEHOLDER, ",").strip()
    if not answer and instruction is None:
        raise AnswerKeyError(f"part {part_no} is empty")

    alternatives = tuple(a.strip() for a in _ALTERNATIVE_SLASH.split(answer) if a.strip())
    if not alternatives:
        return ParsedPart(
            part_no, "instruction", "short", (), instruction=instruction, label=label
        )

    tokens = [_unwrap(a) for a in alternatives]
    if all(token.lower() in CHOICE_TOKENS for token in tokens):
        labels = _option_labels(tokens)
        return ParsedPart(
            part_no,
            "choice",
            "mcq",
            alternatives,
            instruction=instruction,
            label=label,
            option_labels=labels,
            correct_option=tokens[0],
        )
    kind = "number" if all(_is_number(a) for a in alternatives) else "text"
    return ParsedPart(part_no, kind, "short", alternatives, instruction=instruction, label=label)


def _unwrap(value: str) -> str:
    """'(iii)' -> 'iii'; surrounding brackets and a trailing dot are not part of the option."""
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    return value.rstrip(".").strip()


def _is_number(value: str) -> bool:
    cleaned = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", value).replace(" ", "")
    return bool(_NUMBER.match(cleaned))


def _option_labels(tokens: list[str]) -> tuple[str, ...]:
    """Default option labels in the style of the key, widened to include every key."""
    first = tokens[0]
    order = DIGIT_ORDER if first.isdigit() else ROMAN_ORDER
    upper = first.isupper()
    size = 3
    for token in tokens:
        lowered = token.lower()
        if lowered in order:
            size = max(size, order.index(lowered) + 1)
    labels = order[:size]
    return tuple(label.upper() if upper else label for label in labels)
