# 07 — Evaluation and Limitations

> **Be honest about what has been evaluated.** The multimodal learner-state system has **not** been
> validated on synchronized data from real learners. Do not write claims such as "the fusion
> improves detection accuracy" or "validated on MindBridge learners" until the pilot study in §3
> has been completed.

## 1. Three levels of evidence

| Level | What it shows | Status |
| --- | --- | --- |
| **A. Implemented prototype** | The pipeline runs end to end: features → models → reliability → fusion → temporal decision → action, behind a tested API. | Done. Verified by the automated tests ([`08`](08_IMPLEMENTATION_AND_TESTING.md)). |
| **B. Unimodal model evaluation** | How well each XGBoost model separates its proxy label on held-out data from **its own** public dataset (DAiSEE for visual, ASSISTments for behavioural). Thresholds were selected on validation data. | Done. Results in §2; notebooks in `research/learner-state/notebooks/`. |
| **C. Multimodal evaluation** | Reliability-aware fusion and temporal decisions detect confusion and disengagement better, or more usefully, than single modalities on the **same** learners at the **same** time. | **Not done.** Needs synchronized MindBridge pilot data. |

Level A is software correctness. Level B is per-model performance. Neither is evidence for level C.

## 2. Unimodal model results (level B)

The four models were trained and evaluated on Kaggle. The notebooks, with their saved outputs, are in
`research/learner-state/notebooks/`. All numbers below are copied from those saved outputs. Each
threshold was selected by the best macro-F1 on the **validation** split and then frozen; the
results are on the separate **test** split, which was not used for training or threshold choice.

| Model | Notebook | Data and proxy label | Test set (positive rate) | Threshold | ROC-AUC | PR-AUC | Macro-F1 | Positive-class precision / recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Confusion visual | `mindbridge-visual-model-01` | DAiSEE clips; `Confusion ≥ 1` | 1,784 clips (32.7%) | 0.50 | 0.576 | 0.388 | 0.543 | 0.383 / 0.579 |
| Confusion behaviour | `mindbridge-behaviour-model-01` | ASSISTments 2012–13; `Average_confidence(CONFUSED) ≥ 0.5` | 935,093 interactions, 7,002 learners (4.2%) | 0.79 | 0.760 | 0.144 | 0.592 | 0.182 / 0.317 |
| Disengagement visual | `mindbridge-disengagement-model-01` | DAiSEE clips; `Engagement ≤ 1` | 1,784 clips (4.9%) | 0.54 | 0.687 | 0.139 | 0.550 | 0.128 / 0.432 |
| Disengagement behaviour (v2) | `mindbridge-disengagement-model-01` | ASSISTments 2012–13; `Average_confidence(BORED) ≥ 0.5` | 935,093 interactions (15.7%) | 0.53 | 0.536 | 0.173 | 0.516 | 0.183 / 0.195 |

ROC-AUC 0.5 is chance level and 1.0 is perfect. PR-AUC should be compared with the positive rate,
which is its chance level.

How to read these results:

- Only the **confusion behaviour** model separates its classes moderately well (ROC-AUC 0.76).
  The **disengagement behaviour** (0.54) and **confusion visual** (0.58) models are close to chance,
  and the **disengagement visual** model is weak (0.69).
- The ASSISTments split is **learner-wise** (70/15/15 by `user_id`; no learner appears in two
  splits). The DAiSEE results use the dataset's provided train/validation/test label files.
- Learner-history features were tested as ablations. For confusion, adding lifetime or recent
  (20-interaction) baselines did **not** improve validation ROC-AUC (0.7545 without them vs 0.7523
  and 0.7520 with them), so the deployed confusion behaviour model uses no history features. For
  disengagement, the recent-baseline v2 model was only marginally better than v1 (validation
  ROC-AUC 0.536 vs 0.529).
