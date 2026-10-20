from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

import httpx

from app.adaptive_tutor.application.generation import (
    DeterministicFakeLlmProvider,
    GenerationPrompt,
    LlmProvider,
    LlmProviderError,
    LlmProviderUnavailableError,
    ProviderFailureReason,
)
from app.config import Settings

_TIMEOUT_STATUS_CODES = frozenset({408, 504})
_RATE_LIMIT_STATUS_CODES = frozenset({429})
_UNAVAILABLE_STATUS_CODES = frozenset({502, 503})
_AUTH_STATUS_CODES = frozenset({401, 403})
_NOT_FOUND_STATUS_CODES = frozenset({404})
_INVALID_REQUEST_STATUS_CODES = frozenset({400, 422})
# Gemini reports a rejected API key as HTTP 400 INVALID_ARGUMENT with this ErrorInfo reason.
_AUTH_ERROR_REASONS = frozenset({"API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED"})
_BLOCKED_FINISH_REASONS = frozenset(
    {
        "BLOCKLIST",
        "CONTENT_BLOCKED",
        "IMAGE_PROHIBITED_CONTENT",
        "IMAGE_RECITATION",
        "IMAGE_SAFETY",
        "LANGUAGE",
        "PROHIBITED_CONTENT",
        "RECITATION",
        "SAFETY",
        "SPII",
    }
)
_UNSPECIFIED_BLOCK_REASONS = frozenset({"", "BLOCK_REASON_UNSPECIFIED", "UNSPECIFIED"})
_THINKING_LEVELS = frozenset({"MINIMAL", "LOW", "MEDIUM", "HIGH"})


class GeminiConfigurationError(ValueError):
    """Gemini generation configuration is invalid or provider selection is absent."""


@dataclass(frozen=True, slots=True)
class GeminiGenerationConfig:
    """Non-secret generation controls plus an API key excluded from representations."""

    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 30.0
    max_output_tokens: int = 512
    temperature: float = 0.2
    thinking_level: str = ""

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiGenerationConfig":
        config = cls(
            api_key=settings.tutor_gemini_api_key.strip(),
            model=settings.tutor_gemini_model.strip(),
            timeout_seconds=settings.tutor_gemini_timeout_seconds,
            max_output_tokens=settings.tutor_gemini_max_output_tokens,
            temperature=settings.tutor_gemini_temperature,
            thinking_level=settings.tutor_gemini_thinking_level.strip().upper(),
        )
        config.validate_controls()
        return config

    def validate_controls(self) -> None:
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise GeminiConfigurationError("Gemini timeout must be greater than zero")
        if self.max_output_tokens < 1:
            raise GeminiConfigurationError("Gemini max output tokens must be positive")
        if not isfinite(self.temperature) or not 0 <= self.temperature <= 1:
            raise GeminiConfigurationError("Gemini temperature must be between 0 and 1")
        if self.thinking_level and self.thinking_level not in _THINKING_LEVELS:
            raise GeminiConfigurationError(
                "Gemini thinking level must be blank, MINIMAL, LOW, MEDIUM or HIGH"
            )


class GeminiLlmProvider:
    """Synchronous google-genai adapter for the existing provider-neutral boundary."""

    name = "google-gemini"

    def __init__(
        self,
        config: GeminiGenerationConfig,
        *,
        client: Any | None = None,
        client_factory: Callable[[GeminiGenerationConfig], Any] | None = None,
    ) -> None:
        config.validate_controls()
        self.config = config
        self._client = client
        self._client_factory = client_factory or _create_google_genai_client

    def generate(self, prompt: GenerationPrompt) -> str:
        if not self.config.api_key:
            raise LlmProviderUnavailableError(
                "Gemini API key is not configured",
                reason=ProviderFailureReason.PROVIDER_NOT_CONFIGURED,
            )
        if not self.config.model:
            raise LlmProviderUnavailableError(
                "Gemini model is not configured",
                reason=ProviderFailureReason.PROVIDER_NOT_CONFIGURED,
            )

        generation_config: dict[str, object] = {
            "system_instruction": prompt.system_instruction,
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }
        if self.config.thinking_level:
            generation_config["thinking_config"] = {"thinking_level": self.config.thinking_level}

        try:
            client = self._client or self._client_factory(self.config)
            response = client.models.generate_content(
                model=self.config.model,
                contents=prompt.user_content,
                config=generation_config,
            )
        except Exception as error:  # noqa: BLE001 - normalize third-party SDK failures
            _raise_provider_error(error)

        if _response_was_blocked(response):
            raise LlmProviderError(
                "Gemini blocked the response", reason=ProviderFailureReason.RESPONSE_BLOCKED
            )
        return _response_text(response)


