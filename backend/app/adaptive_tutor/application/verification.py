import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Protocol, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.adaptive_tutor.application.generation import (
    MAX_PROVIDER_OUTPUT_CHARS,
    SUPPORTED_RESPONSE_LANGUAGES,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
)
from app.adaptive_tutor.domain import AssistanceLevel
from app.curriculum.application import Grade, RetrievedCurriculumPassage

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
AnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200, strict=True),
]
DiagnosticText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240, strict=True),
]


class VerificationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


class VerificationCheckOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VerificationCheckName(StrEnum):
    GENERATION_STATUS = "GENERATION_STATUS"
    RESPONSE_STRUCTURE = "RESPONSE_STRUCTURE"
    LEVEL_STRUCTURE = "LEVEL_STRUCTURE"
    ANSWER_LEAKAGE = "ANSWER_LEAKAGE"
    LANGUAGE_SCRIPT = "LANGUAGE_SCRIPT"
    CHILD_SAFETY = "CHILD_SAFETY"
    CURRICULUM_EVIDENCE = "CURRICULUM_EVIDENCE"
    CURRICULUM_CITATIONS = "CURRICULUM_CITATIONS"
    SEMANTIC_LEVEL_COMPLIANCE = "SEMANTIC_LEVEL_COMPLIANCE"
    SEMANTIC_ANSWER_LEAKAGE = "SEMANTIC_ANSWER_LEAKAGE"
    SEMANTIC_FACTUAL_SUPPORT = "SEMANTIC_FACTUAL_SUPPORT"
    SEMANTIC_LANGUAGE = "SEMANTIC_LANGUAGE"
    SEMANTIC_AGE_APPROPRIATENESS = "SEMANTIC_AGE_APPROPRIATENESS"


class VerificationReasonCode(StrEnum):
    GENERATION_NOT_AVAILABLE = "GENERATION_NOT_AVAILABLE"
    GENERATION_CONTEXT_MISMATCH = "GENERATION_CONTEXT_MISMATCH"
    RESPONSE_WELL_FORMED = "RESPONSE_WELL_FORMED"
    RESPONSE_EMPTY = "RESPONSE_EMPTY"
    RESPONSE_MALFORMED = "RESPONSE_MALFORMED"
    RESPONSE_TOO_LONG = "RESPONSE_TOO_LONG"
    LEVEL_STRUCTURE_COMPATIBLE = "LEVEL_STRUCTURE_COMPATIBLE"
    LEVEL_STRUCTURE_VIOLATION = "LEVEL_STRUCTURE_VIOLATION"
    LEVEL_COMPLIANCE_UNCERTAIN = "LEVEL_COMPLIANCE_UNCERTAIN"
    TRUSTED_ANSWER_NOT_REQUIRED = "TRUSTED_ANSWER_NOT_REQUIRED"
    TRUSTED_ANSWER_NOT_AVAILABLE = "TRUSTED_ANSWER_NOT_AVAILABLE"
    TRUSTED_ANSWER_NOT_DISCLOSED = "TRUSTED_ANSWER_NOT_DISCLOSED"
    TRUSTED_ANSWER_DISCLOSED = "TRUSTED_ANSWER_DISCLOSED"
    LANGUAGE_SIGNAL_COMPATIBLE = "LANGUAGE_SIGNAL_COMPATIBLE"
    LANGUAGE_SIGNAL_MISMATCH = "LANGUAGE_SIGNAL_MISMATCH"
    LANGUAGE_SIGNAL_UNCERTAIN = "LANGUAGE_SIGNAL_UNCERTAIN"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    NO_OBVIOUS_UNSAFE_CONTENT = "NO_OBVIOUS_UNSAFE_CONTENT"
    OBVIOUS_UNSAFE_CONTENT = "OBVIOUS_UNSAFE_CONTENT"
    CURRICULUM_EVIDENCE_NOT_REQUIRED = "CURRICULUM_EVIDENCE_NOT_REQUIRED"
    CURRICULUM_EVIDENCE_ELIGIBLE = "CURRICULUM_EVIDENCE_ELIGIBLE"
    CURRICULUM_EVIDENCE_MISSING = "CURRICULUM_EVIDENCE_MISSING"
    NO_CURRICULUM_CITATION = "NO_CURRICULUM_CITATION"
    CURRICULUM_CITATION_SUPPORTED = "CURRICULUM_CITATION_SUPPORTED"
    CURRICULUM_CITATION_UNSUPPORTED = "CURRICULUM_CITATION_UNSUPPORTED"
    SEMANTIC_JUDGMENT_PASSED = "SEMANTIC_JUDGMENT_PASSED"
    SEMANTIC_JUDGMENT_FAILED = "SEMANTIC_JUDGMENT_FAILED"
    SEMANTIC_JUDGMENT_INDETERMINATE = "SEMANTIC_JUDGMENT_INDETERMINATE"
    SEMANTIC_VERIFIER_UNAVAILABLE = "SEMANTIC_VERIFIER_UNAVAILABLE"


