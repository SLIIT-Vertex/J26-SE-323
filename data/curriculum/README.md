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

## Rules

- Everything here is a draft until a named reviewer approves it. Registry rows start as
  `PROVISIONAL`, `NOT_INGESTED`, `UNREVIEWED` and usage rights `UNKNOWN`. The retriever only
  returns approved, permitted content.
- Keep `source_id` and `curriculum_node_id` values stable. Gamification items, skills and mappings
  refer to them. Add a new version folder for incompatible changes.
- Component-specific data stays in its component folder. The gamification question bank, answer
  keys, misconceptions and scaffolds live in `data/gamification/` and are never indexed here.
- Do not commit PDFs, credentials or learner data.

## Regenerating

```bash
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py --source-dir /path/to/syllabus-traces
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py --repackage-existing
python backend/scripts/build_curriculum_source_registry.py
python backend/scripts/build_curriculum_source_registry.py --check
```

The first command rebuilds the trace from the source workbooks. The second rewrites schemas,
README and manifests from the existing records when the workbooks are unavailable. Rebuild the
registry after any change to `curriculum_sources.jsonl`; the `--check` form fails when it is out
of date, and `backend/tests/curriculum/test_source_registry.py` enforces the same. When the PDFs
are present locally, the same test checks that every registry `source_location` exists.
