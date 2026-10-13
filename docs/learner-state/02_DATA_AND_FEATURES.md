# 02 — Data and Features

This document lists the exact features the four models expect. Feature order is defined in
`infrastructure/model_loader.py` and is checked against each model file at load time (see
[`03_MODEL_INFERENCE.md`](03_MODEL_INFERENCE.md)).

## 1. Source datasets

The models were trained on two **independent** public datasets:

| Modality | Dataset | Used for |
| --- | --- | --- |
| Visual | **DAiSEE** (webcam videos of students, labelled for affective states including confusion and boredom) | confusion visual model, disengagement visual model |
| Behavioural | **ASSISTments** (logs from an online mathematics tutor) | confusion behaviour model, disengagement behaviour model |

The training scripts and notebooks are not part of this repository; the repository contains only
the trained model files and the runtime code.

> **The two datasets are not synchronized.** DAiSEE videos and ASSISTments interaction logs come
> from different learners, at different times, in different settings. No DAiSEE row was paired
> with any ASSISTments row, and no "multimodal sample" was created from them. Each model only ever
> saw data from its own dataset.

This is why the models are **unimodal**: each one is trained and evaluated on one modality only.
The fusion step ([`04`](04_RELIABILITY_AND_FUSION.md)) and temporal step
([`05`](05_TEMPORAL_DECISION_ENGINE.md)) combine them only at runtime.

Final validation of the multimodal pipeline requires **synchronized MindBridge pilot data**, where
webcam-derived features and in-app interaction logs are recorded from the same learner during the
same window.

## 2. Visual features (11)

Used by both visual models (`VISUAL_FEATURES`). They are summaries over one window, computed on the
client or a separate vision step. The learner-state API accepts only these derived numbers.

| Feature | Meaning |
| --- | --- |
| `mean_eye_openness` | Average eye-openness measure over the window |
| `std_eye_openness` | Variation of eye openness (e.g. blinking, drowsiness) |
| `mean_gaze_ratio` | Average gaze-direction ratio |
| `std_gaze_ratio` | Variation of gaze ratio (looking around) |
| `mean_pitch` | Average head pitch (up/down), signed |
| `mean_yaw` | Average head yaw (left/right), signed |
| `mean_roll` | Average head roll (tilt), signed |
| `mean_abs_pitch` | Average absolute pitch |
| `mean_abs_yaw` | Average absolute yaw |
| `mean_abs_roll` | Average absolute roll |
| `face_visibility_ratio` | Share of the window in which a face was detected (0–1) |

The absolute head-pose features and `face_visibility_ratio` are also used to compute **visual
reliability** ([`04`](04_RELIABILITY_AND_FUSION.md)). Values must be produced in the same way and
the same units as during training, otherwise the model inputs will be out of distribution.

## 3. Confusion behaviour features (10)

Built by `build_confusion_behavior_features()` in `infrastructure/feature_builder.py`
(`CONFUSION_BEHAVIOR_FEATURES`). Nine come directly from the request; one is derived.

| Feature | Source | Meaning |
| --- | --- | --- |
| `correct` | request | Correctness of the response (0–1) |
| `bottom_hint` | request, nullable | Whether the learner reached the final ("bottom-out") hint; `null` when unknown |
| `hint_count` | request | Number of hints used |
| `attempt_count` | request | Number of attempts |
| `ms_first_response` | request | Time to first response, in milliseconds |
| `overlap_time` | request | Time spent on the problem, in milliseconds |
| `first_action` | request | Behavioural model input field retained from the training data |
| `position` | request | Behavioural model input field retained from the training data |
| `original` | request | Behavioural model input field retained from the training data |
| `bottom_hint_missing` | derived | `1.0` if `bottom_hint` is `null`, otherwise `0.0` |

A `null` `bottom_hint` is passed to XGBoost as a missing value (`NaN`), which XGBoost handles
natively. The extra `bottom_hint_missing` flag lets the model learn from missingness explicitly.

The field names follow the ASSISTments column names used during training. This documentation does
not assign a semantic meaning to `first_action`, `position` or `original`; they are passed to the
model as numeric inputs exactly as received. When MindBridge games produce these values, they must
use the same coding and units as the training data.

## 4. Disengagement behaviour features (20)

Built by `build_disengagement_behavior_features()` (`DISENGAGEMENT_BEHAVIOR_FEATURES`). It
contains the 10 confusion features above plus 10 **learner-history** features that compare the
current window with the same learner's recent behaviour in this session.

### 4.1 Learner history

- The service passes the previous behaviour observations of the session (at most 20,
  `HISTORY_WINDOW = 20`). The current window is **not** included.
- `history_confidence = min(history_count / 20, 1.0)` — how much history is available.
- `baseline_available` is `1.0` only when at least 5 previous observations exist
  (`MIN_BASELINE_HISTORY = 5`).

### 4.2 Features

| Feature | Definition (when baseline is available) |
| --- | --- |
| `recent_log_rt` | mean of `log1p(max(0, ms_first_response))` over the history |
| `recent_accuracy` | mean of `correct` over the history |
| `recent_attempts` | mean of `attempt_count` over the history |
| `recent_hints` | mean of `hint_count` over the history |
| `rt_deviation` | `log1p(max(0, current ms_first_response)) - recent_log_rt` |
| `attempt_deviation` | `current attempt_count - recent_attempts` |
| `hint_deviation` | `current hint_count - recent_hints` |
| `accuracy_deviation` | `current correct - recent_accuracy` |
| `history_confidence` | `min(history_count / 20, 1.0)` |
| `baseline_available` | `1.0` |

When fewer than 5 previous observations exist, the eight `recent_*` and `*_deviation` features are
set to `None` (missing for XGBoost), `history_confidence` is still reported, and
`baseline_available` is `0.0`.

This is the "learner-specific" part of the design: the disengagement behaviour model judges the
current response relative to the learner's own recent pace, accuracy, attempts and hint use, not
only against population averages.

| Previous windows in session | `history_confidence` | `baseline_available` | Deviation features |
| --- | --- | --- | --- |
| 0 | 0.00 | 0.0 | missing |
| 4 | 0.20 | 0.0 | missing |
| 5 | 0.25 | 1.0 | computed |
| 20 or more | 1.00 | 1.0 | computed from last 20 |

Note that this history is built **at runtime** from the windows sent to the API in the current
session. It is not loaded from a database and starts empty for every new session.

## 5. Other request inputs

| Input | Used for |
| --- | --- |
| `task_progress` (0–1, optional) | Distinguishing productive from intervention-worthy confusion ([`05`](05_TEMPORAL_DECISION_ENGINE.md)). Not a model feature. |
| `timestamp` | Accepted and carried in the window object; not used in any calculation. Ordering uses `window_id`. |
