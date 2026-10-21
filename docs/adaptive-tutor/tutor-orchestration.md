# Pure Adaptive Tutor Orchestration and Offline Demonstration

## Scope

Task 15B connects the existing application contracts into one synchronous, dependency-injected
workflow. It adds no API, database, HTTP call, model download, Gemini invocation, or production
provider. Controller V1 remains the sole owner of assistance-level selection.

```text
TutorWorkflowRequest
        |
        v
SkillMapper.map
        | MATCHED only
        v
TutorContextAssembler.assemble
        | READY only
        v
ScaffoldingController.decide (exactly once)
        |
        v
optional CurriculumRetriever.retrieve
        | L6 requires FOUND evidence
        v
generate_tutor_draft (injected LlmProvider)
        | DRAFT_GENERATED only
        v
verify_generation_result (injected SemanticVerifier)
        | genuine PASS only
        v
APPROVED_RESPONSE
```

Every other branch stops with a typed safe result. There are no internal HTTP calls and no fallback
provider selection in the orchestrator.

## Request contract

`TutorWorkflowRequest` accepts only:

| Field | Meaning |
|---|---|
| `learner_id` | Shared learner UUID |
| `student_message` | Non-blank message, bounded to 4,000 characters |
| `response_language` | Requested `en`, `si`, or `ta` response language |
| `conversation_context` | Up to eight canonical `ConversationTurn` values, bounded to 4,000 total characters |
| `active_skill_id` | Optional conversation-resolution hint, validated against the supplied taxonomy |

It does not accept mastery, support need, assessment evidence, assistance history, grade, curriculum
evidence, an assistance level, or a generated answer. Grade is resolved through Task 15A. Task 15A's
`READY` result now returns the already validated Grade 4 or 5 separately from `TutoringContext`,
because curriculum and generation need it while Controller V1 does not.

## Result contract and safe statuses

`TutorWorkflowResult` includes only safe diagnostics and relevant audit metadata:

- mapping status, reason codes, and confirmed skill;
- selected assistance level and unchanged Controller V1 reason codes;
- Task 15A issues and evidence provenance;
- curriculum and generation statuses;
- verification outcome, reason codes, evidence provenance, and verifier name; and
- aggregate `REAL`, `SYNTHETIC`, or `MIXED` execution provenance.

Statuses are:

- `APPROVED_RESPONSE`
- `SIMULATED_VERIFICATION_PASS`
- `CLARIFICATION_REQUIRED`
- `NOT_SKILL_RELATED`
- `NO_SUPPORTED_SKILL`
- `CONTEXT_NOT_READY`
- `CURRICULUM_UNAVAILABLE`
- `GENERATION_FAILED`
- `VERIFICATION_FAILED`
- `VERIFICATION_INDETERMINATE`
- `DELIVERY_NOT_AUTHORIZED`
- `UNSUPPORTED_LANGUAGE`
- `INVALID_REQUEST`
- `DEPENDENCY_FAILURE`

Only `APPROVED_RESPONSE` can contain `response_text`. Its contract requires a real-evidence,
non-simulated verification `PASS`. Every other status rejects response text at model validation, so a
failed or indeterminate result cannot accidentally serialize a hidden generation draft.

## Dependency injection

`TutorOrchestrator` receives existing application dependencies directly:

- a mapper implementing `map(SkillMappingRequest) -> SkillMappingResult`;
- mapper `EvidenceSource` provenance;
- `TutorContextAssembler`;
- `ScaffoldingController`;
- canonical `LlmProvider`;
- authoritative skill IDs supplied by the composition root;
- optional canonical `CurriculumRetriever`;
- optional canonical `SemanticVerifier`; and
- optional trusted-answer provider returning the existing `TrustedAnswerReference`.

The trusted-answer provider represents an authoritative Assessment/Game owner. The learner request
cannot provide a reference answer. Missing trusted answers retain the verifier's existing
`INDETERMINATE` behavior for L0-L5; the orchestrator does not derive an answer.

