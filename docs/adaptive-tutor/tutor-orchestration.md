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

## Task 15C FastAPI handoff

A future route should construct dependencies in a composition root, validate authentication and
learner authorization, call `TutorOrchestrator.run`, and translate workflow statuses to a stable API
schema. It must expose `response_text` only for `APPROVED_RESPONSE`, retain the same synthetic
separation, and never turn dependency failures into fake fallback responses.

Task 15C must not initialize a fake provider by default, accept client evidence fields, expose hidden
drafts, or claim that current Gemini terms and validation are sufficient for delivery to children.
