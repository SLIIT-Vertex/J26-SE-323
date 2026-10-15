"""The call log table, the status endpoint and the benchmark script."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application.grading import GradingConfig, KeyPart
from app.knowledge_tracing.application.grading.call_log import CallRecord
from app.knowledge_tracing.application.grading.types import ReviewPolicy, VisionError
from app.knowledge_tracing.infrastructure.db.models import VisionCallModel
from app.knowledge_tracing.infrastructure.db.vision_call_repository import (
    SqlAlchemyVisionCallLog,
    usage_summary,
)
from app.knowledge_tracing.infrastructure.vision import factory
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading
from app.shared.database.base import Base
from scripts.benchmark_vision import (
    LabelledItem,
    LabelledPart,
    evaluate,
    load_labels,
    write_template,
)

# ---- the call log table -----------------------------------------------------------------------


@pytest.fixture
def factory_and_engine() -> Iterator[tuple]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield (lambda: Session(engine)), engine


def test_a_call_is_stored_without_any_content(factory_and_engine: tuple) -> None:
    session_factory, engine = factory_and_engine
    log = SqlAlchemyVisionCallLog(session_factory)
    submission = uuid4()

    log.record(
        CallRecord(
            "gemini", "gemini-2.5-flash", "item-blind-v2", "primary",
            latency_ms=2100, tokens_in=1500, tokens_out=40, http_status=200,
            submission_id=submission,
        )
    )
    log.record(
        CallRecord("gemini", "gemini-2.5-flash", "item-blind-v2", "second_opinion",
                   latency_ms=900, http_status=429, error_code="rate_limit")
    )

    with Session(engine) as session:
        rows = session.scalars(select(VisionCallModel).order_by(VisionCallModel.id)).all()
        assert [(r.role, r.http_status, r.error_code) for r in rows] == [
            ("primary", 200, None),
            ("second_opinion", 429, "rate_limit"),
        ]
        assert rows[0].submission_id == submission
        columns = {c.name for c in VisionCallModel.__table__.columns}
        assert not columns & {"image", "crop", "answer", "text", "raw_text", "transcription"}


def test_the_usage_summary_counts_calls_tokens_and_errors(factory_and_engine: tuple) -> None:
    session_factory, engine = factory_and_engine
    log = SqlAlchemyVisionCallLog(session_factory)
    for tokens, error in [(1000, None), (2000, None), (None, "quota_daily")]:
        log.record(CallRecord("gemini", "m1", "p", latency_ms=100, tokens_in=tokens,
                              tokens_out=10 if tokens else None, error_code=error))
    log.record(CallRecord("gemini", "m2", "p", latency_ms=300, tokens_in=50, tokens_out=5))

    with Session(engine) as session:
        summary = usage_summary(session, datetime.now(UTC) - timedelta(days=1))

    assert summary["gemini/m1"] == {
        "calls": 3, "tokens_in": 3000, "tokens_out": 20, "mean_latency_ms": 100, "errors": 1,
    }
    assert summary["gemini/m2"]["calls"] == 1


# ---- status endpoint --------------------------------------------------------------------------


def test_the_status_says_when_the_reader_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import Settings

    monkeypatch.setattr(
        "app.knowledge_tracing.api.vision_router.get_settings",
        lambda: Settings(database_url="sqlite://", vision_provider="gemini", gemini_api_key=""),
    )
    monkeypatch.setattr(
        "app.knowledge_tracing.api.vision_router.get_vision_provider",
        lambda: (_ for _ in ()).throw(factory.VisionNotConfigured("GEMINI_API_KEY is empty")),
    )

    body = client.get("/api/v1/vision/status").json()

    assert body["configured"] is False
    assert body["provider"] == "gemini"
    assert "GEMINI_API_KEY" in body["problem"]


def test_the_status_reports_the_model_and_warnings(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Fake(MockProvider):
        name = "gemini"
        model = "gemini-2.5-flash"
        warnings = {"vision_quota_exhausted"}  # noqa: RUF012

    monkeypatch.setattr("app.knowledge_tracing.api.vision_router.get_vision_provider", Fake)
    monkeypatch.setattr(
        "app.knowledge_tracing.api.vision_router.get_second_vision_provider", lambda: None
    )

    body = client.get("/api/v1/vision/status").json()

    assert body["configured"] is True
    assert body["model"] == "gemini-2.5-flash"
    assert "vision_quota_exhausted" in body["warnings"]


def test_health_is_unchanged(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


# ---- the benchmark ----------------------------------------------------------------------------


def crop(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    Image.new("RGB", (40, 20), "white").save(path)
    return path


def item(tmp_path: Path, name: str, *parts: LabelledPart, question_id: str = "1.1") -> LabelledItem:
    return LabelledItem(crop(tmp_path, name), question_id, "si", tuple(parts))


def mcq_key() -> list[KeyPart]:
    return [KeyPart(1, "choice", ("2",), option_labels=("1", "2", "3"))]


def word_key(word: str = "rabbit") -> list[KeyPart]:
    return [KeyPart(1, "text", (word,))]


def test_the_benchmark_measures_reading_blanks_parents_and_agreement(tmp_path: Path) -> None:
    items = [
        item(tmp_path, "a.png", LabelledPart("ii", False)),  # read right, marked correct
        item(tmp_path, "b.png", LabelledPart("3", False)),  # read right, marked wrong
        item(tmp_path, "c.png", LabelledPart("", True)),  # left blank, read as blank
        item(tmp_path, "d.png", LabelledPart("rabbit", False)),  # misread as "rabit": marked wrong
        item(tmp_path, "e.png", LabelledPart("", True)),  # blank, but READ as answered: the failure
        item(tmp_path, "f.png", LabelledPart("sun", False)),  # reader unsure: to the parent
    ]
    keys = [mcq_key(), mcq_key(), mcq_key(), word_key("rabbit"), word_key("cat"), word_key("sun")]
    provider = MockProvider(
        reading("ii"), reading("3"), reading(None), reading("rabit"), reading("cat"),
        reading(("sun", 0.3)),
    )

    report = evaluate(items, keys, provider, workers=1)
    summary = report.summary()

    assert summary["items"] == 6 and summary["parts"] == 6
    assert summary["blank_read_as_answered"] == 1
    assert summary["share_sent_to_parent_pct"] == 16.7  # one of six
    # the reading of choice parts: 3 of 3 right; text parts: only "rabbit" misread and "cat"
    choice = summary["reading_accuracy_by_kind"]["choice"]
    text = summary["reading_accuracy_by_kind"]["text"]
    assert choice["parts"] == 3 and choice["reading_accuracy_pct"] == 100.0
    assert text["parts"] == 3
    assert text["reading_accuracy_pct"] < 80  # "rabit" for "rabbit" and "cat" for a blank
    verdict = "\n".join(report.verdict())
    assert "FAIL blank answers read as answered: 1" in verdict


def test_the_final_marking_is_compared_with_the_marking_of_the_label(tmp_path: Path) -> None:
    items = [
        item(tmp_path, "a.png", LabelledPart("ii", False)),
        item(tmp_path, "b.png", LabelledPart("1", False)),  # the child chose 1: wrong
    ]
    # the reader gets the second one wrong: reads "2" where the child wrote "1"
    provider = MockProvider(reading("ii"), reading("2"))

    report = evaluate(items, [mcq_key(), mcq_key()], provider, workers=1)

    assert report.final_decided == 2
    assert report.final_agree == 1  # the first agrees, the second marked correct but should be wrong


def test_a_reader_failure_is_counted_and_is_not_a_blank_reading(tmp_path: Path) -> None:
    items = [item(tmp_path, "a.png", LabelledPart("ii", False))]
    provider = MockProvider(VisionError("quota_daily"))

    report = evaluate(items, [mcq_key()], provider, workers=1)
    summary = report.summary()

    assert summary["items_the_reader_failed"] == 1
    assert summary["errors"] == {"quota_daily": 1}
    assert summary["answered_read_as_blank"] == 0  # nothing was read at all
    assert summary["share_sent_to_parent_pct"] == 100.0


def test_cost_is_only_reported_when_prices_are_given(tmp_path: Path) -> None:
    from app.knowledge_tracing.application.grading.types import CallInfo, ItemRead

    class Priced(MockProvider):
        def read_item(self, crop, parts, language, blank_reference=None):
            item_read, _ = super().read_item(crop, parts, language, blank_reference)
            return item_read, CallInfo(latency_ms=10, tokens_in=2000, tokens_out=100)

    items = [item(tmp_path, "a.png", LabelledPart("ii", False))]

    free = evaluate(items, [mcq_key()], Priced(reading("ii")), workers=1)
    priced = evaluate(
        items, [mcq_key()], Priced(reading("ii")), workers=1, price_in=0.10, price_out=0.40
    )

    assert free.cost is None
    assert priced.cost == pytest.approx((2000 * 0.10 + 100 * 0.40) / 1_000_000)
    assert priced.summary()["tokens_in"] == 2000
    _ = ItemRead  # imported for the type used in the helper above


def test_the_strict_policy_sends_more_to_the_parent(tmp_path: Path) -> None:
    def run(policy: ReviewPolicy) -> float:
        items = [item(tmp_path, "a.png", LabelledPart("rabbit", False))]
        report = evaluate(
            items, [word_key("rabbit")], MockProvider(reading("rabite")), workers=1,
            config=GradingConfig(review_policy=policy),
        )
        return report.sent_to_parent

    assert run(ReviewPolicy.reader_unsure()) == 0  # a spelling slip is just wrong
    assert run(ReviewPolicy.strict()) == 1


def test_labels_are_read_with_keys_blanks_and_references(tmp_path: Path) -> None:
    (tmp_path / "crops").mkdir()
    crop(tmp_path / "crops", "q.png")
    crop(tmp_path / "crops", "q_blank.png")
    labels = {
        "items": [
            {
                "image": "crops/q.png",
                "question_id": "3.41",
                "language": "ta",
                "reference": "crops/q_blank.png",
                "parts": [{"text": "ii"}, {"text": ""}],
                "answer_key": [
                    {"part_no": 1, "kind": "choice", "alternatives": ["2"], "option_labels": ["1", "2", "3"]},
                    {"part_no": 2, "kind": "text", "alternatives": ["மரம்"]},
                ],
            }
        ]
    }
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")

    [loaded] = load_labels(path)

    assert loaded.question_id == "3.41" and loaded.language == "ta"
    assert loaded.reference is not None and loaded.reference.name == "q_blank.png"
    assert [p.blank for p in loaded.parts] == [False, True]  # an empty text is a blank
    assert loaded.answer_key is not None and loaded.answer_key[1].alternatives == ("மரம்",)


def test_a_template_lists_every_picture_in_a_folder(tmp_path: Path) -> None:
    for name in ("b.png", "a.jpg", "notes.txt"):
        (tmp_path / name).write_bytes(b"x" if name.endswith(".txt") else b"")
    crop(tmp_path, "c.png")
    out = tmp_path / "labels.json"

    count = write_template(tmp_path, out)

    assert count == 3
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [i["image"] for i in data["items"]] == ["a.jpg", "b.png", "c.png"]
    assert all(i["question_id"] == "FILL-IN" for i in data["items"])
