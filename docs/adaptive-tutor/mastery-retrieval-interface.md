# Skill-Specific Mastery Retrieval Interface

## Purpose

This interface lets Adaptive Tutor request a Knowledge Tracing-owned mastery estimate for one
shared learner UUID and one authoritative Universal Skill Node. It defines contracts and a provider
boundary only. It does not calculate mastery, access a database, call Controller V1, or connect the
semantic Skill Mapper to Knowledge Tracing.

The ownership boundary follows `docs/architecture.md`: Knowledge Tracing owns mastery estimates and
publishes an application contract; Adaptive Tutor may consume that contract without importing
Knowledge Tracing infrastructure.

## Designed now

### Request

`MasteryRetrievalRequest` contains exactly:

| Field | Type | Rule |
|---|---|---|
| `learner_id` | UUID | Uses the shared learner identity; no duplicate learner profile |
| `skill_id` | non-blank string | Must be checked against `docs/skill_nodes.xlsx` before provider use |

Pydantic rejects malformed UUIDs, blank IDs, extra fields, and ambiguous types. Structural schema
validation and taxonomy membership validation remain separate, matching the existing Skill Mapper
contract pattern. `validate_mastery_request_against_taxonomy` accepts the IDs loaded from the
authoritative workbook; the 30 IDs are not copied into code.

### Result

`MasteryResult` repeats `learner_id` and `skill_id` so the caller can verify that a provider response
belongs to the request. `validate_mastery_result_identity` rejects mismatches.

| Status | Meaning | `mastery` |
|---|---|---|
| `AVAILABLE` | A skill-specific estimate exists | Required, finite, inclusive `0.0–1.0` |
| `NOT_FOUND` | No estimate exists for this learner/skill pair | Must be absent |
| `PROVIDER_UNAVAILABLE` | The provider cannot currently be reached or used | Must be absent |
| `PROVIDER_ERROR` | The provider failed while handling the request | Must be absent |

Missing mastery is never represented as `0`, `0.5`, or another fabricated estimate. An invalid
request is rejected by Pydantic. A structurally valid but unknown skill is rejected by explicit
taxonomy validation before provider use. Those failures are different from a valid request whose
estimate is `NOT_FOUND`.

No source timestamp or estimate version is included because the current Knowledge Tracing module
exposes neither concept. Either may be added later when the owning component defines reliable
semantics for it.

### Provider boundary

`MasteryProvider` is a protocol with one operation:

```text
get_mastery(MasteryRetrievalRequest) -> MasteryResult
```

It has no dependency on SQLAlchemy, PostgreSQL, HTTP, a mastery algorithm, or a database schema.
Tests use a deterministic in-memory fake; production has no provider implementation.

## Skill Mapper handoff

`mastery_request_for_mapping` enforces the handoff policy:

| Skill Mapping status | Mastery action |
|---|---|
| `MATCHED` with a taxonomy-valid `skill_id` | Create a mastery request |
| `AMBIGUOUS` | Do not retrieve; ask the existing clarification question |
| `NO_MATCH` | Do not retrieve |
| `NOT_SKILL_RELATED` | Do not retrieve |
| `MATCHED` with an unknown ID | Reject before provider use |

Candidate rankings are not confirmation. The helper never selects the highest-ranked candidate for
an `AMBIGUOUS` result and does not bypass the Skill Mapper decision policy. It only creates a request;
it does not call a provider or wire the real semantic mapper to Knowledge Tracing.

## Future Controller V1 integration

Controller V1 already expects `TutoringContext.mastery` as a required normalized value. A future
orchestrator may copy `MasteryResult.mastery` into that field only when:

1. the Skill Mapper result is confirmed and taxonomy-valid;
2. the mastery result status is `AVAILABLE`;
3. the returned learner and skill identities match the request; and
4. the other independently owned controller inputs are available.

Those other inputs include `support_need`, attempt count, correctness, error severity, and previous
assistance history. Mastery retrieval does not calculate or fabricate them.

`NOT_FOUND`, `PROVIDER_UNAVAILABLE`, and `PROVIDER_ERROR` cannot currently produce a valid
`TutoringContext`, because Controller V1 requires mastery. Future integration must explicitly decide
whether to defer the controller call, request more evidence, or introduce a separately researched
fallback policy. Task 11A makes no defaulting decision and leaves Controller V1 unchanged.

## Not yet implemented

- Knowledge Tracing algorithm or estimate calculation
- SQLAlchemy model, migration, query, cache, or database table
- HTTP or FastAPI endpoint
- production provider implementation
- automatic Skill Mapper-to-provider orchestration
- Controller V1 invocation or fallback mastery policy
- source timestamps, model versions, confidence intervals, or estimate provenance
- frontend integration, RAG, response generation, or response verification

## Assumptions and limitations

- The shared learner service remains the owner of learner identity and profile data.
- The taxonomy workbook remains the sole source of valid skill identities.
- `0.0` and `1.0` are valid available estimates; neither means “missing.”
- Provider status describes retrieval availability, not learner behavior or certainty calibration.
- Contract validation cannot establish how Knowledge Tracing computes or updates mastery.

## Questions for the Knowledge Tracing teammate

1. What event or evidence causes the first estimate for a learner/skill pair to exist?
2. What should distinguish temporary provider unavailability from a processing failure in the real
   adapter?
3. Will estimates expose an observation timestamp, algorithm/model version, or both, and what are
   their exact semantics?
4. Can estimates become stale, and who owns the staleness policy?
5. What consistency and latency guarantees can the future provider make?
6. Should an unknown learner be represented as `NOT_FOUND`, or rejected separately by an
   orchestration layer after shared learner validation?
7. What reviewed behavior should future orchestration use when mastery is unavailable, given that
   Controller V1 does not accept a missing value?
