# Shared Curriculum RAG: Joint Plan for Adaptive Tutor and Gamification

- Status: **Agreed** on 2026-10-14 by the Adaptive Tutor owner (DilZhan) and the Gamification owner
  (IT23288508)
- Plan version: `shared-curriculum-rag-plan-v1`
- Related: [shared-curriculum-rag-architecture.md](shared-curriculum-rag-architecture.md),
  [pdf-extraction.md](pdf-extraction.md)
- How it is made: [rag-build/how-it-is-made.md](rag-build/how-it-is-made.md).
  Terminal checks: [rag-build/check-from-the-terminal.md](rag-build/check-from-the-terminal.md).

This is the single maintained plan for the curriculum RAG used by both components. Update it here,
with a dated entry in the change log at the end, rather than in component-specific folders.
Changes inside `backend/app/curriculum/` need review from both owners because both components
depend on them.

## 1. Agreed decisions

1. **One RAG.** The contracts, source registry, chunking, index, and retriever all live in the
   shared `app.curriculum` module. Neither component keeps its own copy of the source, chunk, or
   retrieval contracts.
2. **Roles.** Curriculum details for both Adaptive Tutor and Gamification come from this shared
   retriever over `data/curriculum`. Gamification does not keep a runtime question bank. Until
   the retriever exists, it cannot present curriculum questions. Game mechanics stay in
   gamification; question text does not.
3. **Shared skill key.** Chunks are tagged with Universal Skill Node IDs from
   `docs/skill_nodes.xlsx`. Gamification maps each of its fine-grained skills to exactly one
   Universal parent (for example `MAT-FRC`) before calling the retriever.
4. **Trust rules apply equally.** On 2026-10-15 the Gamification owner removed the requirement
   that a source be verified, ingested, approved, and permitted before retrieval. Pending and
   unknown rows can be returned. Rejected chunks and restricted sources stay out. Rows are not
   relabeled as approved or permitted. The Adaptive Tutor owner has not signed this change.
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

Gamification contributions, moved in R0 to the shared trace package
`data/curriculum/grade5-curriculum-trace/v1/`:

- `curriculum_sources.jsonl`: 17 Grade 5 sources (textbooks, teacher guides and activity books)
  with titles, subjects, and file names.
- `curriculum_terms.jsonl`: 250 subject terms with Sinhala and English labels and source pages.
- `curriculum_nodes.jsonl`: 1,884 short curriculum statements (148 competencies, 94 competency
  levels, 171 lessons, 306 learning outcomes, 330 content points, 835 source activities) with
  Sinhala text, page ranges, and parent links. They were transcribed by visual reading/OCR, have
  `extraction_confidence` mostly low, and are `needs_review`. They are statements, not full page
  text. Known issue: 133 nodes have a `parent_node_id` that does not resolve to a traced node.
- A draft crosswalk from 548 Grade 5 gamification skills to Universal Skill Node parents (still in
  `data/gamification/`; restored by gamification correction phase C1).

## 3. Data layout

| Location | Owner | Used by the RAG? |
| --- | --- | --- |
| `data/curriculum/grade5-curriculum-trace/v1/` (sources, nodes, terms) | Shared | Yes: source registry seed, chunk hierarchy and page tags, optional outcome-level chunks, keyword terms |
| `data/curriculum/registry/v1/sources.jsonl` | Shared | Yes: `CurriculumSourceRecord` rows |
| `data/curriculum/raw/`, `extracted/`, `reports/` (gitignored) | Shared | Yes: PDFs and extracted page text |
| `data/gamification/…/v2/` skill candidates, skill source mappings, item curriculum mappings | Gamification | No; they refer to shared node IDs |
| `data/gamification/…/v2/` games, items, answer keys, misconceptions, support actions, verification pairs | Gamification | Never indexed |

One copy of each curriculum fact. The gamification manifest pins the trace version and manifest
hash, so a change to the shared trace is visible as a gamification package change.

Not built yet: a reviewer-signed retrieval query set and legacy-font conversion. The
evaluation runner is in place and has been run on the four `MAT-FRC` chunks with `k` set to 4.
Chunking, the curriculum pgvector branch, and the hybrid retriever are in place. No row has
been relabeled approved or permitted.

## 4. Target design

