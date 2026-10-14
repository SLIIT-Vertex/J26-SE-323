import json

from app.adaptive_tutor.application import GenerationRequest, generate_tutor_draft
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure import GeminiLlmProvider, select_tutor_llm_provider
from app.config import get_settings

_SYNTHETIC_CASES = (
    (
        "L1-si",
        "භාග දෙකක් එකතු කරන්න මම මුලින්ම හිතන්න ඕන මොකක්ද?",
        AssistanceLevel.METACOGNITIVE_PROMPT,
        "si",
    ),
    (
        "L3-ta",
        "1/2 + 1/4 கணக்கில் அடுத்த படி என்ன?",
        AssistanceLevel.TARGETED_HINT,
        "ta",
    ),
    (
        "L5-en",
        "Can you show a different example like 1/2 + 1/4?",
        AssistanceLevel.SIMILAR_WORKED_EXAMPLE,
        "en",
    ),
)


def main() -> int:
    settings = get_settings()
    provider = select_tutor_llm_provider(settings)
    if not isinstance(provider, GeminiLlmProvider):
        raise TypeError("Set TUTOR_LLM_PROVIDER=gemini for the live smoke test")

    observations: list[dict[str, object]] = []
    for case_id, question, level, language in _SYNTHETIC_CASES:
        result = generate_tutor_draft(
            GenerationRequest(
                student_question=question,
                skill_id="MAT-FRC",
                assistance_level=level,
                response_language=language,
                grade=4,
            ),
            provider,
        )
        observations.append(
            {
                "case_id": case_id,
                "model": provider.config.model,
                "status": result.status,
                "assistance_level": result.assistance_level,
                "response_language": result.response_language,
                "observed_unverified_output": result.draft_text,
            }
        )

    print(json.dumps(observations, indent=2, ensure_ascii=False, default=str))
    return 0 if all(item["status"] == "DRAFT_GENERATED" for item in observations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