The production `ConversationalSkillMapper` still requires `SemanticSkillRetriever`. Its pinned E5
adapter is lazy: construction does not import or download the model, but the first real mapping call
needs the selected revision cached locally or available for download. Offline tests inject a fixed
mapper and never load E5.

## Invocation sequence and failure policy

1. Pydantic validates request structure and conversation bounds.
2. Unsupported response languages stop before skill mapping.
3. The mapper is called once. `AMBIGUOUS`, `NO_MATCH`, and `NOT_SKILL_RELATED` stop immediately.
4. A confirmed mapping and its provenance are passed to Task 15A.
5. `NOT_READY` returns its original issues and provenance; Controller V1 is not called.
6. A `READY` canonical context is passed once to `ScaffoldingController.decide`.
7. The decision's level and reason codes are copied unchanged.
8. If a curriculum retriever is injected, canonical retrieval and result validation run.
9. L0-L5 may continue without curriculum evidence. L6 requires eligible canonical passages and is
   never downgraded.
10. The existing generation helper receives the controller-selected level.
11. Only `DRAFT_GENERATED` proceeds to verification.
12. The original generation request and result are passed to Task 14 verification.
13. `FAIL` and `INDETERMINATE` discard the draft.
14. Only a genuine non-simulated real-evidence `PASS` may return `APPROVED_RESPONSE` text.

Unexpected dependency exceptions are reduced to fixed diagnostics. Stack traces, exception text,
provider secrets, and rejected drafts are not stored in the result.

## Curriculum behavior

Canonical `CurriculumRetrievalRequest`, `CurriculumRetrievalResult`, and
`RetrievedCurriculumPassage` are reused. Returned passages are checked against request grade, skill,
and limit.

- L0-L5: approved evidence is optional. Missing or failed retrieval does not create a citation or a
  claim that curriculum verification occurred.
- L6: at least one eligible passage is mandatory. Missing, invalid, unavailable, or failed retrieval
  returns `CURRICULUM_UNAVAILABLE` before generation.

The current repository has no approved runtime textbook corpus or production retriever. Unreviewed
PDF extraction is not promoted into evidence.

## Verification enforcement

Task 14 remains the approval authority. Generation success never changes
`GenerationResult.verified=false`. Missing semantic verification stays `INDETERMINATE`; deterministic
checks alone do not become semantic proof.

`DeterministicFakeSemanticVerifier` is detected as simulated. Even when its configured judgments all
pass, the workflow returns `SIMULATED_VERIFICATION_PASS`, omits `response_text`, and includes:

> SYNTHETIC RESEARCH DEMONSTRATION — NOT REAL LEARNER DATA OR VALIDATED LLM OUTPUT.

Synthetic or mixed context evidence also prevents an `APPROVED_RESPONSE`.

The existing Gemini adapter is additionally blocked from learner delivery even after a verification
pass. It returns `DELIVERY_NOT_AUTHORIZED` without response text. This keeps Task 15B from treating
the current Gemini Developer API integration as authorized for an under-18 production workflow.

## Offline PP1 demonstration harness

`backend/tests/adaptive_tutor/test_orchestration.py` is the opt-in offline harness. It uses:

- selected Task 15A Reference Policy V1 fixtures;
- a fixed injected mapper;
- `DeterministicFakeLlmProvider` or recording/failing test providers;
- configured fake semantic judgments;
- canonical fake approved curriculum evidence only for the synthetic L6 case; and
- the unchanged Controller V1.

It covers valid L0-L6 decisions, cold start, missing evidence, provider failures, L6 evidence
enforcement, verification failure/uncertainty, no draft leakage, and network/database independence.

Run it explicitly from the repository root:

```bash
backend/.venv/bin/pytest -q backend/tests/adaptive_tutor/test_orchestration.py
```

