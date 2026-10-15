"""A scripted reader for tests and for developing without a vision-model key.

It returns the readings it was given, in order, and records every call so a test can check what
the reader was (and was not) told.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from app.knowledge_tracing.application.grading.prompts import PROMPT_VERSION, blind_prompt
from app.knowledge_tracing.application.grading.types import (
    CallInfo,
    ItemRead,
    PartRead,
    PartSpec,
    VisionError,
)


@dataclass(frozen=True, slots=True)
class MockCall:
    parts: tuple[PartSpec, ...]
    language: str
    had_reference: bool
    prompt: str  # exactly the text a real reader would have been sent


class MockProvider:
    name = "mock"
    model = "mock-1"
    prompt_version = PROMPT_VERSION

    def __init__(self, *responses: ItemRead | VisionError) -> None:
        self._queue: deque[ItemRead | VisionError] = deque(responses)
        self.calls: list[MockCall] = []

    def queue(self, *responses: ItemRead | VisionError) -> "MockProvider":
        self._queue.extend(responses)
        return self

    def read_item(
        self,
        crop: bytes,
        parts: Sequence[PartSpec],
        language: str,
        blank_reference: bytes | None = None,
    ) -> tuple[ItemRead, CallInfo]:
        self.calls.append(
            MockCall(
                tuple(parts),
                language,
                blank_reference is not None,
                blind_prompt(parts, language, blank_reference is not None),
            )
        )
        if not self._queue:
            raise VisionError("mock_empty", "the mock provider has no more scripted readings")
        response = self._queue.popleft()
        if isinstance(response, VisionError):
            raise response
        return response, CallInfo(latency_ms=1, tokens_in=0, tokens_out=0, raw_text="mock")


def reading(*answers: str | tuple[str, float] | None, notes: str = "") -> ItemRead:
    """A scripted reading from short notation.

    Each answer is a string (confidence 0.9), an (answer, confidence) pair, or None for blank.
    """
    parts: list[PartRead] = []
    for number, answer in enumerate(answers, start=1):
        if answer is None:
            parts.append(PartRead(part=number, answer="", blank=True, confidence=0.95))
        elif isinstance(answer, tuple):
            text, confidence = answer
            parts.append(
                PartRead(part=number, answer=text, blank=not text, confidence=confidence)
            )
        else:
            parts.append(PartRead(part=number, answer=answer, blank=False, confidence=0.9))
    return ItemRead(parts=parts, notes=notes)