```text
                 docs/skill_nodes.xlsx  (Universal Skill Node IDs — shared key)
                              │
   ┌──────────────────────────┴───────────────────────────┐
   │                app.curriculum (shared)                │
   │  application/ retrieval.py (contracts, v1 → v1.1)     │
   │  application/ source_registry.py   (R0)               │
   │  application/ chunking.py          (R3)               │
   │  infrastructure/ source_registry_jsonl.py (R0)        │
   │  infrastructure/ pgvector_index.py (R4)               │
   │  infrastructure/ hybrid_retriever.py (R4)             │
   └───────────────▲──────────────────────────▲───────────┘
                   │ CurriculumRetriever       │ CurriculumRetriever
   adaptive_tutor/                 gamification/infrastructure
   calls the same retriever later      curriculum_adapter.py calls it for
   (not built in rag-build/)           curriculum details; question text
                                       is retrieved, not owned here
```

## 5. Phases

R0 and R2 are done. How the retriever is put together, and how to check it from the
terminal, is in [rag-build/how-it-is-made.md](rag-build/how-it-is-made.md) and
[rag-build/check-from-the-terminal.md](rag-build/check-from-the-terminal.md). Those files
do not replace this agreement.

### R0 — Shared trace package and source registry (Gamification leads) — implemented

- Moved `curriculum_sources.jsonl`, `curriculum_nodes.jsonl` and `curriculum_terms.jsonl` from the
  gamification dataset to `data/curriculum/grade5-curriculum-trace/v1/`, byte-for-byte, with its
  own schema, README and manifest. IDs are unchanged. The gamification builder writes both
  packages and gained `--repackage-existing` for regeneration without the workbooks.
- `app.curriculum.application.CurriculumSourceRegistry` (port) and
  `app.curriculum.infrastructure.JsonlCurriculumSourceRegistry` (read-only JSONL adapter that
  validates every row and rejects duplicate IDs).
- `backend/scripts/build_curriculum_source_registry.py` writes
  `data/curriculum/registry/v1/sources.jsonl` from the trace: 17 records, all `PROVISIONAL`,
  `NOT_INGESTED`, `UNREVIEWED`, usage rights `UNKNOWN`. Languages are `si`/`en`; subjects use full
  names; `source_location` is `data/curriculum/raw/grade5/<subject>/<original file name>`;
  `source_version` is the recorded edition text; `publisher_authority` is the authority the
  document names, not verified metadata. Unknown subjects or languages fail the build.
- Tests: `backend/tests/curriculum/test_grade5_curriculum_trace.py`,
  `backend/tests/curriculum/test_source_registry.py`, and the updated
  `backend/tests/gamification/test_grade5_dataset_package.py` (references resolve across
  packages, the hash pin holds, and repackaging reproduces both packages byte-for-byte).
- All 17 source PDFs are placed locally under `data/curriculum/raw/grade5/` (gitignored) and
  their page counts match the trace. The trace's `source_document_sha256` fields are empty, so
  file hashes are not yet pinned.

### R1 — Additive contract v1.1

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
  skill, unit), deterministic tie-breaks. Rejected chunks and restricted sources stay out.
- Embedding model and version recorded on each vector. The embedder lives in `app.curriculum`.
  This work does not modify `app/adaptive_tutor/`. See
  [rag-build/how-it-is-made.md](rag-build/how-it-is-made.md).

### R5 — Shared retrieval evaluation (joint)

- A small reviewed query set: tutor learner questions plus gamification authoring queries for the
  first pilot unit (Grade 5 Fractions, `MAT-FRC`).
- Report recall@k, filter-violation rate (must be 0), and insufficient-evidence correctness.
- No accuracy claims until the set is human-reviewed.

## 6. Ownership

| Area | Owner | Reviewer |
| --- | --- | --- |
| Contracts, validators, index, retriever in `app.curriculum` | Shared. Built for both consumers; this build does not edit the Tutor component | Both |
| Source registry seed and transcription import | Gamification | Adaptive Tutor |
| Chunking and evaluation set | Joint | Both |
| Tutor answer generation and verification | Adaptive Tutor | — |
| Game mechanics: templates, misconceptions, scaffolds | Gamification | — |
| Curriculum question text served to either component | Shared retriever | Both |

## 7. Progress

