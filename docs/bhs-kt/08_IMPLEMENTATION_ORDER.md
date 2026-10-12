# 08 — Implementation order

Work in this order. Each step ends with a **Done when** check; do not start the next step until it passes. Steps marked **USER INPUT** need something only the project owner can supply: stop and ask for it.

Size: S = small, M = medium, L = large (relative effort).

```
0 Setup ─► 1 Database + question bank ─► 2 Attempts ─► 3 Model service ─► 4 Mastery API
                      │                                        │
                      └──────────────► 5 Paper selection ◄─────┘
                                              │
                                  6 Layout + PDF + markers ─► 7 Alignment + crops (+ thin upload page)
                                                                      │
                                                  8 Rule engine + vision interface (mock) ─► 9 Real vision provider
                                                                      │                              ▲
                                                10 Submissions API + review + attempts       Benchmark (parallel,
                                                                      │                      starts after step 7)
                                                         11 Frontend screens + iPhone
                                                                      │
                                                         12 End-to-end test, pilot, evaluation
```

---

## Step 0 — Project setup (S)

Tasks
- Create the repository layout from `01_ARCHITECTURE.md`, `pyproject.toml` (FastAPI, SQLAlchemy 2, Alembic, psycopg 3, pydantic-settings, ortools, torch CPU, numpy, opencv-contrib-python-headless, pillow, reportlab, qrcode, pypdfium2, pytest, ruff, mypy, httpx).
- `docker-compose.yml` with Postgres; `.env.example`; `config.py`; `GET /health`.
- Copy `shared/feature_spec.json` into the repo and write `spec.py` that loads it once.

Done when: `docker compose up -d`, `uvicorn app.main:app` and `pytest` all run; `/health` returns ok; ruff and mypy are clean.

Prompt: *"Read 00_README.md and 01_ARCHITECTURE.md. Do Step 0 of 08_IMPLEMENTATION_ORDER.md only. Stop when its 'Done when' passes and summarise what you created."*

## Step 1 — Database and question bank (M) — **USER INPUT**

Tasks
- Alembic migration for every table in `02_DATABASE.md`; seed `skills` from the feature spec; startup check that table and spec agree.
- `StorageBackend` interface with local and S3 implementations (+ signed URL function).
- Question importer with all validation rules (`02` section 2). It must read the teacher's plain-text files directly: `answers_<n>.txt`, `skillMap-<n>.txt`, `difficult-time-<n>.txt` (formats in `09` section 2), plus the image folder, and parse the answer-key syntax (`,` parts, `/` alternatives, `"…"` instructions, `i.`/`ii.` labels). Port `reference/grading_test_harness/gradetest/answer_key.py` and `meta.py` and copy `tests/test_answer_key.py`. Cross-file checks: report ids missing from any file, ids with two skills (D9), duplicate ids, ids with no image. `scripts/import_questions.py`; `scripts/unverified_keys.py`. Tests: single MCQ, single short, three-part short, mixed MCQ + short, instruction part, number with thousand comma (`80,004`), a row whose part count does not match, an id missing from the skill file.
- A test that scans every client-facing response model for the forbidden field names (`correct_option`, `accepted_answers`, `instruction`, `answer_key_raw`).

USER INPUT needed: the question images with their ids, the CSV (skill, type, option labels, correct option or accepted answers, language), and the skill names (English/Sinhala). Until then use generated fake questions (large printed text) from `tests/fixtures/`.

Done when: importing a valid file works; each invalid case from `02` is rejected with line numbers; the forbidden-fields test passes.

## Step 2 — Attempts (S)

Tasks
- `compute_penalty(source, time_ms, hints)` in one place, reading the constants from the spec.
- `POST /attempts` (with idempotency key); `attempts.load_history(student_id)` returns ordered history.

Done when: unit tests for the penalty formula (digital examples; paper constant 0.08), the endpoint inserts rows, idempotency works, history order is `(answered_at, id)`.

## Step 3 — Model service (M) — **USER INPUT**

