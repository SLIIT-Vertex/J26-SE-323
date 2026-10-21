# 12 — Pilot Study Plan (synchronized multimodal validation)

> **Status: draft proposal.** No data has been collected. Every number in this document (sample
> size, session length, label frequency, criteria) is a proposal to be agreed with the supervisor
> and approved through the university's ethics process. The pilot cannot start before the
> prerequisites in §10 are met.

This plan describes the study that provides level-C evidence in
[`07_EVALUATION_AND_LIMITATIONS.md`](07_EVALUATION_AND_LIMITATIONS.md#1-three-levels-of-evidence):
whether reliability-aware fusion and the temporal engine detect confusion and disengagement
usefully for the same learner at the same time. It turns the requirements listed in
[`07` §3](07_EVALUATION_AND_LIMITATIONS.md#3-required-multimodal-validation-future-work) into a
concrete procedure.

## 1. Why a pilot is needed

The four models were trained on two unrelated public datasets: DAiSEE (visual) and ASSISTments
(behaviour). No learner appears in both, so the training data cannot show how the two modalities
relate for one learner at one moment, and the fusion weights, reliability rules and temporal
thresholds are design decisions ([`07` §4.2](07_EVALUATION_AND_LIMITATIONS.md#42-fusion-and-temporal-design)).
The pilot is the first data in which both modalities are recorded together, aligned to the same
answered question, with a reference label for that question.

DAiSEE and ASSISTments remain separate: the pilot does not pair or merge them.

## 2. Research questions

| ID | Question | Main measure |
| --- | --- | --- |
| RQ1 | Can the visual and behavioural evidence be collected reliably from Grade 4–5 learners on the target device? | share of windows with usable visual data, distributions of reliability, head pose and response time, camera errors |
| RQ2 | Does reliability-aware fusion detect confusion and disengagement better than each modality alone and than fixed-weight fusion? | ROC-AUC, PR-AUC and macro-F1 against the reference labels, compared with learner-level bootstrap intervals |
| RQ3 | Does the temporal engine give fewer false alarms than single-window decisions, at an acceptable delay? | false alarms per session, precision of support requests, delay in windows |
| RQ4 | Which reliability constants and temporal thresholds suit this population? | values tuned on tuning learners, evaluated on held-out learners |

Out of scope: learning gains, the quality of tutor or re-engagement content, and any statement
about a child's emotions or mental health. Confusion and disengagement are short-term
learning-support signals ([`07` §5](07_EVALUATION_AND_LIMITATIONS.md#5-privacy-and-ethics)).

## 3. Design

- **Setting:** the game's first complete loop, Grade 5 Sinhala-medium mathematics, fractions
  (`MAT-FRC`), on a phone ([game README §7](../adaptive-gamified-learning/README.md)). Learner-state
  runs inside the game; it does not have its own activity.
- **Participants (proposal):** about 15–20 learners in Grade 4–5, each in 2 sessions of about
  20–25 minutes. This is a feasibility pilot: it estimates data quality, label agreement and effect
  sizes for a later, larger study, and is not powered for confirmatory claims.
- **Unit of analysis:** one learner-state window = one answered question
  ([`10`](10_FRONTEND_INTEGRATION.md#3-processing-pipeline)). With about 20–30 answered questions
  per session this gives roughly 600–1,200 windows in total; the exact count is reported, not
  assumed.
- **Silent mode (recommended):** learner-state decisions are computed and logged but do **not**
  change what the child sees. Otherwise the support given after a detection would change the
  behaviour and the labels that follow it, and the game's own conditions would be mixed with the
  learner-state evaluation. Build the app with `VITE_LEARNER_STATE_PROMPTS=off`: decisions are
  still recorded, and the support prompts of [`11` §7](11_GAME_INTEGRATION.md#7-consuming-the-result)
  are not shown.
- **Learners without camera consent** can still take part in the game. Their windows carry no
  visual evidence and are analysed only for behaviour-only questions.

## 4. Data recorded per window

Only derived numbers are recorded. The privacy rules of [`10` §6](10_FRONTEND_INTEGRATION.md#6-privacy-raw-frames-stay-on-the-device)
are unchanged: no frames leave the device.

| Group | Fields |
| --- | --- |
| Identity | pseudonymous learner code, game session id, `window_id`, Universal Skill ID, item id, phase (baseline / verification), server time |
| Visual (if camera consent) | the 11 window features; samples and samples with a face |
| Behaviour | the fields of [`11` §5](11_GAME_INTEGRATION.md#5-behavioural-fields), as sent to the models |
| Model output | for confusion and disengagement: visual and behaviour probability, both reliabilities, fused evidence, confidence, `temporal_score`, `average_confidence`, `persistent_count`, state, support need; `recommended_action` |
| Context | device model, camera on/off, camera error kind |
| Reference labels | §5 |

**Not recorded:** video, images, face landmarks, audio, names, school or guardian details. No face
recognition is performed.

Today only the latest state per learner and skill is stored ([`07` §5](07_EVALUATION_AND_LIMITATIONS.md#5-privacy-and-ethics)).
A per-window research log for consenting participants has to be added first (§10).

## 5. Reference labels

The public-dataset labels are proxies ([`07` §4.1](07_EVALUATION_AND_LIMITATIONS.md#41-data-and-labels)).
For the pilot, the meaning of "confused" and "disengaged" is fixed in a short coding manual before
data collection.

### 5.1 Observer coding (primary)

- Two trained observers code each answered question live, in the style of the field-observation
  protocol BROMP, whose classroom observations were used to build the affect detectors behind the
  ASSISTments labels. Codes: confusion
  (`confused` / `not confused` / `unsure`) and engagement (`on task` / `off task` / `unsure`).
- Observers code by question number, so that labels align with `window_id` without video. Nothing
  is filmed, so labels cannot be re-checked later; this is an accepted trade-off of the privacy
  design.
- Observers do not see the learner-state output.
- Agreement: both observers code the same windows in at least 20% of sessions. Cohen's κ is
  reported; κ ≥ 0.6 (proposal) is required before single-observer coding is used.

### 5.2 Self-report (secondary)

- A one-tap, child-friendly question after selected items, for example every fourth item:
  "Was this question confusing?" with three faces. Wording is reviewed in Sinhala.
- Kept sparse, because frequent questions can themselves disengage a child.
- Self-report and observer labels are analysed separately and their agreement is reported.

## 6. Session procedure (proposal)

1. Check guardian consent, the child's assent and, separately, camera consent
   (`learner_state_camera`).
2. Place the phone on a stand at about eye level and check with a short camera test that the face
   is in view. The device's camera-in-use indicator stays visible during the session.
3. One practice question (not analysed).
4. About 20 minutes of play in silent mode, with observer coding.
5. End-of-session self-report and a short debrief. The child may stop at any time without giving a
   reason.

## 7. Analysis plan

The analysis is fixed before the labels are examined. All results are reported, including
negative ones.

### 7.1 Splits

- All splits are by learner: no learner's windows are in both tuning and evaluation.
- RQ2 uses the current, unchanged thresholds, so it needs no tuning split.
- RQ4 tunes on about two thirds of the learners and reports on the remaining third. With few
  learners, leave-one-learner-out cross-validation is used instead.
- Uncertainty: bootstrap intervals that resample learners, not windows, because windows of one
  learner are not independent.

### 7.2 RQ1 — data quality

- Share of windows with usable visual data; distributions of `face_visibility_ratio`, visual and
  behavioural reliability, and samples per window (the planned rate is 30 per 10 seconds).
- Head-pose distributions compared with the reliability quantiles taken from DAiSEE (Q75 / Q95,
  [`04` §1.2](04_RELIABILITY_AND_FUSION.md#12-head-pose-quality)). Phones held below the face may
  produce larger pitch than webcams, which would lower visual reliability for everyone.
- Response-time distribution compared with `RT_Q01` / `RT_Q99`
  ([`04` §2.1](04_RELIABILITY_AND_FUSION.md#21-data-quality)).

### 7.3 RQ2 — detection

For confusion and for disengagement, against observer labels (`unsure` excluded):

| Variant | Score |
| --- | --- |
| Visual only | visual threshold-centred evidence |
| Behaviour only | behaviour threshold-centred evidence |
| Fixed-weight fusion | 0.5 × visual + 0.5 × behaviour evidence |
| Reliability-aware fusion (deployed) | fused evidence |

Measures: ROC-AUC and PR-AUC (with the positive rate as chance level), macro-F1 at 0.50 fused
evidence. Fusion is called beneficial only if the learner-bootstrap interval of the ROC-AUC
difference against the best single modality excludes 0.

### 7.4 RQ3 — temporal decisions

On each session's window sequence:

- precision of `request_tutor_support` and `request_reengagement_support` against labels (label
  in the same or previous window);
- false alarms per session (support requested with no positive label in the last 3 windows);
- delay: windows from the first labelled positive window of an episode to the support request;
- compared with a single-window rule that requests support whenever the current fused evidence is
  at least 0.60.

`productive_confusion` is evaluated only if the game supplies `task_progress`; otherwise it is
reported as not evaluable.

### 7.5 RQ4 — calibration

On tuning learners only: the intervention threshold (0.60), `min_persistent_windows` (2), the
head-pose and response-time quantiles, and `min_progress_gain` (0.05, only with `task_progress`).
Tuned values are reported on held-out learners and marked as pilot-derived.

## 8. Success criteria (proposal)

Feasibility, decided before the pilot:

| Criterion | Proposed target |
| --- | --- |
| Sessions completed | ≥ 80% of started sessions |
| Windows with usable visual data (camera-consent learners) | ≥ 70% |
| Observer agreement | Cohen's κ ≥ 0.6 for each code |
| Privacy incidents | none |

Detection results (RQ2–RQ4) are reported whatever they show; they are not pass/fail criteria for
a feasibility pilot.

## 9. Ethics and privacy

- University ethics approval before any contact with children; the approved protocol overrides
  this draft.
- Informed guardian consent and the child's assent, in Sinhala, explaining what is captured (only
  numbers about face position, eyes and answers; never video), what it is used for and how to
  withdraw.
- Camera use has its own consent; a child can play without the camera.
- Withdrawal at any time; the participant's windows are deleted on request.
- Pseudonymous codes only; the key linking codes to names is held separately by the researcher
  and not stored in MindBridge.
- Storage location, access and retention period of the research log are set in the ethics
  application.
- No individual results are reported to children, guardians or teachers as judgements of the
  child. Results are reported in aggregate.

## 10. Prerequisites

| Prerequisite | Owner | Status (2026-10-20) |
| --- | --- | --- |
| Ethics approval of the final protocol | learner-state owner with supervisor | not started |
| Game integration on the active path (`MobileLearningApp`), composing `GameAnswerRecorder` | learner-state owner, agreed with the game owner | done ([`11` §2](11_GAME_INTEGRATION.md#2-integration-point-grade-5-adventures)) |
| Camera-consent flow (`learner_state_camera`) and `useGameVisualFeatures` in the game screen | learner-state owner, agreed with the game owner | done for development; production needs guardian authentication ([`11` §4](11_GAME_INTEGRATION.md#4-camera-consent)) |
| Silent mode: record decisions without acting on them | learner-state owner | done: `VITE_LEARNER_STATE_PROMPTS=off` |
| Logging of shown prompts, if a pilot uses prompts | learner-state owner | not started |
| Per-window research log for consenting participants (§4) | learner-state owner | not started |
| Observer coding sheet or tool keyed by question number, and coding manual | learner-state owner | not started |
| `task_progress` from the game (only for productive confusion) | game owner | optional |
| Phone stand, test devices, Sinhala wording review | learner-state owner | not started |

## 11. Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Phone camera angle differs from DAiSEE webcams | low visual reliability, visual evidence ignored | stand at eye level; RQ1 measures it; RQ4 recalibrates |
| Population differs from DAiSEE (adults) and ASSISTments | weak model transfer | reported as a finding; retraining is future work |
| Few positive labels, especially disengagement | wide intervals | report PR-AUC with positive rate; treat as feasibility evidence |
| Observer presence changes behaviour | fewer off-task moments | practice question, quiet observation, report as limitation |
| Live labels cannot be re-checked | label noise | two observers on a share of sessions, κ reported |
| Session history is in memory | lost on backend restart | single backend process during sessions; log restarts |
