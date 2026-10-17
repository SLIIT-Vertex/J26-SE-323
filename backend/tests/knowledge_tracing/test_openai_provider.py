"""The OpenAI reader against a fake server: no key, no network, no cost."""

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
from app.knowledge_tracing.infrastructure.vision.openai import WARNING_QUOTA, OpenAIProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
JPEG = b"\xff\xd8\xff" + b"y" * 20
READING = {"parts": [{"part": 1, "answer": "ii", "blank": False, "confidence": 0.9}]}
SPECS = [PartSpec(index=1, kind="choice", option_labels=("1", "2", "3"))]
KEY = [KeyPart(1, "choice", ("2",), option_labels=("1", "2", "3"))]
SECRET = "sk-SECRET-KEY-1234567890"


def ok_body(reading: dict | str = READING, tokens_in: int = 1500, tokens_out: int = 30) -> dict:
    text = reading if isinstance(reading, str) else json.dumps(reading)
    return {
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
    }


class FakeServer:
    """A scripted OpenAI: each POST gets the next response."""

    def __init__(self, *responses: httpx.Response | Exception):
        self.responses = list(responses)
        self.posts: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
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


def error(
    status: int,
    message: str = "oops",
    *,
    code: str | None = None,
    param: str | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    body = {"error": {"message": message, "type": "x", "code": code, "param": param}}
    return httpx.Response(status, json=body, headers=headers or {})


def provider(server: FakeServer, **kwargs) -> tuple[OpenAIProvider, MemoryCallLog, list[float]]:
    log, slept = MemoryCallLog(), []
    kwargs.setdefault("model", "my-model")
    model = kwargs.pop("model")
    p = OpenAIProvider(
        SECRET, model, client=server.client(), sleep=slept.append, call_log=log, **kwargs
    )
    return p, log, slept


# ---- the request ------------------------------------------------------------------------------


def test_the_request_has_the_blind_prompt_the_image_and_json_output() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)

    reading, info = p.read_item(PNG, SPECS, "si")

    request = server.posts[0]
    body = json.loads(request.content)
    content = body["messages"][0]["content"]
    assert request.url.path.endswith("/chat/completions")
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(request.url)  # the key is never in the address
    assert body["model"] == "my-model"
    assert "transcribe the child's answer" in content[0]["text"]
    image = content[1]["image_url"]
    assert image["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(image["url"].split(",", 1)[1]) == PNG
    assert image["detail"] == "high"  # handwriting needs the detailed view
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_completion_tokens"] == 4096
    # settings only some models accept are not sent unless asked for
    assert "temperature" not in body and "reasoning_effort" not in body
    assert reading.parts[0].answer == "ii"
    assert (info.tokens_in, info.tokens_out) == (1500, 30)


def test_optional_settings_are_sent_when_given() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server, temperature=0.0, reasoning_effort="low", image_detail="auto", max_output_tokens=2000)

    p.read_item(PNG, SPECS, "si")

    body = json.loads(server.posts[0].content)
    assert body["temperature"] == 0.0
    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 2000
    assert body["messages"][0]["content"][1]["image_url"]["detail"] == "auto"


def test_a_blank_reference_is_sent_as_a_second_image() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)

    p.read_item(JPEG, SPECS, "ta", blank_reference=PNG)

    content = json.loads(server.posts[0].content)["messages"][0]["content"]
    mimes = [c["image_url"]["url"].split(";")[0] for c in content[1:]]
    assert mimes == ["data:image/jpeg", "data:image/png"]


def test_the_answer_key_is_not_in_what_is_sent() -> None:
    server = FakeServer(ok())
    p, _, _ = provider(server)
    key = KeyPart(1, "text", ("RABBIT-ACCEPTED-ANSWER",), instruction=None)
    from app.knowledge_tracing.application.grading.pipeline import part_specs

    p.read_item(PNG, part_specs([key]), "si")

    assert "RABBIT-ACCEPTED-ANSWER" not in server.posts[0].content.decode("utf-8")


# ---- retries ----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_errors_are_retried_with_backoff(status: int) -> None:
    code = "rate_limit_exceeded" if status == 429 else None
    server = FakeServer(error(status, code=code), error(status, code=code), ok())
    p, log, slept = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert len(server.posts) == 3
    assert slept == [4.0, 8.0]
    expected = "rate_limit" if status == 429 else "server_error"
    assert [c.error_code for c in log.records] == [expected, expected, None]


def test_retry_after_is_honoured_but_capped() -> None:
    server = FakeServer(
        error(429, headers={"retry-after": "17"}),
        error(503, headers={"retry-after": "500"}),
        error(429, headers={"retry-after-ms": "2500"}),
        ok(),
    )
    p, _, slept = provider(server)

    p.read_item(PNG, SPECS, "si")

    assert slept == [17.0, 90.0, 2.5]


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
    assert [c.error_code for c in log.records] == ["timeout", "timeout", None]


