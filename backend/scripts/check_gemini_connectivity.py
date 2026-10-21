"""Opt-in, single-call Gemini connectivity check with a fixed non-sensitive prompt.

Makes exactly one live request using the server-side TUTOR_GEMINI_* settings. Prints only the
model, outcome, sanitized reason code and the reply to the fixed prompt; never the API key.
"""

import json
import os

from app.adaptive_tutor.application import (
    GenerationPrompt,
    LlmProviderError,
    LlmProviderUnavailableError,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure import GeminiLlmProvider, select_tutor_llm_provider
from app.config import get_settings

_PROMPT = GenerationPrompt(
    assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
    system_instruction="This is a connectivity check. Reply with exactly one word.",
    user_content="Reply with the word: ready",
)


def main() -> int:
    if os.environ.get("GEMINI_CONNECTIVITY_CHECK_ENABLED", "").casefold() != "true":
        raise PermissionError(
            "set GEMINI_CONNECTIVITY_CHECK_ENABLED=true to permit one live Gemini request"
        )
    provider = select_tutor_llm_provider(get_settings())
    if not isinstance(provider, GeminiLlmProvider):
        raise TypeError("Set TUTOR_LLM_PROVIDER=gemini for the connectivity check")

    observation: dict[str, object] = {"model": provider.config.model}
    try:
        text = provider.generate(_PROMPT)
    except LlmProviderUnavailableError as error:
        observation.update(outcome="PROVIDER_UNAVAILABLE", reason_code=error.reason.value)
    except LlmProviderError as error:
        observation.update(outcome="PROVIDER_ERROR", reason_code=error.reason.value)
    else:
        if text.strip():
            observation.update(outcome="GENERATED", reply=text.strip()[:80])
        else:
            observation.update(outcome="INVALID_OUTPUT", reason_code="EMPTY_OR_MALFORMED_RESPONSE")

    print(json.dumps(observation, indent=2))
    return 0 if observation["outcome"] == "GENERATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
