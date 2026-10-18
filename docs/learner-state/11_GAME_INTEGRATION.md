# 11 — Game Integration (Option B)

This document describes how the learner-state component is integrated with the game
(`backend/app/gamification`, `frontend/src/features/gamification`). It is the design chosen by the
learner-state owner. The learner-state side is implemented (§7). Most of the game side was
implemented by the game owner in `Feature/game dev (#26)` (§8); the adapter that actually calls
learner-state is **not composed yet**, so the running game does not record learner-state windows.
The game owner's own description is in
[`docs/adaptive-gamified-learning/learner-state-answer-integration.md`](../adaptive-gamified-learning/learner-state-answer-integration.md).

## 1. Responsibilities

| Browser (learner-state frontend module) | Game backend | Learner-state backend |
| --- | --- | --- |
| Webcam permission and capture | Source of truth for answer correctness | Feature construction, models, reliability, fusion, temporal decision |
| MediaPipe on the device | Response timing record | Stores the latest state per learner and Universal skill |
| The 11 derived visual features; raw frames never leave the device | Support/hint information | Publishes `support_need` and `recommended_action` |
| Sends the visual window with the game interaction | Question and skill context | — |
| — | Combines behaviour + visual and calls learner-state in process | — |

The browser does **not** call `POST /api/v1/learner-state` in production; that endpoint and a
direct client remain for development and testing.

## 2. Integration point

```text
POST /api/v1/game-sessions/{session_id}/responses
  -> SessionPlay.submit_response()        (idempotent per Idempotency-Key)
     -> _baseline() / _verification()
        1. correct = selected option == item.correct_option_id     (server truth)
        2. open_episode / record_verification
        3. _record_learner_state() -> LearnerStateAnswerGateway.record_answer()
        4. assess_struggle -> struggle trigger   (baseline answers only)
```

The learner-state window is recorded after the server computes `correct` and before
`assess_struggle`, inside the idempotent call, so a retried request does not record a second
window. `record_answer()` returns the `recommended_action` of the window it just recorded, so the
baseline struggle decision uses the evaluation of the current answer. Any gateway error is
swallowed: learner-state evidence never makes an answer fail.

`build_session_play()` does not yet pass a gateway or a consent store, so at the time of writing
step 3 returns without recording anything.

## 3. Data sent by the browser

An optional `visual` object (`VisualFeatureWindow`) on the game's `ResponseRequest`
(`episode_id`, `selected_option_id`, `response_time_ms`). It contains exactly the 11 visual
features, computed from the last 10 seconds before **Submit**
([`10`](10_FRONTEND_INTEGRATION.md)); other fields are rejected (`extra="forbid"`), and all values
must be finite with `face_visibility_ratio` in `[0, 1]`. An invalid `visual` object is dropped and
the answer continues.

In the browser, `GameHost` takes an optional `visualFeatures: () => VisualFeatureWindow | null`
callback, calls it once on **Submit**, keeps only the 11 keys and freezes the snapshot. The
learner-state frontend module provides this callback; `GameHost` does not run its own camera
pipeline.

No frames, landmarks or images are sent. The server also checks consent for the purpose
`learner_state_camera` before the visual values reach the gateway.

