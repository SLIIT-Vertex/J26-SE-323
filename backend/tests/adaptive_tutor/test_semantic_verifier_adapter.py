import json
from dataclasses import dataclass

import pytest

from app.adaptive_tutor.application import (
    SemanticVerifierError,
    SemanticVerifierUnavailableError,
    VerificationCheckOutcome,
    VerificationRequest,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure import ConfiguredSemanticVerifier
from app.adaptive_tutor.infrastructure.semantic_verifier import (
    build_semantic_verifier_from_settings,
)
from app.config import Settings


@dataclass
class RecordingClient:
    response: str
    calls: int = 0
    user_content: str | None = None

    def evaluate(self, *, system_instruction: str, user_content: str) -> str:
        assert "Independently evaluate" in system_instruction
        self.calls += 1
        self.user_content = user_content
        return self.response


def _request() -> VerificationRequest:
    return VerificationRequest(
        student_question="How do I compare fractions?",
        skill_id="MAT-FRC",
        assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
        response_text="Think about equal-sized parts.",
        response_language="en",
        grade=4,
    )


def _response() -> str:
    return json.dumps(
        {
            "assistance_level_compliance": "PASS",
            "answer_leakage": "PASS",
            "factual_support": "NOT_APPLICABLE",
            "language_appropriateness": "PASS",
            "age_appropriateness": "PASS",
            "reason_codes": ["LEVEL_MATCHES"],
            "evidence_references": [],
        }
    )


def test_configured_adapter_requires_authorization_and_independence() -> None:
    client = RecordingClient(_response())

    for authorized, independent in ((False, True), (True, False)):
        verifier = ConfiguredSemanticVerifier(
            client,
            model="mock-verifier",
            version="v1",
            provider_name="independent-verifier",
            generator_provider_name="generator",
            authorized_for_research=authorized,
            independent_from_generator=independent,
        )
        with pytest.raises(SemanticVerifierUnavailableError):
            verifier.verify(_request())
    assert client.calls == 0


def test_configured_adapter_parses_strict_structured_result_with_metadata() -> None:
    client = RecordingClient(_response())
    verifier = ConfiguredSemanticVerifier(
        client,
        model="mock-verifier",
        version="v1",
        provider_name="independent-verifier",
        generator_provider_name="generator",
        authorized_for_research=True,
        independent_from_generator=True,
    )

    result = verifier.verify(_request())

    assert result.assistance_level_compliance is VerificationCheckOutcome.PASS
    assert result.verifier_model == "mock-verifier"
    assert result.verifier_version == "v1"
    assert client.calls == 1
    assert client.user_content is not None
    assert "learner_id" not in client.user_content


def test_malformed_semantic_output_never_becomes_a_judgment() -> None:
    verifier = ConfiguredSemanticVerifier(
        RecordingClient("not json"),
        model="mock-verifier",
        version="v1",
        provider_name="independent-verifier",
        generator_provider_name="generator",
        authorized_for_research=True,
        independent_from_generator=True,
    )

    with pytest.raises(SemanticVerifierError):
        verifier.verify(_request())


def test_same_or_undeclared_provider_cannot_claim_independence() -> None:
    for provider, generator in (("same-provider", "same-provider"), ("", "generator")):
        verifier = ConfiguredSemanticVerifier(
            RecordingClient(_response()),
            model="mock-verifier",
            version="v1",
            provider_name=provider,
            generator_provider_name=generator,
            authorized_for_research=True,
            independent_from_generator=True,
        )
        with pytest.raises(SemanticVerifierUnavailableError):
            verifier.verify(_request())


def test_live_factory_is_opt_in_and_enforces_provider_separation() -> None:
    with pytest.raises(SemanticVerifierUnavailableError, match="disabled"):
        build_semantic_verifier_from_settings(
            Settings(database_url="sqlite://"),
            generator_provider_name="google-gemini",
        )

    verifier = build_semantic_verifier_from_settings(
        Settings(
            database_url="sqlite://",
            tutor_semantic_verifier_enabled=True,
            tutor_semantic_verifier_provider="google-gemini",
            tutor_semantic_verifier_api_key="server-secret",
            tutor_semantic_verifier_base_url="https://verifier.example/v1",
            tutor_semantic_verifier_model="independent-model",
            tutor_semantic_verifier_version="2026-10-19",
            tutor_semantic_verifier_independent=True,
        ),
        generator_provider_name="google-gemini",
        client=object(),
    )
    with pytest.raises(SemanticVerifierUnavailableError, match="independent"):
        verifier.verify(_request())