- On the test data, 7.3% of interactions reach the confusion behaviour threshold of 0.79
  (68,457 of 935,093, derived from the notebook's test confusion matrix).

These are **unimodal results on public datasets** with **proxy labels** (§4.1). They are not
results for MindBridge learners and say nothing about the multimodal pipeline.

Other facts that can be verified from the repository:

| Item | Value | Source |
| --- | --- | --- |
| Model type | XGBoost, `binary:logistic`, 300 trees each | model JSON files, notebooks |
| Feature counts | 11 visual, 10 confusion behaviour, 20 disengagement behaviour | `model_loader.py`, checked against model files at load time |
| End-to-end API behaviour | 200, 404, 409 and 422 responses | `backend/tests/test_learner_state.py` |

## 3. Required multimodal validation (future work)

Final validation of the research contribution needs a **synchronized MindBridge pilot**:

- the same learner, in the same session, with webcam-derived visual features and in-app
  behavioural logs aligned to the same windows;
- ground-truth or reference labels for confusion and disengagement for those windows (for example
  observer coding or self-report, as approved by the ethics process);
- comparison of visual-only, behaviour-only, fixed-weight fusion and reliability-aware fusion;
- comparison of single-window decisions with the temporal engine (for example false alarms per
  session and delay before support);
- tuning of reliability penalties, fusion floors and temporal thresholds on this data, with a
  separate held-out set for final reporting.

## 4. Limitations

### 4.1 Data and labels

- **DAiSEE and ASSISTments are not synchronized.** They come from different learners and settings.
  No sample in either dataset contains both modalities, so the training data cannot show how the
  two modalities relate for one learner at one moment.
- **Labels are proxies.** DAiSEE confusion and engagement labels are annotations of video clips,
  not measured internal states. The ASSISTments labels are thresholded outputs of **existing affect
  detectors** (`Average_confidence(CONFUSED)` and `Average_confidence(BORED)` in the "data with
  predictions" release), not human judgements, so the behaviour models learn to imitate another
  model. In an exploratory check in the fusion notebook, a personalised deviation score (slower,
  more attempts, more hints, accuracy drop) was *inversely* related to the confusion proxy
  (validation ROC-AUC 0.39), so intuitive signs of struggle do not match this label. A model can
  only be as valid as the proxy it learned.
- **Behavioural-model compatibility gap.** The behaviour models use ASSISTments fields that
  MindBridge cannot yet produce truthfully. `position` ("assignment position on the class
  assignments page") has no game equivalent, and the numeric coding of `first_action` is not
  documented. These fields are not filled with invented constants; see
  [`11_GAME_INTEGRATION.md`](11_GAME_INTEGRATION.md#5-behavioural-fields).
- **Training history is lifetime, serving history is per session.** In training, learner-history
  features used each learner's previous ASSISTments interactions across the whole 2012–13 dataset
  (median 140 previous interactions). At runtime, history starts empty in every session.
- **Population mismatch.** Neither dataset was collected from Sri Lankan Grade 4–5 learners or in
  the MindBridge app. Feature distributions (and therefore the reliability constants such as head-
  pose quantiles and response-time percentiles) may differ for the target users.
- **Feature compatibility.** MindBridge must produce the visual and behavioural features with the
  same meaning and units as the training data. Behavioural field names follow ASSISTments columns,
  which do not map one-to-one onto game interactions.

### 4.2 Fusion and temporal design

- **Fusion and temporal rules are not yet validated.** Reliability formulas, penalty sizes, fusion
  floors, thresholds and the 3-window rule are transparent design decisions; they still require
  synchronized pilot data.
- **Windows are counted, not timed.** The `timestamp` is not used; "persistent" means "across
  recent windows", whatever their duration.
- **Confusion detection is conservative when the models disagree.** The 0.79 threshold was
  selected on validation data, and 7.3% of test interactions reach it (§2). When the visual model
  indicates confusion but the behaviour model does not, the fused evidence usually stays below the
  0.60 intervention level, so the system monitors instead of requesting tutor support. Whether this
  is the right behaviour can only be judged with synchronized pilot data.

### 4.3 Runtime and deployment

- **Behavioural history is runtime/session based.** Learner-history features use only windows sent
  in the current session. Each new session starts with no baseline (the first 5 windows have no
  deviation features, and behavioural reliability starts at 70% of its data-quality value).
- **Session state is in memory.** History is stored in a Python dictionary inside one
  `LearnerStateService` instance. It is lost when the backend restarts or reloads.
- **Multiple workers do not share state.** With several Uvicorn/Gunicorn worker processes, windows
  from the same session may reach different workers, each with its own history. Temporal decisions
  and `window_id` checks would then be inconsistent. The current design assumes a single process.
- **History is never evicted automatically.** Sessions stay in memory until restart (or until
  `clear_session` is called from code); there is no API to end a session.
- **Both modalities are required.** The API requires both the `visual` and `behaviour` objects. A
  client without a webcam cannot currently call it; it would need to send `face_visibility_ratio
  = 0` with placeholder visual values, which makes visual reliability 0 so that fusion relies on
  behaviour only. A proper optional-modality contract is future work.
- **No authentication.** The endpoint is open. It does check that `learner_id` exists in the
  shared learners table (HTTP 404 otherwise).
- **Tutor support need is provisional.** The 0–1 `support_need` handed to the AI Tutor is the
  confusion `temporal_score`; this mapping and its scale are not validated (see
  [`09`](09_TUTOR_HANDOFF.md#6-limitations)).
- **Temporal history is per session, not per skill.** After a skill switch, the first windows of
  the new skill still include windows from the previous skill.

## 5. Privacy and ethics

The component is designed to minimise sensitive data:

- **No face recognition.** The component never identifies who a person is. It receives only
  aggregate numbers such as eye openness, gaze ratio, head angles and face-visibility ratio.
- **No raw video.** The API schema has no field for images or video. Raw webcam frames must not be
  sent to or stored by this component; only derived visual features are consumed.
- **Minimal storage of learner-state results.** The database keeps only the **latest** derived
  result per learner and skill (states, support needs, recommended action, one 0–1 score and the
  window time) in `learner_skill_states`. No visual or behavioural features, images or window
  history are stored. Short session history exists only in memory. Any longer-term storage for a
  pilot study should be decided as part of its ethics approval.
- **No diagnosis.** "Confused" and "disengaged" are short-term learning-support signals. They are
  not mental-health, emotional or clinical assessments, and must not be presented to learners,
  parents or teachers as such.
- **Support, not judgement.** Outputs are used only to choose supportive actions such as monitoring,
  a tutor hint or a re-engagement prompt.

Any study with real learners — including the synchronized pilot in §3 — involves children and
webcam-based sensing. It requires appropriate **ethics approval**, informed **parental/guardian
consent**, and the child's **assent**, with clear information about what is captured, how derived
features are used and how participants can withdraw.
