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

**In the mobile games** (`application/engine/area_flow.py`, `submit_before`): an
expert-initialised Bayesian model
(`modeling/misconception_inference/bayesian_model.py::predict_game_belief`).

1. The answer's evidence is read into a band: `normal`, `sparse` (no response time), `low_quality`
   (no interaction summary, in the games that read one) and, for Sinhala, `motor`, `rendering` and
   `motor_and_rendering`. Sinhala ignores timing, so it is never `sparse`.
2. The area's likelihood table gives, for that band and the server's error code, how well each
   misconception explains the answer. Subtraction first rewrites an `unknown_or_other` answer when
   its interaction summary points to a named mistake.
3. A learner prior multiplies each misconception by one plus how often it appeared in this
   learner's last five completed, unaided answers on the skill. Supported answers never count.
4. The reading is uncertain when the top probability is below 0.4, the top two are within 0.1, the
   band is `sparse` or `low_quality`, or, in eight games, the answer's own evidence puts
   `unknown_or_other` first. An uncertain reading names no reason, so Model 2 treats it as
   "unclear". Motor and rendering bands only weaken the evidence, so a clear history of the same
   mistake can still name a reason.

Every table and setting is a provisional expert assumption in
`data/gamification/expert-model-data/v1/`, taken from the earlier rule-based games and not yet
reviewed by a teacher. The model reproduces every reading those rules gave (tested against frozen
reference fixtures). Readings stored before the switch were written by the earlier rules and keep
their own version strings.

**Pilot API:** `probabilistic_model.py`.

## Model 2: support selection

**Question:** which help is most likely to make the child succeed on a fresh item after the help
is gone?

**Help types:** visual guidance, step-by-step guidance, conceptual re-explanation, a simpler
version of the same game, prerequisite repair, and a worked parallel example. The types an area may
use are listed in `content/area_support_catalog.py`.

**In the mobile games:** a LinUCB bandit run greedily (no exploration), expert-initialised,
learning online from valid Independence Gain (`modeling/support_selection/game_bandit.py`, used
through `application/game_help_order.py`). There is one bandit per subject, shared by every child.

- **Proposed condition:** the bandit predicts each drawable help's valid Independence Gain from
  the episode's context and puts the highest first. The context is the reason family and
  uncertainty from Model 1, the current-session Learning State reading, and this child's own
  record on this skill with that help (43 numbers per help). It never tries a help just to learn:
  every choice is its best guess.
- **Expert start:** before any child has played, its predictions reproduce the earlier rule-based
  order exactly: the help that answers Model 1's reason first, then the subject's order, with the
  Learning State adjustments. The starting gains are worth eight episodes of evidence.
- **Learning:** every valid proposed episode updates the subject's bandit once. The help the loop
  ended on is scored with the measured gain at full weight; each help that failed while shown is
  scored 0 at half weight; a help that was not shown teaches nothing. Supported correctness never
  does.
- **Approval:** a subject's bandit decides only after its artifact has been approved once by the
  researcher (`python -m scripts.approve_game_help_bandit`). Without one, the proposed condition
  gets the fixed order and records `no_approved_policy`.
- **Baseline condition:** the subject's fixed order (`support_selection/baseline_order.py`), with
  no Model 1 reason and no history. This is the comparison condition, and it never teaches the
  bandit.
- Mathematics and English each have their own fixed order, and the docstring in
  `baseline_order.py` explains the reasons for both. The worked example comes last in both,
  because it is the help closest to giving the answer. Sinhala keeps its three help types in the
  authored order.

Model cards for each subject's bandit and for the expert tables:
`data/gamification/expert-model-data/model-cards/`.

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

## How to describe the models in the thesis

- **Model 1:** "an expert-initialised Bayesian model". Its likelihood tables and settings are
  provisional expert assumptions taken from the earlier rules; none has been fitted to children.
- **Model 2:** "a LinUCB bandit run greedily (no exploration), expert-initialised, learning online
  from valid Independence Gain", not plain "LinUCB".
- **Credit:** "Model 2 is updated only from valid Independence Gain. The help on which the support
  loop ended receives the measured gain at full weight; helps that failed while shown receive a
  score of 0 at half weight, because a failed supported attempt is weaker evidence than an
  unsupported measurement. The weight is a provisional setting whose effect is reported by
  sensitivity replay (0, 0.25, 0.5, 1)."
- **Evaluation:** every logged choice was the model's best guess, so every propensity is 1 and
  off-policy evaluators cannot be used on these logs. The main test is the comparison of valid
  Independence Gain between the proposed and the baseline condition.
- **Sensitivity:** each provisional setting is reported by replaying the stored ledger with other
  values and counting changed first helps; a replay never invents the outcome of a help that was
  not given. Model 1's two uncertainty thresholds and its prior window are replayed the same way;
  its factor weights are not, because only the answer's mistake has an expert table.

## The research question

Does the misconception-conditioned help order (proposed) produce greater Independence Gain than
the fixed order (baseline), for the same Grade 5 Sinhala-medium content in the same app? The
answer is the comparison of mean valid Independence Gain between the two conditions.
