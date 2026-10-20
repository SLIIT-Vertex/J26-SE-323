# 11 — Game Integration (Option B)

This document describes how the learner-state component is integrated with the game
(`backend/app/gamification`, `frontend/src/features/mobile-learning-flow`). It is the design chosen
by the learner-state owner; the game owner agreed that the learner-state owner implements the
game-side changes. The game owner's description is in
[`docs/adaptive-gamified-learning/learner-state-answer-integration.md`](../adaptive-gamified-learning/learner-state-answer-integration.md).

**Status (2026-10-20):** every scored answer in the Grade 5 mathematics adventures is recorded as a
learner-state window. The result is stored but does not yet change what the child sees (silent
mode, [`12`](12_PILOT_STUDY_PLAN.md#3-design)).

## 1. Responsibilities

| Browser (learner-state frontend module) | Game backend | Learner-state backend |
| --- | --- | --- |
| Webcam permission and capture, only with the guardian's consent | Source of truth for answer correctness | Feature construction, models, reliability, fusion, temporal decision |
| MediaPipe on the device | Response timing record | Stores the latest state per learner and Universal skill |
| The 11 derived visual features; raw frames never leave the device | Camera-consent decisions | Publishes `support_need` and `recommended_action` |
| Sends the visual window with the answer | Question and skill context; calls learner-state in process after the answer is stored | — |

The browser does **not** call `POST /api/v1/learner-state` in production; that endpoint remains for
development and testing.

## 2. Integration point (Grade 5 adventures)

```text
POST /api/v1/development/learning-flow/episodes/{episode_id}/before   (and /after)
  -> LearningFlowOrchestrator.submit_before() / submit_after()
     -> NumberWorldFlow (base of every adventure flow)
        1. score the answer (server truth) and publish game evidence
        2. commit the episode (idempotent per Idempotency-Key)
        3. record_scored_answer()  -> LearnerStateAnswerGateway.record_answer()
                                   -> GameAnswerRecorder (learner-state, published contract)
```

- Step 3 runs only after the commit, and not when a retried request replays a stored receipt, so
  each answer is recorded once and a failed answer is never recorded.
- Only the two unsupported answers of an episode (before and after support) are scored, so
  `supported = false` and `hint_count = 0` are exact.
- The English classroom quest inherits the same flow but does not record learner-state windows
  (`records_learner_state = False`), because the behaviour models were trained on mathematics
  answers.
- Any learner-state error is logged and ignored; the answer is never changed or rejected.

Architecture: the game's application code depends only on its own `LearnerStateAnswerGateway`
protocol. The adapter `infrastructure/gateways/learner_state_answers.py` imports learner-state's
published contract `app.learner_state.application.answer_recording`, as the game's architecture
test allows. `GameAnswerRecorder` records in its own database session, so it never commits or rolls
back the game's transaction.

## 3. Data sent by the browser

Two optional fields on the adventure answer request (`AnswerRequest`):

| Field | Meaning |
| --- | --- |
| `visual` | `VisualFeatureWindow`: exactly the 11 visual features of the last 10 seconds before the answer ([`10`](10_FRONTEND_INTEGRATION.md)); all values finite, `face_visibility_ratio` in `[0, 1]`. An invalid snapshot is dropped and the answer continues. |
| `learner_state_session_id` | one id per app session. Each adventure episode has its own game `session_id`, which would give learner-state only two windows per session; this id lets the temporal engine and learner baseline span all episodes of one sitting. |

The shared client (`learningFlowClient.ts`) adds both to every adventure answer, so the 16
adventure screens are unchanged. It takes one snapshot per answer and re-sends that same snapshot
when a request is retried with the same idempotency key.

No frames, landmarks or images are sent. The server passes the visual values to learner-state only
with current `learner_state_camera` consent. Without camera or consent the answer behaviour is
still recorded with "no visual evidence" (`face_visibility_ratio = 0`), which gives the visual
models zero weight ([`04`](04_RELIABILITY_AND_FUSION.md#4-what-happens-when-one-modality-is-less-reliable)).

## 4. Camera consent

| Part | Implementation |
| --- | --- |
| Storage | `consent_decisions` table (gamification, migration `gam_20261020_01`): latest decision per learner and purpose |
| API | `GET` / `PUT /api/v1/development/learning-flow/consents/learner-state-camera` |
| App | a switch under **Settings** (වැඩිහිටි සැකසුම්), with a short explanation for the guardian |
| Camera | runs only while consent is given and a mathematics game screen is open; stops when consent is withdrawn or the child leaves the game |

The development endpoint stands in for a guardian-authenticated decision; production needs real
guardian authentication. When development learner recovery switches to another learner, the client
re-records a given consent for that learner; a declined consent is never extended.

## 5. Identifier flow

| Identifier | Source and use |
| --- | --- |
| `session_id` (learner-state) | `learner_state_session_id` from the client; the episode's `session_id` if absent |
| `learner_id` | the shared learner UUID; it must exist in `learners` |
| `window_id` | the scoring time in milliseconds: increases across episodes and restarts, needs no allocator; equal times in one session are practically impossible for a child's answers. About 1.8 × 10¹², so `learner_skill_states.window_id` is 64-bit (migration `20261020_02`) |
| Universal `skill_id` | the adventure flow's `universal_skill_id` (for example `MAT-FRC`); the same ID is used for every later lookup |
| `timestamp` | the server's scoring time |

## 6. Behavioural fields

Definitions are quoted from the official ASSISTments 2012–13 dataset documentation
([source](https://sites.google.com/site/assistmentsdata/datasets/2012-13-school-data-with-affect)).

| Field | Official definition | Game value | Status |
| --- | --- | --- | --- |
| `correct` | "1 = Correct on first attempt", decimals are partial credit, "0 = …" | server-computed 1/0 | equivalent (0/1 is a subset) |
| `attempt_count` | "Number of student attempts on this problem." | 1 (one scored submission per item) | equivalent |
| `ms_first_response` | "The time in milliseconds for the student's first response." | `response_time_ms` | equivalent |
| `overlap_time` | "The time in milliseconds for the student's overlap time." | `response_time_ms` for a single response | **provisional**: the official definition is not specific |
| `hint_count` | "Number of hints on this problem." | 0: only unsupported answers are scored | equivalent |
| `bottom_hint` | "Whether or not the student asks for all hints." | not applicable → `null` | honest: sent as missing, handled as in training |
| `original` | "1 = Main problem", "0 = Scaffolding problem" | 1: adventure items are main problems | **provisional** |

No field is filled with an invented constant. `position` and `first_action` had no truthful game
equivalent and are no longer used; both behaviour models were retrained without them
([`07`](07_EVALUATION_AND_LIMITATIONS.md#21-ablation-without-assistments-only-fields)). When a
journey sends no `response_time_ms` (some send none with reduced motion), nothing is recorded,
because both behaviour models need it.

`task_progress` has no game source yet and is `null`, so `productive_confusion` cannot occur. A
value such as "questions completed" would always rise and make every persistent confusion look
productive, so a meaningful source must be agreed first.

## 7. Consuming the result

In the adventures the result is stored only (silent mode); the next steps that would act on it
are a learner-facing re-engagement action and the tutor hand-off ([`09`](09_TUTOR_HANDOFF.md)).

The older pilot path (`POST /api/v1/game-sessions/{session_id}/responses`, `SessionPlay`,
`GameHost`) built in #26 uses `recommended_action` in its struggle trigger instead of a separate
`support_need ≥ 0.70` rule, and looks up stored states with the game `session_id` and a 60-second
maximum age ([`09`](09_TUTOR_HANDOFF.md#321-freshness)). That path is no longer mounted by the app
and has no gateway composed.

## 8. Implemented on the learner-state side

- `LearnerStateRecorder.record(window, skill_id=...)` in `application/recording.py`, with the
  shared `get_learner_state_service()` so HTTP and in-process windows share one session history.
- `GameAnswerRecorder` in `infrastructure/game_answers.py`, published through
  `application/answer_recording.py`: maps the game answer to the behavioural fields of §6, records
  it and returns `recommended_action`. It records nothing without `response_time_ms` and treats
  `visual = None` as "no visual evidence". Its signature is checked against the game protocol by a
  test.
- `useGameVisualFeatures({ enabled })` in the frontend ([`10` §12](10_FRONTEND_INTEGRATION.md#12-connecting-to-the-game)).

## 9. Still open

1. Guardian authentication for the camera decision (§4).
2. Agreement on the provisional `overlap_time` and `original` values, and a source for
   `task_progress` (§6).
3. Leaving silent mode: what the game does with `request_tutor_support` and
   `request_reengagement_support` in the adventures.
4. Session history is in memory; a backend restart starts every learner-state session afresh
   ([`07` §4.3](07_EVALUATION_AND_LIMITATIONS.md#43-runtime-and-deployment)).