class TrustedAnswerReference(BaseModel):
    """Trusted accepted answer forms supplied by an upstream assessment owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_answers: tuple[AnswerText, ...] = Field(min_length=1, max_length=20)
    provenance: NonBlankText

    @model_validator(mode="after")
    def validate_unique_answers(self) -> Self:
        normalized = [_normalize_text(answer) for answer in self.accepted_answers]
        if len(normalized) != len(set(normalized)):
            raise ValueError("trusted accepted answers must be unique")
        return self


class VerificationRequest(BaseModel):
    """Inputs needed to verify one generated draft without selecting assistance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    student_question: NonBlankText
    assistance_level: AssistanceLevel
    response_text: Annotated[str, StringConstraints(strict=True)]
    response_language: NonBlankText
    grade: Grade
    skill_id: NonBlankText | None = None
    curriculum_evidence: tuple[RetrievedCurriculumPassage, ...] = Field(default=(), max_length=10)
    trusted_answer: TrustedAnswerReference | None = None

    @field_validator("curriculum_evidence", mode="before")
    @classmethod
    def require_canonical_evidence_instances(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, RetrievedCurriculumPassage) for item in value
        ):
            raise ValueError(
                "curriculum evidence must be canonical RetrievedCurriculumPassage instances"
            )
        return value

    @model_validator(mode="after")
    def validate_generation_context(self) -> Self:
        GenerationRequest(
            student_question=self.student_question,
            skill_id=self.skill_id,
            assistance_level=self.assistance_level,
            response_language=self.response_language,
            grade=self.grade,
            curriculum_evidence=self.curriculum_evidence,
        )
        return self


class EvidenceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    source_version: NonBlankText
    chunk_id: NonBlankText
    page_number: int | None = None


class VerificationCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check: VerificationCheckName
    outcome: VerificationCheckOutcome
    reason_codes: tuple[VerificationReasonCode, ...] = Field(min_length=1)
    diagnostic: DiagnosticText

    @model_validator(mode="after")
    def validate_reason_codes(self) -> Self:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("verification check reason codes must be unique")
        return self


