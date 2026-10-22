# Command index (adaptive gamified learning and the shared curriculum RAG)

Every offline command for the gamification component, wherever its file lives. Paths are from
the repository root unless the command starts with `cd backend`.

## Gamification data and contracts (`tools/gamification/`)

Details and options: [`tools/gamification/README.md`](gamification/README.md).

| Command | What it does |
|---|---|
| `python tools/gamification/datasets/build_grade5_curriculum_game_dataset.py --source-dir <dir>` | Rebuilds `data/gamification/grade5-curriculum-game-dataset/v2/` and the shared curriculum trace from the syllabus workbooks |
| `python tools/gamification/datasets/build_grade5_pilot_slice.py` | Validates and freezes the Fractions pilot slice |
| `python tools/gamification/datasets/build_grade5_sinhala_curriculum_slice.py` | Validates and manifests the one-skill Sinhala curriculum slice |
| `python tools/gamification/datasets/freeze_synthetic_expert_review.py` | Freezes the synthetic expert-review package |
| `python tools/gamification/skills/build_skill_review_package.py` | Builds the skill catalogue and Universal Skill Node crosswalk (`data/gamification/skill-catalogue-review/v1/`) |
| `python tools/gamification/support_selection/build_support_selection_evidence.py` | Builds synthetic-only Model 2 review evidence (`data/gamification/support-selection/v1/`) |
| `python tools/gamification/learning_flow/build_mobile_learning_contracts.py` | Builds or checks `docs/adaptive-gamified-learning/mobile-learning-contracts-v1.json` |
| `python tools/gamification/learning_flow/run_learning_flow_engineering_load.py` | Small local timing probe (no capacity claim) |
| `python tools/gamification/evaluation/simulate_policy_comparison.py` | Synthetic baseline-versus-proposed comparison |
| `python tools/gamification/evaluation/analyze_pilot_export.py` | Analyses a research export (synthetic or authorised inputs only) |

## Backend CLIs (`cd backend`)

| Command | What it does |
|---|---|
| `python -m app.gamification.demo_seed plan\|seed\|verify\|cleanup\|checklist` | Seeds, verifies or removes the shared demo learner's history (`backend/demo_seeds/`) |
| `python -m app.gamification.validation [--learners N]` | Simulated-cohort validation report (`backend/reports/simulated-validation.json`) |
| `python -m app.gamification.modeling.offline accuracy-report\|manifest\|evaluate-classification\|train-candidate\|train-bayesian` | Offline model tooling |
| `python -m app.shared.learner` | Names an existing learner for development; never invents one |
| `python tools/mobile_learning_e2e_server.py` | Seeds and runs the real API for the mobile end-to-end run (started by `npm run e2e:mobile-learning`) |

## Shared curriculum RAG (`backend/scripts/`, co-owned with the Adaptive Tutor)

These stay in `backend/scripts/` next to the other curriculum steps. How they fit together:
[`docs/curriculum/rag-build/how-it-is-made.md`](../docs/curriculum/rag-build/how-it-is-made.md).

| Command | What it does |
|---|---|
| `python backend/scripts/build_curriculum_source_registry.py [--check]` | Builds `data/curriculum/registry/v1/` from the curriculum trace |
| `python backend/scripts/build_outcome_skill_links.py` | Copies Universal skill ids onto learning-outcome rows (`data/curriculum/skill-links/v1/`) |
| `python backend/scripts/build_curriculum_chunks.py` | Writes `data/curriculum/chunks/v1/` |
| `python backend/scripts/evaluate_curriculum_retrieval.py` | Scores the curriculum query set (`data/curriculum/evaluation/v1/reports/`) |

## Frontend (`cd frontend`)

| Command | What it does |
|---|---|
| `npm run generate:mobile-learning-types` (`check:mobile-learning-types` to verify) | Regenerates `src/features/mobile-learning-flow/api/generated.ts` from the contract |
| `npm run generate:api` | Regenerates `src/features/gamification/api/generated.ts` from `openapi-pilot-v1.json` |
| `npm run check:mobile-learning-artifact` | Inspects the built bundle for the child-app rules |
| `npm run native:generate` / `native:verify` | Regenerates or checks the Capacitor iOS and Android projects |
| `npm run e2e:mobile-learning` | Runs the mobile flow against the real backend |

## Whole stack

| Command | What it does |
|---|---|
| `scripts/dev.sh` | Starts the local API and the Grade 5 app |
| `npm run check:push` | Every check CI runs (`scripts/check.sh push`) |
