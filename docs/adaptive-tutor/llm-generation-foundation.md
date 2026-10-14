# Scaffolding-aware LLM generation foundation

## Scope

The generation application layer lives in
`backend/app/adaptive_tutor/application/generation.py`. It turns a validated request and the
existing Controller V1 `AssistanceLevel` into a provider-neutral prompt and an unverified tutor
draft. The optional Task 13B infrastructure adapter in
`backend/app/adaptive_tutor/infrastructure/gemini.py` can send that exact prompt to Gemini. Neither
layer selects or changes assistance levels, retrieves mastery, infers learner state, retrieves
curriculum, persists conversations, or verifies generated text.

```text
Existing Controller V1 decision
            │
            ▼
GenerationRequest + optional canonical curriculum evidence
            │
            ▼
Evidence and language gates → level-specific prompt
            │
            ▼
LlmProvider (explicit deterministic fake or Gemini adapter)
            │
            ▼
GenerationResult: unverified draft or explicit failure
            │
            ▼
Task 14 response verification
```

Prompt instructions reduce risk but do not prove that a model will follow them. No Task 13A/13B
result is automatically verified.

## Contracts

`GenerationRequest` is immutable, rejects unknown fields, and contains:

| Field | Meaning |
|---|---|
| `student_question` | Required non-blank learner text, limited to 4,000 characters. |
| `skill_id` | Optional confirmed Universal Skill Node ID. Membership is checked separately against the caller-provided authoritative taxonomy. |
| `assistance_level` | Existing `AssistanceLevel`; it must come from Controller V1. |
| `response_language` | Explicit language code. Task 13A supports `si`, `ta`, and `en`. |
| `grade` | Grade 4 or 5. |
| `curriculum_evidence` | Zero to ten canonical `RetrievedCurriculumPassage` values. |
| `conversation_context` | Up to eight existing `ConversationTurn` values and 4,000 total message characters. |

Curriculum evidence is additionally limited to 20,000 content characters. Evidence requires a
confirmed skill, must match the request grade and skill, and may not repeat a chunk ID.

`GenerationResult` has these statuses:

| Status | Meaning |
|---|---|
| `DRAFT_GENERATED` | A provider returned a structurally valid, still-unverified draft. |
| `INSUFFICIENT_CURRICULUM_EVIDENCE` | L6 was requested without eligible curriculum evidence. |
| `PROVIDER_UNAVAILABLE` | The adapter reported unavailability or timeout. |
| `PROVIDER_ERROR` | The adapter reported another provider failure. |
| `INVALID_PROVIDER_OUTPUT` | The provider returned empty, non-text, or oversized output. |
| `INVALID_REQUEST` | Raw input could not construct a valid request. |
| `UNSUPPORTED_LANGUAGE` | A non-empty language other than `si`, `ta`, or `en` was requested. |

Successful results preserve the exact canonical `RetrievedCurriculumPassage` objects used to build
the prompt. This retains source ID, version, title, authority, page, section, metadata status,
review status, usage-rights status, retrieval score, and content without introducing another
curriculum schema. `verified` is permanently `false` in Task 13A.

## Prompt strategies

| Level | Prompt constraint |
|---|---|
| L0 | Encourage one independent retry; no hint, steps, solution, or final answer. |
| L1 | Ask one concise metacognitive question; no content hint or answer. |
| L2 | Give one conceptual hint; no procedure or answer. |
| L3 | Give one targeted next-step hint; do not complete the problem. |
| L4 | Guide only the next step, then pause; do not finish the problem. |
| L5 | Work a similar but different example; keep the current problem unsolved. |
| L6 | Give a concise full explanation grounded only in eligible curriculum evidence. |

The system instruction states the controller-selected level as fixed. Learner text, conversation
turns, and curriculum content are serialized as JSON under `USER_DATA_JSON` and labelled untrusted.
This separation is a defense-in-depth prompt convention, not a security guarantee.

## Language policy

The learner question may contain Sinhala, Tamil, English, Singlish, Tanglish, or mixed language.
Task 13A does not detect or translate language. The caller must explicitly request:

- `si` — Sinhala
- `ta` — Tamil
- `en` — English

There is no silent fallback. A missing language makes the request invalid; another code produces
`UNSUPPORTED_LANGUAGE`. Prompts tell the future provider to preserve numerical expressions and
mathematical symbols.

## Curriculum evidence policy

The generation request reuses `RetrievedCurriculumPassage`. Its canonical validator already
requires verified metadata, ingested and approved sources, approved chunks, matching source
identity/version, and permitted usage rights. Raw extraction text, unreviewed manual text, and
arbitrary strings cannot be supplied as authoritative evidence through this field. The request
accepts canonical passage instances from the internal retrieval boundary, not client-supplied or
serialized dictionaries whose approval fields could be forged.

L0-L5 may operate without curriculum evidence when the prompt can remain bounded and avoid claims
of curriculum authority. L6 requires at least one canonical passage matching the confirmed skill
and grade. This is structural eligibility, not proof that a passage is semantically sufficient;
Task 14 must check grounding and answer leakage.

## Provider boundary

`LlmProvider` has one synchronous operation:

```python
def generate(prompt: GenerationPrompt) -> str: ...
```

Adapters translate provider availability, timeout, and request failures to the supplied provider
exceptions. Task 13B supplies one synchronous `GeminiLlmProvider`, matching the existing synchronous
application contract. It uses Google's supported `google-genai` SDK, forwards the trusted system
instruction separately from `USER_DATA_JSON`, and does not opt into Gemini API request logging or
storage. It does not use chat state, tools, grounding, or automatic function calls.

