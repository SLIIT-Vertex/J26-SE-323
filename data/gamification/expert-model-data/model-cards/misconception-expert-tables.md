# Model card: Bayesian misconception expert tables

Model 1 in every game (37 areas). After a wrong unaided answer it gives a probability for every
misconception in the area's catalogue, always including `unknown_or_other`.

## What it is

- **An expert-initialised Bayesian model**
  (`backend/app/gamification/modeling/misconception_inference/bayesian_model.py::predict_game_belief`,
  model version `bayesian-misconception-v2`). The answer's evidence band and error code select a
  likelihood row from the area's table; a learner prior multiplies each misconception by one plus
  its count in the learner's last five completed, unaided answers on the skill (pseudocount 1);
  the result is normalised.
- **Factors:** only the mistake in the answer carries weight (1). The option chosen, attempts,
  response time and Learning State are recorded as factors but switched off (weight 0), because
  no expert table exists for them.
- **Uncertainty:** a reading is uncertain when the top probability is below 0.4, the top two are
  within 0.1, the evidence band is `sparse` or `low_quality`, or, in eight games, the answer's own
  likelihood row puts `unknown_or_other` first. Motor and rendering bands only weaken the row.

## Evidence

**Provisional expert assumptions, not reviewed by a teacher** (`expert-model-data-v1`,
`reviewed_by: null`). Every table was taken from what the earlier rule-based games did, through the
frozen reference fixtures, never by calling the rules; no child's answers were used to fit them.
The model reproduces every frozen reading of those rules exactly (tested). Tables: one per area in
`../v1/misconception_tables/`; shared settings in `../v1/misconception_settings.json`; each
file's SHA-256 is pinned in `../v1/manifest.json` and checked on loading.

## Provisional settings

Reported by a sensitivity replay on the research dashboard: stored answers are read again with one
value changed, from the same inputs and the same earlier answers, and compared with the child's
next unaided mistake (agreement and Brier score) and with the stored reading (changed reasons and
"unsure" flags).

| Setting | Value | Replayed with |
|---|---|---|
| Top probability below which a reading is unsure | 0.4 | 0.3, 0.4, 0.5 |
| Top-two margin below which a reading is unsure | 0.1 | 0.05, 0.1, 0.2 |
| Learner-prior window (unaided answers remembered) | 5 | 3, 5, 8 |
| Factor weights | mistake 1, others 0 | not replayed: only the mistake has a table |

## Approval

The tables are not an approved artifact: they are a versioned data package whose hashes every
loader checks. A change of a table or setting is a new package version, regenerated only by
`tools/gamification/datasets/build_expert_model_data.py`, and changes the help-order bandits'
artifacts too, which then need a new approval.

## Limits

- Probabilities come from expert assumptions, not from children's data; the dashboard's agreement
  and calibration checks are the evidence of how well they hold.
- Readings stored before the switch were written by the earlier rules and keep their own version
  strings.
