"""Grades one question block: read it blindly, compare with the key, combine the parts.

No network of its own: the reader is a `VisionProvider` (a mock in tests, Gemini in production).
A failure of the reader never turns into "wrong": the parts go to the parent instead.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.knowledge_tracing.application.grading.combine import combine_parts
from app.knowledge_tracing.application.grading.compare import compare_part, norm
from app.knowledge_tracing.application.grading.types import (
    CallInfo,
    GradingConfig,
    ItemRead,
    KeyPart,
    PartGrade,
    PartRead,
    PartSpec,
    QuestionGrade,
    VisionError,
    VisionProvider,
)


@dataclass(frozen=True, slots=True)
class ItemGrade:
    question: QuestionGrade
    calls: tuple[CallInfo, ...] = ()
    errors: tuple[str, ...] = field(default=())  # codes of VisionErrors that were absorbed
    provider: str = ""
    model: str = ""
    prompt_version: str = ""


def part_specs(key: Sequence[KeyPart]) -> list[PartSpec]:
    """What the reader may know about each part. The answer is not in here."""
    return [
        PartSpec(
            index=part.part_no,
            label=part.label,
            kind=part.kind,
            option_labels=part.option_labels if part.kind == "choice" else None,
            instruction=part.instruction,
        )
        for part in key
    ]


def _agree(first: PartRead, second: PartRead) -> bool:
    """Two readings of a part mean the same thing."""
    if first.blank or second.blank:
        return first.blank == second.blank
    both_judged_instruction = (
        first.instruction_met is not None or second.instruction_met is not None
    )
    if both_judged_instruction and first.instruction_met != second.instruction_met:
        return False
    return norm(first.answer) == norm(second.answer)


def _review_all(key: Sequence[KeyPart], reason: str, reading: ItemRead | None = None) -> QuestionGrade:
    by_part = {r.part: r for r in (reading.parts if reading else [])}
    parts = []
    for k in key:
        read = by_part.get(k.part_no)
        parts.append(
            PartGrade(
                part_no=k.part_no,
                status="ambiguous",
                how=reason,
                needs_review=True,
                review_reason=reason,  # type: ignore[arg-type]
                read_text=read.answer if read else "",
                confidence=read.confidence if read else 0.0,
            )
        )
    return combine_parts(parts)


def grade_reading(
    key: Sequence[KeyPart],
    reading: ItemRead,
    config: GradingConfig = GradingConfig(),  # noqa: B008
    second: ItemRead | None = None,
) -> QuestionGrade:
    """Grade an already-made reading against the key."""
    reads = {r.part: r for r in reading.parts}
    expected = [k.part_no for k in key]
    # A different NUMBER of parts means the reader misunderstood the question: check them all.
    if len(reading.parts) != len(key):
        return _review_all(key, "part_count_mismatch", reading)

    # A part number the question does not have means the reader did not understand it.
    if set(reads) - set(expected):
        return _review_all(key, "part_count_mismatch", reading)

    second_reads = {r.part: r for r in second.parts} if second is not None else None
    grades: list[PartGrade] = []
    for k in key:
        read = reads.get(k.part_no)
        if read is None:  # the right number of parts, but this one is not among them
            grades.append(
                PartGrade(k.part_no, "ambiguous", "no reading", True, "part_missing", "", 0.0)
            )
            continue
        second_agrees: bool | None = None
        if second_reads is not None:
            other = second_reads.get(k.part_no)
            second_agrees = other is not None and _agree(read, other)
        grades.append(compare_part(read, k, config, second_agrees=second_agrees))
    return combine_parts(grades)


def grade_item(
    key: Sequence[KeyPart],
    provider: VisionProvider,
    crop: bytes,
    language: str,
    *,
    blank_reference: bytes | None = None,
    second_provider: VisionProvider | None = None,
    config: GradingConfig = GradingConfig(),  # noqa: B008
) -> ItemGrade:
    """Read one question block with the provider, then grade it."""
    specs = part_specs(key)
    calls: list[CallInfo] = []
    errors: list[str] = []

    try:
        reading, info = provider.read_item(crop, specs, language, blank_reference)
        calls.append(info)
    except VisionError as error:
        errors.append(error.code)
        return ItemGrade(
            _review_all(key, "vision_error"),
            tuple(calls),
            tuple(errors),
            provider.name,
            provider.model,
            provider.prompt_version,
        )

    second_reading: ItemRead | None = None
    if second_provider is not None:
        try:
            second_reading, second_info = second_provider.read_item(
                crop, specs, language, blank_reference
            )
            calls.append(second_info)
        except VisionError as error:
            # A second opinion that fails is not a reason to doubt the first reading's rules,
            # but nothing was confirmed either: every part is checked by the parent.
            errors.append(error.code)
            grade = grade_reading(key, reading, config)
            flagged = combine_parts(
                [
                    PartGrade(
                        p.part_no, p.status, p.how, True, p.review_reason or "vision_error",
                        p.read_text, p.confidence, p.instruction_met,
                    )
                    for p in grade.parts
                ]
            )
            return ItemGrade(
                flagged, tuple(calls), tuple(errors),
                provider.name, provider.model, provider.prompt_version,
            )

    question = grade_reading(key, reading, config, second_reading)
    return ItemGrade(
        question, tuple(calls), tuple(errors), provider.name, provider.model, provider.prompt_version
    )
