# 06 — API Specification

The learner-state component exposes **one** endpoint:

```text
POST /api/v1/learner-state
```

- Router: `backend/app/learner_state/api/router.py` (prefix `/learner-state`, tag `learner-state`)
- Schemas: `backend/app/learner_state/api/schemas.py`
- Registered in `backend/app/main.py` under `settings.api_v1_prefix` (`/api/v1`)
- Content type: `application/json`
- Authentication: none (the shared auth boundary is not implemented yet)

One request represents **one window** of one learner session. The client sends windows in order.

## 1. Swagger / OpenAPI

When the backend is running, the endpoint and its schemas are documented automatically by FastAPI:

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

The Swagger UI "Try it out" button can be used with the example request below.

## 2. Request body — `LearnerStateRequest`

### 2.1 Top-level fields

| Field | Type | Required | Validation | Meaning |
| --- | --- | --- | --- | --- |
| `session_id` | string | yes | length 1–100 | Identifies the learning session. History is kept per (`session_id`, `learner_id`). |
| `learner_id` | UUID | yes | valid UUID | Shared MindBridge learner identifier. Not checked against the learners table. |
| `window_id` | integer | yes | ≥ 1 | Sequence number of the window; must increase within a session (§5). |
| `timestamp` | datetime (ISO 8601) | yes | valid datetime | Time of the window. Accepted but not used in calculations. |
| `visual` | object | yes | see §2.2 | Derived webcam features. |
| `behaviour` | object | yes | see §2.3 | Interaction features. Note the British spelling of this request field. |
| `task_progress` | number or null | no (default `null`) | 0.0–1.0 | Learner's progress on the current task. Used only to separate productive from intervention-worthy confusion. |

### 2.2 `visual` — `VisualFeatures`

All fields are required numbers.

| Field | Validation | Meaning |
| --- | --- | --- |
| `mean_eye_openness` | — | Mean eye openness in the window |
| `std_eye_openness` | — | Standard deviation of eye openness |
| `mean_gaze_ratio` | — | Mean gaze ratio |
| `std_gaze_ratio` | — | Standard deviation of gaze ratio |
| `mean_pitch` | — | Mean head pitch (signed) |
| `mean_yaw` | — | Mean head yaw (signed) |
| `mean_roll` | — | Mean head roll (signed) |
| `mean_abs_pitch` | — | Mean absolute head pitch; used in visual reliability |
| `mean_abs_yaw` | — | Mean absolute head yaw; used in visual reliability |
| `mean_abs_roll` | — | Mean absolute head roll; used in visual reliability |
| `face_visibility_ratio` | 0.0–1.0 | Share of the window with a visible face; used in visual reliability |

### 2.3 `behaviour` — `BehaviourFeatures`

| Field | Type | Validation | Meaning |
| --- | --- | --- | --- |
| `correct` | number | 0.0–1.0 | Correctness of the response |
| `bottom_hint` | number or null | — (default `null`) | Whether the bottom-out hint was reached; `null` = unknown (treated as missing) |
| `hint_count` | number | ≥ 0 | Hints used |
| `attempt_count` | number | ≥ 0 | Attempts made |
| `ms_first_response` | number | — | Time to first response (ms) |
| `overlap_time` | number | — | Time spent on the item (ms) |
| `first_action` | number | — | Behavioural model input field retained from the training data |
| `position` | number | — | Behavioural model input field retained from the training data |
| `original` | number | — | Behavioural model input field retained from the training data |

Feature meanings and how they feed the models are described in
[`02_DATA_AND_FEATURES.md`](02_DATA_AND_FEATURES.md).

## 3. Response body — `LearnerStateResponse` (HTTP 200)

| Field | Type | Meaning |
| --- | --- | --- |
| `session_id` | string | Echo of the request |
| `learner_id` | UUID | Echo of the request |
| `window_id` | integer | Echo of the request |
| `confusion` | `ConfusionResult` | Confusion result for this window |
| `disengagement` | `DisengagementResult` | Disengagement result for this window |
| `recommended_action` | enum | One combined action (§3.3) |

### 3.1 `confusion` and `disengagement` objects

Both objects have the same numeric fields (all 0.0–1.0):

| Field | Meaning |
| --- | --- |
| `visual_probability` | Raw output of the visual model for this detector |
| `behavior_probability` | Raw output of the behaviour model for this detector |
| `visual_reliability` | Visual reliability of this window (same value in both objects) |
| `behavior_reliability` | Behavioural reliability of this window (same value in both objects) |
| `fused_evidence` | Reliability-weighted, threshold-centred evidence for **this window** |
| `confidence` | Fusion confidence for **this window** (after the disagreement penalty) |
| `state` | Temporal state (uses recent history, see [`05`](05_TEMPORAL_DECISION_ENGINE.md)) |
| `support_need` | Support requested by this detector |

Response field names use the code spelling `behavior_*`, while the request object is named
`behaviour`.

### 3.2 Enum values

