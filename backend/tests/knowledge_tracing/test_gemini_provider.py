"""The Gemini reader against a fake server: no key, no network, no cost."""

import base64
import json
from uuid import uuid4

import httpx
import pytest

from app.config import Settings
from app.knowledge_tracing.application.grading import (
    ItemJob,
    KeyPart,
    PartSpec,
    VisionError,
    grade_item,
    grade_items,
)
from app.knowledge_tracing.application.grading.call_log import (
    InMemoryReadingCache,
    MemoryCallLog,
    vision_context,
)
from app.knowledge_tracing.infrastructure.vision.factory import (
    VisionNotConfigured,
    create_vision_provider,
)
from app.knowledge_tracing.infrastructure.vision.gemini import (
    WARNING_AUTO_SWITCHED,
    WARNING_NOT_PINNED,
    WARNING_QUOTA,
    GeminiProvider,
)
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
JPEG = b"\xff\xd8\xff" + b"y" * 20
READING = {"parts": [{"part": 1, "answer": "ii", "blank": False, "confidence": 0.9}]}
SPECS = [PartSpec(index=1, kind="choice", option_labels=("1", "2", "3"))]
KEY = [KeyPart(1, "choice", ("2",), option_labels=("1", "2", "3"))]


def ok_body(reading: dict | str = READING, tokens_in: int = 1500, tokens_out: int = 30) -> dict:
    text = reading if isinstance(reading, str) else json.dumps(reading)
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": tokens_in, "candidatesTokenCount": tokens_out},
    }


class FakeServer:
    """A scripted Gemini: each POST gets the next response; GET /models lists the given models."""

    def __init__(self, *responses: httpx.Response | Exception, models: list[dict] | None = None):
        self.responses = list(responses)
        self.posts: list[httpx.Request] = []
        self.gets: list[httpx.Request] = []
        self.models = models if models is not None else [
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-1.5-flash", "supportedGenerationMethods": ["countTokens"]},
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            self.gets.append(request)
            return httpx.Response(200, json={"models": self.models})
        self.posts.append(request)
        if not self.responses:
            return httpx.Response(500, json={"error": {"message": "script ran out"}})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def ok(reading: dict | str = READING, **kwargs) -> httpx.Response:
    return httpx.Response(200, json=ok_body(reading, **kwargs))


def error(status: int, message: str = "oops", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": message}}, headers=headers or {})


def provider(server: FakeServer, **kwargs) -> tuple[GeminiProvider, MemoryCallLog, list[float]]:
    log, slept = MemoryCallLog(), []
    kwargs.setdefault("model", "gemini-2.5-flash")
    p = GeminiProvider(
        "SECRET-KEY-123",
        client=server.client(),
        sleep=slept.append,
        call_log=log,
        **kwargs,
    )
    return p, log, slept


# ---- the request ------------------------------------------------------------------------------


def test_the_request_has_the_blind_prompt_the_image_and_json_output() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)

    reading, info = p.read_item(PNG, SPECS, "si")

    request = server.posts[0]
    body = json.loads(request.content)
    parts = body["contents"][0]["parts"]
    assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
    assert "x-goog-api-key" in request.headers
    assert "SECRET-KEY-123" not in str(request.url)  # the key is never in the address
    assert "item-blind" not in parts[0]["text"]  # the version name is not part of the prompt text
    assert "transcribe the child's answer" in parts[0]["text"]
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert base64.b64decode(parts[1]["inline_data"]["data"]) == PNG
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["temperature"] == 0.0
    assert reading.parts[0].answer == "ii"
    assert (info.tokens_in, info.tokens_out) == (1500, 30)


def test_a_blank_reference_is_sent_as_a_second_image() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)

    p.read_item(JPEG, SPECS, "ta", blank_reference=PNG)

    parts = json.loads(server.posts[0].content)["contents"][0]["parts"]
    assert [x.get("inline_data", {}).get("mime_type") for x in parts[1:]] == ["image/jpeg", "image/png"]
    assert "SECOND image" in parts[0]["text"]
    assert "Tamil" in parts[0]["text"]


