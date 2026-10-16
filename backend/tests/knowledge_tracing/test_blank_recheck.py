"""A blank reading is read once more, so one missed pencil mark is not marked "left blank"."""

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.knowledge_tracing.application.grading import (
    GradingConfig,
    KeyPart,
    VisionError,
    grade_item,
)
from app.knowledge_tracing.application.grading.call_log import vision_context
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading
from tests.knowledge_tracing.test_openai_provider import FakeServer, ok, provider

CROP = b"\x89PNG\r\n\x1a\n" + b"x" * 20
KEY = [KeyPart(1, "choice", ("1",), option_labels=("1", "2", "3"))]
TWO_PARTS = [
    KeyPart(1, "choice", ("1",), option_labels=("1", "2", "3")),
    KeyPart(2, "number", ("90",)),
]
RECHECK = GradingConfig(recheck_blanks=True)


def test_a_missed_mark_is_caught_when_the_second_reading_finds_it() -> None:
    """The real case: a clear underline read as blank once, then as option 1."""
    reader = MockProvider(reading(None), reading("1"))

    result = grade_item(KEY, reader, CROP, "si", config=RECHECK)

    assert len(reader.calls) == 2
    assert result.question.status == "pending_review"  # the parent decides, no mark is lost
    assert result.question.parts[0].review_reason == "models_disagree"


def test_two_blank_readings_stay_blank_and_nobody_is_asked() -> None:
    reader = MockProvider(reading(None), reading(None))

    result = grade_item(KEY, reader, CROP, "si", config=RECHECK)

    assert len(reader.calls) == 2
    assert result.question.status == "blank"
    assert not result.question.needs_review


def test_an_answered_question_is_read_only_once() -> None:
    reader = MockProvider(reading("1"))

    result = grade_item(KEY, reader, CROP, "si", config=RECHECK)

    assert len(reader.calls) == 1  # the re-check costs nothing when there is an answer
    assert result.question.status == "correct"


def test_the_recheck_can_be_switched_off() -> None:
    reader = MockProvider(reading(None))

    result = grade_item(KEY, reader, CROP, "si", config=GradingConfig(recheck_blanks=False))

    assert len(reader.calls) == 1
    assert result.question.status == "blank"


def test_a_blank_in_one_part_of_several_triggers_the_recheck() -> None:
    reader = MockProvider(reading("1", None), reading("1", "90"))

    result = grade_item(TWO_PARTS, reader, CROP, "si", config=RECHECK)

    assert len(reader.calls) == 2
    assert result.question.status == "pending_review"  # the second part disagrees
    assert [p.review_reason for p in result.question.parts if p.needs_review] == ["models_disagree"]


def test_a_failed_recheck_leaves_the_decision_to_the_parent() -> None:
    reader = MockProvider(reading(None), VisionError("rate_limit", "slow down"))

    result = grade_item(KEY, reader, CROP, "si", config=RECHECK)

    assert result.question.status == "pending_review"
    assert result.errors == ("rate_limit",)
    assert result.question.parts[0].review_reason == "vision_error"


def test_a_configured_second_reader_is_used_instead_of_a_repeat() -> None:
    first, second = MockProvider(reading(None)), MockProvider(reading(None))

    result = grade_item(KEY, first, CROP, "si", second_provider=second, config=RECHECK)

    assert len(first.calls) == 1 and len(second.calls) == 1  # no third reading
    assert result.question.status == "blank"


def test_the_extra_reading_is_recorded_as_a_second_opinion() -> None:
    blank = {"parts": [{"part": 1, "answer": "", "blank": True, "confidence": 0.9}]}
    server = FakeServer(ok(blank), ok(blank))
    p, log, _ = provider(server)

    with vision_context(None, None, "primary"):
        grade_item(KEY, p, CROP, "si", config=RECHECK)

    assert len(server.posts) == 2
    assert [r.role for r in log.records] == ["primary", "second_opinion"]
    # the answer key is still not in either request
    assert all("accepted" not in json.loads(r.content)["messages"][0]["content"][0]["text"] for r in server.posts)


def test_the_app_turns_it_on_and_the_tests_turn_it_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.knowledge_tracing.api import submissions_router
    from app.knowledge_tracing.infrastructure.storage import LocalStorage

    # in the app it is on by default (the test setup turns it off through the environment)
    assert Settings.model_fields["grading_recheck_blanks"].default is True

    for flag in (True, False):
        monkeypatch.setattr(
            submissions_router,
            "get_settings",
            lambda flag=flag: Settings(database_url="sqlite://", grading_recheck_blanks=flag),
        )
        with Session(create_engine("sqlite://")) as session:
            service = submissions_router.make_submission_service(
                session, LocalStorage(tmp_path), provider=MockProvider(), use_default_readers=False
            )
        assert service.config.recheck_blanks is flag