| Field | Allowed values |
| --- | --- |
| `confusion.state` | `no_confusion`, `transient_confusion`, `productive_confusion`, `intervention_worthy_confusion`, `recovering_from_confusion`, `uncertain` |
| `confusion.support_need` | `none`, `monitor`, `request_tutor_support`, `collect_more_evidence` |
| `disengagement.state` | `engaged`, `transient_disengagement`, `persistent_disengagement`, `recovering_engagement`, `uncertain` |
| `disengagement.support_need` | `none`, `monitor`, `request_reengagement_support`, `collect_more_evidence` |
| `recommended_action` | `none`, `monitor`, `request_tutor_support`, `request_reengagement_support`, `collect_more_evidence` |

### 3.3 `recommended_action` priority

`request_reengagement_support` > `request_tutor_support` > `collect_more_evidence` > `monitor` >
`none`. See [`05`](05_TEMPORAL_DECISION_ENGINE.md#5-final-recommended-action).

## 4. Example

### 4.1 Request

This is the payload used in `backend/tests/test_learner_state.py`, with a fixed example UUID.

```json
{
  "session_id": "learner-state-test-session",
  "learner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "window_id": 1,
  "timestamp": "2026-10-13T09:45:00+05:30",
  "visual": {
    "mean_eye_openness": 0.27,
    "std_eye_openness": 0.04,
    "mean_gaze_ratio": 0.52,
    "std_gaze_ratio": 0.08,
    "mean_pitch": 8.0,
    "mean_yaw": 5.0,
    "mean_roll": 3.0,
    "mean_abs_pitch": 8.0,
    "mean_abs_yaw": 5.0,
    "mean_abs_roll": 3.0,
    "face_visibility_ratio": 0.95
  },
  "behaviour": {
    "correct": 0.0,
    "bottom_hint": null,
    "hint_count": 3.0,
    "attempt_count": 4.0,
    "ms_first_response": 15000.0,
    "overlap_time": 25000.0,
    "first_action": 0.0,
    "position": 1.0,
    "original": 1.0
  },
  "task_progress": 0.3
}
```

### 4.2 Response (HTTP 200)

Produced by the current implementation for the request above as the first window of a new
session. Values are rounded to 4 decimal places here; the API returns full floating-point values.

```json
{
  "session_id": "learner-state-test-session",
  "learner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "window_id": 1,
  "confusion": {
    "visual_probability": 0.5224,
    "behavior_probability": 0.1904,
    "visual_reliability": 0.95,
    "behavior_reliability": 0.63,
    "fused_evidence": 0.3621,
    "confidence": 0.6142,
    "state": "no_confusion",
    "support_need": "none"
  },
  "disengagement": {
    "visual_probability": 0.7368,
    "behavior_probability": 0.1434,
    "visual_reliability": 0.95,
    "behavior_reliability": 0.63,
    "fused_evidence": 0.4832,
    "confidence": 0.5226,
    "state": "engaged",
    "support_need": "none"
  },
  "recommended_action": "none"
}
```

Sending the same features as windows 2, 3 and 4 moves disengagement to
`transient_disengagement` and then `persistent_disengagement`, with
`recommended_action = "request_reengagement_support"` at window 4 (see the illustrative runtime
walkthrough in [`05`](05_TEMPORAL_DECISION_ENGINE.md#6-illustrative-runtime-walkthrough)). These
example values come from the current committed model artifacts and are not evaluation results.

## 5. `window_id` ordering

- Within one (`session_id`, `learner_id`) pair, each new `window_id` must be **strictly greater**
  than the last accepted one. Gaps are allowed (1, 2, 5 is valid).
- The first window of a session may have any `window_id ≥ 1`.
- The same `session_id` with a different `learner_id` is a different session.
- A rejected window does **not** change the stored history.

## 6. Errors

### 6.1 HTTP 409 Conflict — duplicate or out-of-order window

Returned when `window_id` is equal to or lower than the last accepted window for the session:

```json
{
  "detail": "window_id must increase within a learner session"
}
```

The router converts any `ValueError` raised by `LearnerStateService.evaluate` into 409. In normal
operation the ordering check is the only source of this error.

### 6.2 HTTP 422 Unprocessable Entity — validation error

Returned by FastAPI/Pydantic before the service runs, for example when:

- a required field is missing (including the whole `visual` or `behaviour` object),
- `learner_id` is not a valid UUID or `timestamp` is not a valid datetime,
- `window_id < 1`,
- `session_id` is empty or longer than 100 characters,
- `face_visibility_ratio`, `correct` or `task_progress` is outside 0–1,
- `hint_count` or `attempt_count` is negative,
- a numeric field has a non-numeric value.

The body uses FastAPI's standard format, for example:

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "visual", "face_visibility_ratio"],
      "msg": "Input should be less than or equal to 1",
      "input": 1.4,
      "ctx": {"le": 1.0}
    }
  ]
}
```

### 6.3 Other errors

HTTP 409 and HTTP 422 are the only error responses this endpoint documents. The router does not
define any other error response. As with any FastAPI endpoint, an unexpected unhandled server error
may result in HTTP 500; this is not part of the learner-state API contract.

## 7. Endpoints that do not exist

There is currently no endpoint to read history, reset a session, or list past learner states.
`LearnerStateService.clear_session()` exists in code but is not exposed through the API.