USER INPUT needed: `mindbridge_dkt_v2_best.pt` and `golden_history.json` exported from Colab (see `03` section 5).

Tasks
- `ml/model.py`, `features.py`, `inference.py` exactly as in `03`; load weights at startup; model version string.
- Golden test; `scripts/penalty_sensitivity.py`.

Done when: the golden test passes within 1e-3; empty history gives all `null`; skills with < 3 attempts give `null`; sensitivity script prints a table.

## Step 4 — Mastery API (S)

Tasks: `mastery.recompute`, `mastery_snapshots`, `GET /students/{id}/mastery`, recompute endpoint (debounced).

Done when: after inserting a scripted history through `POST /attempts`, the endpoint returns 30 entries with correct `null` handling and the same values as the direct function call.

## Step 5 — Paper selection (M)

Tasks: `paper_selection.py` exactly as in `04` section 2: the **knapsack formulation solved with OR-Tools CP-SAT**, the greedy baseline and fallback, practice and diagnostic mode, deterministic with seed; all edge cases and tests listed there; `scripts/eval_selection.py` comparing knapsack with greedy.

Done when: all selection tests pass using fake mastery vectors and a fake question pool of ≥ 200 questions.

## Step 6 — Layout, PDF, markers, QR (L)

Tasks
- `paper_layout.py` (geometry constants, fractions), `paper_pdf.py` (markers, QR, images, header/footer), self-check by rendering and detecting.
- `POST /students/{id}/papers`, `GET /papers/{id}`, `GET /papers/{id}/pdf`; save `papers` and `paper_items` in one transaction.

Done when: layout tests pass; the generated PDF passes its own marker/QR self-check; **USER INPUT:** print one paper at 100% on a real printer and check the black squares are fully printed and nothing is clipped.

## Step 7 — Alignment and crops (L), plus a thin upload page

Tasks
- `alignment.py` with method A (ArUco + QR) as primary and method B (SIFT + RANSAC registration to the rendered PDF page, accept ≥ 25 inliers) as fallback, and `crops.py` cutting **one crop per question block** (extends to the right frame edge; small padding), as in `05` sections 1–2. Port `reference/grading_test_harness/gradetest/locator.py`.
- `scripts/make_synthetic_photo.py` and the synthetic-photo tests (including a photo with the markers hidden that must still align by method B, and a photo of the wrong paper that must be rejected).
- A very simple web page (single HTML or the start of the React app) that uploads a photo for a given paper page and shows the straightened result, so real phone photos can be collected early.

**USER INPUT:** photograph 10–20 printed papers with a phone (good and bad conditions) and share them (or run the pipeline yourself) to tune blur and marker thresholds.

Done when: synthetic tests meet the targets in `05` section 11; on real photos, at least 90% of reasonable photos align (by A or B); failures give a clear reason (`markers_missing`, `low_match`, `blurry`, `wrong_paper`, `wrong_page`).

## Step 8 — Rule engine and vision interface (M)

Tasks: `rules_compare.py` (port of `answer_key.compare` and normalisation incl. Sinhala digits and ZWJ), `combine_parts()` (`05`), `vision/base.py` with `PartSpec` / `PartRead` / `ItemRead`, `MockProvider`, `pipeline.py` using the mock; unit tests for every row of the comparison table in `05` (choice equivalence i/ii/iii = 1/2/3, number-in-text "6 more" for 6, near-miss → review, blank, two marks, instruction part) and multi-part questions (part *n* of the reading is compared with part *n* of the key; a part-count mismatch from the vision model is flagged). A test must fail if any prompt string contains an accepted answer or the correct option.

Done when: the full pipeline test with scripted mock readings produces the expected statuses for all cases, including cross-out, blank, ambiguous and near-miss.

## Step 9 — Real vision provider and benchmark (M) — **USER INPUT**

USER INPUT needed: API keys in `.env` (never committed); cropped, consented photos of children's answers with the human `labels.csv`.

