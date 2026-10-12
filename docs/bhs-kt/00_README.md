# MindBridge — Knowledge Tracing, Paper Generation and Paper Grading (component spec)

> **Read this file first, then follow `08_IMPLEMENTATION_ORDER.md` step by step.**
> These documents describe ONE component of a four-person SLIIT research project. They are written for an AI coding assistant working inside the project repository.

## 1. What the whole app is (context only)

MindBridge is an adaptive learning app for Sri Lankan Grade 5 scholarship-exam children (Sinhala and English). A child learns in two ways:

1. **Digital games** in the app (answers are logged with time and hints).
2. **Printed practice papers**, which the app generates for that child. The parent photographs the answered pages and uploads them; the system grades them.

Teammates own the games, the main app screens, login and everything else. **This component** owns:

| Part | What it does |
| --- | --- |
| **A. Knowledge model service** | A trained GRU knowledge-tracing model (PyTorch) turns a child's answer history (digital + paper) into a "mastery" value for each of 30 skills. |
| **B. Paper generator** | Chooses questions from the question bank for one child from their mastery values and builds a printable PDF with alignment markers and a QR code. |
| **C. Paper grading pipeline** | Takes photos of the answered pages, straightens them, crops each question, uses an external vision model to read the child's marks/handwriting, applies deterministic grading rules, and asks the parent to confirm unclear answers. |
| **D. Data layer + API** | Postgres schema, image storage, REST API for the above. |
| **E. Frontend pieces** | React + Capacitor screens for: generate/open a paper, photograph and upload pages, confirm unclear answers, show mastery. |

**Research contribution (do not break it):** the model uses a `source` feature (digital = 1, paper = 0) so that digital play and paper writing are combined into one honest estimate of the child's mastery. Keep `source` in every attempt record.

## 2. Tech stack (decided)

| Layer | Choice |
| --- | --- |
| Database | PostgreSQL 15+ |
| Backend | Python 3.11+, **FastAPI**, Pydantic v2, SQLAlchemy 2.x, Alembic, psycopg 3 |
| ML | PyTorch (CPU inference only), NumPy |
| Optimisation | Google OR-Tools (CP-SAT) for the knapsack that chooses paper questions |
| Images | OpenCV (`opencv-contrib-python-headless`, needed for ArUco), Pillow |
| PDF | ReportLab (generation), `pypdfium2` (rendering PDF to PNG in tests) |
| Storage | Behind a `StorageBackend` interface: local folder in development, private S3 bucket in production |
| Vision model | Behind a `VisionProvider` interface. Tested on real photos: **Gemini Flash-class (primary)** and Groq (Qwen vision, secondary / second opinion). Free tiers are for development only; production needs a paid key (see `05` section 9, `09`) |
| Frontend | React + TypeScript + Vite + **Capacitor** (iOS and Android) |
| Tests | pytest (backend), Vitest (frontend) |

If the group already has a shared backend repository, add this component as a module inside it and reuse its auth and `students` table. Otherwise create it as a standalone service (layout in `01_ARCHITECTURE.md`).

## 3. Document map

| File | Contents |
| --- | --- |
| `00_README.md` | This file: scope, rules, glossary, open decisions |
| `01_ARCHITECTURE.md` | Repo layout, modules, data flows, configuration |
| `02_DATABASE.md` | Full Postgres schema (DDL), constraints, import rules |
| `03_MODEL_SERVICE.md` | The model, the feature spec, inference code, golden test |
| `04_PAPER_GENERATOR.md` | Question selection, PDF layout, markers, QR, stored coordinates |
| `05_GRADING_PIPELINE.md` | **v2.** Alignment (markers, or feature registration), block crops, blind vision reading, comparison rules, review flow, operations |
| `06_API_SPEC.md` | REST endpoints with example JSON |
| `07_FRONTEND_AND_IPHONE.md` | React/Capacitor screens, iPhone testing, CORS and iOS settings |
| `08_IMPLEMENTATION_ORDER.md` | **The ordered build plan with a "done when" check per step and a ready-made prompt per step** |
| `09_GRADING_TEST_FINDINGS.md` | What the grading experiment on real photos showed, the teacher's file formats, and how to grade every generated paper |
| `UPDATE_NOTES.md` | What changed in this version of the package, and the prompt to give your IDE |
| `shared/feature_spec.json` | The single source of truth for skill order, source coding, difficulty mapping, penalty rule |
| `reference/mindbridge_dkt_v2_1.py` | The Colab training script that produced the model (reference, do not run in production) |
| `reference/grading_test_harness/` | Working code of the grading experiment (answer-key parser, photo alignment, providers, prompts, report). Port from it; do not ship it |

## 4. Rules for the AI assistant

