"""Bookkeeping around reader calls: who asked, what it cost, and not paying twice.

Nothing here holds an image or a transcription. A call record is only timings, token counts and
an error code, so it can be stored and shown to the owner freely.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Literal, Protocol
from uuid import UUID

from app.knowledge_tracing.application.grading.types import ItemRead

CallRole = Literal["primary", "second_opinion"]


@dataclass(frozen=True, slots=True)
class CallContext:
    """What one reader call is for. Set around a call with `vision_context`."""

    submission_id: UUID | None = None
    paper_item_id: UUID | None = None
    role: CallRole = "primary"


_current: ContextVar[CallContext | None] = ContextVar("vision_call_context", default=None)
_EMPTY = CallContext()


def current_context() -> CallContext:
    return _current.get() or _EMPTY


@contextmanager
def vision_context(
    submission_id: UUID | None = None,
    paper_item_id: UUID | None = None,
    role: CallRole = "primary",
) -> Iterator[CallContext]:
    context = CallContext(submission_id, paper_item_id, role)
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


@contextmanager
def vision_role(role: CallRole) -> Iterator[CallContext]:
    """The current context with another role (the second reader of the same question)."""
    context = replace(_current.get() or _EMPTY, role=role)
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


@dataclass(frozen=True, slots=True)
class CallRecord:
    """One HTTP attempt to a reader. A retried call produces one record per attempt."""

    provider: str
    model: str
    prompt_version: str
    role: CallRole = "primary"
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    http_status: int | None = None
    error_code: str | None = None  # quota_daily, rate_limit, model_not_found, invalid_json ...
    submission_id: UUID | None = None
    paper_item_id: UUID | None = None


class CallLog(Protocol):
    def record(self, call: CallRecord) -> None: ...


class ReadingCache(Protocol):
    """Remembers readings so a retry or a restart never pays for the same question twice."""

    def get(self, key: tuple) -> ItemRead | None: ...

    def put(self, key: tuple, reading: ItemRead) -> None: ...


class InMemoryReadingCache:
    def __init__(self) -> None:
        self._items: dict[tuple, ItemRead] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple) -> ItemRead | None:
        with self._lock:
            found = self._items.get(key)
        return None if found is None else found.model_copy(deep=True)

    def put(self, key: tuple, reading: ItemRead) -> None:
        with self._lock:
            self._items[key] = reading.model_copy(deep=True)

    def __len__(self) -> int:
        return len(self._items)


class MemoryCallLog:
    """Keeps records in a list (tests, and the benchmark script)."""

    def __init__(self) -> None:
        self.records: list[CallRecord] = []
        self._lock = threading.Lock()

    def record(self, call: CallRecord) -> None:
        with self._lock:
            self.records.append(call)