class SemanticVerificationResult(BaseModel):
    """Provider-neutral judgments; these are not generation results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assistance_level_compliance: VerificationCheckOutcome
    answer_leakage: VerificationCheckOutcome
    factual_support: VerificationCheckOutcome
    language_appropriateness: VerificationCheckOutcome
    age_appropriateness: VerificationCheckOutcome


class SemanticVerifier(Protocol):
    name: str

    def verify(self, request: VerificationRequest) -> SemanticVerificationResult: ...


class SemanticVerifierError(RuntimeError):
    """An independent semantic verifier could not provide a trusted judgment."""


class SemanticVerifierUnavailableError(SemanticVerifierError):
    """The independent semantic verifier is unavailable."""


@dataclass(frozen=True, slots=True)
class DeterministicFakeSemanticVerifier:
    """Offline test double; configured judgments are not model evaluation."""

    result: SemanticVerificationResult
    name: str = "deterministic-fake-semantic-verifier"

    def verify(self, request: VerificationRequest) -> SemanticVerificationResult:
        return self.result


class VerificationResult(BaseModel):
    """Independent approval decision for a still-unverified generation draft."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: VerificationOutcome
    checks: tuple[VerificationCheckResult, ...] = Field(min_length=1)
    reason_codes: tuple[VerificationReasonCode, ...] = Field(min_length=1)
    sufficient_evidence_for_pass: bool
    evidence_provenance: tuple[EvidenceProvenance, ...] = ()
    semantic_verifier_name: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if len({check.check for check in self.checks}) != len(self.checks):
            raise ValueError("verification checks must be unique")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("verification result reason codes must be unique")
        observed_codes = {code for check in self.checks for code in check.reason_codes}
        if observed_codes != set(self.reason_codes):
            raise ValueError("result reason codes must summarize check reason codes")
        if self.sufficient_evidence_for_pass is not (self.outcome is VerificationOutcome.PASS):
            raise ValueError("only PASS has sufficient evidence for pass")
        if self.outcome is VerificationOutcome.PASS and any(
            check.outcome in {VerificationCheckOutcome.FAIL, VerificationCheckOutcome.INDETERMINATE}
            for check in self.checks
        ):
            raise ValueError("PASS cannot contain failed or indeterminate checks")
        return self


def verify_response(
    request: VerificationRequest,
    semantic_verifier: SemanticVerifier | None = None,
) -> VerificationResult:
    """Run deterministic checks, then optional independent semantic judgments."""

    checks = [
        _check_response_structure(request),
        _check_level_structure(request),
        _check_answer_leakage(request),
        _check_language_script(request),
        _check_child_safety(request),
        _check_curriculum_evidence(request),
        _check_curriculum_citations(request),
    ]
    checks.extend(_semantic_checks(request, semantic_verifier))
    return _build_result(
        checks,
        request.curriculum_evidence,
        semantic_verifier.name if semantic_verifier is not None else None,
    )


def verify_generation_result(
    generation_request: GenerationRequest,
    generation_result: GenerationResult,
    *,
    trusted_answer: TrustedAnswerReference | None = None,
    semantic_verifier: SemanticVerifier | None = None,
) -> VerificationResult:
    """Task 15 handoff: reject absent or context-mismatched generation before verification."""

    if generation_result.status is not GenerationStatus.DRAFT_GENERATED:
        return _build_result(
            [
                _check(
                    VerificationCheckName.GENERATION_STATUS,
                    VerificationCheckOutcome.FAIL,
                    VerificationReasonCode.GENERATION_NOT_AVAILABLE,
                    "No generated draft is available for verification.",
                )
            ],
            (),
            None,
        )

    if (
        generation_result.assistance_level is not generation_request.assistance_level
        or generation_result.response_language != generation_request.response_language
        or generation_result.curriculum_evidence != generation_request.curriculum_evidence
    ):
        return _build_result(
            [
                _check(
                    VerificationCheckName.GENERATION_STATUS,
                    VerificationCheckOutcome.FAIL,
                    VerificationReasonCode.GENERATION_CONTEXT_MISMATCH,
                    "The generated draft does not match its trusted generation context.",
                )
            ],
            (),
            None,
        )

    assert generation_result.draft_text is not None
    return verify_response(
        VerificationRequest(
            student_question=generation_request.student_question,
            assistance_level=generation_request.assistance_level,
            response_text=generation_result.draft_text,
            response_language=generation_request.response_language,
            grade=generation_request.grade,
            skill_id=generation_request.skill_id,
            curriculum_evidence=generation_result.curriculum_evidence,
            trusted_answer=trusted_answer,
        ),
        semantic_verifier,
    )