1. **Follow the order in `08`.** Finish a step, run its tests, report, then continue. Do not jump ahead.
2. **Never invent project facts.** If something is not in these documents (a table owned by a teammate, an auth scheme, a deadline), look in the repository first, then stop and ask the user. Items marked `DECISION` have a stated default: use the default, and put a one-line note in the final summary of that step.
3. **Answer keys never leave the server.** The answer key of a question (correct option, accepted answers) must never be sent to the mobile client and never be sent to the vision model. The vision model only *reads* what the child wrote; code compares it with the key ("blind reading", see `05`). Instruction texts (e.g. "check that three boxes are coloured") are allowed in prompts, expected results are not.
4. **One feature spec.** Skill order, source coding, difficulty mapping and the penalty rule are read from `shared/feature_spec.json` by both training code and serving code. Never hard-code a second copy.
5. **No secrets in git.** API keys and database passwords come from environment variables (`.env` is git-ignored; commit `.env.example`).
6. **Children's data is sensitive.** Do not log image contents, do not put a child's name or face data in file names or QR codes. Papers carry only an opaque code. Store images in a private bucket and serve them with short-lived signed URLs.
7. **Tests are part of the work.** Every step in `08` lists the tests that must pass. Keep unit tests free of network calls: vision providers are mocked in tests.
8. **Small, readable commits** (one step or sub-step each), type hints everywhere, `ruff` and `mypy` clean.
9. **Be honest in comments and docs about the model.** It was trained on *simulated* data. Do not write claims such as "validated on real children".

## 5. Glossary

| Term | Meaning |
| --- | --- |
| Skill | One of 30 codes, e.g. `MAT-FRC` (fractions). Fixed list and order in `shared/feature_spec.json`. |
| Question | One row in the question bank: one image = one question. |
| Part | One answer of a question. Most questions have one part; a question with several answers on one image has one part per answer, in the order the child answers them. A part may accept several alternative answers (`ans1/ans2`) and may carry a grader instruction (see `02` and `09`). |
| Source | How an answer was given: `1` = digital game, `0` = paper. |
| Attempt | One answered question by one child (digital or paper). The model's training unit. |
| Mastery | For one skill: the model's predicted probability that the child answers a **medium-difficulty paper question** of that skill correctly. `null` (unknown) if the child has fewer than 3 attempts in that skill. |
| Paper | One generated PDF for one child; has 1–3 pages. |
| Paper item | One question placed at one position on a paper. Stores the page and the box coordinates. |
| Block box | The rectangle of the page that holds one question image plus its answer area. |
| Answer box | For each short-answer part: the numbered rectangle where the child writes that answer. |
| Frame | The rectangle between the 4 corner marker centres. All stored coordinates are fractions of this frame (`0..1`), so printing at a slightly wrong scale does not matter. |
| Submission | One uploaded photo of one page of a paper. |
| Graded answer | The reading and grade for one paper item from one submission. |

## 6. Open decisions (defaults to use unless the user says otherwise)

| # | Decision | Default |
| --- | --- | --- |
| D1 | Difficulty labels | Every question has `easy`, `medium` or `hard`; the loader gives each question its skill's default level, and the owner overrides single questions. Model values: 0.0 / 0.5 / 1.0. |
| D2 | Time and hints for paper answers | Not available. Use the constant penalty `0.08` for paper attempts (`shared/feature_spec.json`). Run the sensitivity check in `03`. |
| D3 | Questions per paper | Default: up to 15 questions, 25 minutes and 3 pages, configurable per request. In practice the page space decides (about 8–16 questions); measure the real average block height once the bank is loaded and adjust. |
| D4 | Unknown skills | A skill with fewer than 3 attempts is `null`; the generator treats it as "needs a diagnostic question". |
| D5 | Vision provider | `mock` in tests. Primary: Gemini Flash-class (best result in the real-photo experiment; model name from `GEMINI_MODEL`, never hard-coded). Optional second opinion: Groq or another model (`VISION_SECOND_PROVIDER`). Confirm with the benchmark in `05` section 11. |
| D6 | Parent confirmation threshold | A reading with confidence below `0.70` goes to the parent. Tune after the benchmark. |
| D7 | Teammate interfaces | Who calls `POST /attempts` for game answers, and who owns the mastery display screen, must be agreed with the teammates. Default: the game backend calls `POST /attempts`; the mastery screen reads `GET /students/{id}/mastery`. |
| D9 | Questions with two skills | Some bank questions list two skills (e.g. `LAN-CMP, LAN-ORT`) with two difficulties and two times. Default: `skill_code` = the first skill, the others go to `secondary_skill_codes`; `difficulty` = the first one's; `est_seconds` = the sum of the times. The model treats the question as the first skill only. Revisit with the model owner. |
| D10 | Reading unit for grading | One vision call per question block (whole crop, all parts), blind (no key), parts returned in key order. Per-answer-box crops are not needed for grading. |
| D8 | Questions with several answers | One attempt per question; it is `correct` only if all parts are correct. Part-by-part results are kept for feedback. The game must follow the same rule. Prefer splitting an image into separate questions when possible. |

## 7. Definition of done for the whole component

- A game answer and a photographed paper answer both end up as rows in `attempts` with the right `source`.
- `GET /students/{id}/mastery` returns 30 values (or `null` for unknown) computed by the trained model, and the golden test proves it matches the Colab output.
- A paper is generated from that mastery, printed, photographed with a phone, and every question is graded as `correct`, `wrong`, `blank` or sent to parent review.
- Parent confirmations feed back into `attempts`, and mastery is recomputed.
- Every number in the final report can be reproduced by a script in the repository.
