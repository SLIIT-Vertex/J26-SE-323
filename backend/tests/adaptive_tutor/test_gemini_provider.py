from types import SimpleNamespace

import pytest

from app.adaptive_tutor.application import (
    DeterministicFakeLlmProvider,
    GenerationPrompt,
    GenerationRequest,
    GenerationStatus,
    LlmProviderError,
    generate_tutor_draft,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure import (
    GeminiConfigurationError,
    GeminiGenerationConfig,
    GeminiLlmProvider,
    select_tutor_llm_provider,
)
from app.config import Settings


class RecordingModels:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class RecordingClient:
    def __init__(self, outcome: object) -> None:
        self.models = RecordingModels(outcome)


class SdkError(Exception):
    def __init__(self, code: int, message: str = "provider detail") -> None:
        super().__init__(message)
        self.code = code


class MalformedResponse:
    @property
    def text(self) -> str:
        raise ValueError("response has no text part")


def gemini_config(**overrides: object) -> GeminiGenerationConfig:
    values: dict[str, object] = {
        "api_key": "synthetic-test-key",
        "model": "synthetic-gemini-model",
        "timeout_seconds": 12.0,
        "max_output_tokens": 321,
        "temperature": 0.15,
    }
    values.update(overrides)
    return GeminiGenerationConfig(**values)  # type: ignore[arg-type]


def prompt_for(level: AssistanceLevel = AssistanceLevel.CONCEPTUAL_HINT) -> GenerationPrompt:
    return GenerationPrompt(
        assistance_level=level,
        system_instruction=f"The controller selected {level.value}; preserve it.",
        user_content='USER_DATA_JSON\n{"student_question":"Synthetic question"}',
    )


def request_for(level: AssistanceLevel = AssistanceLevel.CONCEPTUAL_HINT) -> GenerationRequest:
    return GenerationRequest(
        student_question="Synthetic fractions question",
        skill_id="MAT-FRC",
        assistance_level=level,
        response_language="en",
        grade=4,
    )


def settings_for(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite://",
        "tutor_llm_provider": "gemini",
        "tutor_gemini_api_key": "synthetic-test-key",
        "tutor_gemini_model": "synthetic-gemini-model",
        "tutor_gemini_timeout_seconds": 12.0,
        "tutor_gemini_max_output_tokens": 321,
        "tutor_gemini_temperature": 0.15,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_success_uses_existing_generation_contract() -> None:
    client = RecordingClient(SimpleNamespace(text="A concise synthetic hint."))
    provider = GeminiLlmProvider(gemini_config(), client=client)

    result = generate_tutor_draft(request_for(), provider)

    assert result.status is GenerationStatus.DRAFT_GENERATED
    assert result.draft_text == "A concise synthetic hint."
    assert result.assistance_level is AssistanceLevel.CONCEPTUAL_HINT
    assert result.provider_name == "google-gemini"
    assert result.verified is False


def test_prompt_model_and_generation_controls_are_forwarded() -> None:
    client = RecordingClient(SimpleNamespace(text="Synthetic response"))
    provider = GeminiLlmProvider(gemini_config(), client=client)
    prompt = prompt_for()

    provider.generate(prompt)

    assert client.models.calls == [
        {
            "model": "synthetic-gemini-model",
            "contents": prompt.user_content,
            "config": {
                "system_instruction": prompt.system_instruction,
                "temperature": 0.15,
                "max_output_tokens": 321,
            },
        }
    ]


@pytest.mark.parametrize("level", list(AssistanceLevel))
def test_adapter_preserves_every_controller_selected_level(level: AssistanceLevel) -> None:
    client = RecordingClient(SimpleNamespace(text="Synthetic response"))
    provider = GeminiLlmProvider(gemini_config(), client=client)
    prompt = prompt_for(level)

    provider.generate(prompt)

    call = client.models.calls[0]
    assert f"selected {level.value}" in call["config"]["system_instruction"]  # type: ignore[index]
    assert prompt.assistance_level is level


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (TimeoutError("secret timeout detail"), GenerationStatus.PROVIDER_UNAVAILABLE),
        (ConnectionError("secret network detail"), GenerationStatus.PROVIDER_UNAVAILABLE),
        (SdkError(401), GenerationStatus.PROVIDER_ERROR),
        (SdkError(403), GenerationStatus.PROVIDER_ERROR),
        (SdkError(429), GenerationStatus.PROVIDER_UNAVAILABLE),
        (SdkError(503), GenerationStatus.PROVIDER_UNAVAILABLE),
        (SdkError(500), GenerationStatus.PROVIDER_ERROR),
    ],
)
def test_provider_failures_map_to_existing_statuses(
    error: Exception, status: GenerationStatus
) -> None:
    client = RecordingClient(error)
    provider = GeminiLlmProvider(gemini_config(), client=client)

    result = generate_tutor_draft(request_for(), provider)

    assert result.status is status
    assert result.draft_text is None
    assert len(client.models.calls) == 1


