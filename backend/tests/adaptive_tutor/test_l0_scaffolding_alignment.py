"""Regression tests for L0 over-assistance seen in the PP1 live run 2026-10-21T154841.

These verify prompts and deterministic detection only. They cannot show that Gemini will now
comply; that needs a new bounded live run and independent review.
"""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adaptive_tutor.application.generation import (
    GenerationRequest,
    assistance_level_instruction,
    build_generation_prompt,
)
from app.adaptive_tutor.application.verification import (
    VerificationCheckName,
    VerificationCheckOutcome,
    VerificationOutcome,
    VerificationRequest,
    verify_response,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.adaptive_tutor.infrastructure import ConfiguredSemanticVerifier
from app.adaptive_tutor.infrastructure.gemini import GeminiGenerationConfig, GeminiLlmProvider
from app.adaptive_tutor.infrastructure.research_sessions import ExperimentalHintGenerator

QUESTION = "Why is 1/2 equal to 2/4?"
# Verbatim real Gemini drafts from the sanitized transcript (gemini-3.1-flash-lite, thinking LOW).
REAL_L0_OVER_ASSISTANCE = (
    "Think about what happens to a single whole object if you cut it into two equal pieces versus "
    "cutting it into four equal pieces. If you have one of the two pieces, how could you cut that "
    "same piece again to make it look like two of the four pieces? Try to draw a picture or use "
    "objects to show how the amount of the whole remains the same in both cases."
)
REAL_L2_COMPLIANT = (
    "Think about how the total number of pieces in a whole changes when you slice each existing "
    "piece into smaller, equal sections."
)
# The pre-change wording for every other level: L1–L6 semantics must stay byte-identical.
UNCHANGED_INSTRUCTIONS = {
    AssistanceLevel.METACOGNITIVE_PROMPT: (
        "Ask one concise metacognitive question about the learner's approach. Do not give a "
        "content hint, solution, or final answer."
    ),
    AssistanceLevel.CONCEPTUAL_HINT: (
        "Give one concise conceptual hint. Do not provide procedural steps, solve the current "
        "problem, or reveal its final answer."
    ),
    AssistanceLevel.TARGETED_HINT: (
        "Give one targeted hint about the next useful reasoning step. Do not complete the "
        "current problem or reveal its final answer."
    ),
    AssistanceLevel.GUIDED_STEPS: (
        "Guide only the next appropriate step, then pause for the learner. Do not finish the "
        "current problem or reveal its final answer."
    ),
    AssistanceLevel.SIMILAR_WORKED_EXAMPLE: (
        "Use a similar but different worked example and explain its steps. Keep the learner's "
        "current problem unsolved and do not reveal its final answer."
    ),
    AssistanceLevel.FULL_EXPLANATION: (
        "Give a clear, concise, age-appropriate full explanation grounded only in the supplied "
        "approved curriculum evidence."
    ),
}


def level_check(level: AssistanceLevel, text: str) -> VerificationCheckOutcome:
    result = verify_response(
        VerificationRequest(
            student_question=QUESTION,
            assistance_level=level,
            response_text=text,
            response_language="en",
            grade=5,
            skill_id="MAT-FRC",
        )
    )
    return next(
        check.outcome
        for check in result.checks
        if check.check is VerificationCheckName.LEVEL_STRUCTURE
    )


def test_real_l0_over_assistance_is_no_longer_structurally_accepted() -> None:
    assert level_check(AssistanceLevel.INDEPENDENT_RETRY, REAL_L0_OVER_ASSISTANCE) is (
        VerificationCheckOutcome.INDETERMINATE
    )
    result = verify_response(
        VerificationRequest(
            student_question=QUESTION,
            assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
            response_text=REAL_L0_OVER_ASSISTANCE,
            response_language="en",
            grade=5,
            skill_id="MAT-FRC",
        )
    )
    assert result.outcome is not VerificationOutcome.PASS


@pytest.mark.parametrize(
    "text",
    [
        "Have another go on your own, then tell me what you found.",
        "You can do this! Try it again by yourself.",
    ],
)
def test_neutral_encouragement_passes_the_l0_structure_check(text: str) -> None:
    assert level_check(AssistanceLevel.INDEPENDENT_RETRY, text) is VerificationCheckOutcome.PASS


@pytest.mark.parametrize(
    "text", ["Try 1/2 again on your own.", "Remember that 2 × 1 = 2. Try again!"]
)
def test_l0_with_numbers_or_notation_fails(text: str) -> None:
    assert level_check(AssistanceLevel.INDEPENDENT_RETRY, text) is VerificationCheckOutcome.FAIL


def test_short_l0_hint_in_words_is_a_known_deterministic_gap() -> None:
    # Documented limitation: a brief conceptual hint without notation is only catchable semantically.
    assert level_check(
        AssistanceLevel.INDEPENDENT_RETRY, "Think about cutting each half again."
    ) is (VerificationCheckOutcome.PASS)


def test_other_levels_keep_their_structure_semantics() -> None:
    assert (
        level_check(AssistanceLevel.CONCEPTUAL_HINT, REAL_L2_COMPLIANT)
        is VerificationCheckOutcome.PASS
    )
    assert level_check(AssistanceLevel.TARGETED_HINT, REAL_L0_OVER_ASSISTANCE) is (
        VerificationCheckOutcome.PASS
    )


def test_l0_instruction_allows_only_neutral_encouragement() -> None:
    instruction = assistance_level_instruction(AssistanceLevel.INDEPENDENT_RETRY)
    for forbidden in (
        "concepts",
        "strategies",
        "guiding questions",
        "steps",
        "formulas",
        "numbers",
    ):
        assert forbidden in instruction
    assert "intermediate results" in instruction and "final answer" in instruction
    prompt = build_generation_prompt(
        GenerationRequest(
            student_question=QUESTION,
            skill_id="MAT-FRC",
            assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
            response_language="en",
            grade=5,
        )
    )
    assert instruction in prompt.system_instruction


def test_l1_to_l6_instructions_are_unchanged() -> None:
    for level, text in UNCHANGED_INSTRUCTIONS.items():
        assert assistance_level_instruction(level) == text


class RecordingModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            text="Have another go on your own.", prompt_feedback=None, candidates=[]
        )