def test_a_network_failure_is_reported_when_it_never_recovers() -> None:
    server = FakeServer(*[httpx.ConnectError("down") for _ in range(5)])
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "network"


# ---- quota ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("You exceeded your current quota, please check your plan and billing details.", "insufficient_quota"),
        ("Rate limit reached for gpt on requests per day (RPD): Limit 200", "rate_limit_exceeded"),
        ("Rate limit reached on tokens per day (TPD): Limit 200000", "rate_limit_exceeded"),
    ],
)
def test_a_hard_quota_fails_at_once_without_retrying(message: str, code: str) -> None:
    server = FakeServer(error(429, message, code=code))
    p, log, slept = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "quota_daily"
    assert len(server.posts) == 1 and slept == []
    assert WARNING_QUOTA in p.warnings
    assert log.records[0].error_code == "quota_daily"


def test_a_per_minute_limit_is_not_mistaken_for_a_hard_quota() -> None:
    server = FakeServer(
        error(429, "Rate limit reached for gpt on tokens per min (TPM): Limit 30000", code="rate_limit_exceeded"),
        ok(),
    )
    p, _, slept = provider(server)

    p.read_item(PNG, SPECS, "si")

    assert len(server.posts) == 2 and slept == [4.0]
    assert WARNING_QUOTA not in p.warnings


def test_a_quota_failure_becomes_a_parent_check_not_a_wrong_answer() -> None:
    server = FakeServer(error(429, "no credit", code="insufficient_quota"))
    p, _, _ = provider(server)

    result = grade_item(KEY, p, PNG, "si")

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "vision_error"
    assert result.errors == ("quota_daily",)


# ---- a model that refuses a setting, a wrong model name ----------------------------------------


def test_a_refused_temperature_is_dropped_and_the_call_repeated() -> None:
    server = FakeServer(
        error(400, "Unsupported value: 'temperature' does not support 0 with this model.",
              code="unsupported_value", param="temperature"),
        ok(),
    )
    p, _, slept = provider(server, temperature=0.0)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"
    assert "temperature" in json.loads(server.posts[0].content)
    assert "temperature" not in json.loads(server.posts[1].content)
    assert slept == []  # mending the request is not a failed try


def test_a_refused_setting_is_found_from_the_message_when_no_param_is_given() -> None:
    server = FakeServer(error(400, "Unsupported parameter: 'reasoning_effort' is not supported."), ok())
    p, _, _ = provider(server, reasoning_effort="low")

    p.read_item(PNG, SPECS, "si")

    assert "reasoning_effort" not in json.loads(server.posts[1].content)


def test_an_older_server_gets_max_tokens_instead() -> None:
    server = FakeServer(
        error(400, "Unrecognized request argument: max_completion_tokens",
              code="unsupported_parameter", param="max_completion_tokens"),
        ok(),
    )
    p, _, _ = provider(server)

    p.read_item(PNG, SPECS, "si")

    second = json.loads(server.posts[1].content)
    assert "max_completion_tokens" not in second and second["max_tokens"] == 4096


def test_a_bad_request_that_cannot_be_mended_is_reported() -> None:
    server = FakeServer(error(400, "Invalid image", code="invalid_image"))
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "bad_request"
    assert len(server.posts) == 1


def test_an_unknown_model_is_reported_with_a_hint() -> None:
    server = FakeServer(error(404, "The model `nope` does not exist", code="model_not_found"))
    p, log, _ = provider(server, model="nope")

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "model_not_found"
    assert "OPENAI_MODEL" in str(caught.value)
    assert len(server.posts) == 1  # not retried
    assert log.records[0].error_code == "model_not_found"


def test_the_api_key_never_appears_in_an_error() -> None:
    message = f"Incorrect API key provided: {SECRET}. Also seen as sk-proj-abcdef123456."
    server = FakeServer(error(401, message, code="invalid_api_key"))
    p, _, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "auth_failed"
    text = str(caught.value)
    assert SECRET not in text and "sk-proj-abcdef123456" not in text and "***" in text


# ---- the reply --------------------------------------------------------------------------------


def test_invalid_json_is_retried_once_then_reported() -> None:
    server = FakeServer(ok("not json at all"), ok("{{ still not"))
    p, log, _ = provider(server)

    with pytest.raises(VisionError) as caught:
        p.read_item(PNG, SPECS, "si")

    assert caught.value.code == "invalid_json"
    assert len(server.posts) == 2
    assert [r.error_code for r in log.records].count("invalid_json") == 2


def test_invalid_json_that_recovers_on_the_second_try() -> None:
    server = FakeServer(ok("oops"), ok())
    p, _, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"


def test_a_reply_wrapped_in_a_code_fence_is_accepted() -> None:
    server = FakeServer(ok("```json\n" + json.dumps(READING) + "\n```"))
    p, _, _ = provider(server)

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"


def test_a_reply_made_of_text_parts_is_accepted() -> None:
    body = {
        "choices": [{"message": {"content": [{"type": "text", "text": json.dumps(READING)}]}, "finish_reason": "stop"}],
        "usage": {},
    }
    p, _, _ = provider(FakeServer(httpx.Response(200, json=body)))

    reading, _ = p.read_item(PNG, SPECS, "si")

    assert reading.parts[0].answer == "ii"


