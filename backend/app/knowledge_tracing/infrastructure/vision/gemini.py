"""The Gemini reader: a cropped question picture in, a blind reading out.

Talks to the Gemini REST API with httpx (no vendor SDK). What it does around the call:

* blind prompt `item-blind-v2`, JSON output requested, reply validated and parsed;
* a rate limit or a server error is retried with back-off (4 s, 8 s ... at most 90 s, and the
  server's Retry-After is honoured);
* a HARD quota (a daily limit) is not retried: it fails at once so a parent is not left waiting;
* a model that was withdrawn (HTTP 404) switches once to the newest Gemini Flash and sets a
  warning, so the owner can pin a model;
* every HTTP attempt is recorded (time, tokens, status, error code, no image or text);
* a reading already paid for (same submission, question, model and prompt) is reused.

The API key goes in a request header, never in a URL, and is never logged.
"""

import base64
import logging
import re
import threading
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

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
HARD_QUOTA_MARKERS = ("limit: 0", "perday", "per day", "per_day", "tokens per day", "requests per day")
WARNING_AUTO_SWITCHED = "vision_model_auto_switched"
WARNING_NOT_PINNED = "vision_model_not_pinned"
WARNING_QUOTA = "vision_quota_exhausted"
_FLASH_MODEL = re.compile(r"^models/gemini-(\d+(?:\.\d+)?)-flash$")