def test_the_answer_key_is_not_in_what_is_sent() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)
    key = [KeyPart(1, "text", ("a-very-secret-answer", "alt-secret"))]

    grade_item(key, p, PNG, "si")

    sent = server.posts[0].content.decode()
    assert "a-very-secret-answer" not in sent
    assert "alt-secret" not in sent


# ---- retries ----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_errors_are_retried_with_backoff(status: int) -> None:
    server = FakeServer(error(status), error(status), ok())
    p, log, slept = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert len(server.posts) == 3
    assert slept == [4.0, 8.0]  # 4 s, then 8 s
    assert [c.error_code for c in log.records] == [
        "rate_limit" if status == 429 else "server_error",
        "rate_limit" if status == 429 else "server_error",
        None,
    ]


def test_retry_after_is_honoured_but_capped() -> None:
    server = FakeServer(error(429, headers={"retry-after": "17"}), error(503, headers={"retry-after": "500"}), ok())
    p, _, slept = provider(server)

    p.read_item(PNG, SPECS, "si")

    assert slept == [17.0, 90.0]


def test_giving_up_after_the_last_try() -> None:
    server = FakeServer(*[error(503) for _ in range(5)])
    p, log, slept = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "server_error"
    assert len(server.posts) == 5
    assert len(slept) == 4  # no wait after the final try
    assert len(log.records) == 5


def test_a_timeout_is_retried_then_reported() -> None:
    server = FakeServer(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), ok())
    p, log, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert [c.error_code for c in log.records][:2] == ["timeout", "timeout"]


def test_a_network_failure_is_reported_when_it_never_recovers() -> None:
    server = FakeServer(*[httpx.ConnectError("down") for _ in range(5)])
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "network"


# ---- quota ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "Quota exceeded for metric ... limit: 0, model: gemini-2.5-flash",
        "Quota exceeded for quota metric 'Requests' PerDay per project",
        "You exceeded your current quota: requests per day limit",
    ],
)
def test_a_hard_daily_quota_fails_at_once_without_retrying(message: str) -> None:
    server = FakeServer(error(429, message), ok())
    p, log, slept = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "quota_daily"
    assert len(server.posts) == 1  # not retried
    assert slept == []
    assert WARNING_QUOTA in p.warnings
    assert log.records[0].error_code == "quota_daily"


def test_a_plain_rate_limit_is_not_mistaken_for_a_daily_quota() -> None:
    server = FakeServer(error(429, "Resource has been exhausted (e.g. check quota)."), ok())
    p, _, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert WARNING_QUOTA not in p.warnings


# ---- the model --------------------------------------------------------------------------------


def test_a_withdrawn_model_switches_once_to_the_newest_flash() -> None:
    server = FakeServer(error(404, "model is no longer available"), ok())
    p, log, _ = provider(server, model="gemini-1.0-flash")

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert p.model == "gemini-2.5-flash"  # not the lite, not the pro, not the 2.0
    assert WARNING_AUTO_SWITCHED in p.warnings
    assert "gemini-2.5-flash:generateContent" in server.posts[1].url.path
    assert [c.error_code for c in log.records] == ["model_not_found", None]
    assert log.records[1].model == "gemini-2.5-flash"


def test_a_model_that_keeps_failing_is_reported_not_looped() -> None:
    server = FakeServer(error(404), error(404))
    p, _, _ = provider(server, model="gemini-1.0-flash")

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "model_not_found"
    assert len(server.posts) == 2  # one try, one after switching


def test_no_model_configured_picks_the_newest_flash_and_warns() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server, model="")

    p.read_item(PNG, SPECS, "si")

    assert p.model == "gemini-2.5-flash"
    assert WARNING_NOT_PINNED in p.warnings


