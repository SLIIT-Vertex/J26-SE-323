# 07 — Evaluation and Limitations

> **Be honest about what has been evaluated.** The multimodal learner-state system has **not** been
> validated on synchronized data from real learners. Do not write claims such as "the fusion
> improves detection accuracy" or "validated on MindBridge learners" until the pilot study in §3
> has been completed.

## 1. Three levels of evidence

| Level | What it shows | Status |
| --- | --- | --- |
| **A. Implemented prototype** | The pipeline runs end to end: features → models → reliability → fusion → temporal decision → action, behind a tested API. | Done. Verified by the automated tests ([`08`](08_IMPLEMENTATION_AND_TESTING.md)). |
| **B. Unimodal model evaluation** | Each XGBoost model separates its target class on held-out data from **its own** public dataset (DAiSEE for visual, ASSISTments for behavioural). Thresholds were selected on validation data. | Done during model development, outside this repository. |
| **C. Multimodal evaluation** | Reliability-aware fusion and temporal decisions detect confusion and disengagement better, or more usefully, than single modalities on the **same** learners at the **same** time. | **Not done.** Needs synchronized MindBridge pilot data. |

Level A is software correctness. Level B is per-model performance. Neither is evidence for level C.

## 2. Prototype metrics

This repository contains the trained model files and the runtime code, but **no** training
scripts, evaluation notebooks or metric reports for the learner-state models. No metric can
therefore be verified from the repository, and none is reported here.

What can be verified from the repository:

| Item | Value | Source |
| --- | --- | --- |
| Model type | XGBoost, `binary:logistic`, 300 trees each | model JSON files |
| Feature counts | 11 visual, 10 confusion behaviour, 20 disengagement behaviour | `model_loader.py`, checked against model files at load time |
| Decision thresholds | confusion visual 0.50, confusion behaviour 0.79, disengagement visual 0.54, disengagement behaviour 0.53 | `domain/confusion.py`, `domain/disengagement.py` |
| End-to-end API behaviour | 200 response with all fields; 409 on duplicate window | `backend/tests/test_learner_state.py` |

When unimodal metrics (for example AUC, F1, precision and recall at the selected threshold, and
the test-set size) are added to the project, they should be:

1. reported **per model and per dataset**, never as a "multimodal" result;
2. reproducible by a script or notebook committed under `research/`;
3. reported with the threshold at which they were computed.

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
- **Labels are proxies.** DAiSEE confusion and boredom labels are annotations of video clips, not
  measured internal states. The behavioural labels used with ASSISTments are also proxy
  definitions of confusion and disengagement. A model can only be as valid as the proxy it learned.
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
- **No authentication or learner check.** The endpoint is open and does not check that
  `learner_id` exists in the shared learners table.

## 5. Privacy and ethics

The component is designed to minimise sensitive data:

- **No face recognition.** The component never identifies who a person is. It receives only
  aggregate numbers such as eye openness, gaze ratio, head angles and face-visibility ratio.
- **No raw video.** The API schema has no field for images or video. Raw webcam frames must not be
  sent to or stored by this component; only derived visual features are consumed.
- **No storage of learner-state results.** The component currently writes nothing to the database
  or disk; short session history exists only in memory.
- **No diagnosis.** "Confused" and "disengaged" are short-term learning-support signals. They are
  not mental-health, emotional or clinical assessments, and must not be presented to learners,
  parents or teachers as such.
- **Support, not judgement.** Outputs are used only to choose supportive actions such as monitoring,
  a tutor hint or a re-engagement prompt.

Any study with real learners — including the synchronized pilot in §3 — involves children and
webcam-based sensing. It requires appropriate **ethics approval**, informed **parental/guardian
consent**, and the child's **assent**, with clear information about what is captured, how derived
features are used and how participants can withdraw.