def _mime_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class GeminiProvider:
    name = "gemini"
    prompt_version = PROMPT_VERSION

    def __init__(
        self,
        api_key: str,
        model: str = "",
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 90.0,
        max_output_tokens: int = 1024,
        max_tries: int = 5,
        backoff_base: float = 4.0,
        backoff_max: float = 90.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        call_log: CallLog | None = None,
        cache: ReadingCache | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for the gemini provider")
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.max_tries = max_tries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep
        self._call_log = call_log
        self._cache = cache
        self._lock = threading.Lock()
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

        if not self.model:
            self._choose_model(initial=True)

        started = time.perf_counter()
        prompt = blind_prompt(parts, language, blank_reference is not None)
        images = [crop] + ([blank_reference] if blank_reference else [])

        invalid_json_tries = 0
        while True:
            text, usage = self._generate(prompt, images)
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
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
            raw_text=text,
        )
        return reading, info

    # ---- one reply, with retries -----------------------------------------------------------

    def _generate(self, prompt: str, images: list[bytes]) -> tuple[str, dict]:
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                    + [
                        {
                            "inline_data": {
                                "mime_type": _mime_type(image),
                                "data": base64.b64encode(image).decode("ascii"),
                            }
                        }
                        for image in images
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        switched = False
        last_error: VisionError | None = None
        attempt = 0
        while attempt < self.max_tries:
            attempt += 1
            started = time.perf_counter()
            try:
                response = self._client.post(
                    f"{self.base_url}/v1beta/models/{self.model}:generateContent",
                    json=body,
                    headers={"x-goog-api-key": self._api_key},
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

            detail = self._error_text(response)
            if status == 404 and not switched:
                self._record(started=started, http_status=status, error_code="model_not_found")
                switched = True
                self._choose_model(initial=False)  # raises if there is nothing to switch to
                attempt -= 1  # switching the model is not a failed try
                continue
            if status == 404:
                self._record(started=started, http_status=status, error_code="model_not_found")
                raise VisionError("model_not_found", detail)
            if status == 429 and self._is_hard_quota(detail):
                self.warnings.add(WARNING_QUOTA)
                self._record(started=started, http_status=status, error_code="quota_daily")
                raise VisionError("quota_daily", detail)  # do not retry: fail fast
            if status in RETRYABLE_STATUSES:
                code = "rate_limit" if status == 429 else "server_error"
                self._record(started=started, http_status=status, error_code=code)
                last_error = VisionError(code, detail)
                self._wait(attempt, response.headers.get("retry-after"))
                continue
            if status in (400, 401, 403):
                code = "auth_failed" if "api key" in detail.lower() or status != 400 else "bad_request"
                self._record(started=started, http_status=status, error_code=code)
                raise VisionError(code, detail)
            self._record(started=started, http_status=status, error_code=f"http_{status}")
            raise VisionError(f"http_{status}", detail)

        raise last_error or VisionError("failed", "the reader could not be reached")

    def _read_success(self, response: httpx.Response, started: float) -> tuple[str, dict]:
        try:
            payload = response.json()
        except ValueError:
            self._record(started=started, http_status=200, error_code="invalid_json")
            raise VisionError("invalid_json", "the reply was not JSON") from None

        usage = payload.get("usageMetadata") or {}
        block = (payload.get("promptFeedback") or {}).get("blockReason")
        if block:
            self._record(started=started, http_status=200, error_code="blocked", usage=usage)
            raise VisionError("blocked", f"the picture was blocked: {block}")
        candidates = payload.get("candidates") or []
        pieces = [
            part.get("text", "")
            for candidate in candidates[:1]
            for part in (candidate.get("content") or {}).get("parts", [])
            if isinstance(part, dict)
        ]
        text = "".join(pieces).strip()
        if not text:
            reason = (candidates[0].get("finishReason") if candidates else None) or "no candidates"
            self._record(started=started, http_status=200, error_code="empty_reply", usage=usage)
            raise VisionError("empty_reply", str(reason))
        self._record(started=started, http_status=200, usage=usage)
        return text, usage

    # ---- model choice ------------------------------------------------------------------------

    def _choose_model(self, *, initial: bool) -> None:
        """Pick the newest Gemini Flash the key can use for generateContent."""
        with self._lock:
            response = self._client.get(
                f"{self.base_url}/v1beta/models",
                params={"pageSize": 200},
                headers={"x-goog-api-key": self._api_key},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise VisionError("model_not_found", f"could not list models: {response.status_code}")
            candidates: list[tuple[float, str]] = []
            for item in response.json().get("models", []):
                name = item.get("name", "")
                match = _FLASH_MODEL.match(name)
                if match and "generateContent" in item.get("supportedGenerationMethods", []):
                    candidates.append((float(match.group(1)), name.removeprefix("models/")))
            if not candidates:
                raise VisionError("model_not_found", "no gemini-*-flash model is available")
            chosen = max(candidates)[1]
            if chosen != self.model:
                logger.warning(
                    "vision model %r is not available; using %r. Pin GEMINI_MODEL to %r.",
                    self.model, chosen, chosen,
                )
            self.model = chosen
            self.warnings.add(WARNING_NOT_PINNED if initial else WARNING_AUTO_SWITCHED)

    # ---- small helpers -------------------------------------------------------------------------

    def _wait(self, attempt: int, retry_after: str | None) -> None:
        if attempt >= self.max_tries:
            return
        delay = min(self.backoff_max, self.backoff_base * (2 ** (attempt - 1)))
        if retry_after:
            try:
                delay = min(self.backoff_max, max(0.0, float(retry_after)))
            except ValueError:
                pass
        self._sleep(delay)

    @staticmethod
    def _error_text(response: httpx.Response) -> str:
        try:
            error = response.json().get("error", {})
            return str(error.get("message") or response.text)[:500]
        except (ValueError, AttributeError):
            return response.text[:500]

    @staticmethod
    def _is_hard_quota(detail: str) -> bool:
        lowered = detail.lower()
        return any(marker in lowered for marker in HARD_QUOTA_MARKERS)

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
                    tokens_in=usage.get("promptTokenCount"),
                    tokens_out=usage.get("candidatesTokenCount"),
                    http_status=http_status,
                    error_code=error_code,
                    submission_id=context.submission_id,
                    paper_item_id=context.paper_item_id,
                )
            )
        except Exception:
            logger.warning("could not record a vision call", exc_info=True)