def test_no_usable_model_is_an_error() -> None:
    server = FakeServer(models=[{"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]}])
    p, _, _ = provider(server, model="")

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "model_not_found"


# ---- bad replies and other errors -------------------------------------------------------------


def test_invalid_json_is_retried_once_then_reported() -> None:
    server = FakeServer(ok("this is not json"), ok("still not json"))
    p, log, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "invalid_json"
    assert len(server.posts) == 2
    assert [c.error_code for c in log.records].count("invalid_json") == 2


def test_invalid_json_that_recovers_on_the_second_try() -> None:
    server = FakeServer(ok("```json\nnot really\n```"), ok())
    p, _, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"


def test_a_reply_wrapped_in_a_code_fence_is_accepted() -> None:
    server = FakeServer(ok("```json\n" + json.dumps(READING) + "\n```"))
    p, _, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (error(401, "unauthorised"), "auth_failed"),
        (error(403, "permission denied"), "auth_failed"),
        (error(400, "API key not valid. Please pass a valid API key."), "auth_failed"),
        (error(400, "Invalid JSON payload"), "bad_request"),
        (error(418, "teapot"), "http_418"),
    ],
)
def test_other_errors_are_reported_and_not_retried(response: httpx.Response, code: str) -> None:
    server = FakeServer(response, ok())
    p, _, slept = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == code
    assert len(server.posts) == 1
    assert slept == []


def test_a_blocked_picture_and_an_empty_reply_are_errors() -> None:
    blocked = httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    empty = httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS"}]})
    server = FakeServer(blocked, empty)
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as first:
        p.read_item(PNG, SPECS, "si")
    with pytest.raises(VisionError) as second:
        p.read_item(PNG, SPECS, "si")

    assert first.value.code == "blocked"
    assert second.value.code == "empty_reply"


def test_the_api_key_never_appears_in_an_error() -> None:
    server = FakeServer(error(400, "API key not valid"))
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert "SECRET-KEY-123" not in str(caught.value)


# ---- call log and cache -----------------------------------------------------------------------


def test_every_call_is_recorded_with_its_context_and_no_content() -> None:
    server = FakeServer(ok(tokens_in=1234, tokens_out=56))
    p, log, _ = provider(server)
    submission, item = uuid4(), uuid4()

    with vision_context(submission, item, "primary"):
        p.read_item(PNG, SPECS, "si")

    [record] = log.records
    assert (record.provider, record.model, record.prompt_version) == (
        "gemini", "gemini-2.5-flash", "item-blind-v2"
    )
    assert (record.tokens_in, record.tokens_out, record.http_status) == (1234, 56, 200)
    assert record.error_code is None
    assert record.latency_ms is not None and record.latency_ms >= 0
    assert (record.submission_id, record.paper_item_id, record.role) == (submission, item, "primary")
    fields = set(type(record).__dataclass_fields__)
    assert not fields & {"image", "crop", "answer", "text", "raw_text"}


def test_a_second_reader_is_recorded_as_a_second_opinion() -> None:
    server_a, server_b = FakeServer(ok()), FakeServer(ok())
    first, log_a, _ = provider(server_a)
    second, log_b, _ = provider(server_b)

    grade_item(KEY, first, PNG, "si", second_provider=second)

    assert [r.role for r in log_a.records] == ["primary"]
    assert [r.role for r in log_b.records] == ["second_opinion"]


def test_a_reading_already_paid_for_is_reused() -> None:
    server = FakeServer(ok(), ok({"parts": [{"part": 1, "answer": "3", "confidence": 0.9}]}))
    p, log, _ = provider(server, cache=InMemoryReadingCache())
    submission, item = uuid4(), uuid4()

    with vision_context(submission, item):
        first, _ = p.read_item(PNG, SPECS, "si")
        again, info = p.read_item(PNG, SPECS, "si")

    assert first.parts[0].answer == again.parts[0].answer == "ii"
    assert len(server.posts) == 1  # the second call cost nothing
    assert info.raw_text == "cached"
    assert len(log.records) == 1


def test_a_different_question_is_not_taken_from_the_cache() -> None:
    server = FakeServer(ok(), ok({"parts": [{"part": 1, "answer": "3", "confidence": 0.9}]}))
    p, _, _ = provider(server, cache=InMemoryReadingCache())

    with vision_context(uuid4(), uuid4()):
        first, _ = p.read_item(PNG, SPECS, "si")
    with vision_context(uuid4(), uuid4()):
        second, _ = p.read_item(PNG, SPECS, "si")

    assert (first.parts[0].answer, second.parts[0].answer) == ("ii", "3")
    assert len(server.posts) == 2


def test_nothing_is_cached_without_a_submission_context() -> None:
    server = FakeServer(ok(), ok())
    p, _, _ = provider(server, cache=InMemoryReadingCache())

    p.read_item(PNG, SPECS, "si")
    p.read_item(PNG, SPECS, "si")

    assert len(server.posts) == 2


# ---- through the grading pipeline ------------------------------------------------------------


def test_a_quota_failure_becomes_a_parent_check_not_a_wrong_answer() -> None:
    server = FakeServer(error(429, "limit: 0"))
    p, _, _ = provider(server)

    result = grade_item(KEY, p, PNG, "si")

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "vision_error"
    assert result.errors == ("quota_daily",)


def test_a_page_of_questions_is_graded_concurrently_and_returned_in_order() -> None:
    answers = ["ii", "3", "1", "ii", "2", "3", "ii", "1"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"models": []})
        sent = json.loads(request.content)["contents"][0]["parts"][1]["inline_data"]["data"]
        index = base64.b64decode(sent)[-1]  # each crop ends with its own number
        return ok({"parts": [{"part": 1, "answer": answers[index], "confidence": 0.9}]})

    log = MemoryCallLog()
    p = GeminiProvider(
        "k",
        "gemini-2.5-flash",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
        call_log=log,
    )
    jobs = [ItemJob(KEY, PNG + bytes([i]), "si") for i in range(len(answers))]

    results = grade_items(jobs, p, workers=4)

    assert [r.question.parts[0].read_text for r in results] == answers  # same order as the jobs
    assert [r.question.status for r in results] == [
        "correct", "wrong", "wrong", "correct", "correct", "wrong", "correct", "wrong"
    ]
    assert len(log.records) == len(answers)


