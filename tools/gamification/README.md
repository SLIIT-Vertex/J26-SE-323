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

The builder writes two packages:

- the shared curriculum trace, `data/curriculum/grade5-curriculum-trace/v1/` (change with
  `--curriculum-output-dir`): `curriculum_sources.jsonl`, `curriculum_nodes.jsonl`,
  `curriculum_terms.jsonl`, schema, README and manifest. It is co-owned with the Adaptive Tutor
  and feeds the shared curriculum RAG;
- the gamification package, `data/gamification/grade5-curriculum-game-dataset/v2/` (change with
  `--output-dir`), whose manifest pins the trace version and manifest hash.

Without the workbooks, `--repackage-existing` rewrites schemas, READMEs, reports and manifests for
both packages from their existing records. After changing curriculum sources, also run
`python backend/scripts/build_curriculum_source_registry.py`.

The version 2 gamification output is split by ownership and review meaning:
- provisional skill review: `skill_candidates.jsonl`, `skill_relationships.jsonl`, and
  `skill_source_mappings.jsonl`;
- games and content: `games.jsonl`, `game_items.jsonl`, item mappings, content assets, and asset
  requirements;
- three-model review inputs: the misconception fallback, structured-error mappings, support
  actions, and verification-pair candidates;
- governance: QA issues, formal review decisions, source-workbook annotations, JSON schema,
  validation report, readiness report, and content-addressed manifest.

Candidate skill IDs are the canonical gamification skill IDs. Unapproved support and verification
records remain ineligible. An empty mapping or review file is an explicit release gap, not
permission to infer missing evidence.

The builder requires `openpyxl` and accepts an explicit destination. CSV mirrors, spreadsheets, and
derived review reports do not belong in `data/`; generate them temporarily when a human review
workflow needs them.

The canonical package lives under `data/gamification/grade5-curriculum-game-dataset/v2/`, with
its shared curriculum trace under `data/curriculum/grade5-curriculum-trace/v1/`.
Superseded package copies are not retained in the repository.

## Synthetic research-workflow fixture

`datasets/freeze_synthetic_expert_review.py` validates and freezes the development-only expert
review simulation. It calculates simulated reviewer agreement, creates learner-disjoint splits,
runs the example classification evaluation, checks the predeclared engineering thresholds, and
writes a content-addressed manifest:

```bash
PYTHONPATH=backend python3 tools/gamification/datasets/freeze_synthetic_expert_review.py
```

The resulting package is useful only for application development. It contains no human data and
cannot authorize research claims or child-facing model activation.

## Skill review package

`skills/build_skill_review_package.py` builds the Phase 5A development package from the
gamification-owned Grade 5 skill candidates. It creates a stable inventory, draft reviews,
identity bindings, the Universal Skill Node crosswalk, schema, and content-addressed manifest:

```bash
PYTHONPATH=backend python3 tools/gamification/skills/build_skill_review_package.py
```

The crosswalk is restored with `git show` from the Phase 5 bindings pinned at commit `7033835`
and validated against the shared taxonomy in `docs/skill_nodes.xlsx` (ADR-0010), so the builder
needs the repository history and `openpyxl`. It reads no other component's question bank or
datasets and never upgrades a draft record to approved.

## Pilot content slice

`datasets/build_grade5_pilot_slice.py` validates and freezes the hand-authored Grade 5
Mathematics Fractions pilot (ADR-0006) in `data/gamification/grade5-pilot-slice/v1/`. It checks
the JSON Schema for every record type, cross-references, citations against the shared trace and
source registry, misconception coverage, recomputed answer keys, parallel groups, scaffold arms,
worked-example value leakage, and template compatibility. It then writes the structured error
mappings, readiness report, schema, README, and content-addressed manifest:

```bash
PYTHONPATH=backend python3 tools/gamification/datasets/build_grade5_pilot_slice.py
PYTHONPATH=backend python3 tools/gamification/datasets/build_grade5_pilot_slice.py --check
PYTHONPATH=backend python3 tools/gamification/datasets/build_grade5_pilot_slice.py \
  --check --verify-source-pdfs data/curriculum/raw
```

`--check` fails if a generated file is stale. `--verify-source-pdfs` confirms that the local
Mathematics PDFs match the SHA-256 values pinned in `source_documents.jsonl`; the PDFs themselves
are never committed. The builder never changes a review status.
