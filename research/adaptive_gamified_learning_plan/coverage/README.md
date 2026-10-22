# Grade 5 supplied-area coverage

This folder is the coverage inventory for the 57 supplied Grade 5 areas. It is planning
evidence. It is not learner content, not a review approval, and not a release decision.
The full specification lives in `private-notes/adaptive_gamified_learning_plan/`.

| File | Role |
| --- | --- |
| `grade5-supplied-area-coverage-v1.jsonl` | One row for each supplied area. This is the matrix. |
| `emit_grade5_area_matrix.py` | Regenerates the matrix from the shared curriculum trace and the status rules below. |
| `staged-implementation-batches.md` | Finite batches. No batch authors a game from a category name. |
| `draft-app-build-plan.md` | Development missions for the 54 mapped areas and slots for their traced outcomes. Publication stays closed. |
| `area-support-types.md` | Provisional support types the game model may choose for each mapped area. This is not an expert review. |

Regenerate from the repository root:

```sh
python3 research/adaptive_gamified_learning_plan/coverage/emit_grade5_area_matrix.py
```

## ID rule

`G5-AREA-ENV-01` through `G5-AREA-ENV-16`, `G5-AREA-MAT-01` through `G5-AREA-MAT-16`, and
`G5-AREA-SIN-01` through `G5-AREA-SIN-25` follow the supplied order. Existing node, skill, item,
and Universal Skill IDs are unchanged.

## Status rule

Every row that has a Grade 5 trace locator is `MAPPED_DRAFT`. The two Sinhala rows with no
trace locator stay `BLOCKED`. `content_status` uses `NONE`
or `IMPLEMENTED_UNREVIEWED`. `REVIEWED` and `RELEASE_READY` are unused because no human approval
exists. `NONE` means no accepted learner content or game. Prototype rows in the curriculum game
dataset do not change `NONE`.

A draft competency or outcome citation is not an atomic skill. The only atomic skill ID in the
matrix is the existing fractions skill `G5-MAT-C03-L01-O01`.