Tasks
- Providers ported from `reference/grading_test_harness/gradetest/providers/`: `gemini`, `openai_compat` (covers OpenAI, Groq, OpenRouter and custom endpoints). Use the **blind** prompt `vision/prompts/item_blind_v2.txt` (`05`); never send the key. Model names come from `.env`; on HTTP 404 (model withdrawn) switch to the newest available Flash-class model and report `vision_model_auto_switched` in `/health`; retry 429/5xx with back-off; fail fast on a hard daily quota; concurrency 3–4; cache by (submission, item, provider, model, prompt version); write every call to `vision_calls`.
- Optional second-opinion provider with consensus rule (`05` section 8): same reading → accept, different → `needs_review`.
- `scripts/benchmark_vision.py` (can wrap the harness `run.py grade`) and the results table.
- Choose the provider, the paid plan and the confidence threshold from the benchmark. Free tiers are for development only (daily caps; data-use terms).

Done when: a table of accuracy / share sent to the parent / cost / latency per provider exists; `VISION_PROVIDER` is set to the chosen one; the four real test photos grade end to end through the product pipeline with results at least as good as the harness run.

> The benchmark can start as soon as Step 7 yields real crops. It does not block Steps 10–11, which run on the mock provider.

## Step 10 — Submissions API, review, attempts (M)

Tasks
- `POST /papers/{id}/pages/{n}/photo` with background grading; `GET /submissions/{id}`; `POST /submissions/{id}/confirm`.
- Create `attempts` for confirmed items (paper source), then `mastery.recompute`.
- Paper status transitions (`generated` → `partially_uploaded` → `graded`/`needs_review` → `confirmed`).
- Review items carry the block crop and the reason (`06`); instruction parts are confirmed with yes/no.
- Monitoring: `vision_calls` admin report (share of items needing review, mean latency, cost per paper, errors by provider); quota and model-withdrawn errors visible in `/health` warnings.

Done when: an integration test goes from "generate paper" through "upload synthetic photo" to "confirm" and checks that attempts exist with `source = 0` and mastery changed; the answer key never appears in any response.

## Step 11 — Frontend screens and iPhone testing (L)

Tasks: set up Vite + Capacitor (see `07`), generate API types from `openapi.json`, build the five screens, camera upload, review screen, mastery screen; run on an iPhone (Option A or B in `07`).

Done when: on a real iPhone you can generate a paper, open the PDF, photograph a printed page, see it graded, and confirm an unclear answer.

## Step 12 — End-to-end test, pilot, evaluation (M)

Tasks
- Scripted end-to-end run (new child → diagnostic paper → answers → next paper).
- **USER INPUT:** a small pilot with consented children if possible; otherwise a clearly labelled simulated walk-through.
- Evaluation scripts that reproduce every report number: model AUC vs baselines (from Colab), grading accuracy from the benchmark, share of items sent to the parent, penalty-sensitivity table.
- Write the limitations section: simulated training data, small pilot, Sinhala handwriting accuracy, no per-question time on paper.

Done when: every number in the report comes from a script or notebook in the repository.

---

## Parallel track: things the owner must do outside the codebase

| When | Task |
| --- | --- |
| Before Step 1 | Verify every answer key with a second person; decide the 30 skill names; give each skill a default difficulty. |
| Before Step 3 | Export `mindbridge_dkt_v2_best.pt` and `golden_history.json` from Colab. |
| During Steps 6–7 | Print a paper; take phone photos in different conditions. |
| Before Step 1 | Fix the data problems listed in `09` section 2 (ids missing from skill files, the `4.54`/`4.50` label, two questions on one image) and decide D9 (questions with two skills). |
| Before Step 9 | Get parental consent, crop names and faces, label what each child marked or wrote. Decide the second-opinion provider. Create a paid API key and read its data-use terms before real children's photos are sent. |
| Any time | Agree interfaces with teammates: who calls `POST /attempts`, who owns the mastery screen, how login works. |
