# Learner-state integration at answer submission

This note describes how the adaptive game connects a scored answer to learner-state support
recommendations and learner-evidence events. It is the implementation contract for the pilot
and learning-flow development flows.

## 1. Answer flow

For each accepted answer, the server:

1. validates and scores the answer from the server-owned rubric;
2. assigns the next session-local learner-state window id;
3. checks current camera consent before using optional visual features;
4. asks the learner-state gateway for a recent recommendation;
5. applies only an active, recognized support action to the immediate struggle decision; and
6. emits one deduplicated `gamification_item_scored` learner-evidence event.

Learner-state integration is fail-open. A missing visual snapshot, missing or withdrawn camera
consent, stale result, unmapped recommendation, or gateway failure does not reject an otherwise
valid answer. The server's score remains authoritative.

The game owns the answer-time gateway. Domain and application code do not import the
learner-state component directly; the implementation is composed through the gamification
infrastructure boundary.

## 2. Optional visual snapshot

The pilot answer request may include `visual`. It is an optional snapshot containing
exactly these 11 finite numeric values:

```text
mean_eye_openness
std_eye_openness
mean_gaze_ratio
std_gaze_ratio
mean_pitch
mean_yaw
mean_roll
mean_abs_pitch
mean_abs_yaw
mean_abs_roll
face_visibility_ratio
```

`face_visibility_ratio` must be between `0` and `1`, inclusive. An invalid optional snapshot is
discarded while the answer continues. The answer API does not accept raw images, video,
landmarks, embeddings, or biometric identifiers.

Before the gateway receives visual features, the server rechecks consent for the purpose
`learner_state_camera`. No current consent means no visual features leave the gamification
boundary. The client must treat capture as optional and must stop or avoid capture when consent
is absent.

The visual snapshot participates in the answer idempotency fingerprint. Reusing an idempotency
key with different visual values is therefore a conflicting request, just as changing the
answer itself would be.

## 3. Window identity and recommendation freshness

Every accepted answer advances a per-session `learner_state_window_id`. The current pilot
allocator is held in the development session process; a production deployment needs a durable,
concurrency-safe allocator before multiple workers can own the same session.

The gateway requests the learner-state result with the game `session_id` and a maximum age of
60 seconds. A stale result carries no actionable recommendation.

The active recommendation mapping is:

| Learner-state recommendation | Game behavior |
| --- | --- |
| `request_tutor_support` | Mark immediate tutor support as requested |
| `request_reengagement_support` | Mark immediate re-engagement support as requested |
| `none`, `monitor`, `collect_more_evidence`, missing, or unknown | Do not trigger immediate support |

The two request types remain distinct in the recorded reason. The learner-facing UI still needs
a dedicated re-engagement action before that distinction changes what the child sees.

A legacy numeric support-need threshold remains only for compatibility with the older v1
in-process adapter. New integrations should use the explicit recommendation.

## 4. Learner-evidence event

The pilot publishes the `gamification-learner-evidence-v2` contract. Validators continue to
accept v1 records during migration. One `gamification_item_scored` event is emitted with the
deduplication key:

```text
<attempt_id>:gamification_item_scored
```

The v2 scored event includes:

- `attempt_id`;
- the server-computed correctness result;
- canonical skill id `MAT-FRC`;
- normalized difficulty;
- nullable `response_time_ms`;
- whether the attempt was supported;
- `hint_count`, currently `0` or `1`;
- the runtime environment; and
- `model_ingestion_eligible`.

Pilot numeric difficulty is normalized under `pilot-difficulty-v1`:

| Source value | Normalized value |
| --- | --- |
| `1` | `easy` |
| `2` | `medium` |
| `3` | `hard` |

The original numeric value is retained. learning-flow maps its source category `introductory` to
`easy` under `learning_flow-introductory-v1`, retains the source category, and does not invent a
numeric value. learning-flow answer requests also accept nullable `response_time_ms`.

Development and test events set `model_ingestion_eligible = false`. That field is a producer
signal, not final authorization: the Knowledge Tracing ingestion boundary owns the final
eligibility decision.

## 5. Frontend responsibility

`GameHost` resolves the learner id from its prop or `VITE_LEARNER_ID`; the gamification feature
does not contain a hard-coded development learner id.

The host may receive an injected `visualFeatures` callback. When present, it sanitizes the
returned values and freezes one snapshot for the answer request. The host does not start a
second camera pipeline. Camera lifecycle, permission handling, and snapshot production belong
to the shared visual-feature hook.

The shared hook is `useGameVisualFeatures({ enabled })` in
`frontend/src/features/learner-state/game/`. `GameHost` is no longer mounted by the app; the
learning-flow adventures use the hook as described in §6.

## 6. Learning-flow adventures (active path)

The Grade 5 adventures (`/development/learning-flow/episodes`) record learner-state evidence
for every scored mathematics answer:

1. `NumberWorldFlow`, the base of every adventure flow, scores and commits the answer as before.
2. Only after the commit, and never for a replayed idempotent request, it calls
   `record_scored_answer()` (`application/learner_state_answers.py`) with the Universal Skill ID
   of the area, the server correctness, `response_time_ms`, `supported = false` and
   `hint_count = 0` (only unsupported answers are scored).
3. Camera values are passed only with current `learner_state_camera` consent; the answer
   behaviour is recorded either way, and fusion then gives the visual models zero weight.
4. The gateway is learner-state's published `GameAnswerRecorder`
   (`app.learner_state.application.answer_recording`), composed in
   `infrastructure/gateways/learner_state_answers.py`. It records in its own database session.
5. Any learner-state error is logged and ignored; the answer is never changed or rejected.

The result does not change the adventure yet (silent mode for the pilot,
`docs/learner-state/12_PILOT_STUDY_PLAN.md`). The English classroom quest does not record
learner-state evidence, because the behaviour models were trained on mathematics answers.

Request fields (both optional, both part of the idempotency fingerprint when sent):

| Field | Meaning |
| --- | --- |
| `visual` | the 11 on-device camera numbers of the last 10 seconds; an invalid snapshot is dropped and the answer continues |
| `learner_state_session_id` | one id per app session, so learner-state history spans the episodes played in one sitting (each episode has its own `session_id`); without it the episode's `session_id` is used |

The window id is the scoring time in milliseconds, so it increases across episodes and does not
need an allocator.

Camera consent is stored in `consent_decisions` (migration `gam_20261020_01`) and read and
written through `GET` / `PUT /development/learning-flow/consents/learner-state-camera`. In the
app, a guardian switch under **Settings** (වැඩිහිටි සැකසුම්) sets it; the camera runs only while
consent is given and a mathematics game screen is open. The development endpoint stands in for a
guardian-authenticated decision, which production needs.

## 7. Remaining work

- Guardian authentication for the camera decision.
- Agreement on the provisional behaviour values used by `GameAnswerRecorder`
  (`original = 1`, `overlap_time = response_time_ms`) and a source for `task_progress`
  (`docs/learner-state/11_GAME_INTEGRATION.md`).
- A learner-facing re-engagement action before learner-state results change what the child sees.
- Confirm downstream ingestion policy for v2 evidence.

## 8. Contract and verification locations

The generated request and response schemas are published in:

- `docs/adaptive-gamified-learning/openapi-pilot-v1.json`
- `docs/adaptive-gamified-learning/mobile-learning-contracts-v1.json`

The integration was verified with the backend suite, focused learner-state and gamification
tests, Python linting, frontend type checking and linting, frontend tests, the web build, the
learning-flow type-drift check, and whitespace validation. The web build retains its existing warning
about the large Phaser chunk.