def _check_response_structure(request: VerificationRequest) -> VerificationCheckResult:
    text = request.response_text
    if not text.strip():
        return _check(
            VerificationCheckName.RESPONSE_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.RESPONSE_EMPTY,
            "The generated response is empty.",
        )
    if len(text) > MAX_PROVIDER_OUTPUT_CHARS:
        return _check(
            VerificationCheckName.RESPONSE_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.RESPONSE_TOO_LONG,
            "The generated response exceeds the configured size limit.",
        )
    if any(
        unicodedata.category(character) == "Cc" and character not in "\n\r\t" for character in text
    ):
        return _check(
            VerificationCheckName.RESPONSE_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.RESPONSE_MALFORMED,
            "The generated response contains invalid control characters.",
        )
    return _check(
        VerificationCheckName.RESPONSE_STRUCTURE,
        VerificationCheckOutcome.PASS,
        VerificationReasonCode.RESPONSE_WELL_FORMED,
        "The generated response is non-empty and structurally bounded.",
    )


def _check_level_structure(request: VerificationRequest) -> VerificationCheckResult:
    text = request.response_text
    level = request.assistance_level
    if level is not AssistanceLevel.FULL_EXPLANATION and _has_explicit_answer_disclosure(text):
        return _check(
            VerificationCheckName.LEVEL_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.LEVEL_STRUCTURE_VIOLATION,
            "The response contains an explicit answer disclosure prohibited at this level.",
        )
    numbered_steps = re.findall(r"(?m)^\s*(?:step\s*)?\d+[.)]\s+", text, re.IGNORECASE)
    if (
        level
        in {
            AssistanceLevel.INDEPENDENT_RETRY,
            AssistanceLevel.METACOGNITIVE_PROMPT,
            AssistanceLevel.CONCEPTUAL_HINT,
            AssistanceLevel.TARGETED_HINT,
        }
        and len(numbered_steps) >= 2
    ):
        return _check(
            VerificationCheckName.LEVEL_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.LEVEL_STRUCTURE_VIOLATION,
            "The response contains a multi-step solution structure prohibited at this level.",
        )
    if level is AssistanceLevel.METACOGNITIVE_PROMPT and "?" not in text:
        return _check(
            VerificationCheckName.LEVEL_STRUCTURE,
            VerificationCheckOutcome.INDETERMINATE,
            VerificationReasonCode.LEVEL_COMPLIANCE_UNCERTAIN,
            "A metacognitive question could not be established structurally.",
        )
    if level is AssistanceLevel.FULL_EXPLANATION and _is_answer_only(text):
        return _check(
            VerificationCheckName.LEVEL_STRUCTURE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.LEVEL_STRUCTURE_VIOLATION,
            "The response gives an answer without an instructional explanation.",
        )
    return _check(
        VerificationCheckName.LEVEL_STRUCTURE,
        VerificationCheckOutcome.PASS,
        VerificationReasonCode.LEVEL_STRUCTURE_COMPATIBLE,
        "No obvious structural conflict with the selected assistance level was detected.",
    )


def _check_answer_leakage(request: VerificationRequest) -> VerificationCheckResult:
    if request.assistance_level is AssistanceLevel.FULL_EXPLANATION:
        return _check(
            VerificationCheckName.ANSWER_LEAKAGE,
            VerificationCheckOutcome.NOT_APPLICABLE,
            VerificationReasonCode.TRUSTED_ANSWER_NOT_REQUIRED,
            "L6 permits the current final answer as part of a supported explanation.",
        )
    if request.trusted_answer is None:
        return _check(
            VerificationCheckName.ANSWER_LEAKAGE,
            VerificationCheckOutcome.INDETERMINATE,
            VerificationReasonCode.TRUSTED_ANSWER_NOT_AVAILABLE,
            "No trusted answer was supplied, so final-answer leakage is not fully checkable.",
        )
    if _trusted_answer_disclosed(request.response_text, request.trusted_answer.accepted_answers):
        return _check(
            VerificationCheckName.ANSWER_LEAKAGE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.TRUSTED_ANSWER_DISCLOSED,
            "A trusted accepted answer is disclosed in a final-answer context.",
        )
    return _check(
        VerificationCheckName.ANSWER_LEAKAGE,
        VerificationCheckOutcome.PASS,
        VerificationReasonCode.TRUSTED_ANSWER_NOT_DISCLOSED,
        "No obvious disclosure of a trusted accepted answer was detected.",
    )


