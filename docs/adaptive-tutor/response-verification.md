# Hybrid scaffolding response verification

## Purpose and boundary

Task 14 adds an independently testable application boundary for deciding whether an unverified
tutoring draft is eligible to proceed toward learner delivery. It verifies the response against the
`AssistanceLevel` already selected by Controller V1; it does not select, increase, or decrease that
level and does not duplicate controller policy.

```text
Controller V1 decision
        |
        v
GenerationResult (still unverified)
        |
        v
Deterministic checks + optional independent semantic verifier
        |
        v
VerificationResult: PASS | FAIL | INDETERMINATE
        |
        v
Future Task 15 orchestration (only PASS may be considered for delivery)
```

The implementation is in
`backend/app/adaptive_tutor/application/verification.py`. It is synchronous, stateless, performs no
I/O, and requires no live Gemini or other model call. `GenerationResult.verified` remains `false`;
verification is represented by a separate result.

## Contracts

`VerificationRequest` is immutable, rejects unknown fields, and contains:

| Field | Meaning |
|---|---|
| `student_question` | Original non-blank learner question. |
| `assistance_level` | Existing Controller V1 `AssistanceLevel` (L0-L6). |
| `response_text` | Generated draft to assess. Empty text is accepted by the contract so the verifier can reject it explicitly. |
| `response_language` | Requested `en`, `si`, or `ta` language code. |
| `grade` | Existing canonical Grade 4 or 5 value. |
| `skill_id` | Optional confirmed Universal Skill Node ID. |
| `curriculum_evidence` | Up to ten canonical `RetrievedCurriculumPassage` instances. |
| `trusted_answer` | Optional `TrustedAnswerReference` supplied by a trusted upstream assessment owner. |

`TrustedAnswerReference` holds one or more unique accepted answer forms and non-blank provenance.
The verifier never derives or invents a reference answer. Verification reuses `GenerationRequest`
validation, including grade, skill, language, evidence eligibility, and source consistency rules.
Serialized dictionaries cannot be promoted to canonical approved passages at this boundary.

`VerificationResult` contains:

- an overall `PASS`, `FAIL`, or `INDETERMINATE` outcome;
- one result per executed check, each with a stable name, outcome, reason codes, and concise safe
  diagnostic;
- the deduplicated reason-code summary;
- `sufficient_evidence_for_pass`, which is true only for `PASS`;
- source, version, chunk, and page provenance for supplied canonical evidence; and
- the semantic verifier name when one was used.

Check-level outcomes also include `NOT_APPLICABLE`. This is not an overall response outcome and
does not represent a successful check where a required judgment is missing.

## Deterministic checks

The verifier performs conservative, explainable checks for:

1. non-empty, bounded, structurally valid output without invalid control characters;
2. obvious level conflicts, including prohibited explicit answers, multi-step solution structures
   at L0-L3, a non-question L1, and answer-only L6 output;
3. trusted-answer disclosure at L0-L5 when a trusted answer is supplied;
4. basic English, Sinhala, and Tamil script compatibility without rejecting normal code-mixing;
5. a small set of explicit child-safety violations;
6. mandatory canonical evidence for L6 and for detected claims of curriculum authority; and
7. detectable source-ID and page citations against the exact evidence supplied.

These checks detect bounded failure patterns. Passing them does not prove semantic correctness,
pedagogical quality, safety, or factual grounding.

## L0-L6 compliance policy

| Level | Required response behavior | Deterministic coverage | Semantic judgment still needed |
|---|---|---|---|
| L0 | Independent retry; no hint or answer | Rejects explicit answers and multi-step structures | Whether subtle content constitutes a hint |
| L1 | Metacognitive prompt; no direct solution | Requires a question signal; rejects explicit answers and multi-step structures | Whether the question is genuinely metacognitive |
| L2 | Conceptual hint; no final answer | Rejects explicit answers and multi-step structures | Conceptual relevance and hidden procedural disclosure |
| L3 | Targeted next-step hint; no final answer | Rejects explicit answers and multi-step structures | Whether only an appropriate next step is revealed |
| L4 | Guided next step without unnecessary completion | Rejects explicit final-answer language | Whether guidance completes too much of the problem |
| L5 | Similar but different worked example | Rejects explicit final-answer language for the learner's problem | Whether the example is genuinely different and analogous |
| L6 | Evidence-supported full explanation | Requires canonical evidence and rejects answer-only text | Factual support, completeness, and use of the evidence |

Controller V1 remains the sole owner of level selection. The verifier assesses the fixed selected
level and cannot substitute another one.

## Answer-leakage policy

At L0-L5, a trusted answer enables detection of obvious disclosure in final-answer contexts such
as `the answer is`, `the result is`, or an equation. Common integer, decimal, and fraction forms are
normalized, and mathematically equivalent fractions and exact finite decimals are compared. This
catches examples such as `3/4`, `6/8`, and `0.75` when the trusted answer is `3/4`.

