from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from app.adaptive_tutor.application import (
    DeterministicFakeLlmProvider,
    DeterministicFakeSemanticVerifier,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    SemanticVerificationResult,
    SemanticVerifierUnavailableError,
    TrustedAnswerReference,
    VerificationCheckName,
    VerificationCheckOutcome,
    VerificationOutcome,
    VerificationReasonCode,
    VerificationRequest,
    generate_tutor_draft,
    verify_generation_result,
    verify_response,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.curriculum.application import (
    CurriculumChunk,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
)


def approved_passage() -> RetrievedCurriculumPassage:
    source = CurriculumSourceRecord(
        source_id="SYNTHETIC-SRC-001",
        title="Synthetic reviewed fractions source",
        publisher_authority="Synthetic test authority",
        grade=4,
        subject="Mathematics",
        language="en",
        source_type="synthetic-test-fixture",
        source_location="repository://synthetic/not-a-real-textbook.pdf",
        source_version="synthetic-v1",
        metadata_status=MetadataStatus.VERIFIED,
        ingestion_status=IngestionStatus.INGESTED,
        review_status=CurriculumReviewStatus.APPROVED,
        usage_rights_status=UsageRightsStatus.PERMITTED,
    )
    return RetrievedCurriculumPassage(
        chunk=CurriculumChunk(
            chunk_id="SYNTHETIC-SRC-001-C001",
            source_id=source.source_id,
            source_version="synthetic-v1",
            content="Fractions can be renamed as equivalent fractions before addition.",
            grade=4,
            subject="Mathematics",
            language="en",
            skill_ids=("MAT-FRC",),
            page_number=12,
            section_locator="Synthetic fractions section",
            review_status=CurriculumReviewStatus.APPROVED,
        ),
        source=source,
        score=1.0,
    )


def trusted_answer(*answers: str) -> TrustedAnswerReference:
    return TrustedAnswerReference(
        accepted_answers=answers or ("3/4",),
        provenance="synthetic teacher-authored fixture",
    )


def semantic_result(
    *,
    level: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
    leakage: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
    factual: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
    language: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
    age: VerificationCheckOutcome = VerificationCheckOutcome.PASS,
) -> SemanticVerificationResult:
    return SemanticVerificationResult(
        assistance_level_compliance=level,
        answer_leakage=leakage,
        factual_support=factual,
        language_appropriateness=language,
        age_appropriateness=age,
    )


def fake_semantic(**overrides: VerificationCheckOutcome) -> DeterministicFakeSemanticVerifier:
    return DeterministicFakeSemanticVerifier(result=semantic_result(**overrides))


def request_for(
    level: AssistanceLevel,
    response: str,
    *,
    language: str = "en",
    evidence: Sequence[RetrievedCurriculumPassage] = (),
    answer: TrustedAnswerReference | None = None,
) -> VerificationRequest:
    return VerificationRequest(
        student_question="What is 1/2 + 1/4?",
        assistance_level=level,
        response_text=response,
        response_language=language,
        grade=4,
        skill_id="MAT-FRC",
        curriculum_evidence=tuple(evidence),
        trusted_answer=answer,
    )


def check_outcome(result: object, name: VerificationCheckName) -> VerificationCheckOutcome:
    assert hasattr(result, "checks")
    return next(check.outcome for check in result.checks if check.check is name)


@pytest.mark.parametrize(
    ("level", "response"),
    [
        (AssistanceLevel.INDEPENDENT_RETRY, "Try it once yourself. What could you do first?"),
        (
            AssistanceLevel.METACOGNITIVE_PROMPT,
            "What strategy could help you compare the denominators?",
        ),
        (AssistanceLevel.CONCEPTUAL_HINT, "Think about making the parts the same size."),
        (
            AssistanceLevel.TARGETED_HINT,
            "Start by rewriting one half in quarters, then pause.",
        ),
        (
            AssistanceLevel.GUIDED_STEPS,
            "First rewrite one half as two quarters. What should you add next?",
        ),
        (
            AssistanceLevel.SIMILAR_WORKED_EXAMPLE,
            "For example, 1/3 + 1/6 becomes 2/6 + 1/6 = 3/6. Now try your problem.",
        ),
        (
            AssistanceLevel.FULL_EXPLANATION,
            "Rename 1/2 as 2/4. Then 2/4 + 1/4 = 3/4 because the parts now match.",
        ),
    ],
)
def test_design_authored_valid_case_for_every_level(level: AssistanceLevel, response: str) -> None:
    evidence = (approved_passage(),) if level is AssistanceLevel.FULL_EXPLANATION else ()
    answer = None if level is AssistanceLevel.FULL_EXPLANATION else trusted_answer("3/4")

    result = verify_response(
        request_for(level, response, evidence=evidence, answer=answer),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.PASS
    assert result.sufficient_evidence_for_pass is True


@pytest.mark.parametrize(
    ("level", "response", "evidence"),
    [
        (AssistanceLevel.INDEPENDENT_RETRY, "1. Add.\n2. Simplify.", ()),
        (AssistanceLevel.METACOGNITIVE_PROMPT, "1. Add.\n2. Simplify.", ()),
        (AssistanceLevel.CONCEPTUAL_HINT, "1. Add.\n2. Simplify.", ()),
        (AssistanceLevel.TARGETED_HINT, "1. Add.\n2. Simplify.", ()),
        (AssistanceLevel.GUIDED_STEPS, "The final answer is 3/4.", ()),
        (AssistanceLevel.SIMILAR_WORKED_EXAMPLE, "The final answer is 3/4.", ()),
        (
            AssistanceLevel.FULL_EXPLANATION,
            "The answer is 3/4.",
            (approved_passage(),),
        ),
    ],
)
def test_clear_structural_violation_for_every_level_fails(
    level: AssistanceLevel,
    response: str,
    evidence: tuple[RetrievedCurriculumPassage, ...],
) -> None:
    answer = None if level is AssistanceLevel.FULL_EXPLANATION else trusted_answer("3/4")
    result = verify_response(
        request_for(level, response, evidence=evidence, answer=answer),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.LEVEL_STRUCTURE_VIOLATION in result.reason_codes


@pytest.mark.parametrize(
    "response",
    [
        "The final answer is 3/4.",
        "The answer is 6/8.",
        "Work through it: 1/2 + 1/4 = 3/4.",
        "The result is 0.75.",
    ],
)
def test_direct_disguised_and_equivalent_answer_leakage_fails(response: str) -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.TARGETED_HINT,
            response,
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.TRUSTED_ANSWER_DISCLOSED in result.reason_codes


def test_normal_numbers_are_not_assumed_to_be_final_answer() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "Think about 3 groups and 4 equal parts before choosing a strategy.",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.PASS
    assert VerificationReasonCode.TRUSTED_ANSWER_NOT_DISCLOSED in result.reason_codes


def test_missing_trusted_answer_makes_l0_to_l5_leakage_indeterminate() -> None:
    result = verify_response(
        request_for(AssistanceLevel.CONCEPTUAL_HINT, "Think about equal-sized parts."),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.INDETERMINATE
    assert check_outcome(result, VerificationCheckName.ANSWER_LEAKAGE) is (
        VerificationCheckOutcome.INDETERMINATE
    )


@pytest.mark.parametrize(
    ("language", "response"),
    [
        ("si", "කොටස් එකම ප්‍රමාණයට පත් කරන්නේ කොහොමද කියලා සිතන්න."),
        ("ta", "பகுதிகளை ஒரே அளவாக மாற்றுவது எப்படி என்று சிந்தியுங்கள்."),
        ("en", "Think about making the parts equal."),
        ("si", "කොටස් equal කරන්න පුළුවන් කොහොමද කියලා සිතන්න."),
    ],
)
def test_sinhala_tamil_english_and_code_mixed_script_signals_pass(
    language: str, response: str
) -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            response,
            language=language,
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.PASS


def test_romanized_sinhala_is_uncertain_not_an_automatic_failure() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "Kotasa sama pramanayata karanna balanna.",
            language="si",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.INDETERMINATE
    assert check_outcome(result, VerificationCheckName.LANGUAGE_SCRIPT) is (
        VerificationCheckOutcome.INDETERMINATE
    )


def test_obvious_wrong_indic_script_fails_language_check() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "பகுதிகளை ஒரே அளவாக மாற்றுங்கள்.",
            language="si",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.LANGUAGE_SIGNAL_MISMATCH in result.reason_codes


@pytest.mark.parametrize("response", ["", "   ", "Valid text\x00hidden"])
def test_empty_or_malformed_response_fails(response: str) -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            response,
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert check_outcome(result, VerificationCheckName.RESPONSE_STRUCTURE) is (
        VerificationCheckOutcome.FAIL
    )


def test_oversized_response_fails() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "x" * 12_001,
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.RESPONSE_TOO_LONG in result.reason_codes


def test_obvious_unsafe_content_fails_closed() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "Send me your home address before I help with fractions.",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.OBVIOUS_UNSAFE_CONTENT in result.reason_codes


def test_l6_missing_curriculum_evidence_fails() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.FULL_EXPLANATION,
            "Rename the fractions, add them, and simplify the result.",
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.CURRICULUM_EVIDENCE_MISSING in result.reason_codes


def test_authoritative_claim_without_evidence_fails() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "According to the textbook, always add the denominators.",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.CURRICULUM_EVIDENCE_MISSING in result.reason_codes


def test_fabricated_source_or_page_citation_fails() -> None:
    passage = approved_passage()
    for response in (
        "According to Source: FAKE-SRC-999, rename the fraction.",
        "According to the textbook on page 99, rename the fraction.",
    ):
        result = verify_response(
            request_for(
                AssistanceLevel.FULL_EXPLANATION,
                response,
                evidence=(passage,),
            ),
            fake_semantic(),
        )

        assert result.outcome is VerificationOutcome.FAIL
        assert VerificationReasonCode.CURRICULUM_CITATION_UNSUPPORTED in result.reason_codes


def test_supported_citation_preserves_source_provenance() -> None:
    passage = approved_passage()
    result = verify_response(
        request_for(
            AssistanceLevel.FULL_EXPLANATION,
            "According to Source: SYNTHETIC-SRC-001 on page 12, rename equivalent fractions.",
            evidence=(passage,),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.PASS
    assert VerificationReasonCode.CURRICULUM_CITATION_SUPPORTED in result.reason_codes
    assert result.evidence_provenance[0].source_id == "SYNTHETIC-SRC-001"
    assert result.evidence_provenance[0].chunk_id == "SYNTHETIC-SRC-001-C001"
    assert result.evidence_provenance[0].page_number == 12


def test_serialized_evidence_cannot_claim_canonical_approval() -> None:
    with pytest.raises(ValidationError, match="canonical RetrievedCurriculumPassage"):
        VerificationRequest(
            student_question="What is 1/2 + 1/4?",
            assistance_level=AssistanceLevel.FULL_EXPLANATION,
            response_text="Explanation",
            response_language="en",
            grade=4,
            skill_id="MAT-FRC",
            curriculum_evidence=(approved_passage().model_dump(),),
        )


def test_semantic_verifier_absence_or_uncertainty_never_becomes_pass() -> None:
    request = request_for(
        AssistanceLevel.CONCEPTUAL_HINT,
        "Think about equal-sized parts.",
        answer=trusted_answer("3/4"),
    )

    unavailable = verify_response(request)
    uncertain = verify_response(
        request,
        fake_semantic(level=VerificationCheckOutcome.INDETERMINATE),
    )

    assert unavailable.outcome is VerificationOutcome.INDETERMINATE
    assert uncertain.outcome is VerificationOutcome.INDETERMINATE
    assert unavailable.sufficient_evidence_for_pass is False


class UnavailableSemanticVerifier:
    name = "unavailable-semantic-test-double"

    def verify(self, _request: VerificationRequest) -> SemanticVerificationResult:
        raise SemanticVerifierUnavailableError


def test_semantic_provider_failure_is_indeterminate() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "Think about equal-sized parts.",
            answer=trusted_answer("3/4"),
        ),
        UnavailableSemanticVerifier(),
    )

    assert result.outcome is VerificationOutcome.INDETERMINATE
    assert VerificationReasonCode.SEMANTIC_VERIFIER_UNAVAILABLE in result.reason_codes


def test_semantic_failure_rejects_deterministically_clean_response() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "Think about equal-sized parts.",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(age=VerificationCheckOutcome.FAIL),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.SEMANTIC_JUDGMENT_FAILED in result.reason_codes


def test_deterministic_failure_overrides_semantic_pass() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.CONCEPTUAL_HINT,
            "The answer is 3/4.",
            answer=trusted_answer("3/4"),
        ),
        fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL


def test_l6_semantic_factual_uncertainty_prevents_pass() -> None:
    result = verify_response(
        request_for(
            AssistanceLevel.FULL_EXPLANATION,
            "Rename equivalent fractions before adding them.",
            evidence=(approved_passage(),),
        ),
        fake_semantic(factual=VerificationCheckOutcome.INDETERMINATE),
    )

    assert result.outcome is VerificationOutcome.INDETERMINATE
    assert check_outcome(result, VerificationCheckName.SEMANTIC_FACTUAL_SUPPORT) is (
        VerificationCheckOutcome.INDETERMINATE
    )


def test_generation_handoff_preserves_unverified_draft_and_can_pass_separately() -> None:
    request = GenerationRequest(
        student_question="What is 1/2 + 1/4?",
        skill_id="MAT-FRC",
        assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
        response_language="en",
        grade=4,
    )
    generation = generate_tutor_draft(
        request,
        DeterministicFakeLlmProvider(response="Think about making the parts the same size."),
    )

    verification = verify_generation_result(
        request,
        generation,
        trusted_answer=trusted_answer("3/4"),
        semantic_verifier=fake_semantic(),
    )

    assert generation.verified is False
    assert verification.outcome is VerificationOutcome.PASS


@pytest.mark.parametrize(
    "status",
    [
        GenerationStatus.PROVIDER_UNAVAILABLE,
        GenerationStatus.PROVIDER_ERROR,
        GenerationStatus.INVALID_PROVIDER_OUTPUT,
    ],
)
def test_failed_generation_cannot_become_verified(status: GenerationStatus) -> None:
    request = GenerationRequest(
        student_question="What is 1/2 + 1/4?",
        skill_id="MAT-FRC",
        assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
        response_language="en",
        grade=4,
    )

    result = verify_generation_result(
        request,
        GenerationResult(
            status=status,
            assistance_level=request.assistance_level,
            response_language="en",
            provider_name="synthetic-failed-provider",
        ),
        trusted_answer=trusted_answer("3/4"),
        semantic_verifier=fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.GENERATION_NOT_AVAILABLE in result.reason_codes


def test_generation_context_mismatch_fails_before_semantic_verification() -> None:
    request = GenerationRequest(
        student_question="What is 1/2 + 1/4?",
        skill_id="MAT-FRC",
        assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
        response_language="en",
        grade=4,
    )
    generation = generate_tutor_draft(
        request,
        DeterministicFakeLlmProvider(response="Think about equal-sized parts."),
    ).model_copy(update={"assistance_level": AssistanceLevel.FULL_EXPLANATION})

    result = verify_generation_result(
        request,
        generation,
        trusted_answer=trusted_answer("3/4"),
        semantic_verifier=fake_semantic(),
    )

    assert result.outcome is VerificationOutcome.FAIL
    assert VerificationReasonCode.GENERATION_CONTEXT_MISMATCH in result.reason_codes


def test_contracts_reject_malformed_input_and_duplicate_trusted_answers() -> None:
    with pytest.raises(ValidationError):
        VerificationRequest(
            student_question="Question",
            assistance_level="L2",
            response_text=None,
            response_language="en",
            grade=4,
        )
    with pytest.raises(ValidationError, match="must be unique"):
        trusted_answer("3/4", " 3/4 ")
