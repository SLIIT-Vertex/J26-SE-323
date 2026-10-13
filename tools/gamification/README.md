# Gamification developer tools

This directory owns repository tooling for the adaptive gamified learning component. Tool code may
read files and create artifacts, but it is not imported by the backend runtime.

## Dataset workflow

`datasets/build_grade5_curriculum_game_dataset.py` normalizes four Grade 5 syllabus-trace
workbooks and writes the three JSONL inputs consumed by future curriculum and game importers. It
accepts a source directory explicitly so the workflow is portable and does not depend on a
contributor's home directory:

```bash
python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py \
  --source-dir /path/to/syllabus-traces
```

The source directory must contain `grade5_ENV_syllabus_trace_v1.xlsx`,
`grade5_SIN_syllabus_trace_v1.xlsx`, `grade5_ENG_syllabus_trace_v1.xlsx`, and
`grade5_MAT_syllabus_trace_v1.xlsx`. The `MINDBRIDGE_GRADE5_SYLLABUS_DIR` environment variable is an
alternative to `--source-dir`.

The canonical output contains only:

- `curriculum_nodes.jsonl` for curriculum/skill ingestion;
- `games.jsonl` for game configuration ingestion;
- `game_items.jsonl` for item-bank ingestion;
- `schema.json` and `manifest.json` for validation and reproducibility.

The builder requires `openpyxl` and accepts an explicit destination. CSV mirrors, spreadsheets, and
derived review reports do not belong in `data/`; generate them temporarily when a human review
workflow needs them.

The canonical machine inputs live under
`data/gamification/grade5-curriculum-game-dataset/v1/`.