def _check_language_script(request: VerificationRequest) -> VerificationCheckResult:
    language = request.response_language
    if language not in SUPPORTED_RESPONSE_LANGUAGES:
        return _check(
            VerificationCheckName.LANGUAGE_SCRIPT,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.UNSUPPORTED_LANGUAGE,
            "The requested response language is unsupported.",
        )

    counts = {
        "en": len(re.findall(r"[A-Za-z]", request.response_text)),
        "si": len(re.findall(r"[\u0D80-\u0DFF]", request.response_text)),
        "ta": len(re.findall(r"[\u0B80-\u0BFF]", request.response_text)),
    }
    if counts[language] > 0:
        return _check(
            VerificationCheckName.LANGUAGE_SCRIPT,
            VerificationCheckOutcome.PASS,
            VerificationReasonCode.LANGUAGE_SIGNAL_COMPATIBLE,
            "The response contains a script signal compatible with the requested language.",
        )
    if sum(counts.values()) == 0 or (language in {"si", "ta"} and counts["en"] > 0):
        return _check(
            VerificationCheckName.LANGUAGE_SCRIPT,
            VerificationCheckOutcome.INDETERMINATE,
            VerificationReasonCode.LANGUAGE_SIGNAL_UNCERTAIN,
            "Script signals alone cannot establish the requested language.",
        )
    return _check(
        VerificationCheckName.LANGUAGE_SCRIPT,
        VerificationCheckOutcome.FAIL,
        VerificationReasonCode.LANGUAGE_SIGNAL_MISMATCH,
        "The observed script conflicts with the requested language.",
    )


_UNSAFE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bkill yourself\b",
        r"\bhurt yourself\b",
        r"\bsend me your (?:home )?address\b",
        r"\bsend me your password\b",
        r"\bmeet me alone\b",
        r"\b(?:porn|pornographic)\b",
        r"\bexplicit sexual\b",
    )
)


def _check_child_safety(request: VerificationRequest) -> VerificationCheckResult:
    if any(pattern.search(request.response_text) for pattern in _UNSAFE_PATTERNS):
        return _check(
            VerificationCheckName.CHILD_SAFETY,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.OBVIOUS_UNSAFE_CONTENT,
            "The response contains an obvious child-safety violation.",
        )
    return _check(
        VerificationCheckName.CHILD_SAFETY,
        VerificationCheckOutcome.PASS,
        VerificationReasonCode.NO_OBVIOUS_UNSAFE_CONTENT,
        "No obvious deterministic child-safety violation was detected.",
    )


def _check_curriculum_evidence(request: VerificationRequest) -> VerificationCheckResult:
    if (
        request.assistance_level is AssistanceLevel.FULL_EXPLANATION
        and not request.curriculum_evidence
    ):
        return _check(
            VerificationCheckName.CURRICULUM_EVIDENCE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.CURRICULUM_EVIDENCE_MISSING,
            "L6 requires eligible approved curriculum evidence.",
        )
    if request.curriculum_evidence:
        return _check(
            VerificationCheckName.CURRICULUM_EVIDENCE,
            VerificationCheckOutcome.PASS,
            VerificationReasonCode.CURRICULUM_EVIDENCE_ELIGIBLE,
            "Canonical structurally eligible curriculum evidence was supplied.",
        )
    if _claims_curriculum_authority(request.response_text):
        return _check(
            VerificationCheckName.CURRICULUM_EVIDENCE,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.CURRICULUM_EVIDENCE_MISSING,
            "The response claims curriculum authority without supplied approved evidence.",
        )
    return _check(
        VerificationCheckName.CURRICULUM_EVIDENCE,
        VerificationCheckOutcome.NOT_APPLICABLE,
        VerificationReasonCode.CURRICULUM_EVIDENCE_NOT_REQUIRED,
        "No mandatory curriculum-evidence condition was detected.",
    )


