# The three models

This page explains what each model does and where its code is. For the code-level table of which
implementation each app path runs, see
[`backend/app/gamification/modeling/README.md`](../../backend/app/gamification/modeling/README.md).

## The loop

```text
unsupported before item → score → detect difficulty
  → Model 1: estimate WHY the child struggled
  → Model 2: choose WHICH help, in which order
  → help rounds → withdraw every trace of help
  → fresh unsupported after item → score
  → Model 3: Independence Gain = after − before, and is it valid?
  → a valid gain is the only reward Model 2 learns from
```

Supported correctness, coins and XP never train a model.

## Model 1: misconception inference

**Question:** why is this child likely to be wrong on this skill?

**Output:** a probability for each misconception in the skill's reviewed catalogue, always
including `unknown_or_other`, plus confidence. Low evidence moves the belief toward
`unknown_or_other` and marks it low confidence. It then cannot drive a narrow help choice.

**In the mobile games** (`application/engine/area_flow.py`, `submit_before`):

1. The area's authored rule `content/<slug>.py::infer_belief(error_code)` turns the server's
   error code into a normalised distribution. It puts most of the mass on the misconception that
   error code names, and keeps the rest on the other hypotheses and `unknown_or_other`. The
   weights are authored per area. For example, the Sinhala rule in `content/sinhala_common.py`
   also moves mass to `unknown_or_other` for motor or rendering problems. Sparse evidence, such as
   missing timing, moves most of the mass to `unknown_or_other`.
2. `modeling/misconception_inference/learner_prior.py::apply_learner_prior` adjusts that belief
   with a bounded Dirichlet prior from this learner's last five completed, unsupported answers on
   the same skill. Supported answers never count.

**Research models (offline and tests):** `misconception_inference/bayesian_model.py` is an
expert-initialised Bayesian update, with `training.py` and `evaluation.py`. The pilot API uses
`probabilistic_model.py`.

## Model 2: support selection

**Question:** which help is most likely to make the child succeed on a fresh item after the help
is gone?

**Help types:** visual guidance, step-by-step guidance, conceptual re-explanation, a simpler
version of the same game, prerequisite repair, and a worked parallel example. The types an area may
use are listed in `content/area_support_catalog.py`.

**In the mobile games:** `modeling/support_selection/support_order.py::choose_support_order`
fixes the help order for the episode.

- **Proposed condition:** the first help answers Model 1's reason. A current-session Learning
  State reading can change that. `disengaged`, or `confused` while Model 1 is uncertain, puts the
  simpler version first. `confused` alone moves the worked example earlier. The help with the
  best record of valid post-withdrawal gains for this learner and skill then moves to the front;
  when the learning state has changed the order, it needs enough successes to do so. The rest
  follow the subject's order.
- **Baseline condition:** the subject's fixed order is used, with no Model 1 reason and no
  history. This is the comparison condition.
- Mathematics and English each have their own fixed order, and the docstring in
  `support_order.py` explains the reasons for both. The worked example always comes last, because
  it is the help closest to giving the answer.

**Pilot API:** `reference_policy.py::SafeSupportPolicy` and the contextual bandit
`learned_policy.py::LinUCBPolicy`. The bandit is updated by `application/policy_update.py` and
replayed offline by `offline_update.py`.

## Model 3: Independence Gain

**Question:** did the child's unsupported performance improve after the help was removed?

```text
B  = before score / before maximum      (unsupported_before item)
A  = after score  / after maximum       (fresh unsupported_after item)
IG = A − B                              (raw; no weighted variant replaces it)
```

**In the mobile games:** `modeling/independence_gain/episode_measurement.py::measure_withdrawn_episode`.
It reads only the before attempt and the after attempt, never the help rounds.

**Validity.** A gain is valid only if all of the following hold. Otherwise it is stored with its
exclusion reason and Model 2 does not learn from it (`independence_gain/validity.py`):

- the before and after items are the same skill and the same reviewed parallel family;
- the after item is unseen and was not exposed by any help;
- all help was withdrawn and confirmed (`all_support_removed`, `answer_revealing_state_cleared`,
  `input_handlers_cleared`);
- no adult or tutor help was given;
- the scoring and equivalence versions are compatible;
- the episode is complete.

## The research question

Does the misconception-conditioned help order (proposed) produce greater Independence Gain than
the fixed order (baseline), for the same Grade 5 Sinhala-medium content in the same app? The
answer is the comparison of mean valid Independence Gain between the two conditions.
