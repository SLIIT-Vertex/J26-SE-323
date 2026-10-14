# Shared Curriculum RAG: Joint Plan for Adaptive Tutor and Gamification

- Status: **Agreed** on 2026-10-14 by the Adaptive Tutor owner (DilZhan) and the Gamification owner
  (IT23288508)
- Plan version: `shared-curriculum-rag-plan-v1`
- Related: [shared-curriculum-rag-architecture.md](shared-curriculum-rag-architecture.md),
  [pdf-extraction.md](pdf-extraction.md)

This is the single maintained plan for the curriculum RAG used by both components. Update it here,
with a dated entry in the change log at the end, rather than in component-specific folders.
Changes inside `backend/app/curriculum/` need review from both owners because both components
depend on them.

## 1. Agreed decisions

1. **One RAG.** The contracts, source registry, chunking, index, and retriever all live in the
   shared `app.curriculum` module. Neither component keeps its own copy of the source, chunk, or
   retrieval contracts.
2. **Roles.** Runtime curriculum retrieval for a child belongs to Adaptive Tutor. Gamification
   uses a reviewed, versioned question bank for child-facing play. It uses the shared retriever
   only for authoring support (writing items, scaffolds, and misconception rationales) and for
   teacher-facing source citations.
3. **Shared skill key.** Chunks are tagged with Universal Skill Node IDs from
   `docs/skill_nodes.xlsx`. Gamification maps each of its fine-grained skills to exactly one
   Universal parent (for example `MAT-FRC`) before calling the retriever.
4. **Trust rules apply equally.** Approval, usage-rights, and review statuses gate retrieval for
   both consumers. Generated or machine-transcribed text is never approved automatically.
5. **Additive changes only.** Contract changes are optional, backwards-compatible fields, so
   existing Adaptive Tutor code keeps working.

## 2. Starting point