_SOURCE_ID_PATTERN = re.compile(
    r"\bsource(?:\s+id|_id)?\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9_.:-]*)",
    re.IGNORECASE,
)
_BRACKET_SOURCE_PATTERN = re.compile(r"\[([A-Za-z][A-Za-z0-9_.:]*-[A-Za-z0-9_.:-]+)\]")
_PAGE_PATTERN = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)


def _check_curriculum_citations(request: VerificationRequest) -> VerificationCheckResult:
    cited_source_ids = set(_SOURCE_ID_PATTERN.findall(request.response_text))
    cited_source_ids.update(_BRACKET_SOURCE_PATTERN.findall(request.response_text))
    cited_pages = {int(page) for page in _PAGE_PATTERN.findall(request.response_text)}
    authority_claim = _claims_curriculum_authority(request.response_text)

    if not cited_source_ids and not cited_pages and not authority_claim:
        return _check(
            VerificationCheckName.CURRICULUM_CITATIONS,
            VerificationCheckOutcome.NOT_APPLICABLE,
            VerificationReasonCode.NO_CURRICULUM_CITATION,
            "The response makes no detectable curriculum citation.",
        )

    supplied_source_ids = {passage.source.source_id for passage in request.curriculum_evidence}
    supplied_pages = {
        passage.chunk.page_number
        for passage in request.curriculum_evidence
        if passage.chunk.page_number is not None
    }
    if (
        not request.curriculum_evidence
        or not cited_source_ids.issubset(supplied_source_ids)
        or not cited_pages.issubset(supplied_pages)
    ):
        return _check(
            VerificationCheckName.CURRICULUM_CITATIONS,
            VerificationCheckOutcome.FAIL,
            VerificationReasonCode.CURRICULUM_CITATION_UNSUPPORTED,
            "A detected curriculum citation is not supported by the supplied approved evidence.",
        )
    return _check(
        VerificationCheckName.CURRICULUM_CITATIONS,
        VerificationCheckOutcome.PASS,
        VerificationReasonCode.CURRICULUM_CITATION_SUPPORTED,
        "Detected curriculum citations correspond to supplied approved evidence.",
    )


_SEMANTIC_DIMENSIONS = (
    (
        VerificationCheckName.SEMANTIC_LEVEL_COMPLIANCE,
        "assistance_level_compliance",
        "Independent semantic assistance-level compliance",
    ),
    (
        VerificationCheckName.SEMANTIC_ANSWER_LEAKAGE,
        "answer_leakage",
        "Independent semantic answer-leakage assessment",
    ),
    (
        VerificationCheckName.SEMANTIC_FACTUAL_SUPPORT,
        "factual_support",
        "Independent semantic factual-support assessment",
    ),
    (
        VerificationCheckName.SEMANTIC_LANGUAGE,
        "language_appropriateness",
        "Independent semantic language assessment",
    ),
    (
        VerificationCheckName.SEMANTIC_AGE_APPROPRIATENESS,
        "age_appropriateness",
        "Independent semantic age-appropriateness assessment",
    ),
)