@pytest.mark.parametrize(
    ("level", "curriculum_sent"),
    [(AssistanceLevel.INDEPENDENT_RETRY, False), (AssistanceLevel.CONCEPTUAL_HINT, True)],
)
def test_experimental_l0_prompt_withholds_teaching_content(
    level: AssistanceLevel, curriculum_sent: bool
) -> None:
    models = RecordingModels()
    generator = ExperimentalHintGenerator(
        GeminiLlmProvider(
            GeminiGenerationConfig(api_key="test-key", model="gemini-test"),
            client=SimpleNamespace(models=models),
        ),
        "UNREVIEWED equivalent fractions: 1/2 = 2/4 because both name the same amount.",
        lambda _learner_id: 5,
    )

    generator.generate(
        learner_id=uuid4(),
        question=QUESTION,
        language="en",
        assistance_level=level,
        skill_id="MAT-FRC",
    )

    payload = json.loads(str(models.calls[0]["contents"]).split("\n", 1)[1])
    assert (payload["experimental_curriculum"] is not None) is curriculum_sent
    assert assistance_level_instruction(level) in str(models.calls[0]["config"])


def test_semantic_verifier_receives_the_level_definition() -> None:
    captured: dict[str, str] = {}

    class Client:
        def evaluate(self, *, system_instruction: str, user_content: str) -> str:
            captured["payload"] = user_content
            return json.dumps(
                {
                    "assistance_level_compliance": "FAIL",
                    "answer_leakage": "PASS",
                    "factual_support": "NOT_APPLICABLE",
                    "language_appropriateness": "PASS",
                    "age_appropriateness": "PASS",
                    "reason_codes": ["LEVEL_EXCEEDED"],
                    "evidence_references": [],
                }
            )

    verifier = ConfiguredSemanticVerifier(
        Client(),
        model="mock-verifier",
        version="v1",
        provider_name="independent-verifier",
        generator_provider_name="generator",
        authorized_for_research=True,
        independent_from_generator=True,
    )

    verifier.verify(
        VerificationRequest(
            student_question=QUESTION,
            assistance_level=AssistanceLevel.INDEPENDENT_RETRY,
            response_text=REAL_L0_OVER_ASSISTANCE,
            response_language="en",
            grade=5,
            skill_id="MAT-FRC",
        )
    )

    payload = json.loads(captured["payload"])
    assert payload["assistance_level"] == "L0"
    assert payload["assistance_level_definition"] == assistance_level_instruction(
        AssistanceLevel.INDEPENDENT_RETRY
    )