def select_tutor_llm_provider(
    settings: Settings,
    *,
    gemini_client: Any | None = None,
) -> LlmProvider:
    """Select exactly one configured provider; never fall back implicitly."""

    selection = settings.tutor_llm_provider.strip().casefold()
    if selection == "fake":
        return DeterministicFakeLlmProvider()
    if selection == "gemini":
        return GeminiLlmProvider(
            GeminiGenerationConfig.from_settings(settings),
            client=gemini_client,
        )
    if not selection:
        raise GeminiConfigurationError("TUTOR_LLM_PROVIDER must be explicitly configured")
    raise GeminiConfigurationError("TUTOR_LLM_PROVIDER must be 'fake' or 'gemini'")


def _create_google_genai_client(config: GeminiGenerationConfig) -> Any:
    try:
        from google import genai
    except ImportError as error:
        # Another google-* package can provide the `google` namespace without `genai`, which
        # raises a plain ImportError rather than ModuleNotFoundError.
        raise LlmProviderUnavailableError(
            "Install the backend 'gemini' extra to use Gemini generation",
            reason=ProviderFailureReason.PROVIDER_SDK_NOT_INSTALLED,
        ) from error

    return genai.Client(
        api_key=config.api_key,
        http_options={
            "timeout": round(config.timeout_seconds * 1_000),
            "retry_options": {"attempts": 1},
        },
    )


def _raise_provider_error(error: Exception) -> None:
    if isinstance(error, LlmProviderError):
        raise error
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        raise LlmProviderUnavailableError(
            "Gemini request timed out", reason=ProviderFailureReason.NETWORK_OR_TIMEOUT
        ) from None
    if isinstance(error, (ConnectionError, httpx.TransportError)):
        raise LlmProviderUnavailableError(
            "Gemini network request failed", reason=ProviderFailureReason.NETWORK_OR_TIMEOUT
        ) from None

    status_code = _status_code(error)
    if status_code in _TIMEOUT_STATUS_CODES:
        raise LlmProviderUnavailableError(
            "Gemini request timed out", reason=ProviderFailureReason.NETWORK_OR_TIMEOUT
        ) from None
    if status_code in _RATE_LIMIT_STATUS_CODES:
        raise LlmProviderUnavailableError(
            "Gemini quota or rate limit reached", reason=ProviderFailureReason.RATE_LIMITED
        ) from None
    if status_code in _UNAVAILABLE_STATUS_CODES:
        raise LlmProviderUnavailableError("Gemini is temporarily unavailable") from None
    if status_code in _AUTH_STATUS_CODES or (
        status_code in _INVALID_REQUEST_STATUS_CODES and _has_auth_error_reason(error)
    ):
        raise LlmProviderError(
            "Gemini authentication failed", reason=ProviderFailureReason.AUTHENTICATION_FAILED
        ) from None
    if status_code in _NOT_FOUND_STATUS_CODES:
        raise LlmProviderError(
            "Gemini model was not found", reason=ProviderFailureReason.MODEL_NOT_FOUND
        ) from None
    if status_code in _INVALID_REQUEST_STATUS_CODES:
        raise LlmProviderError(
            "Gemini rejected the request", reason=ProviderFailureReason.INVALID_REQUEST
        ) from None
    raise LlmProviderError("Gemini provider request failed") from None


def _has_auth_error_reason(error: Exception) -> bool:
    details = getattr(error, "details", None)
    body = details.get("error") if isinstance(details, dict) else None
    entries = body.get("details") if isinstance(body, dict) else None
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(entry, dict) and entry.get("reason") in _AUTH_ERROR_REASONS for entry in entries
    )


def _status_code(error: Exception) -> int | None:
    for attribute in ("code", "status_code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _response_was_blocked(response: object) -> bool:
    prompt_feedback = getattr(response, "prompt_feedback", None)
    block_reason = _enum_name(getattr(prompt_feedback, "block_reason", None))
    if block_reason not in _UNSPECIFIED_BLOCK_REASONS:
        return True

    candidates = getattr(response, "candidates", ()) or ()
    return any(
        _enum_name(getattr(candidate, "finish_reason", None)) in _BLOCKED_FINISH_REASONS
        for candidate in candidates
    )


def _response_text(response: object) -> str:
    try:
        text = getattr(response, "text", "")
    except (AttributeError, TypeError, ValueError):
        return ""
    return text if isinstance(text, str) else ""


def _enum_name(value: object) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name.upper()
    return str(value).rsplit(".", maxsplit=1)[-1].upper()