| Step | Status | Notes |
| --- | --- | --- |
| R0 | Done | Shared trace package, registry port, JSONL adapter, registry builder, tests, local PDFs placed |
| R1 | Done | 2026-10-15. Optional filters, `purpose`, chunk hierarchy fields, and `retriever_version` (`curriculum-retriever-contract-v1.1`). |
| R2 | Done | 2026-10-14. Gamification's duplicate retriever is gone. `SharedCurriculumAdapter` calls the shared retriever with the Universal skill id. |
| R3 | Done | 2026-10-15. `chunking-v1` manifest at `data/curriculum/chunks/v1/manifest.json`. 189 `REVIEW_PENDING` outcome statements written from the draft Universal-skill crosswalk. 1815 quarantined (133 unresolved parents, 1208 `conversion_unavailable` pages, 443 pages with no covering outcome, 31 pages with no usable text). All 17 placed PDFs remain `NOT_INGESTED`. No row is approved. |
| R4 | Done | 2026-10-15. Curriculum Alembic branch `20261015_01` from `20261007_01` (`branch_labels = curriculum`). Hybrid retriever. `retriever_version` names `chunking-v1`, embedding revision `d829207ab28e6a5fb3aafb5d4c44111b8146db32`, and `reciprocal-rank-fusion-k60`. Pending chunks can be returned. Rejected and restricted rows stay out. |
| R5 | Run | 2026-10-15. Report `data/curriculum/evaluation/v1/reports/retrieval-evaluation.json`. Chunk manifest sha256 `593769f283f9faa2dfea02ae8d666e3c439a38d7e087f5e11f91390e611f99bb`. `k` is 4, the number of `MAT-FRC` chunks. `MAT-FRC-PILOT` is unsigned. `CONTENT_AUTHORING` recall is 1.0 because those four chunk ids came back. Filter-violation rate is 0. `reviewed` is false. `tutor-queries.jsonl` is absent. This is not an effectiveness claim. |

## Change log

- 2026-10-14: plan agreed by both owners (`shared-curriculum-rag-plan-v1`).
- 2026-10-14: clarified that gamification curriculum nodes are short statements, not full page
  text, and that the gamification question bank is never indexed.
- 2026-10-14: R0 implemented. Curriculum trace moved to `data/curriculum/grade5-curriculum-trace/v1/`;
  source registry, port and adapter added; data layout section added.
- 2026-10-14: source PDFs placed under `data/curriculum/raw/grade5/<subject>/`; registry
  `source_location` values updated to match.
- 2026-10-15: execution detail for R1 and R3–R5 was added under `rag-build/`. This file
  stays the agreement.
- 2026-10-15: the `rag-build/` step files were replaced by
  [how-it-is-made.md](rag-build/how-it-is-made.md) and
  [check-from-the-terminal.md](rag-build/check-from-the-terminal.md).
- 2026-10-15: build plans keep Tutor needs and Gamification needs apart. The shared RAG is the
  only work in that folder. `app/adaptive_tutor/` is not part of the build.
- 2026-10-15: R1 contract v1.1 implemented in `app.curriculum.application.retrieval`. No tutor
  package edits.
- 2026-10-15: R3 `chunking-v1` writes `data/curriculum/chunks/v1/`. The Grade 5 trace has no
  Universal skill ids on learning outcomes, so no chunk was written. Quarantine counts are in
  the manifest. Sources stay `NOT_INGESTED`. No tutor package edits.
- 2026-10-15: R4 adds the curriculum migration branch and `HybridCurriculumRetriever`. The
  approved-fixture tests pass. No real source was marked approved or ingested. No tutor package
  edits.
- 2026-10-15: R5 runner writes `data/curriculum/evaluation/v1/reports/retrieval-evaluation.json`.
  Chunk manifest sha256 `593769f283f9faa2dfea02ae8d666e3c439a38d7e087f5e11f91390e611f99bb`.
  No reviewer-signed `MAT-FRC` queries, so recall is not computed and no effectiveness claim
  is made. `tutor-queries.jsonl` was not invented. Owner sign-off of this report is still open.
- 2026-10-15: draft Universal skill ids for all 306 Grade 5 learning outcomes were copied from
  `universal-skill-crosswalk.jsonl` into `data/curriculum/skill-links/v1/`. No reviewer signed
  them. 189 resolved outcomes became `REVIEW_PENDING` chunks. 117 outcomes stay quarantined
  because their parent does not resolve.
- 2026-10-15: the Gamification owner removed the approval gate on retrieval. Pending and unknown
  rows can be returned. Rejected and restricted rows stay out. Nothing was stamped approved or
  permitted. The fractions pilot loads the four `MAT-FRC` chunks and sets `k` to 4. The unsigned
  query `MAT-FRC-PILOT` returned all four. Recall is 1.0 for that check only. The Adaptive Tutor
  owner has not signed this change.
