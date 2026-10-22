# `modeling/`: the three research models

| Model | Question it answers | Package |
|---|---|---|
| **Model 1**: misconception inference | *Why* did the child get the unsupported item wrong? A probability over the skill's misconception catalogue, including `unknown_or_other` | `misconception_inference/` |
| **Model 2**: support selection | *Which help, in which order*, is most likely to make the child succeed on a fresh item after the help is gone? | `support_selection/` |
| **Model 3**: Independence Gain | *Did it work?* After-score minus before-score on parallel unsupported items, plus validity checks. Valid gains are Model 2's only reward | `independence_gain/` |

`shared/` holds feature building, contracts and the artifact registry. `offline/` is the offline
CLI (`python -m app.gamification.modeling.offline`). `synthetic/` generates seeded synthetic data
only; its numbers are never learner evidence.

## Which implementation runs where

The code supports three app paths. Each uses a different implementation of the same model, so
always say which path you mean. Verified by tracing imports on 2026-10-22.

| App path | Entry point | Model 1 | Model 2 | Model 3 |
|---|---|---|---|---|
| **Mobile area games** (what children play) | `api/learning_flow_router.py` → `application/learning_flow_orchestration.py` → `application/engine/area_flow.py` | Authored rule `content/<slug>.py::infer_belief`, then `misconception_inference/learner_prior.py::apply_learner_prior` (bounded Dirichlet prior over the last five unsupported answers) | `support_selection/support_order.py::choose_support_order`. Proposed condition: the first help answers Model 1's reason (`LEAD_BY_REASON`), a current-session Learning State reading (`disengaged`, or `confused` with an uncertain Model 1) may put the simpler version first, the help with the best record of valid post-withdrawal gains for this learner and skill moves to the front, the rest follow the subject's fallback order. Baseline condition: the subject's fixed order, no reason, no history. `content/<slug>.py::scaffold_decision` is stored only as `reference_decision` | `independence_gain/episode_measurement.py::measure_withdrawn_episode` |
| **Draft Sinhala curriculum slice** (fallback inside the orchestrator) | `learning_flow_orchestration.py` when no area flow matches | `misconception_inference/inference.py` | `support_selection/selection.py` | `independence_gain/measurement.py` |
| **Pilot API** | `api/router.py` → `api/dependencies.py` → `application/episode_use_cases.py`, `session_play.py` | `misconception_inference/probabilistic_model.py::ProbabilisticMisconceptionModel` | `support_selection/reference_policy.py::SafeSupportPolicy` plus `learned_policy.py::LinUCBPolicy`, updated online by `application/policy_update.py` and offline by `offline_update.py` | `independence_gain/calculator.py::RawIndependenceGainCalculator` |

These are used only by tests and offline research, not by any running path:

- `misconception_inference/bayesian_model.py` (`BayesianMisconceptionModel`), `deterministic_baseline.py`, `training.py`, `evaluation.py`
- `orchestration/episode_model_pipeline.py` (`ThreeModelPipeline`)
- `support_selection/evaluation.py`, `synthetic/`

> **Reporting note.** In the mobile games, Model 1 is an authored rule plus a learner prior, not
> the Bayesian model. Describe it that way in the thesis and the dashboard until
> `bayesian_model.py` is connected to that path.

## Shared rules (all paths)

- Only a **valid** Independence Gain (same skill, parallel family, unseen after item, help fully
  withdrawn, no leakage) may update Model 2: `independence_gain/validity.py`,
  `support_selection/reward.py`.
- Supported answers never enter Model 1's prior or Model 3's score.
- Every decision is stored with its version strings (`*_version` on each area profile) so a
  result can be traced to the exact rule that produced it.
