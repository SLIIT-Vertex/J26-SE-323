"""The OpenAI reader: a cropped question picture in, a blind reading out.

Talks to the Chat Completions API with httpx (no vendor SDK), so the same reader also works with any
server that speaks the same protocol (set OPENAI_BASE_URL). It does the same things around the call
as the Gemini reader, with the same blind prompt (`item-blind-v2`):

* JSON output is requested and the reply is validated and parsed;
* a rate limit or a server error is retried with back-off (the server's Retry-After is honoured);
* a HARD quota (no credit left, or a daily limit) is not retried: it fails at once, so a parent is
  not left waiting and the page can be tried again later;
* a setting the model does not accept (some models refuse `temperature` or `reasoning_effort`) is
  dropped and the call is repeated, so a new model name does not need a code change;
* every HTTP attempt is recorded (time, tokens, status, error code, no image or text);
* a reading already paid for (same submission, question, model and prompt) is reused.

The model name is never fixed in code: it comes from OPENAI_MODEL. The API key goes in a request
header, never in a URL, and is removed from any error text.
"""

import base64
import logging
import re
import time
from collections.abc import Callable, Sequence

import httpx

from app.knowledge_tracing.application.grading.call_log import (
    CallLog,
    CallRecord,
    ReadingCache,
    current_context,
)
from app.knowledge_tracing.application.grading.prompts import (
    PROMPT_VERSION,
    blind_prompt,
    parse_item_read,
)
from app.knowledge_tracing.application.grading.types import (
    CallInfo,
    ItemRead,
    PartSpec,
    VisionError,
)

logger = logging.getLogger("mindbridge.vision")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
HARD_QUOTA_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "requests per day",
    "tokens per day",
    "billing_hard_limit",
)
WARNING_QUOTA = "vision_quota_exhausted"
_SECRET = re.compile(r"sk-[A-Za-z0-9_\-]{6,}")
_ADAPTABLE = ("temperature", "reasoning_effort", "response_format", "max_completion_tokens", "max_tokens")


