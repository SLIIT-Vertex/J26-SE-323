# Shared curriculum data

Curriculum facts shared by the Adaptive Tutor and the Gamification component, and the data side of
the shared curriculum RAG (`docs/curriculum/shared-rag-joint-plan.md`).

## Folders

| Folder | Tracked | Contents | Produced by |
| --- | --- | --- | --- |
| `grade5-curriculum-trace/v1/` | yes | Grade 5 sources, curriculum nodes (competencies, lessons, learning outcomes, content points, activities) and terms, with page ranges | `tools/gamification/datasets/build_grade5_curriculum_game_dataset.py` |
| `registry/v1/sources.jsonl` | yes | `CurriculumSourceRecord` rows for every traced source | `backend/scripts/build_curriculum_source_registry.py` |
| `raw/grade<N>/<subject>/` | no | Source PDFs with their original file names; subject folders are `english`, `environmental-studies`, `mathematics`, `sinhala` | placed manually |
| `extracted/`, `reports/` | no | PDF text extraction output | `backend/scripts/extract_curriculum_pdfs.py` |
| `skill-links/v1/` | yes | Draft Universal skill id for each Grade 5 learning outcome, copied from the crosswalk. No reviewer has signed them | `backend/scripts/build_outcome_skill_links.py` |
| `chunks/v1/` | yes | `chunking-v1` rows, quarantine, and manifest. Written rows stay `REVIEW_PENDING` | `backend/scripts/build_curriculum_chunks.py` |
| `evaluation/v1/` | yes | Retrieval query files, the frozen-limit manifest, and the score report. `tutor-queries.jsonl` is added by the tutor owner | `backend/scripts/evaluate_curriculum_retrieval.py` |

## Rules

- Registry rows stay `PROVISIONAL`, `NOT_INGESTED`, `UNREVIEWED`, and usage rights `UNKNOWN`.
  The retriever can return those rows. It does not return rejected chunks or restricted sources,
  and it does not relabel a row as approved or permitted.
- Keep `source_id` and `curriculum_node_id` values stable. Gamification items, skills and mappings
  refer to them. Add a new version folder for incompatible changes.
- Gamification reads curriculum details from this folder through the shared retriever. It does
  not keep a runtime question bank. Draft files under `data/gamification/` are not a substitute
  for retrieval, and question text from that package is not served as play.
- Learning-outcome Universal ids are copied from the draft crosswalk into `skill-links/v1/`.
  That copy is not a review. A chunk is written only when its parent chain resolves and the
  outcome has one of those ids. Nodes
  with an unresolved parent, pages with no usable text, and `conversion_unavailable` pages
  are listed in `chunks/v1/quarantine.jsonl` and are not indexed.
- `evaluation/v1/manifest.json` sets `k` to 4, the number of `MAT-FRC` chunks.
  `gamification-queries.jsonl` has one unsigned query, `MAT-FRC-PILOT`, whose listed ids are
  those four chunks. The report records query ids and counts, not page text.
- Do not commit PDFs, credentials or learner data. Extracted page text stays in `extracted/`.

## Regenerating

```bash
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py --source-dir /path/to/syllabus-traces
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py --repackage-existing
python backend/scripts/build_curriculum_source_registry.py
python backend/scripts/build_curriculum_source_registry.py --check
python backend/scripts/extract_curriculum_pdfs.py --input data/curriculum/raw --output data/curriculum/extracted --report-dir data/curriculum/reports
python backend/scripts/build_curriculum_chunks.py
python backend/scripts/evaluate_curriculum_retrieval.py
```

The first command rebuilds the trace from the source workbooks. The second rewrites schemas,
README and manifests from the existing records when the workbooks are unavailable. Rebuild the
registry after any change to `curriculum_sources.jsonl`; the `--check` form fails when it is out
of date, and `backend/tests/curriculum/test_source_registry.py` enforces the same. When the PDFs
are present locally, the same test checks that every registry `source_location` exists.