Adaptive Tutor work merged in `develop` (`6d7ca0d`, PR #16):

- `backend/app/curriculum/application/retrieval.py` defines the neutral contracts:
  `CurriculumSourceRecord`, `CurriculumChunk`, `CurriculumRetrievalRequest`,
  `RetrievedCurriculumPassage`, `CurriculumRetrievalResult`, and the `CurriculumRetriever`
  Protocol. It also defines the metadata, ingestion, review, and usage-rights statuses, and the
  validators `validate_curriculum_skill_ids` and `validate_retrieval_result_for_request`.
- Retrieval returns only approved, permitted chunks. `INSUFFICIENT_EVIDENCE` and `UNAVAILABLE`
  are explicit outcomes.
- `backend/scripts/extract_curriculum_pdfs.py` extracts per-page text with PyMuPDF and marks it
  `review_status: pending`, `rag_eligible: false`. It detects legacy FM Sinhala fonts and refuses
  to emit unreliable text (`conversion_unavailable`).
- The tutor side has a skill mapper, context assembly, generation, verification, and a Gemini
  embedding client.

Gamification contributions:

- `data/gamification/grade5-curriculum-game-dataset/v2/curriculum_sources.jsonl`: 17 Grade 5
  sources (textbooks and teacher guides) with titles, subjects, and file locators.
- `curriculum_nodes.jsonl`: 1,884 short curriculum statements (148 competencies, 94 competency
  levels, 171 lessons, 306 learning outcomes, 330 content points, 835 source activities) with
  Sinhala text, page ranges, and parent links. They were transcribed by visual reading/OCR, have
  `extraction_confidence` mostly low, and are `needs_review`. They are statements, not full page
  text.
- A draft crosswalk from 548 Grade 5 gamification skills to Universal Skill Node parents.

Not built yet: real source registry records, chunking, a pgvector index, a retriever
implementation, hybrid keyword+vector search, a retrieval evaluation set, and legacy-font
conversion.

## 3. Target design

```text
                 docs/skill_nodes.xlsx  (Universal Skill Node IDs — shared key)
                              │
   ┌──────────────────────────┴───────────────────────────┐
   │                app.curriculum (shared)                │
   │  application/ retrieval.py (contracts, v1 → v1.1)     │
   │  application/ source_registry.py   (R0)               │
   │  application/ chunking.py          (R3)               │
   │  infrastructure/ registry_jsonl.py (R0)               │
   │  infrastructure/ pgvector_index.py (R4)               │
   │  infrastructure/ hybrid_retriever.py (R4)             │
   └───────────────▲──────────────────────────▲───────────┘
                   │ CurriculumRetriever       │ CurriculumRetriever
   adaptive_tutor/infrastructure        gamification/infrastructure
   (answers learner questions)          curriculum_adapter.py (authoring and
                                        teacher-facing citations only)
```

## 4. Phases

### R0 — Seed the shared source registry (Gamification leads)

- Add a source-registry port in `app.curriculum.application` and a JSONL adapter in
  `app.curriculum.infrastructure`. The registry file is metadata only, tracked at
  `data/curriculum/registry/v1/sources.jsonl`. Raw PDFs stay in gitignored `data/curriculum/raw`.
- Write `tools/curriculum/seed_registry_from_gamification.py`. It converts the 17 gamification
  sources into `CurriculumSourceRecord` rows with `metadata_status=PROVISIONAL`,
  `ingestion_status=NOT_INGESTED`, `review_status=UNREVIEWED`, and `usage_rights_status=UNKNOWN`.
  No publisher or licence is claimed without evidence.
- Tests: every record validates against the shared contract; IDs are stable and unique; output is
  deterministic.
- The gamification dataset then references shared `source_id`s.

### R1 — Additive contract v1.1 (Adaptive Tutor reviews)

| Contract | Addition | Reason |
| --- | --- | --- |
| `CurriculumRetrievalRequest` | `subject: str \| None` | subject filter |
| `CurriculumRetrievalRequest` | `required_language: str \| None` (hard filter, distinct from the `requested_language` preference) | Sinhala-medium only for version 1 |
| `CurriculumRetrievalRequest` | `unit_id: str \| None` | unit-scoped authoring |
| `CurriculumRetrievalRequest` | `purpose: Literal["TUTOR_ANSWER", "CONTENT_AUTHORING"] = "TUTOR_ANSWER"` | `learner_question` stays the query text; purpose is logged for audit |
| `CurriculumChunk` | `unit_id: str \| None`, `learning_outcome_id: str \| None` | hierarchy filter |
| `CurriculumRetrievalResult` | `retriever_version: str` | reproducible evaluation |

`validate_retrieval_result_for_request` enforces the new hard filters. Contract tests are added in
`backend/tests/curriculum/`.

### R2 — Remove the gamification duplicate (Gamification)

- Delete gamification's own `CurriculumRetriever` port, `CurriculumEvidence` record,
  `CurriculumEvidenceContract`, and in-memory retriever.
- Add `backend/app/gamification/infrastructure/curriculum_adapter.py` over
  `app.curriculum.application.CurriculumRetriever`. It translates gamification skill IDs to
  Universal IDs.
- Gamification architecture tests allow `app.curriculum.application` only in gamification
  infrastructure and forbid `app.curriculum.infrastructure`.

### R3 — Text and chunking (joint)

- The Adaptive Tutor extractor stays the source of machine text.
- Gamification curriculum nodes supply the hierarchy (`unit_id`, `learning_outcome_id`) and page
  ranges used to tag chunks. Their Sinhala statements may also be imported as small
  outcome-level chunks with `transcription_method="visual_read"` and
  `review_status=REVIEW_PENDING`, approved by a human one by one.
- Full page text for pages flagged `conversion_unavailable` still needs a legacy FM→Unicode
  converter or reviewed manual transcription; the gamification nodes do not cover it. When a
  converter exists, its output is checked against the node statements on the same pages.
- The gamification question bank (games, items, answer keys, misconceptions, scaffolds) is never
  indexed into the RAG. It is not curriculum evidence, and indexing it would let the tutor
  retrieve game answers.
- One shared `chunking-v1`: structure-aware (unit → lesson → paragraph), page-bounded,
  about 300–500 tokens, versioned. Chunks inherit Universal skill tags through
  `learning_outcome_id`.

### R4 — Index and retriever (Adaptive Tutor leads)

- pgvector table and migration owned by `app.curriculum` as its own Alembic branch.
- Hybrid retrieval: keyword (BM25) plus vector, metadata pre-filtering (grade, subject, language,
  skill, unit, approved and permitted only), deterministic tie-breaks.
- Embedding model and version recorded. Gemini embeddings are already wired.

### R5 — Shared retrieval evaluation (joint)

- A small reviewed query set: tutor learner questions plus gamification authoring queries for the
  first pilot unit (Grade 5 Fractions, `MAT-FRC`).
- Report recall@k, filter-violation rate (must be 0), and insufficient-evidence correctness.
- No accuracy claims until the set is human-reviewed.

## 5. Ownership

| Area | Owner | Reviewer |
| --- | --- | --- |
| Contracts, validators, index, retriever | Adaptive Tutor | Gamification |
| Source registry seed and transcription import | Gamification | Adaptive Tutor |
| Chunking and evaluation set | Joint | Both |
| Tutor answer generation and verification | Adaptive Tutor | — |
| Game question bank, misconceptions, scaffolds | Gamification | — |

## 6. Progress

| Phase | Status | Notes |
| --- | --- | --- |
| R0 | Not started | |
| R1 | Not started | |
| R2 | Not started | |
| R3 | Not started | |
| R4 | Not started | |
| R5 | Not started | |

## Change log

- 2026-10-14: plan agreed by both owners (`shared-curriculum-rag-plan-v1`).
- 2026-10-14: clarified that gamification curriculum nodes are short statements, not full page
  text, and that the gamification question bank is never indexed.
