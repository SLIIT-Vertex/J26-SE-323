# Curriculum RAG Foundation

## Scope and current source inventory

Task 12A defines contracts, trust rules, and a replaceable retrieval boundary. It does not ingest,
index, embed, search, translate, or generate from curriculum material.

The neutral Task 12A contracts now belong to `app.curriculum.application` so Adaptive Tutor and the
Game Component can consume one authoritative implementation. Adaptive Tutor keeps a thin compatibility
re-export and its Tutor-specific `MATCHED` Skill Mapper eligibility helper. See
`docs/curriculum/shared-curriculum-rag-architecture.md` for ownership and integration guidance.

Repository inspection found no Grade 4–5 textbooks, teacher guides, syllabi, approved educational
resources, curriculum PDFs, DOC/DOCX files, or passage corpus. `docs/skill_nodes.xlsx` is the
authoritative Universal Skill Node taxonomy, not curriculum evidence. Project Markdown, evaluation
datasets, and Controller reference scenarios are research/design artifacts and are not approved
curriculum sources.

Therefore the current curriculum source inventory is empty. No publisher, authority, licence,
permission, official status, page citation, or curriculum content is claimed.

## Implemented in Task 12A

### Source metadata contract

The shared `CurriculumSourceRecord` inventories a potential source without asserting that it may be
used.

| Field | Meaning |
|---|---|
| `source_id` | Stable project identifier |
| `title` | Recorded document title |
| `publisher_authority` | Publisher or authority when evidenced; otherwise absent |
| `grade` | Grade 4 or 5 when known |
| `subject` | Recorded subject when known |
| `language` | Recorded language when known |
| `source_type` | Descriptive type such as textbook, teacher guide, or syllabus |
| `source_location` | Source URI or repository location when available |
| `source_version` | Edition, version, or stable content version when known |
| `metadata_status` | `VERIFIED`, `PROVISIONAL`, or `UNKNOWN` |
| `ingestion_status` | `NOT_INGESTED`, `READY`, `INGESTED`, or `FAILED` |
| `review_status` | `UNREVIEWED`, `REVIEW_PENDING`, `APPROVED`, or `REJECTED` |
| `usage_rights_status` | `UNKNOWN`, `PERMITTED`, or `RESTRICTED` |

`VERIFIED` means the recorded metadata has supporting evidence. It does not mean the document is
official, educationally approved, accurate, or licensed. `APPROVED` means accepted through the
project's future curriculum review process; it does not imply government approval. Usage rights are
tracked separately.

### Curriculum chunk contract

`CurriculumChunk` represents a future retrievable passage. It requires:

- stable `chunk_id`;
- non-blank `source_id` and `source_version` for traceability;
- non-blank text content;
- Grade 4 or 5;
- subject and language;
- at least one unique Universal Skill Node ID;
- optional positive page number and optional section locator; and
- explicit review status.

Skill membership is validated separately against IDs loaded from `docs/skill_nodes.xlsx`. The 30
IDs are not duplicated in code. Multiple skills are allowed when reviewers determine that a passage
genuinely supports more than one node. Page numbers and section labels remain absent when the source
does not provide reliable locators.

### Retrieval request

`CurriculumRetrievalRequest` contains:

| Field | Rule |
|---|---|
| `learner_question` | Required non-blank learner text |
| `skill_id` | Confirmed, taxonomy-valid skill |
| `grade` | Grade 4 or 5 |
| `requested_language` | Optional preference, not an instruction to translate |
| `limit` | Optional result limit from 1 to 10; default 5 |

The result limit is an operational contract bound, not a researched optimal retrieval depth.

Adaptive Tutor's `curriculum_request_for_mapping` adapter creates a shared request only from a
`MATCHED` Skill Mapper result. It
returns no request for `AMBIGUOUS`, `NO_MATCH`, or `NOT_SKILL_RELATED`, even if ranked candidates are
present. An unknown confirmed ID is rejected against the workbook taxonomy.

### Retrieval response

`CurriculumRetrievalResult` preserves passage order and uses these statuses:

| Status | Meaning |
|---|---|
| `FOUND` | One or more approved, traceable passages were returned |
| `NO_RELEVANT_PASSAGES` | Approved sources exist but no relevant passage was found |
| `NO_APPROVED_SOURCE` | No approved, permitted source is available for the request |
| `PROVIDER_UNAVAILABLE` | Retrieval cannot currently be reached or used |
| `PROVIDER_ERROR` | Retrieval failed while processing the request |