These traces test software wiring only. They do not demonstrate real learner adaptation, semantic
mapping quality, LLM quality, verifier accuracy, safety, or educational effectiveness.

## Implemented, fake-only, and blocked

| Capability | State |
|---|---|
| Skill Mapper contracts/prototype | Implemented; real E5 runtime not invoked by the demo |
| Context readiness and assembly | Implemented |
| Controller V1 | Implemented and unchanged |
| Curriculum contracts | Implemented; runtime approved corpus/retriever missing |
| Generation contracts/Gemini adapter | Implemented; offline workflow uses fake generation |
| Verification foundation | Implemented; no validated real semantic verifier |
| KT mastery | Contract only; real provider missing |
| Numeric support need | Provider contract only; reviewed Learner State adapter missing |
| Assessment evidence | Provider contract only; owner/read service unresolved |
| Tutor assistance history | Provider contract only; persistence/read service missing |
| Learner delivery authorization | Not established |

## Task 15C restricted research API

Task 15C registers `POST /api/v1/adaptive-tutor/responses`. The route appears in Swagger at `/docs`
and in `/openapi.json` even while execution is disabled. Its bounded public request contains only
the canonical `TutorWorkflowRequest` fields and maps directly to that application contract: learner
UUID, student message, response language, bounded conversation context, and optional active skill
ID. Mastery, support need, assessment evidence, history, assistance level, verification state, and
curriculum evidence remain server-owned.

Runtime activation is explicit:

```bash
# Default: route is documented but returns HTTP 503.
TUTOR_API_MODE=disabled

# Controlled local/offline research demonstration only.
TUTOR_API_MODE=synthetic-demo
```

`synthetic-demo` constructs a new `TutorOrchestrator` from Reference Policy V1 fixtures, the
authoritative spreadsheet taxonomy, Controller V1, deterministic fake generation, fake approved
curriculum evidence, and a deterministic fake semantic verifier. It uses no database, model
download, Gemini credential, network request, real KT estimate, or real Learner State prediction.
There is no automatic fallback from a real provider to this profile.

Example controlled request:

```json
{
  "learner_id": "00000000-0000-4000-8000-000000000001",
  "student_message": "Help me understand this fractions problem.",
  "response_language": "en",
  "conversation_context": []
}
```

The safe response contains mapping, context-readiness, Controller, curriculum, generation,
verification, execution-mode, and provenance metadata. A configured fake semantic `PASS` produces
`SIMULATED_VERIFICATION_PASS`, `delivery_authorized=false`, and no `response_text` field. Rejected or
indeterminate generated drafts are not copied into the public DTO.

HTTP 200 means only that a normal domain workflow outcome was returned; it does not mean a tutoring
response was approved. Malformed requests return 422, unknown controlled synthetic learners return
404, disabled execution returns 503, and unexpected boundary failures return a fixed sanitized 500.
Ambiguous mapping, unsupported skills, unavailable evidence, generation failure, and verification
uncertainty remain structured HTTP 200 outcomes.

The router injects a composition factory and invokes the existing orchestrator once. It does not
reimplement workflow decisions. Synthetic mode must be used only in a controlled local or otherwise
access-restricted research environment. Authentication and learner authorization are not implemented.

A working API demonstrates software wiring only. It does not prove real learner adaptation, and
synthetic evidence is not real KT or Learner State inference. Fake semantic verification does not
establish correctness. Real Gemini use for a Grade 4–5 learner-facing application remains blocked
pending provider eligibility, privacy, safety, authorization, and governance review.

Before Task 16 evaluation, freeze an evaluation protocol and obtain reviewed multilingual examples,
a real skill-specific mastery provider, a reviewed numeric support-need adapter, assessment/history
read services, an approved curriculum corpus, an independently validated semantic verifier, and
documented child-safety and provider-governance approval. A researcher-only fixture viewer would be
a separate tool if PP1 needs visible fake hint text; it must not be added to this learner-facing API.
