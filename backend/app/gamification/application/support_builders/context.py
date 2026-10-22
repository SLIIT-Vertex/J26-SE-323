"""What a help builder receives and what it returns.

A builder turns one failed item into the public game data of one help type. It never decides
which type comes next and never scores; the support-round service does both.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal, Protocol
from uuid import uuid4

from app.gamification.application.support_builders.answer_reveal import answer_reveal
from app.gamification.content.support_types import SupportType

StageKind = Literal["practice", "target", "view"]
# Seeds for help items start far from the episode seed's neighbours, so a help item is never the
# before or after item by accident.
SUPPORT_SEED_OFFSET = 7_919
SUPPORT_SEED_ATTEMPTS = 48


class SupportItemSource(Protocol):
    """The game flow, seen only as a source of items for its own area."""

    skills: Mapping[str, object]

    def support_item(self, skill_id: str, seed: int) -> object: ...

    def simpler_support_item(
        self, skill_id: str, seed: int, failed_record: Mapping[str, object]
    ) -> object | None:
        """An easier item of the same skill and game than the failed one, or ``None``."""

    def support_record(self, item: object, at: datetime) -> dict[str, object]: ...

    def support_activity(self, record: Mapping[str, object]) -> dict[str, object]: ...

    def support_solution(
        self, record: Mapping[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]: ...


@dataclass(frozen=True)
class SupportBuildContext:
    source: SupportItemSource
    skill_id: str
    failed_item: object
    failed_record: Mapping[str, object]
    reserved_revisions: frozenset[str]
    seed: int
    reason_family: str | None
    at: datetime
    # The area's subject code (``MAT``, ``ENG``): which wording the cues use.
    subject: str = "MAT"
    # The area itself: which theory a mathematics help teaches.
    area_id: str = ""
    # What the child answered on the failed item, for help that starts from their mistake.
    failed_response: Mapping[str, object] | None = None


@dataclass(frozen=True)
class SupportStage:
    kind: StageKind
    cues_si: tuple[str, ...]
    item: dict[str, object] | None = None
    # A practice stage that gates: the child returns to the failed item only after succeeding.
    gate_on_success: bool = False
    worked_example: dict[str, object] | None = None
    # The item's real answer, tinted on the board while the child plays (see answer_reveal).
    answer: dict[str, object] | None = None
    # Guided reasoning only: each question with its answer for this game.
    guidance: tuple[tuple[str, str], ...] = ()
    # Mathematics only: what the stage teaches in words (see support_builders.teaching).
    lesson: dict[str, object] | None = None

    def with_lesson(self, lesson: dict[str, object] | None) -> SupportStage:
        return replace(self, lesson=lesson)

    def as_record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "cues_si": list(self.cues_si),
            "item": self.item,
            "gate_on_success": self.gate_on_success,
            "worked_example": self.worked_example,
            "answer": self.answer,
            "guidance": [
                {"question_si": question, "answer_si": answer} for question, answer in self.guidance
            ],
            "lesson": self.lesson,
        }


@dataclass(frozen=True)
class SupportPlan:
    scaffold_type: SupportType
    title_si: str
    stages: tuple[SupportStage, ...] = field(default_factory=tuple)


class SupportBuilder(Protocol):
    scaffold_type: SupportType

    def build(self, context: SupportBuildContext) -> SupportPlan | None:
        """The plan for this episode, or ``None`` when this game cannot render the type."""


def target_stage(
    context: SupportBuildContext,
    cues_si: tuple[str, ...],
    guidance: tuple[tuple[str, str], ...] = (),
) -> SupportStage:
    """The failed item again, inside the help, as a supported attempt, its answer tinted."""

    record = json.loads(json.dumps(context.failed_record))
    record.update(
        presentation_id=str(uuid4()),
        role="supported_practice",
        assistance_state="active",
        created_at=context.at.isoformat(),
    )
    return SupportStage(
        kind="target",
        cues_si=cues_si,
        item=record,
        answer=answer_reveal(context, context.failed_record, "tint"),
        guidance=guidance,
    )


def practice_record(context: SupportBuildContext, item: object) -> dict[str, object]:
    record = context.source.support_record(item, context.at)
    record.update(role="supported_practice", assistance_state="active")
    return record


def practice_stage(
    context: SupportBuildContext,
    record: dict[str, object],
    cues_si: tuple[str, ...],
    *,
    gate_on_success: bool = False,
) -> SupportStage:
    """Another item of the help, played by the child with its answer tinted."""

    return SupportStage(
        kind="practice",
        cues_si=cues_si,
        item=record,
        gate_on_success=gate_on_success,
        answer=answer_reveal(context, record, "tint"),
    )


def teaches(context: SupportBuildContext) -> bool:
    """Mathematics help explains its steps and answers in words; other subjects keep their cues."""

    return context.subject == "MAT"


def skill_name(context: SupportBuildContext, skill_id: str) -> str | None:
    skill = context.source.skills.get(skill_id)
    name = getattr(skill, "name_si", None) or getattr(skill, "title_si", None)
    return str(name) if name else None


def answer_tokens(context: SupportBuildContext) -> frozenset[str]:
    """Numbers in the failed item's answer that the child has not already been shown."""

    solution = context.source.support_solution(context.failed_record)
    shown = _numbers(context.source.support_activity(context.failed_record))
    return frozenset(_numbers(solution.get("correct_response")) - shown)


def without_answer(lines: tuple[str, ...], tokens: frozenset[str]) -> tuple[str, ...]:
    return tuple(line for line in lines if not (_numbers(line) & tokens))


def solution_matches_failed(context: SupportBuildContext, record: Mapping[str, object]) -> bool:
    """True when another item would show the failed item's own answer."""

    failed = context.source.support_solution(context.failed_record).get("correct_response")
    other = context.source.support_solution(record).get("correct_response")
    return failed is not None and _canonical(failed) == _canonical(other)


def _numbers(value: object) -> set[str]:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return {token.replace(" ", "") for token in re.findall(r"\d[\d ]*\d|\d", text)}


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