Numbers are not treated as answers merely because they occur in educational text. The checker is
not a general mathematics solver and does not infer answers from the learner question. It will not
reliably detect every paraphrase, symbolic transformation, unit conversion, multi-answer solution,
or language-specific disclosure. If no trusted answer is supplied for L0-L5, the answer-leakage
check is `INDETERMINATE`, never an assumed pass. L6 permits the current answer as part of an
adequately supported explanation, so this particular prohibition is not applicable there.

## Curriculum grounding and provenance

L6 cannot pass without eligible, approved canonical evidence. Detected claims such as “according
to the textbook” also require evidence. Detectable source IDs and page numbers must occur in the
supplied evidence; otherwise verification fails with `CURRICULUM_CITATION_UNSUPPORTED`.

Structural eligibility and citation identity do not prove that the response is entailed by the
passage. Factual support is therefore a required semantic dimension for L6, whenever evidence is
present, or whenever curriculum authority is claimed. Unreviewed extraction output remains
ineligible under the canonical Curriculum RAG contracts.

## Optional semantic verification boundary

`SemanticVerifier` accepts the same `VerificationRequest` and returns independent judgments for:

- assistance-level compliance;
- answer leakage;
- factual support from approved evidence;
- language appropriateness; and
- age appropriateness.

The boundary is provider-neutral. Task 14 supplies only `DeterministicFakeSemanticVerifier`, a
configured offline test double. Its judgments are fixtures, not measurements and not evidence that
an AI verifier works. No Gemini/OpenAI API is invoked. A future provider should be operationally
independent of the generator where practical, should return structured judgments, and must be
empirically evaluated on qualified human-reviewed examples.

When a required semantic judgment is absent, unavailable, malformed, or explicitly uncertain, its
check is `INDETERMINATE`. The implementation does not treat the same generator as a trusted
self-certifier.

## Decision policy

The overall policy is fail-closed:

- any failed deterministic or semantic check produces `FAIL`;
- with no failures, any required indeterminate check produces `INDETERMINATE`;
- `PASS` requires every required configured check to pass;
- `NOT_APPLICABLE` checks do not block a pass; and
- provider failure, a missing draft, or mismatch between the trusted generation request and result
  produces `FAIL` before response verification.

Neither `FAIL` nor `INDETERMINATE` is eligible for learner delivery. Task 14 deliberately does not
generate a fallback response.

## Task 15 handoff

Future orchestration should call `verify_generation_result` with the original `GenerationRequest`
and its `GenerationResult`. The helper rejects failed generation and detects mismatched assistance
level, response language, or curriculum evidence before constructing a `VerificationRequest`.

```python
verification = verify_generation_result(
    generation_request,
    generation_result,
    trusted_answer=trusted_answer_from_an_authoritative_owner,
    semantic_verifier=independent_verifier,
)

if verification.outcome is VerificationOutcome.PASS:
    # Future Task 15 may consider the response for delivery.
    ...
```

Task 15 must retain both results, require an explicit `PASS`, and must not mutate the generation
result's `verified=false` field or expose rejected/indeterminate drafts.

## Synthetic tests

`backend/tests/adaptive_tutor/test_verification.py` uses design-authored synthetic fixtures and
covers:

- valid and clearly invalid examples across L0-L6;
- direct, disguised, equivalent-fraction, and decimal answer leakage;
- ordinary mathematical values that must not be mistaken for final answers;
- missing evidence, unsupported authority claims, and fabricated citations;
- English, Sinhala, Tamil, code-mixed, romanized, and wrong-script signals;
- empty, malformed, oversized, and obviously unsafe output;
- missing, unavailable, uncertain, failing, and contradictory semantic judgments; and
- generation failures and trusted-context mismatches.

The tests are deterministic and offline. No precision, recall, false-positive rate, or real-world
accuracy is claimed from this synthetic dataset.

Run the focused verification tests from the repository root:

```bash
backend/.venv/bin/pytest -q backend/tests/adaptive_tutor/test_verification.py
```

## Known limitations

- Structural patterns cannot establish subtle L0-L6 pedagogical compliance.
- Script detection cannot verify fluency, meaning, translation quality, or romanized Sinhala/Tamil.
- The bounded unsafe-content patterns are not a comprehensive child-safety classifier.
- Answer equivalence is limited to simple numeric, decimal, and fraction forms in detectable answer
  contexts.
- Citation checks cover detectable source IDs and page references, not the truth of every claim.
- A future semantic verifier will itself require independence analysis, calibration, multilingual
  validation, adversarial evaluation, privacy review, and monitored failure handling.

Passing Task 14 tests establishes only the behavior of this conservative software foundation. It
does not establish a production-safe, clinically validated, or educationally validated tutoring
system, and it does not authorize delivery of real model output to children.