The SDK client has a bounded request timeout and `retry_options.attempts=1`. MindBridge adds no
retry, so a single generation operation cannot silently repeat a billable request. Empty or
malformed text becomes `INVALID_PROVIDER_OUTPUT`; timeouts, network failures, rate limiting and
temporary unavailability become `PROVIDER_UNAVAILABLE`; authentication, provider, and safety-block
failures become `PROVIDER_ERROR`. No failure produces a fabricated response.

`DeterministicFakeLlmProvider` always returns its configured fixed text. Its provider name contains
`fake`, its default output is labelled fake, and it is only a test double—not a simulated measure of
real LLM quality or compliance.

## Configuration and provider selection

Install the optional SDK with the repository package convention:

```bash
backend/.venv/bin/pip install -e 'backend[dev,gemini]'
```

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Default | Purpose |
|---|---:|---|
| `TUTOR_LLM_PROVIDER` | blank in application settings; `fake` in the example file | Required explicit selection: `fake` or `gemini`. |
| `TUTOR_GEMINI_API_KEY` | blank | Secret API credential. Never commit it. This is separate from KT vision configuration. |
| `TUTOR_GEMINI_MODEL` | blank | Explicit model identifier. MindBridge does not assume that a particular model is available. |
| `TUTOR_GEMINI_TIMEOUT_SECONDS` | `30` | Positive end-to-end SDK request timeout. |
| `TUTOR_GEMINI_MAX_OUTPUT_TOKENS` | `512` | Positive output budget for concise tutoring drafts. |
| `TUTOR_GEMINI_TEMPERATURE` | `0.2` | Sampling temperature in the supported range `[0, 1]`. |

`select_tutor_llm_provider(settings)` accepts only the two named choices. Missing or unknown
selection raises `GeminiConfigurationError`; it never silently switches to the fake provider.
Selecting Gemini with a missing key or model returns `PROVIDER_UNAVAILABLE` when generation is
attempted, without opening a network client. Unit tests and normal repository checks therefore need
no API key.

## Privacy, security, and external-service eligibility

The adapter receives only the bounded Task 13A prompt. It does not add a learner UUID, learner
profile, mastery record, or unrelated conversation history. It does not log keys, student questions,
provider payloads, or responses. Exception text from the SDK is not exposed because it could include
sensitive request details. Student messages and curriculum passages remain untrusted prompt data,
and provider safety controls are not treated as a guarantee of safety or instruction compliance.

Before any real children's data is sent externally, the project must complete legal, privacy,
security, consent, retention, region, and provider data-processing review. This is currently a
deployment blocker: the [Gemini API Additional Terms effective March 23, 2026](https://ai.google.dev/gemini-api/terms)
state that Gemini API clients must not be directed toward or likely accessed by people under 18.
MindBridge targets Grade 4–5 learners, so this developer-API adapter is for synthetic research and
technical evaluation only unless an authorized Google service/contract and qualified review confirm
the intended use is permitted. Paid and unpaid service data handling also differs; review the
[current logging policy](https://ai.google.dev/gemini-api/docs/logs-policy) and terms rather than
assuming the Generate Content API's default no-storage behavior alone provides the required
protection.

## Synthetic example

This example is synthetic and does not represent a real model response:

```python
from app.adaptive_tutor.application import (
    DeterministicFakeLlmProvider,
    GenerationRequest,
    generate_tutor_draft,
)
from app.adaptive_tutor.domain import AssistanceLevel

request = GenerationRequest(
    student_question="What should I think about first for 1/2 + 1/4?",
    skill_id="MAT-FRC",
    assistance_level=AssistanceLevel.CONCEPTUAL_HINT,
    response_language="en",
    grade=4,
)
result = generate_tutor_draft(
    request,
    DeterministicFakeLlmProvider(response="Synthetic fixed hint."),
)
```

The result is `DRAFT_GENERATED`, retains L2, identifies `deterministic-fake-llm`, and has
`verified == false`.

## Tests

From the repository root:

```bash
backend/.venv/bin/pytest -q backend/tests/adaptive_tutor/test_generation.py
npm run check:push
```

The tests validate contracts, prompt construction, status handling, fake-provider determinism,
Gemini request translation, error mapping, explicit selection, key redaction, and instruction/data
separation. Gemini unit tests inject a recording client and make no network call. They do not
demonstrate safety, educational quality, factual correctness, language quality, grounding, or
no-leakage behavior from a real LLM.

Run the focused mocked tests with:

```bash
backend/.venv/bin/pytest -q \
  backend/tests/adaptive_tutor/test_gemini_provider.py \
  backend/tests/adaptive_tutor/test_generation.py
```

An explicitly invoked, billable live smoke command is available for synthetic L1 Sinhala, L3 Tamil,
and L5 English prompts:

```bash
cd backend
TUTOR_LLM_PROVIDER=gemini \
TUTOR_GEMINI_API_KEY='configured-outside-version-control' \
TUTOR_GEMINI_MODEL='an-explicitly-approved-model-id' \
.venv/bin/python -m scripts.smoke_test_gemini_generation
```

It prints the configured model, status, retained assistance level, language, and observed unverified
output. It must not be put in ordinary test or deployment startup paths, and its output must not be
shown to learners. The separate Task 14 verifier is not invoked by this smoke command.

## Next integration boundaries

Task 14 independently assesses generated output against the selected assistance level, evidence,
language, and child-safety rules; see
[`response-verification.md`](response-verification.md). Its outcome is separate from
`GenerationResult`, so Task 13A/13B drafts remain unverified. Before deployment work, resolve the
under-18 service-eligibility blocker and complete a provider data-handling review. Future Task 15
orchestration must consume real Controller V1 decisions and must not fabricate missing KT mastery
or Learner State support need.
