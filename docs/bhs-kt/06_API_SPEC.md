# 06 — REST API (v1)

Base path `/api/v1`. JSON everywhere except file uploads (`multipart/form-data`) and the PDF. Dates are ISO 8601 with time zone. Ids are UUIDs except questions (text ids such as `3.41`).

**Auth (DECISION D7):** the group's login system is owned by a teammate. Implement a dependency `current_user()` that returns the logged-in parent and a helper `assert_can_access_student(user, student_id)`; until the real auth exists, use a development stub that reads the header `X-Dev-Parent-Id`. Every route below that takes a `student_id` or a `paper_id` must call the access check.

**Never in any client response:** `correct_option`, `accepted_answers`, `instruction`, `answer_key_raw`, `key_verified_*`. A test must enforce this (see `02`).

**Error shape:** `{"error": {"code": "markers_missing", "message": "Could not find all four corner squares.", "details": {}}}` with a suitable HTTP status.

## 1. Attempts

### `POST /attempts` — log a digital answer (called by the game backend)
```json
{ "student_id": "…", "question_id": "3.41", "correct": true,
  "time_ms": 14250, "hints": 1, "answered_at": "2026-10-07T16:20:11+05:30" }
```
Server sets `source = 1`, computes `penalty`, inserts. Response `201`: `{"attempt_id": 1234}`.
Validation: question exists; `time_ms` 0–600000; `hints` 0–10. Idempotency: optional header `Idempotency-Key`; the same key returns the same `attempt_id`.

## 2. Mastery

### `GET /students/{student_id}/mastery`
Returns the latest snapshot (computes one if none exists).
```json
{ "computed_at": "…", "model_version": "dkt-v2.1-1a2b3c4d", "n_attempts": 212,
  "definition": "Chance of answering a medium-difficulty paper question correctly",
  "skills": [
    { "code": "MAT-FRC", "area": "MAT", "mastery": 0.62, "attempts": 14 },
    { "code": "APT-PAT", "area": "APT", "mastery": null, "attempts": 1 }
  ] }
```
`mastery: null` means "not enough answers yet" (fewer than 3). Always 30 entries, in `sort_index` order.

### `POST /students/{student_id}/mastery/recompute` → same body as above (admin/debug; rate-limited).

## 3. Papers

### `POST /students/{student_id}/papers` — generate
```json
{ "mode": "practice", "max_questions": 15, "max_minutes": 25, "max_pages": 3,
  "languages": ["si", "en"], "focus_skills": ["MAT-FRC"] }
```
All fields optional (defaults in `04`). Response `201`:
```json
{ "paper_id": "…", "code": "K7QX4M2PD9TB", "status": "generated", "mode": "practice",
  "page_count": 3, "question_count": 14, "estimated_minutes": 22,
  "pdf_url": "https://…signed…", "skipped_skills": [] }
```
Errors: `409 not_enough_questions`.
Generation is fast enough to be synchronous (a few seconds). If it grows slow, return `202` and poll `GET /papers/{id}`.

### `GET /papers/{paper_id}`
```json
{ "paper_id": "…", "code": "K7QX…", "status": "partially_uploaded", "page_count": 2,
  "pages": [ { "page": 1, "submission_status": "graded" },
             { "page": 2, "submission_status": null } ],
  "pdf_url": "…" }
```

### `GET /papers/{paper_id}/pdf` → `302` to a fresh signed URL (or the PDF stream in local development).

### `GET /students/{student_id}/papers?limit=20` → list of the above, newest first.

## 4. Submissions (photo upload and grading)

### `POST /papers/{paper_id}/pages/{page}/photo`
`multipart/form-data`, field `image` (JPEG/PNG/HEIC converted client-side if possible, max 15 MB). Response `202`:
```json
{ "submission_id": "…", "status": "uploaded" }
```
Grading starts in the background.

### `GET /submissions/{submission_id}`
```json
{ "submission_id": "…", "paper_id": "…", "page": 1,
  "status": "needs_review",                       // uploaded | failed_alignment | graded | needs_review | confirmed
  "failure_reason": null,                         // markers_missing | low_match | blurry | wrong_paper | wrong_page
  "summary": { "items": 10, "auto_final": 8, "needs_review": 2 },
  "review_items": [
    { "paper_item_id": "…", "position": 4, "part_no": 1, "part_type": "mcq",
      "crop_url": "https://…signed…",          // the whole question block as photographed
      "reading": { "selected": "3" },
      "reason": "two_marks",                   // two_marks | low_confidence | near_miss | models_disagree | instruction_check | vision_error | part_count_mismatch
      "options": ["1","2","3","4"] },
    { "paper_item_id": "…", "position": 9, "part_no": 2, "part_type": "short",
      "crop_url": "https://…signed…",
      "reading": { "text": "කුරුල්ලා" },
      "reason": "near_miss" },
    { "paper_item_id": "…", "position": 12, "part_no": 1, "part_type": "short",
      "crop_url": "https://…signed…",
      "reading": { "text": "" },
      "reason": "instruction_check",
      "ask": "Is it done as the question asks?" }   // instruction parts: the parent answers yes/no (the instruction text itself is not shown)
  ] }
```
`part_no` is 1 for ordinary questions; a question with several answers produces one review entry per flagged part.
For `confirmed`/`graded` pages the response also lists per-item results: `{"position": 2, "result": "correct"|"wrong"|"blank", "parts": [{"part_no": 1, "result": "correct"}, …]}` (`parts` only when the question has more than one). The result of a **flagged** part is hidden until the parent has decided.

### `POST /submissions/{submission_id}/confirm`
```json
{ "decisions": [
    { "paper_item_id": "…", "part_no": 1, "selected": "3" },          // MCQ part: option label, or null for blank
    { "paper_item_id": "…", "part_no": 2, "text": "කුරුල්ලා" },        // short part: the text the child wrote, or "" for blank
    { "paper_item_id": "…", "part_no": 1, "instruction_met": true }     // instruction part: yes / no
] }
```
`part_no` defaults to 1 when omitted. For an instruction part the server treats `instruction_met` as the part result (it cannot be compared with a text key). The server grades these readings with the normal rules, combines the parts of each question (all parts must be correct for the question to count as correct), creates one attempt per question, recomputes mastery, and returns the final per-item results. Errors: `422` if a flagged part is missing from `decisions`.

## 5. Questions (for the game and for admin)

- `GET /questions/{question_id}/image-url` → `{"url": "…signed…", "expires_in": 600}` (no answer key).
- `POST /admin/questions/import` — multipart CSV/JSON + images zip; returns the import report (all line errors or the count imported). Admin only.
- `GET /admin/questions/unverified` — questions whose key has not been verified.
- `POST /admin/questions/{id}/verify` `{ "verified_by": "name" }`.

## 6. Health
`GET /health` → `{"status": "ok", "db": true, "model_version": "…", "vision_provider": "gemini", "vision_model": "gemini-…-flash", "warnings": []}`. `warnings` includes `"vision_model_auto_switched"` when the configured model was withdrawn and a fallback is in use, and `"vision_quota_exhausted"` after a hard quota error.

## 7. Contract tests
Generate an OpenAPI file (`openapi.json`) in CI. The frontend generates its TypeScript types from it (`openapi-typescript`), so the two sides cannot drift.