@pytest.mark.parametrize("missing", [{"api_key": ""}, {"model": ""}])
def test_missing_gemini_configuration_is_unavailable_without_network(
    missing: dict[str, object],
) -> None:
    client = RecordingClient(SimpleNamespace(text="must not be used"))
    provider = GeminiLlmProvider(gemini_config(**missing), client=client)

    result = generate_tutor_draft(request_for(), provider)

    assert result.status is GenerationStatus.PROVIDER_UNAVAILABLE
    assert client.models.calls == []


@pytest.mark.parametrize("response", [SimpleNamespace(text=""), MalformedResponse(), object()])
def test_empty_or_malformed_response_uses_invalid_output_status(response: object) -> None:
    provider = GeminiLlmProvider(gemini_config(), client=RecordingClient(response))

    result = generate_tutor_draft(request_for(), provider)

    assert result.status is GenerationStatus.INVALID_PROVIDER_OUTPUT
    assert result.draft_text is None


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(
            text=None,
            prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
            candidates=[],
        ),
        SimpleNamespace(
            text=None,
            prompt_feedback=None,
            candidates=[SimpleNamespace(finish_reason="SAFETY")],
        ),
    ],
)
def test_safety_blocked_response_uses_provider_error(response: object) -> None:
    provider = GeminiLlmProvider(gemini_config(), client=RecordingClient(response))

    result = generate_tutor_draft(request_for(), provider)

    assert result.status is GenerationStatus.PROVIDER_ERROR
    assert result.draft_text is None


def test_api_key_is_redacted_from_representations_and_errors() -> None:
    secret = "do-not-expose-this-key"
    config = gemini_config(api_key=secret)
    provider = GeminiLlmProvider(
        config,
        client=RecordingClient(SdkError(401, f"request failed for key {secret}")),
    )

    with pytest.raises(LlmProviderError) as caught:
        provider.generate(prompt_for())

    assert secret not in repr(config)
    assert secret not in str(caught.value)


def test_explicit_provider_selection_has_no_silent_fallback() -> None:
    client = RecordingClient(SimpleNamespace(text="Synthetic response"))

    fake = select_tutor_llm_provider(settings_for(tutor_llm_provider="fake"))
    gemini = select_tutor_llm_provider(settings_for(), gemini_client=client)

    assert isinstance(fake, DeterministicFakeLlmProvider)
    assert isinstance(gemini, GeminiLlmProvider)
    with pytest.raises(GeminiConfigurationError, match="explicitly configured"):
        select_tutor_llm_provider(settings_for(tutor_llm_provider=""))
    with pytest.raises(GeminiConfigurationError, match="fake.*gemini"):
        select_tutor_llm_provider(settings_for(tutor_llm_provider="other"))


def test_fake_provider_remains_deterministic() -> None:
    provider = select_tutor_llm_provider(settings_for(tutor_llm_provider="fake"))

    first = generate_tutor_draft(request_for(), provider)
    second = generate_tutor_draft(request_for(), provider)

    assert first == second
    assert first.provider_name == "deterministic-fake-llm"


@pytest.mark.parametrize(
    "overrides",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": float("inf")},
        {"max_output_tokens": 0},
        {"temperature": -0.1},
        {"temperature": 1.1},
    ],
)
def test_invalid_generation_controls_fail_explicitly(overrides: dict[str, object]) -> None:
    with pytest.raises(GeminiConfigurationError):
        GeminiLlmProvider(gemini_config(**overrides))


def test_injected_client_makes_unit_test_network_free() -> None:
    client = RecordingClient(SimpleNamespace(text="Synthetic response"))

    def unexpected_factory(_config: GeminiGenerationConfig) -> object:
        raise AssertionError("network client factory must not run")

    provider = GeminiLlmProvider(
        gemini_config(),
        client=client,
        client_factory=unexpected_factory,
    )

    assert provider.generate(prompt_for()) == "Synthetic response"


def test_lazy_client_factory_receives_configured_timeout() -> None:
    client = RecordingClient(SimpleNamespace(text="Synthetic response"))
    created_with: list[GeminiGenerationConfig] = []

    def recording_factory(config: GeminiGenerationConfig) -> RecordingClient:
        created_with.append(config)
        return client

    config = gemini_config(timeout_seconds=7.5)
    provider = GeminiLlmProvider(config, client_factory=recording_factory)

    assert provider.generate(prompt_for()) == "Synthetic response"
    assert created_with == [config]
    assert created_with[0].timeout_seconds == 7.5
