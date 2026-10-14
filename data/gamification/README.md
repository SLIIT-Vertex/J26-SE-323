# Gamification data

This is the single location for data used by the gamification component.

## Folders

- `grade5-curriculum-game-dataset/v2/` — canonical curriculum, skills, games, items, mappings,
  support candidates, review state, schema, and validation reports. Records are not learner-ready
  unless their approval fields explicitly permit delivery.
- `synthetic-model-data/v1/` — fictional model-development data used by tests and offline workflows.
  It must never be treated as learner evidence or expert validation.

## Rules

- Runtime Python code belongs under `backend/`; data files belong here.
- Use the manifest and schema in each canonical dataset package to validate inputs.
- Add a new version folder for incompatible schema or identifier changes.
- Do not add duplicate CSV or spreadsheet exports. Generate human-review views temporarily.
- Set `MINDBRIDGE_GAMIFICATION_DATA_DIR` only when these datasets are mounted elsewhere.