def test_a_refusal_and_an_empty_reply_are_errors() -> None:
    refusal = {"choices": [{"message": {"content": None, "refusal": "I cannot help"}, "finish_reason": "stop"}]}
    cut_off = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}], "usage": {"completion_tokens": 4096}}
    p, log, _ = provider(FakeServer(httpx.Response(200, json=refusal), httpx.Response(200, json=cut_off)))

    with pytest.raises(VisionError) as first:
        p.read_item(PNG, SPECS, "si")
    with pytest.raises(VisionError) as second:
        p.read_item(PNG, SPECS, "si")

    assert first.value.code == "blocked"
    assert second.value.code == "empty_reply" and "length" in str(second.value)
    assert [r.error_code for r in log.records] == ["blocked", "empty_reply"]


# ---- call log and cache -----------------------------------------------------------------------


def test_every_call_is_recorded_with_its_context_and_no_content() -> None:
    server = FakeServer(ok(tokens_in=1234, tokens_out=56))
    p, log, _ = provider(server)
    submission, item = uuid4(), uuid4()

    with vision_context(submission, item, "primary"):
        p.read_item(PNG, SPECS, "si")

    [record] = log.records
    assert (record.provider, record.model, record.prompt_version) == ("openai", "my-model", "item-blind-v2")
    assert (record.tokens_in, record.tokens_out, record.http_status) == (1234, 56, 200)
    assert record.error_code is None
    assert (record.submission_id, record.paper_item_id, record.role) == (submission, item, "primary")
    assert not set(type(record).__dataclass_fields__) & {"image", "crop", "answer", "text", "raw_text"}


def test_a_second_reader_is_recorded_as_a_second_opinion() -> None:
    first, log_a, _ = provider(FakeServer(ok()))
    second, log_b, _ = provider(FakeServer(ok()))

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
    assert len(server.posts) == 1
    assert info.raw_text == "cached"
    assert len(log.records) == 1


def test_a_page_of_questions_is_graded_concurrently_and_returned_in_order() -> None:
    answers = ["ii", "3", "1", "ii", "2", "3"]

    def handler(request: httpx.Request) -> httpx.Response:
        url = json.loads(request.content)["messages"][0]["content"][1]["image_url"]["url"]
        index = base64.b64decode(url.split(",", 1)[1])[-1]  # each crop ends with its own number
        reading = {"parts": [{"part": 1, "answer": answers[index], "confidence": 0.9}]}
        return httpx.Response(200, json=ok_body(reading))

    p = OpenAIProvider(SECRET, "my-model", client=httpx.Client(transport=httpx.MockTransport(handler)))
    jobs = [ItemJob(KEY, PNG + bytes([i]), "si") for i in range(len(answers))]

    results = grade_items(jobs, p, workers=3)

    assert [r.question.parts[0].read_text for r in results] == answers  # same order as the jobs


# ---- the factory and the status page ----------------------------------------------------------


def settings(**overrides) -> Settings:
    return Settings(database_url="sqlite://", **overrides)


def test_the_factory_builds_openai_from_settings() -> None:
    p = create_vision_provider(
        settings(
            vision_provider="openai",
            openai_api_key=" sk-abc ",
            openai_model="my-model",
            openai_reasoning_effort="low",
            openai_temperature="0",
            openai_max_output_tokens=3000,
        )
    )

    assert p.name == "openai" and p.model == "my-model"
    assert p.reasoning_effort == "low" and p.temperature == 0.0 and p.max_output_tokens == 3000


def test_the_factory_refuses_openai_without_a_key_or_a_model() -> None:
    with pytest.raises(VisionNotConfigured, match="OPENAI_API_KEY"):
        create_vision_provider(settings(vision_provider="openai", openai_api_key="", openai_model="m"))
    with pytest.raises(VisionNotConfigured, match="OPENAI_MODEL"):
        create_vision_provider(settings(vision_provider="openai", openai_api_key="sk-abc", openai_model=""))
    with pytest.raises(VisionNotConfigured, match="OPENAI_TEMPERATURE"):
        create_vision_provider(
            settings(vision_provider="openai", openai_api_key="sk-abc", openai_model="m", openai_temperature="hot")
        )


def test_openai_can_be_the_second_reader_while_gemini_stays_the_first() -> None:
    first = create_vision_provider(
        settings(vision_provider="gemini", gemini_api_key="g", gemini_model="gemini-2.5-flash")
    )
    second = create_vision_provider(
        settings(openai_api_key="sk-abc", openai_model="my-model"), "openai"
    )

    assert (first.name, second.name) == ("gemini", "openai")


def test_an_unknown_name_lists_the_readers_that_exist() -> None:
    with pytest.raises(VisionNotConfigured, match="openai"):
        create_vision_provider(settings(vision_provider="groq"))
