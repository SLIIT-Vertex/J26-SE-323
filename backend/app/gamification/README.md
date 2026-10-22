# `app.gamification`: adaptive gamified learning (backend)

Grade 5 Sinhala-medium area games, the adaptive episode around them, and the three research
models. Design and scope: [`docs/adaptive-gamified-learning/README.md`](../../../docs/adaptive-gamified-learning/README.md).
The models in plain words: [`docs/adaptive-gamified-learning/models.md`](../../../docs/adaptive-gamified-learning/models.md).

## Map

```text
gamification/
  api/
    learning_flow_router.py      /learning-flow and /development/learning-flow  ← the mobile games
    router.py                    pilot API: /adaptive-episodes, /game-sessions, /admin, /evaluation, /research/exports
    research_dashboard_router.py /research-dashboard (researcher-only)
    contracts.py, research_contracts.py, dependencies.py (pilot wiring)
  application/
    engine/                      ← THE SHARED EPISODE ENGINE (start here)
      area_flow.py               AreaGameFlow: one episode for any area
      english_area_flow.py       EnglishAreaFlow: base of the English games
      sinhala_area_flow.py       SinhalaAreaFlow: base of the Sinhala games
    <slug>_flow.py  × 37         one small profile class per playable area (see table below)
    learning_flow_orchestration.py  LearningFlowOrchestrator: routes an episode to its area flow
    support_rounds.py            the multi-help loop inside one episode
    support_builders/            builds each help type; lessons/<topic>.py hold the teaching text
    research_dashboard/          read models behind the research dashboard
    episode_use_cases.py, session_play.py, delivery.py, policy_update.py, …   the pilot API path
    records.py, ports.py         records and ports shared by both paths
  content/
    <slug>.py  × 37              per area: items, answer checking, authored Model 1/2 rules
    loader.py, records.py, catalog.py, *_catalog.py, playable_area_package.py   package loaders
  modeling/                      Model 1, Model 2, Model 3 (see modeling/README.md)
  domain/                        episode state machine and value types
  infrastructure/
    db/                          SQLAlchemy models and stores (all tables: db/models.py)
    gateways/                    adapters to knowledge tracing and learner state
    memory.py, episode_memory.py in-memory adapters for tests and the pilot wiring
  skill_catalogue/               reviewed skill catalogue
  demo_seed/                     python -m app.gamification.demo_seed   (seed and verify a demo learner)
  validation/                    python -m app.gamification.validation  (simulated cohort)
  data_paths.py                  where data/gamification/ is (env MINDBRIDGE_GAMIFICATION_DATA_DIR)
```

Area game files keep the `application/<slug>_flow.py` layout on purpose:
`backend/scripts/build_game_skill_map.py` and `tests/gamification/test_pilot_evidence_release.py`
discover games by scanning that folder for `*_flow.py` modules.

## One episode, in code order

The mobile app calls `api/learning_flow_router.py` → `LearningFlowOrchestrator` → the area's
flow. Every step below is a method of `AreaGameFlow` in `application/engine/area_flow.py`.

| Step | Method | What happens |
|---|---|---|
| 1 | `open` | Draw a before item and a parallel after item; reserve the after item so it stays unseen |
| 2 | `submit_before` | Score the unsupported answer on the server (`validate_constructed_response`) |
| 3 | `submit_before` | **Model 1**: `self._infer_belief` (the area's `infer_belief`) then `apply_learner_prior` |
| 4 | `_start_support_loop` | **Model 2**: `choose_support_order` fixes the help order; the content module's `scaffold_decision` is stored as `reference_decision` |
| 5 | `submit_supported`, `complete_support` | Help rounds (`support_rounds.py`, `support_builders/`) |
| 6 | `withdraw` | Every trace of help is removed and confirmed |
| 7 | `present_after`, `submit_after` | Fresh unsupported after item |
| 8 | `submit_after` | **Model 3**: `measure_withdrawn_episode` → Independence Gain and validity |

## Where is…?

| Question | Answer |
|---|---|
| How does one game episode run? | `application/engine/area_flow.py` (table above) |
| How does Model 1 / 2 / 3 work? | [`modeling/README.md`](modeling/README.md) |
| Which game is area `G5-AREA-MAT-08`? | `application/division_adventure_flow.py` + `content/division_adventure.py`; full table in [`frontend/src/features/areas/README.md`](../../../frontend/src/features/areas/README.md) |
| How is an answer scored? | `content/<slug>.py::validate_constructed_response` |
| Where are items generated? | `content/<slug>.py::generate_item` and `generate_simpler_item` |
| Where is the help (lesson) text? | `application/support_builders/lessons/<topic>.py` |
| Which help types may an area use? | `content/area_support_catalog.py` (data: `data/gamification/grade5-area-support-catalog/`) |
| Where is the research dashboard? | `api/research_dashboard_router.py` → `application/research_dashboard/` → `infrastructure/db/research_dashboard_reader.py` |
| Where are the tables? | `infrastructure/db/models.py`; migrations in `backend/alembic/versions/` |
| How do I add an area game? | Add `content/<slug>.py` and `application/<slug>_flow.py` (copy a sibling profile), register the class in `learning_flow_orchestration.py`, then add the frontend folder and registry row |
