# Gamification data

This is the single location for data used by the gamification component.
The component owner and maintainer is `hareeshagunasekara`. Official curriculum publications may
be cited as primary evidence, but no dataset or mapping authored by another project member is an
input to this directory's runtime or generated packages.

## Folders

- `grade5-curriculum-game-dataset/v2/` — canonical skills, games, items, mappings, support
  candidates, review state, schema, and validation reports. Records are not learner-ready unless
  their approval fields explicitly permit delivery. Curriculum sources, nodes and terms are shared
  with the Adaptive Tutor and live in `../curriculum/grade5-curriculum-trace/v1/`; this package
  pins that version and manifest hash in `manifest.json`.
- `grade5-pilot-slice/v1/` — the Grade 5 Mathematics Fractions pilot (ADR-0006): five skills
  under Universal Skill Node `MAT-FRC`, a versioned misconception catalogue, Sinhala items with
  mapped distractors, parallel groups, the three scaffold arms per skill, and SHA-256 pins for the
  cited Mathematics PDFs. Everything is researcher-authored draft content awaiting educator
  review; `load_pilot_content_package` refuses it unless `allow_draft=True`.
- `synthetic-model-data/v1/` — fictional model-development data used by tests and offline workflows.
  It includes the development protocol, simulated two-reviewer cases, example classification
  predictions, and their frozen manifest. `synthetic-misconception-catalogue.json`
  (`synthetic-misconceptions-v1`) lists every synthetic label so fixtures cannot be mistaken for
  the pilot catalogue. It must never be treated as learner evidence or expert validation.
- `skill-catalogue-review/v1/` — Phase 5A inventory, draft reviews, identity bindings, and the
  Universal Skill Node crosswalk (ADR-0010), generated from the component-owned Grade 5 skill
  candidates. Draft records are development-only and do not open the RAG or child-facing gates.

## Rules

- Runtime Python code belongs under `backend/`; data files belong here.
- Component builders must not read another research component's datasets or identifiers. The
  shared curriculum data in `data/curriculum/` is not another component's data; it is co-owned.
  The Universal Skill Node taxonomy in `docs/skill_nodes.xlsx` is likewise the shared
  cross-component vocabulary (ADR-0010), read only to validate crosswalk parents.
- The question bank (games, items, answer keys, misconceptions, scaffolds) stays here and is never
  indexed into the shared curriculum RAG.
- Use the manifest and schema in each canonical dataset package to validate inputs.
- Add a new version folder for incompatible schema or identifier changes.
- Do not add duplicate CSV or spreadsheet exports. Generate human-review views temporarily.
- Set `MINDBRIDGE_GAMIFICATION_DATA_DIR` only when these datasets are mounted elsewhere.