**Open point.** The current game code records a learner-state window only when a `visual` object
is present and consent is granted. The original design records every answer, using "no visual
evidence" (zeros and `face_visibility_ratio = 0`) when there is no camera, so the visual models get
zero weight and the behavioural evidence is still used (see
[`04`](04_RELIABILITY_AND_FUSION.md#4-what-happens-when-one-modality-is-less-reliable)). Which of the two is
used must be agreed with the game owner.

## 4. Identifier flow

| Identifier | Source and use |
| --- | --- |
| `session_id` | the game session UUID, used as the learner-state `session_id` |
| `learner_id` | the shared learner UUID; it must exist in `learners` |
| `window_id` | `learner_state_window_id`, kept by the game backend per game session, +1 for each submitted answer (also when no window is recorded, which leaves allowed gaps); in process memory for the pilot |
| Universal `skill_id` | `item.skill_id` -> game crosswalk (`universal-skill-crosswalk.jsonl`) -> Universal Skill ID; the same ID is used to record the window and for every later lookup |
| `timestamp` | the server's submission time |

## 5. Behavioural fields

Definitions are quoted from the official ASSISTments 2012–13 dataset documentation
([source](https://sites.google.com/site/assistmentsdata/datasets/2012-13-school-data-with-affect)).

| Field | Official definition | Game value | Status |
| --- | --- | --- | --- |
| `correct` | "1 = Correct on first attempt", decimals are partial credit, "0 = …" | server-computed 1/0 for the single submission | equivalent (0/1 is a subset) |
| `attempt_count` | "Number of student attempts on this problem." | 1 (one submission per item) | equivalent |
| `ms_first_response` | "The time in milliseconds for the student's first response." | `response_time_ms` (shown → submitted) | equivalent |
| `overlap_time` | "The time in milliseconds for the student's overlap time." | `response_time_ms` for a single response | **to confirm**: the official definition is not specific |
| `hint_count` | "Number of hints on this problem." | 0 for baseline answers (no help exists before answering); the game currently also passes 0 for verification answers | equivalent for baseline; **to agree** for verification answers (support was shown by the system, not requested) |
| `bottom_hint` | "Whether or not the student asks for all hints." | not applicable → `null` | honest: sent as missing, handled as in training |
| `original` | "1 = Main problem", "0 = Scaffolding problem" | answered game items are main problems | **to agree**: likely 1, but verification items must be confirmed as main problems |

No field is filled with an invented constant. Two further ASSISTments fields had no truthful game
equivalent and are **no longer used**: `position` ("Assignment position on the class assignments
page") and `first_action` ("The type of first action: attempt or ask for a hint", with an
undocumented numeric coding). Both behaviour models were retrained without them at almost no cost
(see [`07`](07_EVALUATION_AND_LIMITATIONS.md#21-ablation-without-assistments-only-fields)).

`task_progress` is not available in the game yet and is sent as `null`, so
`productive_confusion` cannot occur.

## 6. Consuming the result

The game receives the `recommended_action` of the current answer's window. To avoid a second,
independent threshold on top of the learner-state decision, the struggle trigger
(`application/struggle_trigger.py`) uses `recommended_action` instead of its `support_need ≥ 0.70`
rule:

| Learner-state result | Game behaviour (implemented in #26) |
| --- | --- |
| `request_tutor_support` | reason `LEARNER_STATE_TUTOR_SUPPORT` |
| `request_reengagement_support` | reason `LEARNER_STATE_REENGAGEMENT_SUPPORT`; the learner-facing re-engagement action is still to be designed by the game |
| `collect_more_evidence`, `monitor`, `none` | no learner-state trigger |
| any other value | skipped as `LEARNER_STATE_UNKNOWN_RECOMMENDATION` |

The 0.70 rule is kept only for older gateways that return no `recommended_action`. The
learner-state 0.60 intervention threshold is not changed and is not replaced by the game's 0.70
value; they have different responsibilities.

For lookups through `SupportNeedProvider`, the game's gateway passes the game `session_id` and a
60-second maximum age (`RECOMMENDED_MAX_STATE_AGE_MS`, provisional and configurable) and treats
`STALE` as absent ([`09`](09_TUTOR_HANDOFF.md#321-freshness)). `SupportNeedResult` also carries
`recommended_action` for fresh results; the game owner added this field in #26.

## 7. Implemented on the learner-state side

- `LearnerStateRecorder.record(window, skill_id=...)` in `application/recording.py`: the
  application use case for in-process callers, with the Universal Skill ID ([`01`](01_ARCHITECTURE.md#41-recording-use-case)).
- `get_learner_state_service()`: one shared service instance, so HTTP and in-process windows share
  one session history and `window_id` sequence.
- `WindowOrderError` and `UnknownLearnerError` for callers outside HTTP.
- `SupportNeedResult.session_id`, the `STALE` status and optional `session_id` / `max_age_ms` on
  `SupportNeedRequest`; all backward compatible.
- `GameAnswerRecorder` in `infrastructure/game_answers.py`: the adapter behind the game's
  `LearnerStateAnswerGateway`. Its `record_answer()` has the same signature as the game protocol
  (checked by a test), maps the game answer to the behavioural fields as in §5 (`attempt_count = 1`,
  `overlap_time = ms_first_response = response_time_ms`, provisional `original = 1`,
  `bottom_hint` missing, `task_progress` unknown), opens its own database session, records the
  window through `LearnerStateRecorder` with the shared service, and returns the window's
  `recommended_action`. It records nothing when `response_time_ms` is unknown, accepts
  `visual = None` as "no visual evidence", and logs and re-raises errors. The game composes it as
  `GameAnswerRecorder(session_factory=SessionLocal)`.

## 8. Status of the game side

Implemented by the game owner in #26:

- the optional `visual` object on `ResponseRequest` and the `visualFeatures` callback in `GameHost`;
- the `learner_state_camera` consent check;
- the per-session `learner_state_window_id` counter;
- the `LearnerStateAnswerGateway.record_answer()` boundary, called after scoring and before the
  struggle decision;
- `recommended_action` instead of the 0.70 rule, and 60-second / same-session freshness for lookups.

Still open:

1. Composing the adapter (`GameAnswerRecorder`, §7) in `build_session_play()` together with a
   consent store and a way to record `learner_state_camera` consent; neither exists in the game
   yet.
2. Agreement on the provisional values for `overlap_time`, `original` and `hint_count` on
   verification answers, and a source for `task_progress` (§5). `position` and `first_action` no
   longer need a value.
3. Whether answers without a camera are recorded with "no visual evidence" (§3).
4. Using `useGameVisualFeatures({ enabled })` in the game screen once camera consent exists; the
   hook that provides the `visualFeatures` callback is implemented
   ([`10`](10_FRONTEND_INTEGRATION.md#12-connecting-to-the-game)).
5. A durable `window_id` allocator before more than one backend worker can serve a session.
