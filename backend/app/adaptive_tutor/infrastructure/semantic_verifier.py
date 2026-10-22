"""Configured independent semantic-verifier adapter; disabled until explicitly authorized."""

import json
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from app.adaptive_tutor.application.generation import assistance_level_instruction
from app.adaptive_tutor.application.verification import (
    SemanticVerificationResult,
    SemanticVerifierError,
    SemanticVerifierUnavailableError,
    VerificationRequest,
)
from app.config import Settings


class StructuredSemanticClient(Protocol):
    def evaluate(self, *, system_instruction: str, user_content: str) -> str: ...


@dataclass(frozen=True, slots=True)
class SemanticVerifierProviderConfig:
    provider_name: str
    api_key: str
    base_url: str
    model: str
    version: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "SemanticVerifierProviderConfig":
        config = cls(
            provider_name=settings.tutor_semantic_verifier_provider.strip(),
            api_key=settings.tutor_semantic_verifier_api_key.strip(),
            base_url=settings.tutor_semantic_verifier_base_url.strip().rstrip("/"),
            model=settings.tutor_semantic_verifier_model.strip(),
            version=settings.tutor_semantic_verifier_version.strip(),
            timeout_seconds=settings.tutor_semantic_verifier_timeout_seconds,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not all((self.provider_name, self.api_key, self.base_url, self.model, self.version)):
            raise ValueError("semantic verifier provider configuration is incomplete")
        if not self.base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("semantic verifier URL must use HTTPS or an explicit local host")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("semantic verifier timeout must be greater than zero")


class OpenAICompatibleStructuredSemanticClient:
    """Minimal opt-in client; no request is made during construction."""

    def __init__(
        self,
        config: SemanticVerifierProviderConfig,
        *,
        client: Any | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._client = client

    def evaluate(self, *, system_instruction: str, user_content: str) -> str:
        client = self._client or httpx.Client(timeout=self._config.timeout_seconds)
        close = self._client is None
        try:
            response = client.post(
                f"{self._config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._config.model,
                    "temperature": 0,
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_content},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TypeError("semantic provider returned no content")
            return content
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise SemanticVerifierUnavailableError("semantic provider is unavailable") from error
        except (httpx.HTTPStatusError, KeyError, IndexError, TypeError, ValueError) as error:
            raise SemanticVerifierError("semantic provider response was invalid") from error
        finally:
            if close:
                client.close()


@dataclass(frozen=True, slots=True)
class ConfiguredSemanticVerifier:
    """Translate a provider's strict JSON result to the existing verifier protocol.

    Authorization and operational independence are explicit constructor controls. No
    production factory enables them, so merely configuring a client cannot authorize PASS.
    """

    client: StructuredSemanticClient
    model: str
    version: str
    provider_name: str = ""
    generator_provider_name: str = ""
    authorized_for_research: bool = False
    independent_from_generator: bool = False
    name: str = "configured-independent-semantic-verifier"

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.version.strip():
            raise ValueError("semantic verifier model and version are required")

    def verify(self, request: VerificationRequest) -> SemanticVerificationResult:
        independently_configured = (
            self.provider_name.strip()
            and self.generator_provider_name.strip()
            and self.provider_name.strip().casefold()
            != self.generator_provider_name.strip().casefold()
        )
        if (
            not self.authorized_for_research
            or not self.independent_from_generator
            or not independently_configured
        ):
            raise SemanticVerifierUnavailableError(
                "semantic verifier is not authorized as an independent research provider"
            )
        payload = {
            "student_question": request.student_question,
            "confirmed_skill_id": request.skill_id,
            "assistance_level": request.assistance_level.value,
            # The judge needs the level's meaning, not just its code, to rate compliance.
            "assistance_level_definition": assistance_level_instruction(request.assistance_level),
            "response_language": request.response_language,
            "grade": request.grade,
            "draft": request.response_text,
            "curriculum_evidence": [
                {
                    "chunk_id": passage.chunk.chunk_id,
                    "source_id": passage.source.source_id,
                    "source_version": passage.source.source_version,
                    "content": passage.chunk.content,
                }
                for passage in request.curriculum_evidence
            ],
        }
        system = (
            "Independently evaluate the draft. Return only JSON with PASS, FAIL, or "
            "INDETERMINATE for assistance_level_compliance, answer_leakage, factual_support, "
            "language_appropriateness, and age_appropriateness; also return reason_codes and "
            "evidence_references arrays. Never treat self-declared confidence as evidence."
        )
        try:
            raw = self.client.evaluate(
                system_instruction=system,
                user_content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
            parsed = json.loads(raw)
            result = SemanticVerificationResult.model_validate(parsed)
        except (TimeoutError, ConnectionError) as error:
            raise SemanticVerifierUnavailableError("semantic provider is unavailable") from error
        except (json.JSONDecodeError, TypeError, ValidationError) as error:
            raise SemanticVerifierError(
                "semantic provider returned invalid structured output"
            ) from error
        except (SemanticVerifierUnavailableError, SemanticVerifierError):
            raise
        except Exception as error:
            raise SemanticVerifierError("semantic provider request failed") from error
        return result.model_copy(
            update={"verifier_model": self.model, "verifier_version": self.version}
        )


def build_semantic_verifier_from_settings(
    settings: Settings,
    *,
    generator_provider_name: str,
    client: Any | None = None,
) -> ConfiguredSemanticVerifier:
    """Build only when live research verification is explicitly enabled."""

    if not settings.tutor_semantic_verifier_enabled:
        raise SemanticVerifierUnavailableError("semantic verifier is disabled")
    config = SemanticVerifierProviderConfig.from_settings(settings)
    return ConfiguredSemanticVerifier(
        client=OpenAICompatibleStructuredSemanticClient(config, client=client),
        model=config.model,
        version=config.version,
        provider_name=config.provider_name,
        generator_provider_name=generator_provider_name,
        authorized_for_research=True,
        independent_from_generator=settings.tutor_semantic_verifier_independent,
    )
