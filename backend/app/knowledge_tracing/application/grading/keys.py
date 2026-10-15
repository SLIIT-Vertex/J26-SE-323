"""Building answer keys from stored question parts. Server side only."""

from collections.abc import Iterable
from typing import Protocol

from app.knowledge_tracing.application.grading.types import KeyPart, PartKind

_KINDS: tuple[PartKind, ...] = ("choice", "number", "text", "instruction")


class StoredPart(Protocol):
    """The fields of a stored question part that grading needs (a database row fits)."""

    part_no: int
    part_type: str
    answer_kind: str
    option_labels: list[str] | None
    correct_option: str | None
    accepted_answers: list[str] | None
    instruction: str | None
    label_on_image: str | None


def to_key_part(part: StoredPart) -> KeyPart:
    kind: PartKind = part.answer_kind if part.answer_kind in _KINDS else "text"  # type: ignore[assignment]
    alternatives = tuple(part.accepted_answers or ())
    if not alternatives and part.correct_option:
        alternatives = (part.correct_option,)
    labels = tuple(part.option_labels) if part.option_labels else None
    return KeyPart(
        part_no=part.part_no,
        kind=kind,
        alternatives=alternatives,
        option_labels=labels,
        instruction=part.instruction,
        label=part.label_on_image,
    )


def to_key(parts: Iterable[StoredPart]) -> list[KeyPart]:
    return [to_key_part(p) for p in sorted(parts, key=lambda p: p.part_no)]
