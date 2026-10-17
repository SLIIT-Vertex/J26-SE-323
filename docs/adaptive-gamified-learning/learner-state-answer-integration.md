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

The pilot answer request may include `visual_features`. It is an optional snapshot containing
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
| `none`, `monitor`, `collect_more`, missing, or unknown | Do not trigger immediate support |

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

No shared `useVisualFeatures()` implementation is currently available in this checkout, so the
camera lifecycle has not been activated or end-to-end tested here. Answers continue without it.

## 6. Remaining composition work

The answer flow can consume an immediate learner-state recommendation, but the concrete
`LearnerStateRecorder` adapter is not yet composed. Its behavior payload still needs agreed
definitions for `overlap_time`, `first_action`, `position`, `original`, and `task_progress`, as
well as a decision on whether verification hints may be exposed. Until those fields are
defined, the game must not fabricate them.

Before production release:

- provide and test the shared visual-feature hook and consent-driven camera lifecycle;
- define the missing behavior semantics and compose the recorder adapter;
- replace the in-memory window allocator with durable allocation;
- implement the learner-facing re-engagement action; and
- confirm downstream ingestion policy for v2 evidence.

## 7. Contract and verification locations

The generated request and response schemas are published in:

- `docs/adaptive-gamified-learning/openapi-pilot-v1.json`
- `docs/adaptive-gamified-learning/mobile-learning-contracts-v1.json`

The integration was verified with the backend suite, focused learner-state and gamification
tests, Python linting, frontend type checking and linting, frontend tests, the web build, the
learning-flow type-drift check, and whitespace validation. The web build retains its existing warning
about the large Phaser chunk.
