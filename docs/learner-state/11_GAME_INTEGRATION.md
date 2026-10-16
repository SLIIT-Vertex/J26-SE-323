# 11 — Game Integration (Option B)

This document describes how the learner-state component is integrated with the game
(`backend/app/gamification`, `frontend/src/features/gamification`). It is the design chosen by the
learner-state owner. **The game-side changes are not implemented yet** and need the game owner's
agreement. The learner-state side that the integration needs is implemented (§7).

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
        3. >>> record the learner-state window here <<<
        4. assess_struggle -> struggle trigger
```

The learner-state window is recorded after the server computes `correct` and before
`assess_struggle`, inside the idempotent call, so a retried request does not record a second
window. At the time of writing the running game does not call learner-state at all:
`build_session_play()` passes no learner-state gateway.

## 3. Data sent by the browser

An optional `visual` object added to the game's existing `ResponseRequest`
(`episode_id`, `selected_option_id`, `response_time_ms`):

| Field | Meaning |
| --- | --- |
| the 11 visual features | from the last 10 seconds before **Submit** ([`10`](10_FRONTEND_INTEGRATION.md)) |
| `usable`, `reason` | whether the window has usable face data (`no-face`, `no-head-pose`, …) |
| `samples`, `samples_with_face` | how many of the 30 samples were taken and contained a face |
| `captured_at` | when the window was taken |

No frames, landmarks or images are sent. Without a camera the object is omitted and the backend
records the window with "no visual evidence" (zeros and `face_visibility_ratio = 0`), which gives the
visual models zero weight.

## 4. Identifier flow

| Identifier | Source and use |
| --- | --- |
| `session_id` | the game session UUID, used as the learner-state `session_id` |
| `learner_id` | the shared learner UUID; it must exist in `learners` |
| `window_id` | a counter kept by the game backend per game session, +1 for each submitted answer |
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
| `hint_count` | "Number of hints on this problem." | 0 for baseline answers (no help exists before answering) | equivalent for baseline; **differs** for verification answers (support was shown by the system, not requested) |
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

The game receives the full evaluation for the current answer, so no lookup or staleness rule is
needed for that decision. To avoid a second, independent threshold on top of the learner-state
decision, the game uses `recommended_action` instead of its `support_need ≥ 0.70` rule:

| Learner-state result | Game behaviour |
| --- | --- |
| `request_tutor_support` | learner-state reason to offer support |
| `request_reengagement_support` | re-engagement path (designed by the game) |
| `collect_more_evidence` | recorded, never a trigger |
| `monitor`, `none` | no learner-state trigger |

The learner-state 0.60 intervention threshold is not changed and is not replaced by the game's
0.70 value; they have different responsibilities.

For later lookups (for example when choosing the next activity), the game passes the current
`session_id` and `max_age_ms = RECOMMENDED_MAX_STATE_AGE_MS` (60 s, provisional and configurable)
to `SupportNeedProvider` and treats `STALE` as absent ([`09`](09_TUTOR_HANDOFF.md#321-freshness)).
The game's current 7-day maximum age is not suitable for moment-to-moment states.

## 7. Implemented on the learner-state side

- `LearnerStateRecorder.record(window, skill_id=...)` in `application/recording.py`: the
  application use case for in-process callers, with the Universal Skill ID ([`01`](01_ARCHITECTURE.md#41-recording-use-case)).
- `get_learner_state_service()`: one shared service instance, so HTTP and in-process windows share
  one session history and `window_id` sequence.
- `WindowOrderError` and `UnknownLearnerError` for callers outside HTTP.
- `SupportNeedResult.session_id`, the `STALE` status and optional `session_id` / `max_age_ms` on
  `SupportNeedRequest`; all backward compatible.

## 8. Still to agree with the game owner

1. The optional `visual` object on `ResponseRequest` and how the game composes
   `LearnerStateRecorder` (database session, learner check).
2. The per-session `window_id` counter.
3. Using `recommended_action` instead of the 0.70 support-need rule, and the 60-second / same-session
   freshness for lookups.
4. The values for `overlap_time`, `hint_count` on verification answers and `original`.
