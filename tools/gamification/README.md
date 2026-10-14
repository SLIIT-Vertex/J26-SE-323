# Gamification developer tools

This directory owns repository tooling for the adaptive gamified learning component. Tool code may
read files and create artifacts, but it is not imported by the backend runtime.

## Dataset workflow

`datasets/build_grade5_curriculum_game_dataset.py` normalizes four Grade 5 syllabus-trace
workbooks plus the game-dataset master workbook. The canonical package contains source, mapping,
model-catalogue, review, asset, schema, validation and readiness artifacts.
It accepts a source directory explicitly so the workflow is portable and does not depend on a
contributor's home directory:

```bash
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py \
  --source-dir /path/to/syllabus-traces
```

The source directory must contain `grade5_ENV_syllabus_trace_v1.xlsx`,
`grade5_SIN_syllabus_trace_v1.xlsx`, `grade5_ENG_syllabus_trace_v1.xlsx`, and
`grade5_MAT_syllabus_trace_v1.xlsx`, plus `grade5_game_dataset_master.xlsx`. The
`MINDBRIDGE_GRADE5_SYLLABUS_DIR` environment variable is an alternative to `--source-dir`.

The version 2 output is split by ownership and review meaning:

- source evidence: `curriculum_sources.jsonl`, `curriculum_nodes.jsonl`, and
  `curriculum_terms.jsonl`;
- provisional skill review: `skill_candidates.jsonl`, `skill_relationships.jsonl`, and
  `skill_source_mappings.jsonl`;
- games and content: `games.jsonl`, `game_items.jsonl`, item mappings, content assets, and asset
  requirements;
- three-model review inputs: the misconception fallback, structured-error mappings, support
  actions, and verification-pair candidates;
- governance: QA issues, formal review decisions, source-workbook annotations, JSON schema,
  validation report, readiness report, and content-addressed manifest.

Candidate skill IDs do not replace Knowledge Tracing-owned skill IDs. Unapproved support and
verification records remain ineligible. An empty mapping or review file is an explicit release
gap, not permission to infer the missing evidence.

The builder requires `openpyxl` and accepts an explicit destination. CSV mirrors, spreadsheets, and
derived review reports do not belong in `data/`; generate them temporarily when a human review
workflow needs them.

The canonical package lives under `data/gamification/grade5-curriculum-game-dataset/v2/`.
Superseded package copies are not retained in the repository.