Only `FOUND` may contain passages, and `FOUND` requires at least one. Empty and failure states never
fabricate text.

Each `RetrievedCurriculumPassage` contains the chunk, its complete source reference, and an optional
finite retrieval score. Contracts require matching source IDs and versions, verified source metadata,
an ingested and approved source, an approved chunk, and explicitly permitted usage rights.
Result/request validation checks the requested limit, grade, and skill. Scores are ranking signals,
not calibrated probabilities or evidence of correctness.

### Retriever interface

The shared `CurriculumRetriever` exposes one replaceable operation:

```text
retrieve(CurriculumRetrievalRequest) -> CurriculumRetrievalResult
```

The protocol contains no PostgreSQL, pgvector, embedding, LLM, HTTP, or storage dependency. Only a
deterministic test fake exists.

## Provenance and trust policy

Before any document can support retrieval:

1. record its origin without filling unknown fields with guesses;
2. retain evidence for publisher, authority, edition, and location claims;
3. establish usage permission before copying or ingesting copyrighted content;
4. preserve a stable source version and page/section locators where available;
5. review extracted text against the source;
6. review grade, subject, language, and skill alignment;
7. keep source approval separate from chunk approval and usage permission; and
8. retain rejected or superseded versions for audit without returning them as evidence.

Retrieval does not make a source verified. If approved sources contradict one another, future source
checks must flag the conflict in the evidence package and preserve both citations; retrieval or an
LLM must not silently choose a winner. Curriculum experts must define the resolution policy.

## Grade, subject, skill, and multilingual behavior

- Grade is a hard request/result constraint: Grade 4 requests cannot return Grade 5 chunks.
- Confirmed `skill_id` is a hard constraint. Subject is retained on every chunk and should be used
  with the skill during future indexing and filtering.
- English, Sinhala, and Tamil passages retain their original language labels.
- `requested_language` is a preference. If no approved passage exists in that language, the
  retriever must return an explicit empty result or a separately defined fallback—not translate or
  fabricate material.
- Cross-language retrieval may be evaluated in Task 12B, but automatic translation is not part of
  this foundation.
- Code-mixed learner questions may be accepted as query text; returned evidence still preserves the
  source passage's actual language.

## Future Task 12B architecture

```text
Approved Curriculum Documents
        ↓
Text Extraction
        ↓
Structure-Aware Chunking
        ↓
Metadata and Skill Alignment
        ↓
Embedding / Indexing
        ↓
Skill-Constrained Retrieval
        ↓
Relevance and Source Checks
        ↓
Evidence Package
        ↓
Future LLM Tutor
        ↓
Future Hybrid Verifier
```

Possible Task 12B experiments—not current implementation—include:

- comparing PDF text extraction tools on reviewed sample pages, including Sinhala/Tamil font and
  OCR behavior;
- preserving page, heading, table, exercise, and worked-example boundaries;
- selecting chunk size and overlap through retrieval evaluation rather than arbitrary tuning;
- comparing multilingual embeddings only after a reviewed multilingual evaluation set exists;
- using PostgreSQL with pgvector once storage ownership and migration design are approved;
- comparing vector retrieval with keyword or hybrid retrieval under identical skill constraints;
- versioning extracted text, chunking configuration, metadata, embeddings, and source documents;
- measuring top-k evidence recall, source/locator accuracy, unsupported retrieval rate, language
  coverage, and expert relevance judgments; and
- testing contradiction detection and evidence abstention separately from answer generation.

## Not implemented

- curriculum content or source records
- document download, copying, ingestion, extraction, OCR, or parsing
- chunk generation or automatic skill alignment
- embeddings, vector search, keyword search, reranking, or pgvector tables
- database migrations, APIs, networking, caches, or external model calls
- automatic translation
- LLM tutoring responses or hybrid verification
- live Skill Mapper, Knowledge Tracing, Controller, frontend, or session integration

## Decisions required before Task 12B

1. Identify candidate Grade 4–5 sources and document authority, version, provenance, and usage rights.
2. Define who may approve sources, extracted chunks, skill alignment, and contradictory evidence.
3. Select a small legally usable multilingual pilot corpus.
4. Define source-version identifiers and supersession rules.
5. Choose page/section extraction acceptance criteria, especially for Sinhala and Tamil documents.
6. Create reviewed retrieval queries and relevance judgments without using model output as labels.
7. Define language fallback and cross-language retrieval policies.
8. Establish retrieval quality and safety thresholds before connecting evidence to an LLM.