def test_job_contexts_reach_the_call_records() -> None:
    server = FakeServer(ok(), ok())
    p, log, _ = provider(server)
    ids = [(uuid4(), uuid4()), (uuid4(), uuid4())]
    from app.knowledge_tracing.application.grading.call_log import CallContext

    jobs = [ItemJob(KEY, PNG, "si", context=CallContext(s, i)) for s, i in ids]

    grade_items(jobs, p, workers=2)

    assert {(r.submission_id, r.paper_item_id) for r in log.records} == set(ids)


# ---- building a provider from settings -------------------------------------------------------


def settings(**overrides) -> Settings:
    return Settings(database_url="sqlite://", **overrides)


def test_the_factory_builds_gemini_from_settings() -> None:
    p = create_vision_provider(
        settings(vision_provider="gemini", gemini_api_key=" abc ", gemini_model="gemini-2.5-flash")
    )

    assert p.name == "gemini"
    assert p.model == "gemini-2.5-flash"


def test_the_factory_refuses_gemini_without_a_key() -> None:
    with pytest.raises(VisionNotConfigured, match="GEMINI_API_KEY"):
        create_vision_provider(settings(vision_provider="gemini", gemini_api_key=""))


def test_the_factory_builds_the_mock_and_rejects_unknown_names() -> None:
    assert isinstance(create_vision_provider(settings(vision_provider="mock")), MockProvider)
    with pytest.raises(VisionNotConfigured):
        create_vision_provider(settings(vision_provider="groq"))
