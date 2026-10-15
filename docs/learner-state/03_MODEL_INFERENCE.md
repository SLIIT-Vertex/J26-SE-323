# 03 — Model Inference

## 1. The four models

The component uses four binary XGBoost classifiers, stored as XGBoost JSON files under
`backend/app/learner_state/infrastructure/models/`.

| Detector | Modality | File | Input features |
| --- | --- | --- | --- |
| Confusion | Visual | `mindbridge_visual_model.json` | 11 `VISUAL_FEATURES` |
| Confusion | Behavioural | `mindbridge_behavior_model.json` | 10 `CONFUSION_BEHAVIOR_FEATURES` |
| Disengagement | Visual | `mindbridge_disengagement_visual_model.json` | 11 `VISUAL_FEATURES` |
| Disengagement | Behavioural | `mindbridge_disengagement_behavior_model_v2.json` | 20 `DISENGAGEMENT_BEHAVIOR_FEATURES` |

Facts readable from the model files:

- objective `binary:logistic` (the output is a probability between 0 and 1),
- 300 trees per model,
- saved from the XGBoost scikit-learn classifier interface.

Each model is unimodal and was trained on a single public dataset (see
[`02_DATA_AND_FEATURES.md`](02_DATA_AND_FEATURES.md)). The models themselves know nothing about the
other modality, reliability or time.

The models were trained with XGBoost, but the backend does **not** depend on the `xgboost`
package. It reads the model JSON files and evaluates the trees itself (see §3).

## 2. Loading and feature-order validation

`LearnerStateModels.load_default()` in `infrastructure/model_loader.py` loads all four models.
For each file, `_load_model()`:

1. checks that the file exists, otherwise raises `FileNotFoundError`;
2. reads the XGBoost JSON (`learner.feature_names`, the `gbtree` booster, the `binary:logistic`
   objective, `base_score` and the 300 trees); a missing or unexpected part raises `RuntimeError`;
3. compares the stored feature names, **including order**, with the expected tuple in the code;
   on any difference it raises `RuntimeError` with both lists.

```python
if actual_features != expected_features:
    raise RuntimeError(f"Feature mismatch for {filename}. ...")
```

This protects against a silent bug where a retrained model with a different column order is
dropped in and receives features in the wrong positions.

## 3. Generating a prediction

`_predict_probability()` is shared by all four `predict_*` methods:

1. Checks that every expected feature name is present in the feature dictionary; if not, raises
   `ValueError` listing the missing names.
2. Builds one row in the expected order; `None` values become `NaN` (missing).
3. Rounds every input value to float32, as XGBoost does. Split thresholds are rounded to float32
   when the model is loaded.
4. Walks each tree: a missing value follows the tree's default direction; otherwise it goes left
   when `value < threshold`. The leaf values of all trees are added to the base margin.
5. Applies the logistic function and clips the result to `[0, 1]`.

```text
features dict --(order, None -> NaN, float32)--> 300 trees --> margin --> sigmoid --> clip 0..1
```

The float32 rounding matters. Comparing in float64 sends values that lie on or next to a
threshold down the wrong branch. Such values occur in real requests; for example
`history_confidence` is always a multiple of 1/20, and the models' thresholds were learned from
exactly those values. Without the rounding, 31 of 150 realistic disengagement-behaviour cases in
the reference test differed from XGBoost.

All four predictions are made for every window (about 0.5 ms in total). Visual features are shared
by both visual models.

### Equivalence with XGBoost

`backend/tests/learner_state/test_model_reference_predictions.py` compares the evaluator with
1,200 predictions made by real XGBoost on the committed model files (300 per model): half with
inputs exactly on and next to the models' split thresholds, half from realistic learner sessions
built with the feature builder. All agree within 1e-6. The reference file is produced by
`research/learner-state/tools/generate_model_reference_predictions.py`, which needs an
environment with `xgboost` installed.

## 4. Decision thresholds

A raw probability of 0.5 does not mean the same thing for every model, because each model was
trained on a different dataset with different class balance. Each model therefore has its own
decision threshold. The values below are the defaults used by the implementation
(`domain/confusion.py` and `domain/disengagement.py`); the code comments describe them as
validation-selected thresholds.

| Model | Threshold | Parameter |
| --- | --- | --- |
| Confusion visual | **0.50** | `evaluate_confusion_window(visual_threshold=0.50)` |
| Confusion behaviour | **0.79** | `evaluate_confusion_window(behavior_threshold=0.79)` |
| Disengagement visual | **0.54** | `evaluate_disengagement_window(visual_threshold=0.54)` |
| Disengagement behaviour | **0.53** | `evaluate_disengagement_window(behavior_threshold=0.53)` |

`LearnerStateService` calls these functions without overriding the thresholds, so the defaults
above are what the API uses.

## 5. Threshold-centred evidence

Before fusion, each probability is mapped to an **evidence** value on a common scale, using
`threshold_centered_evidence()` in `domain/fusion.py`. The model's threshold maps to 0.5:

```text
p = clip(probability, 0, 1),  t = threshold  (must satisfy 0 < t < 1)

if p <= t:   evidence = 0.5 * p / t
else:        evidence = 0.5 + 0.5 * (p - t) / (1 - t)
```

Properties:

- `p = 0` gives 0, `p = t` gives 0.5, `p = 1` gives 1.
- The mapping is piecewise linear and keeps the ordering of probabilities.
- After the mapping, "evidence ≥ 0.5" means "this model's own threshold was reached", for every
  model.

Example — confusion behaviour model, threshold 0.79:

| Probability | Evidence |
| --- | --- |
| 0.19 | 0.5 × 0.19 / 0.79 ≈ 0.12 |
| 0.79 | 0.50 |
| 0.895 | 0.5 + 0.5 × 0.105 / 0.21 = 0.75 |

Without this step, a behaviour probability of 0.70 (below its 0.79 threshold) would be treated as
stronger confusion evidence than a visual probability of 0.55 (above its 0.50 threshold), which
would be wrong.

## 6. Training notebooks and results

The Kaggle notebooks that trained these models, with their saved outputs, are in
`research/learner-state/notebooks/`. They show how each label was defined, how each threshold was
selected on the validation split, and the test results, which are summarised in
[`07_EVALUATION_AND_LIMITATIONS.md`](07_EVALUATION_AND_LIMITATIONS.md#2-unimodal-model-results-level-b).
They are unimodal results on public datasets with proxy labels, not results for MindBridge
learners.
