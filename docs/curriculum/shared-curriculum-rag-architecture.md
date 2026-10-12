# Shared Curriculum RAG Architecture

## Why curriculum retrieval is shared

Adaptive Tutor and the Game Component both need traceable curriculum evidence, but neither should
own a second source inventory, approval policy, or retrieval implementation. The shared curriculum
module provides one neutral contract boundary while each consumer retains responsibility for how
evidence is requested and used.

No real curriculum corpus or retriever currently exists. The repository still contains no approved
textbooks, teacher guides, syllabi, or ingested passages.

## Module ownership and dependency direction

The authoritative contracts live in:

```text
backend/app/curriculum/
└── application/
    ├── __init__.py
    └── retrieval.py
```

The shared module owns:

- curriculum source metadata;
- source provenance, version, review, ingestion, and usage-rights states;
- curriculum chunk structure and skill alignment;
- retrieval request/result contracts and statuses;
- the replaceable `CurriculumRetriever` protocol; and
- pure taxonomy/result validation helpers.

Dependency direction is one way:

```text
Adaptive Tutor ─┐
                ├──> Shared Curriculum Application Contracts
Game Component ─┘
```

`app.curriculum` does not import Adaptive Tutor, Game/Gamification, Knowledge Tracing, Learner State,
an LLM provider, or consumer infrastructure. Consumers may depend on the shared application API;
the shared module must never call back into a consumer.

## Contracts and trust rules

The shared module is the only implementation of:

- `CurriculumSourceRecord`
- `CurriculumChunk`
- `CurriculumRetrievalRequest`
- `RetrievedCurriculumPassage`
- `CurriculumRetrievalResult`
- `CurriculumRetriever`
- retrieval, review, ingestion, metadata, and usage-rights statuses
- taxonomy membership and request/result consistency validation

The contracts preserve the Task 12A rules: frozen models, forbidden extra fields, Grade 4–5 limits,
unique skill IDs, finite scores, retrieval limits, matching source ID/version, verified metadata,
ingested and approved sources, approved chunks, and permitted usage rights.

Project approval is not a claim of government approval. Metadata verification, educational review,
ingestion, and usage permission remain separate. A retrieved passage keeps the full source reference
and optional score; the score is a ranking signal, not a probability.

## Skill authorization boundary

The shared request accepts a skill ID but does not decide whether a consumer is authorized to use
it. Every consumer must validate the ID against `docs/skill_nodes.xlsx` before retrieval.

Adaptive Tutor keeps `curriculum_request_for_mapping` in its own application layer. Only a confirmed
`MATCHED` result may create a retrieval request. `AMBIGUOUS`, `NO_MATCH`, and
`NOT_SKILL_RELATED` must not trigger automatic retrieval, and candidate ranking is not confirmation.

Game does not need the conversational Skill Mapper when a taxonomy-valid skill was explicitly chosen
through its own approved workflow.

## Adaptive Tutor workflow

```text
SkillMappingResult
        ↓ MATCHED only
Adaptive Tutor eligibility adapter
        ↓ taxonomy-valid CurriculumRetrievalRequest
Shared CurriculumRetriever
        ↓
CurriculumRetrievalResult
```

`backend/app/adaptive_tutor/application/curriculum_retrieval.py` remains a compatibility adapter. It
re-exports the exact shared class objects and owns only the Tutor-specific Skill Mapper handoff.
Existing imports through `app.adaptive_tutor.application` therefore continue to work without a
duplicate contract implementation.

## Game consumer workflow

Conceptually, Game may request evidence using an educational query, validated skill, grade, language
preference, and result limit:

```python
from app.curriculum.application import CurriculumRetrievalRequest

request = CurriculumRetrievalRequest(
    learner_question="Create an activity about fractions",
    skill_id="MAT-FRC",
    grade=4,
    requested_language="en",
    limit=3,
)
```

The future Game application may pass this request to a shared `CurriculumRetriever` and handle
`FOUND`, empty, unavailable, and error statuses explicitly.

Game owns:

- question and answer-key generation;
- difficulty adaptation;
- gameplay behavior;
- question validation and game-specific safety; and
- authorization of its selected skill workflow.

Shared Curriculum does not implement or validate those Game behaviors. No Game files were changed by
this refactor.

## Provenance, citations, and failures

Every returned passage must trace to the same source ID and version recorded in its chunk. Only
verified, ingested, reviewed, and usage-permitted evidence may appear in `FOUND`. Missing evidence,
missing approved sources, provider unavailability, and provider errors remain explicit empty states;
consumers must not fabricate passages.

Future evidence packages should retain source title, version, location, page/section locator, chunk
identity, and retrieval configuration. Contradictory approved sources must be flagged for curriculum
review rather than silently resolved by either consumer.

## Future ingestion and indexing responsibilities

A future shared curriculum infrastructure layer may own approved-source registration, PDF/OCR
extraction, structure-aware chunking, versioning, storage, embeddings, keyword/vector indexes, and a
concrete retriever. Those components must implement the shared application contracts without adding
consumer dependencies.

Task 12B.1 should begin with a read-only audit of the external curriculum PDFs: inventory files,
capture evidence-backed metadata and rights status, inspect extractability and language/font issues,
and select a legally usable pilot. It should not ingest or index files merely because they exist.

## Teammate integration guidance

- Import neutral contracts from `app.curriculum.application`.
- Do not import Adaptive Tutor merely to obtain curriculum types.
- Validate skill IDs from the authoritative taxonomy at the consumer boundary.
- Treat requested language as a preference, not permission to translate.
- Branch explicitly on retrieval status.
- Preserve source references when passing evidence to later generators or verifiers.
- Do not create consumer-specific copies of the source, chunk, or retrieval contracts.

## Current limitations

- No curriculum sources or source records exist in the repository.
- No PDF audit, permission review, extraction, chunking, indexing, or retrieval exists.
- No source-review workflow or approved reviewer roles are defined.
- No Game workflow, question generation, LLM integration, or Tutor-RAG orchestration exists.
- No retrieval-quality evaluation set exists.