def _mime_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class OpenAIProvider:
    name = "openai"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 90.0,
        max_output_tokens: int = 4096,
        image_detail: str = "high",
        reasoning_effort: str = "",
        temperature: float | None = None,
        max_tries: int = 5,
        backoff_base: float = 4.0,
        backoff_max: float = 90.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        call_log: CallLog | None = None,
        cache: ReadingCache | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        if not model:
            raise ValueError("OPENAI_MODEL is required for the openai provider")
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.image_detail = image_detail
        self.reasoning_effort = reasoning_effort
        self.temperature = temperature
        self.max_tries = max_tries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep
        self._call_log = call_log
        self._cache = cache
        self.warnings: set[str] = set()

    # ---- public --------------------------------------------------------------------------

    def read_item(
        self,
        crop: bytes,
        parts: Sequence[PartSpec],
        language: str,
        blank_reference: bytes | None = None,
    ) -> tuple[ItemRead, CallInfo]:
        context = current_context()
        cache_key = None
        if self._cache is not None and context.submission_id and context.paper_item_id:
            cache_key = (
                context.submission_id,
                context.paper_item_id,
                context.role,
                self.name,
                self.model,
                self.prompt_version,
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached, CallInfo(latency_ms=0, raw_text="cached")

        started = time.perf_counter()
        prompt = blind_prompt(parts, language, blank_reference is not None)
        images = [crop] + ([blank_reference] if blank_reference else [])

        invalid_json_tries = 0
        while True:
            text, usage = self._complete(prompt, images)
            try:
                reading = parse_item_read(text)
            except VisionError as error:
                invalid_json_tries += 1
                self._record(error_code="invalid_json")
                if invalid_json_tries >= 2:  # one more try, then give up
                    raise error from None
                continue
            break

        if cache_key is not None and self._cache is not None:
            self._cache.put(cache_key, reading)
        info = CallInfo(
            latency_ms=round((time.perf_counter() - started) * 1000),
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
            raw_text=text,
        )
        return reading, info

    # ---- one reply, with retries -----------------------------------------------------------

    def _body(self, prompt: str, images: list[bytes]) -> dict:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image in images:
            data = base64.b64encode(image).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{_mime_type(image)};base64,{data}",
                        "detail": self.image_detail,
                    },
                }
            )
        body: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": self.max_output_tokens,
        }
        # Only sent when asked for: some models accept nothing but their own defaults.
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _complete(self, prompt: str, images: list[bytes]) -> tuple[str, dict]:
        body = self._body(prompt, images)
        last_error: VisionError | None = None
        attempt = 0
        adaptations = 0
        while attempt < self.max_tries:
            attempt += 1
            started = time.perf_counter()
            try:
                response = self._client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=self.timeout,
                )
            except httpx.TimeoutException:
                self._record(started=started, error_code="timeout")
                last_error = VisionError("timeout", "the reader did not answer in time")
                self._wait(attempt, None)
                continue
            except httpx.TransportError as error:
                self._record(started=started, error_code="network")
                last_error = VisionError("network", type(error).__name__)
                self._wait(attempt, None)
                continue

            status = response.status_code
            if status == 200:
                return self._read_success(response, started)

            error = self._error_object(response)
            detail = self._clean(str(error.get("message") or response.text)[:500])
            code_text = f"{error.get('code') or ''} {error.get('type') or ''} {detail}".lower()

            if status == 400 and adaptations < 4 and self._adapt(body, error):
                adaptations += 1
                attempt -= 1  # fixing a request the model refused is not a failed try
                continue
            if status == 404 or error.get("code") == "model_not_found":
                self._record(started=started, http_status=status, error_code="model_not_found")
                raise VisionError(
                    "model_not_found", f"{detail} (check OPENAI_MODEL: the key may not have this model)"
                )
            if status == 429 and any(marker in code_text for marker in HARD_QUOTA_MARKERS):
                self.warnings.add(WARNING_QUOTA)
                self._record(started=started, http_status=status, error_code="quota_daily")
                raise VisionError("quota_daily", detail)  # do not retry: fail fast
            if status in RETRYABLE_STATUSES:
                code = "rate_limit" if status == 429 else "server_error"
                self._record(started=started, http_status=status, error_code=code)
                last_error = VisionError(code, detail)
                self._wait(attempt, self._retry_after(response))
                continue
            if status in (401, 403):
                self._record(started=started, http_status=status, error_code="auth_failed")
                raise VisionError("auth_failed", detail)
            if status == 400:
                self._record(started=started, http_status=status, error_code="bad_request")
                raise VisionError("bad_request", detail)
            self._record(started=started, http_status=status, error_code=f"http_{status}")
            raise VisionError(f"http_{status}", detail)

        raise last_error or VisionError("failed", "the reader could not be reached")

    def _read_success(self, response: httpx.Response, started: float) -> tuple[str, dict]:
        try:
            payload = response.json()
        except ValueError:
            self._record(started=started, http_status=200, error_code="invalid_json")
            raise VisionError("invalid_json", "the reply was not JSON") from None

        usage = payload.get("usage") or {}
        choices = payload.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        finish = choice.get("finish_reason")
        if message.get("refusal") or finish == "content_filter":
            self._record(started=started, http_status=200, error_code="blocked", usage=usage)
            raise VisionError("blocked", "the picture was refused by the reader")

        content = message.get("content")
        if isinstance(content, list):  # some servers answer with a list of text parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        text = (content or "").strip()
        if not text:
            # "length" with nothing written: the model used its whole allowance thinking
            reason = finish or "no choices"
            self._record(started=started, http_status=200, error_code="empty_reply", usage=usage)
            raise VisionError("empty_reply", str(reason))
        self._record(started=started, http_status=200, usage=usage)
        return text, usage

    # ---- small helpers -------------------------------------------------------------------------

    @staticmethod
    def _adapt(body: dict, error: dict) -> bool:
        """Drop or rename the one setting the model refused. True if the request was changed."""
        param = str(error.get("param") or "")
        message = str(error.get("message") or "").lower()
        if param not in _ADAPTABLE:
            param = next((p for p in _ADAPTABLE if f"'{p}'" in message), "")
        if not param or param not in body:
            return False
        if param == "max_completion_tokens":
            body["max_tokens"] = body.pop("max_completion_tokens")
        elif param == "max_tokens":
            body["max_completion_tokens"] = body.pop("max_tokens")
        else:
            del body[param]
        return True

    def _wait(self, attempt: int, retry_after: float | None) -> None:
        if attempt >= self.max_tries:
            return
        delay = min(self.backoff_max, self.backoff_base * (2 ** (attempt - 1)))
        if retry_after is not None:
            delay = min(self.backoff_max, max(0.0, retry_after))
        self._sleep(delay)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        for header, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
            value = response.headers.get(header)
            if value:
                try:
                    return float(value) * scale
                except ValueError:
                    continue
        return None

    @staticmethod
    def _error_object(response: httpx.Response) -> dict:
        try:
            error = response.json().get("error", {})
            return error if isinstance(error, dict) else {"message": str(error)}
        except (ValueError, AttributeError):
            return {"message": response.text[:500]}

    def _clean(self, text: str) -> str:
        """No part of the key, and nothing that looks like one, ever leaves in an error."""
        return _SECRET.sub("***", text.replace(self._api_key, "***"))

    def _record(
        self,
        *,
        started: float | None = None,
        http_status: int | None = None,
        error_code: str | None = None,
        usage: dict | None = None,
    ) -> None:
        if self._call_log is None:
            return
        context = current_context()
        usage = usage or {}
        try:
            self._call_log.record(
                CallRecord(
                    provider=self.name,
                    model=self.model,
                    prompt_version=self.prompt_version,
                    role=context.role,
                    latency_ms=None if started is None else round((time.perf_counter() - started) * 1000),
                    tokens_in=usage.get("prompt_tokens"),
                    tokens_out=usage.get("completion_tokens"),
                    http_status=http_status,
                    error_code=error_code,
                    submission_id=context.submission_id,
                    paper_item_id=context.paper_item_id,
                )
            )
        except Exception:
            logger.warning("could not record a vision call", exc_info=True)
