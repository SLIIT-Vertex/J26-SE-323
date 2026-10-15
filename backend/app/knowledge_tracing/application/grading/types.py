"""Shared types of the grading rule engine.

The most important rule of the whole grading design lives in how these types are used:

    The vision model only READS what the child wrote or marked. It is told what kind of answer
    each part expects (a choice label, a number, a word) but never the correct answer. Our own
    code compares the reading with the answer key.

`PartSpec` is therefore everything the reader is ever told about a part, and it has no field that
could hold an answer. `KeyPart` is the answer key and never leaves the server.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

PartKind = Literal["choice", "number", "text", "instruction"]
PartStatus = Literal["correct", "wrong", "blank", "ambiguous"]
QuestionStatus = Literal["correct", "wrong", "blank", "pending_review"]
ReviewReason = Literal[
    "two_marks",
    "choice_text_given",
    "near_miss",
    "long_text_close",
    "extra_words",
    "word_order",
    "roman_arabic",
    "unit_missing",
    "unit_unknown",
    "negation_words",
    "instruction_check",
    "low_confidence",
    "models_disagree",
    "part_missing",
    "vision_error",
    "part_count_mismatch",
]


@dataclass(frozen=True, slots=True)
class KeyPart:
    """The answer key of one part. Server side only: never sent to a client or a model."""

    part_no: int  # 1-based, the order the child answers in
    kind: PartKind
    alternatives: tuple[str, ...] = ()  # accepted answers, raw (a choice part: the right option)
    option_labels: tuple[str, ...] | None = None
    instruction: str | None = None
    label: str | None = None


class PartSpec(BaseModel):
    """What the reader is told about a part. There is deliberately no field for the answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int  # 1-based, the order of the parts in the key
    label: str | None = None  # printed label such as "i" or "ii", when the key has one
    kind: PartKind
    option_labels: tuple[str, ...] | None = None  # choice parts: every option, not the right one
    instruction: str | None = None  # something to LOOK for, e.g. "check the boxes are coloured"


class PartRead(BaseModel):
    """What the reader saw for one part."""

    model_config = ConfigDict(extra="ignore")

    part: int
    answer: str = ""  # exactly what the child wrote; a choice part: the option label as printed
    blank: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    instruction_met: bool | None = None  # only when the part has an instruction
    notes: str = ""


class ItemRead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    parts: list[PartRead]
    notes: str = ""


@dataclass(frozen=True, slots=True)
class CallInfo:
    latency_ms: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    raw_text: str = ""


class VisionError(Exception):
    """The reader could not produce a usable reading (network, quota, invalid output ...)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code  # e.g. quota_daily, rate_limit, timeout, invalid_json, model_not_found


class VisionProvider(Protocol):
    name: str
    model: str
    prompt_version: str

    def read_item(
        self,
        crop: bytes,
        parts: Sequence[PartSpec],
        language: str,
        blank_reference: bytes | None = None,
    ) -> tuple[ItemRead, CallInfo]:
        """Read one question block. Raises VisionError when no usable reading can be made."""
        ...


@dataclass(frozen=True, slots=True)
class PartGrade:
    part_no: int
    status: PartStatus
    how: str  # exact | choice-equivalent | number found in text | loose | similar | different | ...
    needs_review: bool
    review_reason: ReviewReason | None
    read_text: str
    confidence: float
    instruction_met: bool | None = None


@dataclass(frozen=True, slots=True)
class QuestionGrade:
    """The result for one question block (all its parts)."""

    status: QuestionStatus  # pending_review while any part waits for the parent
    parts: tuple[PartGrade, ...]
    correct_parts: int
    total_parts: int

    @property
    def needs_review(self) -> bool:
        return any(p.needs_review for p in self.parts)


ReviewAction = Literal["review", "correct", "wrong"]


@dataclass(frozen=True)
class ReviewPolicy:
    """What happens to a part when a rule is unsure about it.

    The rules (compare.py) name WHY a part is uncertain. The policy decides whether that
    uncertainty is worth a parent's time ("review") or is settled automatically ("correct" or
    "wrong"). Failures of the reader itself are never settled automatically: a reading that could
    not be made, or was made with low confidence, always goes to the parent.
    """

    actions: dict[str, ReviewAction]
    # An instruction part ("colour three boxes") is accepted on one confident reading. With True
    # it also needs a second reader to agree, otherwise it always goes to the parent.
    instruction_needs_second_reader: bool = False

    def action_for(self, reason: str | None) -> ReviewAction:
        return self.actions.get(reason or "", "review")

    @classmethod
    def reader_unsure(cls) -> "ReviewPolicy":
        """The default: the parent only sees what the reader itself could not make sense of.

        Rule-level doubts are settled automatically. These choices are judgment calls that the
        project owner should confirm; see the notes next to each one.
        """
        return cls(
            actions={
                # the child's word is a slip of the right word: a spelling mistake is wrong
                "near_miss": "wrong",
                "long_text_close": "wrong",
                # the right words are all there, with more around them
                "extra_words": "correct",
                # the same words in another order: not what the key says
                "word_order": "wrong",
                # the key asks for one numeral system and the child used the other
                "roman_arabic": "wrong",
                # the numbers are right and only the unit is missing or spelled unusually
                "unit_missing": "correct",
                "unit_unknown": "correct",
                # "6 less" is not 6
                "negation_words": "wrong",
            },
            instruction_needs_second_reader=False,
        )

    @classmethod
    def strict(cls) -> "ReviewPolicy":
        """Every doubt goes to the parent (the rule table exactly as specified)."""
        return cls(actions={}, instruction_needs_second_reader=True)


@dataclass(frozen=True, slots=True)
class GradingConfig:
    confidence_min: float = 0.60  # below this a reading goes to the parent
    # A wrong word at least this similar to the key goes to the parent. 0.80 catches a child's
    # typical slip on a short word ("rabite" for "rabbit" scores 0.83); 0.85 missed it.
    # A starting value to tune on real answers.
    near_miss_ratio: float = 0.80
    near_miss_min_length: int = 4
    # A long answer (15+ characters after normalising) that is at least this similar to the key
    # but not equal goes to the parent: a child's slip in a long word is not "clearly wrong".
    long_length: int = 15
    near_long_ratio: float = 0.60
    review_policy: ReviewPolicy = field(default_factory=ReviewPolicy.reader_unsure)