def _semantic_checks(
    request: VerificationRequest,
    verifier: SemanticVerifier | None,
) -> list[VerificationCheckResult]:
    required = {
        "assistance_level_compliance": True,
        "answer_leakage": request.assistance_level is not AssistanceLevel.FULL_EXPLANATION,
        "factual_support": bool(request.curriculum_evidence)
        or request.assistance_level is AssistanceLevel.FULL_EXPLANATION
        or _claims_curriculum_authority(request.response_text),
        "language_appropriateness": True,
        "age_appropriateness": True,
    }
    if verifier is None:
        return [
            _missing_semantic_check(check, required[field], label)
            for check, field, label in _SEMANTIC_DIMENSIONS
        ]

    try:
        result = verifier.verify(request)
    except (SemanticVerifierError, TimeoutError):
        return [
            _unavailable_semantic_check(check, required[field], label)
            for check, field, label in _SEMANTIC_DIMENSIONS
        ]
    if not isinstance(result, SemanticVerificationResult):
        return [
            _unavailable_semantic_check(check, required[field], label)
            for check, field, label in _SEMANTIC_DIMENSIONS
        ]

    checks: list[VerificationCheckResult] = []
    for check_name, field, label in _SEMANTIC_DIMENSIONS:
        judgment = getattr(result, field)
        if judgment is VerificationCheckOutcome.NOT_APPLICABLE and required[field]:
            judgment = VerificationCheckOutcome.INDETERMINATE
        checks.append(_semantic_check(check_name, judgment, label))
    return checks


def _missing_semantic_check(
    check_name: VerificationCheckName,
    required: bool,
    label: str,
) -> VerificationCheckResult:
    if not required:
        return _semantic_check(check_name, VerificationCheckOutcome.NOT_APPLICABLE, label)
    return _check(
        check_name,
        VerificationCheckOutcome.INDETERMINATE,
        VerificationReasonCode.SEMANTIC_VERIFIER_UNAVAILABLE,
        f"{label} is unavailable.",
    )


def _unavailable_semantic_check(
    check_name: VerificationCheckName,
    required: bool,
    label: str,
) -> VerificationCheckResult:
    return _missing_semantic_check(check_name, required, label)


def _semantic_check(
    check_name: VerificationCheckName,
    outcome: VerificationCheckOutcome,
    label: str,
) -> VerificationCheckResult:
    if outcome is VerificationCheckOutcome.PASS:
        code = VerificationReasonCode.SEMANTIC_JUDGMENT_PASSED
        suffix = "passed."
    elif outcome is VerificationCheckOutcome.FAIL:
        code = VerificationReasonCode.SEMANTIC_JUDGMENT_FAILED
        suffix = "failed."
    elif outcome is VerificationCheckOutcome.NOT_APPLICABLE:
        code = VerificationReasonCode.SEMANTIC_JUDGMENT_PASSED
        suffix = "is not applicable."
    else:
        code = VerificationReasonCode.SEMANTIC_JUDGMENT_INDETERMINATE
        suffix = "is indeterminate."
    return _check(check_name, outcome, code, f"{label} {suffix}")


def _build_result(
    checks: list[VerificationCheckResult],
    evidence: tuple[RetrievedCurriculumPassage, ...],
    semantic_verifier_name: str | None,
) -> VerificationResult:
    if any(check.outcome is VerificationCheckOutcome.FAIL for check in checks):
        outcome = VerificationOutcome.FAIL
    elif any(check.outcome is VerificationCheckOutcome.INDETERMINATE for check in checks):
        outcome = VerificationOutcome.INDETERMINATE
    else:
        outcome = VerificationOutcome.PASS

    reason_codes = tuple(dict.fromkeys(code for check in checks for code in check.reason_codes))
    provenance = tuple(
        EvidenceProvenance(
            source_id=passage.source.source_id,
            source_version=passage.chunk.source_version,
            chunk_id=passage.chunk.chunk_id,
            page_number=passage.chunk.page_number,
        )
        for passage in evidence
    )
    return VerificationResult(
        outcome=outcome,
        checks=tuple(checks),
        reason_codes=reason_codes,
        sufficient_evidence_for_pass=outcome is VerificationOutcome.PASS,
        evidence_provenance=provenance,
        semantic_verifier_name=semantic_verifier_name,
    )


def _check(
    name: VerificationCheckName,
    outcome: VerificationCheckOutcome,
    reason_code: VerificationReasonCode,
    diagnostic: str,
) -> VerificationCheckResult:
    return VerificationCheckResult(
        check=name,
        outcome=outcome,
        reason_codes=(reason_code,),
        diagnostic=diagnostic,
    )


