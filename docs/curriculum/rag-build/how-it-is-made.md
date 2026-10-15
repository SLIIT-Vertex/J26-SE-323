# How the shared curriculum RAG is made

One retriever in `backend/app/curriculum` answers both Adaptive Tutor and Gamification.
The text it searches lives in `data/curriculum`. Gamification does not keep a second copy,
and it does not serve question text from `data/gamification/`.

The agreement between the two owners stays in
[../shared-rag-joint-plan.md](../shared-rag-joint-plan.md). This file describes the system
that is built. Terminal checks are in [check-from-the-terminal.md](check-from-the-terminal.md).

## Architecture

```text
data/curriculum/raw/                  Grade 5 PDFs (not committed)
        │
        ▼
extract_curriculum_pdfs.py            page text, or conversion_unavailable
        │
grade5-curriculum-trace/v1/           competencies, lessons, outcomes, activities
skill-links/v1/                       outcome id → Universal skill id
        │
        ▼
build_curriculum_chunks.py            chunking-v1
        │
        ├── chunks/v1/chunks.jsonl    retrievable outcome statements
        └── chunks/v1/quarantine.jsonl
        │
        ▼
curriculum_sources                    registry row for the source
curriculum_chunks                     one row per written chunk
curriculum_chunk_embeddings           one vector per model revision
        │
        ▼
HybridCurriculumRetriever             BM25 + vector, reciprocal rank fusion
        │
        ├── Gamification  SharedCurriculumAdapter   purpose CONTENT_AUTHORING
        └── Adaptive Tutor                        purpose TUTOR_ANSWER, not wired here
```

`app.curriculum` does not import Adaptive Tutor, Gamification, Knowledge Tracing, or
Learner State. Gamification may call the retriever only through
`backend/app/gamification/infrastructure/curriculum_adapter.py`.

## Request path

1. Gamification names one of its own skill ids, for example `G5-MAT-C03-L01-O01`.
2. `SharedCurriculumAdapter` looks that id up in the crosswalk and sends the Universal
   id, here `MAT-FRC`. The request purpose is `CONTENT_AUTHORING`.
3. The index keeps rows whose grade, subject, required language, unit, and skill match.
   `requested_language` is a preference and does not drop a row.
4. Keyword rank uses Okapi BM25 (`k1` 1.5, `b` 0.75). Vector rank uses cosine distance.
   The two lists are fused with reciprocal rank fusion, constant 60. Ties break by
   `chunk_id` ascending.
5. The result is cut to `limit`. The contract allows 1 to 10. The fractions pilot uses 4,
   because that skill has four chunks.

A result is `FOUND` when at least one passage comes back. `NO_APPROVED_SOURCE` means no
source row matched the request. `NO_RELEVANT_PASSAGES` means a source matched and no chunk
did. `PROVIDER_UNAVAILABLE` means the embedding library is missing. `PROVIDER_ERROR` means
the embedder or the database failed, and the result contains no passages.

Rejected chunks and restricted sources stay out. A row can still be returned while its
review status is `REVIEW_PENDING` and its usage rights are `UNKNOWN`. The loader does not
relabel those fields.

## How a chunk is written

`chunking-v1` walks the Grade 5 trace. A learning outcome becomes a chunk only when all of
these hold:

- Its parent chain resolves to nodes that exist in `curriculum_nodes.jsonl`.
- It has one Universal skill id from `data/curriculum/skill-links/v1/`. Those ids are copied
  from the draft crosswalk. No reviewer has signed them.
- The outcome statement is non-empty.
- The source is in `data/curriculum/registry/v1/sources.jsonl`.

The written text is the outcome statement (`transcription_method` `visual_read`), not the
PDF page. A page becomes its own chunk only when extraction produced usable text and a
resolved outcome covers that page. Pages marked `conversion_unavailable` are quarantined.
The legacy-font converter is not enabled.

The current manifest has 189 written chunks and 1,815 quarantined rows.

| Subject | Written chunks | Source | What a call can return |
| --- | --- | --- | --- |
| Sinhala | 84 | `SRC-G5-SIN-TG-01` | `LAN-CMP`, `LAN-WRT`, `LAN-AGR`, `LAN-ORT`, `LAN-VOC`, `LAN-TNS`, `LAN-IDM` |
| Mathematics | 65 | `SRC-G5-MAT-TG-01` | `MAT-OPS`, `MAT-TIM`, `MAT-MAS`, `MAT-NUM`, `MAT-FRC`, `MAT-LEN`, `MAT-MON`, `MAT-DAT`, `APT-PAT` |
| English | 40 | `SRC-G5-ENG-TG-01` | `LAN-BIL` |
| Environmental Studies | 0 | PDFs are in `raw/grade5/environmental-studies/` | nothing |

Environmental Studies has 117 learning outcomes and skill ids (`ENV-CIV`, `ENV-PHY`,
`ENV-HLT`, `ENV-GEO`, `ENV-AGR`). Each outcome's parent was inferred as an id such as
`G5-ENV-C01-L00`. No node has that id. `L00` is a placeholder in the trace, so the parent
check quarantines every Environmental Studies outcome. Most of those PDF pages are also
`conversion_unavailable`. The nine activity books are in the registry, and the trace nodes
cite only the teacher guide `SRC-G5-ENV-TG-01`.

## Code

| Piece | Path |
| --- | --- |
| Contracts and trust checks | `backend/app/curriculum/application/retrieval.py` |
| Chunking | `backend/app/curriculum/application/chunking.py` |
| Tables | `backend/app/curriculum/infrastructure/models.py` |
| Migration `curr_20261015_01`, branch `curriculum`, parent `20261007_01` | `backend/alembic/versions/20261015_01_create_curriculum_tables.py` |
| Index | `backend/app/curriculum/infrastructure/pgvector_index.py` |
| Hybrid retriever | `backend/app/curriculum/infrastructure/hybrid_retriever.py` |
| Load one skill into a database | `backend/app/curriculum/infrastructure/skill_index.py` |
| Gamification translation | `backend/app/gamification/infrastructure/curriculum_adapter.py` |
| Fractions score | `backend/scripts/evaluate_curriculum_retrieval.py` |

The recorded embedding pair is `intfloat/multilingual-e5-small`, revision
`d829207ab28e6a5fb3aafb5d4c44111b8146db32`, 384 dimensions. The terminal check and the
fractions score use `pilot-hash-v1` so they do not download that model. A hash vector is
not that model. PostgreSQL stores the column as `vector(384)`. The checks use SQLite, where
the same column is JSON. The `vector(384)` statement is in the migration and has not been
executed against a live PostgreSQL server.

The version string on a hash run is
`chunking-v1;embedding-revision=pilot-hash-v1;fusion=reciprocal-rank-fusion-k60`.

## What a successful retrieval is

A working call returns `FOUND` and the chunk ids for that Universal skill. The fractions
score file `data/curriculum/evaluation/v1/reports/retrieval-evaluation.json` records
`CONTENT_AUTHORING` recall 1.0 for query `MAT-FRC-PILOT` at `k` 4. That means the four
listed chunk ids came back. The query has no reviewer, so `reviewed` is false. Recall here
is not an educational-effectiveness claim.

`POST /game-sessions/{id}/next-activity` still answers `CURRICULUM_RETRIEVAL_UNAVAILABLE`.
The retrieved rows are curriculum statements. They have no answer options, so the play
screen does not turn them into a scored question.