_EXPLICIT_ANSWER_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:the\s+)?(?:final\s+)?answer\s+(?:is|equals)\s+(?!\?)\S+",
        r"\b(?:final\s+)?answer\s*[:=]\s*\S+",
        r"අවසාන\s+පිළිතුර\s*(?:වන්නේ|[:=])\s*\S+",
        r"இறுதி\s+விடை\s*(?:என்பது|[:=])\s*\S+",
    )
)


def _has_explicit_answer_disclosure(text: str) -> bool:
    return any(pattern.search(text) for pattern in _EXPLICIT_ANSWER_PATTERNS)


def _is_answer_only(text: str) -> bool:
    normalized = " ".join(text.split())
    return bool(
        re.fullmatch(
            r"(?:the\s+)?(?:final\s+)?answer\s*(?:is|equals|[:=])\s*[^.!?]+[.!]?",
            normalized,
            re.IGNORECASE,
        )
    )


_DISCLOSURE_CONTEXT_MARKERS = (
    "answer",
    "result",
    "therefore",
    "thus",
    "hence",
    "you get",
    "equals",
    "පිළිතුර",
    "ඒ නිසා",
    "விடை",
    "எனவே",
)
_NUMBER_PATTERN = re.compile(r"(?<![\w/])[+-]?\d+(?:\s*/\s*\d+|\.\d+)?(?![\w/])")


def _trusted_answer_disclosed(text: str, accepted_answers: tuple[str, ...]) -> bool:
    digit_normalized_text = _normalize_digits(unicodedata.normalize("NFKC", text))
    numeric_candidates = [
        (match.start(), match.end(), _numeric_value(match.group()))
        for match in _NUMBER_PATTERN.finditer(digit_normalized_text)
    ]

    for accepted in accepted_answers:
        normalized_answer = _normalize_digits(unicodedata.normalize("NFKC", accepted))
        expected_number = _numeric_value(normalized_answer)
        if expected_number is not None:
            if any(
                candidate == expected_number
                and _has_disclosure_context(digit_normalized_text, start, end)
                for start, end, candidate in numeric_candidates
                if candidate is not None
            ):
                return True
            continue

        answer_pattern = re.compile(
            r"(?<!\w)" + r"\s+".join(map(re.escape, normalized_answer.split())) + r"(?!\w)",
            re.IGNORECASE,
        )
        if any(
            _has_disclosure_context(digit_normalized_text, match.start(), match.end())
            for match in answer_pattern.finditer(digit_normalized_text)
        ):
            return True
    return False


def _has_disclosure_context(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 80) : start].casefold()
    suffix = text[end : end + 10].lstrip()
    return (
        bool(re.search(r"(?:=|:)\s*$", prefix))
        or any(marker in prefix for marker in _DISCLOSURE_CONTEXT_MARKERS)
        or suffix.startswith(("is the answer", "is the result"))
    )


def _numeric_value(value: str) -> Fraction | None:
    compact = re.sub(r"\s+", "", value)
    try:
        if re.fullmatch(r"[+-]?\d+/\d+", compact):
            return Fraction(compact)
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", compact):
            return Fraction(Decimal(compact))
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None
    return None


def _normalize_digits(value: str) -> str:
    normalized: list[str] = []
    for character in value:
        try:
            normalized.append(str(unicodedata.digit(character)))
        except (TypeError, ValueError):
            normalized.append(character)
    return "".join(normalized)


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


_AUTHORITY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\baccording to (?:the )?(?:curriculum|textbook|source)\b",
        r"\b(?:the )?(?:curriculum|textbook|source) says\b",
        r"\bsource(?:\s+id|_id)?\s*[:=]",
        r"\bpage\s+\d+\b",
    )
)


def _claims_curriculum_authority(text: str) -> bool:
    return any(pattern.search(text) for pattern in _AUTHORITY_PATTERNS)
