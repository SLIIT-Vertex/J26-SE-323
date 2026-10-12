# 01 — Architecture

## 1. Repository layout (standalone service; adapt if joining the group repo)

```
mindbridge/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration
│   │   ├── config.py                # Settings from environment (pydantic-settings)
│   │   ├── db.py                    # engine, session dependency
│   │   ├── models/                  # SQLAlchemy models (one file per table group)
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── api/                     # routers: attempts, mastery, papers, submissions, admin
│   │   ├── services/
│   │   │   ├── question_import.py   # CSV/JSON importer + validation
│   │   │   ├── attempts.py          # logging attempts, loading history
│   │   │   ├── mastery.py           # snapshots, recompute
│   │   │   ├── paper_selection.py   # knapsack (CP-SAT) + greedy baseline; pure function, no I/O
│   │   │   ├── paper_layout.py      # place questions on pages (pure function)
│   │   │   ├── paper_pdf.py         # draw PDF, markers, QR
│   │   │   ├── grading/
│   │   │   │   ├── alignment.py     # method A: ArUco + homography; method B: SIFT feature registration to the PDF page
│   │   │   │   ├── crops.py         # crop whole question blocks (to the right page edge)
│   │   │   │   ├── answer_key.py    # parse the key syntax (parts, alternatives, instructions) - used by the importer
│   │   │   │   ├── rules_compare.py # normalisation + comparison rules (ported from the harness)
│   │   │   │   ├── combine.py       # combine_parts()
│   │   │   │   ├── pipeline.py      # orchestration for one submission (blind reading, compare, review flags)
│   │   │   │   └── vision/
│   │   │   │       ├── base.py      # VisionProvider interface + PartSpec/PartRead/ItemRead schemas
│   │   │   │       ├── prompts/     # item_blind_v2.txt (versioned)
│   │   │   │       ├── mock.py
│   │   │   │       ├── gemini.py
│   │   │   │       └── openai_compat.py  # Groq, OpenRouter, OpenAI, Mistral ... (OpenAI-style chat API)
│   │   ├── ml/
│   │   │   ├── model.py             # MindBridgeDKT (identical to training)
│   │   │   ├── features.py          # attempts -> tensors (reads shared/feature_spec.json)
│   │   │   ├── inference.py         # compute_mastery, predict_item_probs
│   │   │   └── weights/             # mindbridge_dkt_v2_best.pt (+ model_meta.json)
│   │   └── storage/                 # StorageBackend: local.py, s3.py
│   ├── alembic/                     # migrations
│   ├── tests/
│   │   ├── fixtures/                # golden_history.json, sample question images
│   │   ├── unit/
│   │   └── integration/
│   ├── scripts/
│   │   ├── import_questions.py
│   │   ├── make_synthetic_photo.py  # warps a rendered PDF page like a phone photo
│   │   └── benchmark_vision.py      # compare vision models on labelled child photos (reuse the harness in reference/)
│   └── pyproject.toml
├── frontend/                        # React + Vite + Capacitor (see 07)
├── shared/feature_spec.json         # single source of truth (copied from this package)
├── docker-compose.yml               # postgres (+ minio optional) for local dev
├── .env.example
└── docs/                            # these .md files
```

## 2. Data flows

### 2.1 Learning loop

```
Game answer ──► POST /attempts ─────────────┐
                                            ▼
                                     attempts (source=1)
                                            │
Paper photo ─► grading pipeline ─► parent ──┤  attempts (source=0)
                                   confirms │
                                            ▼
                    history (ordered by answered_at, id)
                                            │
                                            ▼
                       ml.inference.compute_mastery()
                                            │
                                            ▼
                         mastery_snapshots (30 values or null)
                                            │
                                            ▼
                       paper_selection (needs + stretch zone)
                                            │
                                            ▼
                paper_layout ─► paper_pdf ─► papers + paper_items
```

### 2.2 Grading one uploaded page

```
photo ─► EXIF rotate ─► QR + 4 ArUco markers (else SIFT registration to the PDF page) ─► check paper id/page
      ─► homography ─► canonical page image
      ─► for each paper_item on this page:
            crop the whole block (to the right page edge)
            ─► VisionProvider (blind: NO answer key) ─► one reading per part
            ─► comparison rules (normalise, alternatives, number-in-text, choice equivalence)
            ─► (optional) second provider: disagree ─► needs_review
            ─► auto_status + confidence
      ─► items with low confidence or ambiguous ─► "needs_review"
      ─► parent confirms ─► final_status ─► attempts (source = 0) ─► recompute mastery
```

## 3. Module boundaries (keep these clean)

| Module | Pure? | Notes |
| --- | --- | --- |
| `paper_selection`, `paper_layout`, `answer_key`, `rules_compare`, `combine` | **Pure functions** (no DB, no network) | Easy to unit-test with fake data. |
| `ml.*` | Pure given weights | Loaded once at startup; CPU only. |
| `alignment`, `crops` | Pure given image arrays | Tested with synthetic photos. |
| `vision.*` | Network | Hidden behind `VisionProvider`; mocked in tests. |
| `api.*` | Thin | Validate, call services, return schemas. |

## 4. Configuration (`.env.example`)

```
DATABASE_URL=postgresql+psycopg://mindbridge:mindbridge@localhost:5432/mindbridge
STORAGE_BACKEND=local            # local | s3
LOCAL_STORAGE_DIR=./data
S3_BUCKET=
S3_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SIGNED_URL_SECONDS=600
MODEL_WEIGHTS_PATH=app/ml/weights/mindbridge_dkt_v2_best.pt
FEATURE_SPEC_PATH=../shared/feature_spec.json
VISION_PROVIDER=mock             # mock | gemini | groq | openai | openrouter | custom
VISION_SECOND_PROVIDER=          # optional second opinion, same choices; empty = off
GEMINI_API_KEY=
GEMINI_MODEL=                    # pin a model; empty = newest available Flash (logged as a warning)
GROQ_API_KEY=
GROQ_MODEL=
OPENAI_API_KEY=
OPENAI_MODEL=
VISION_CONFIDENCE_MIN=0.70
VISION_CONCURRENCY=3
VISION_TIMEOUT_SECONDS=90
CORS_ORIGINS=http://localhost:5173,http://localhost,capacitor://localhost
SECRET_KEY=change-me
```

## 5. Background work

Grading one page takes tens of seconds (one vision call per question, 4–25 s each, sometimes much longer; run 3–4 in parallel). Start simple:

- `POST .../photo` stores the image, creates a `paper_submissions` row with `status='uploaded'`, returns at once, and schedules grading with FastAPI `BackgroundTasks`.
- The client polls `GET /submissions/{id}` until `status` is `graded`, `needs_review` or `failed_alignment`.
- Keep grading in one function `grade_submission(submission_id)` so it can later move to a worker (RQ/Celery) without changes.

## 6. Error handling principles

- Alignment cannot find all four markers → `failed_alignment` with a plain reason (`markers_missing`, `blurry`, `wrong_paper`); the app asks the parent to retake the photo. Never guess.
- A vision call fails or returns invalid JSON → retry once; if it still fails mark the item `needs_review` with `reason='vision_error'`. Never mark such an item wrong. Rate limits (429/503) are retried with back-off; a **hard quota** (daily limit) is not retried, marks the item `needs_review` and alerts the owner (`05` section 9).
- Never lose an upload: store the original image before any processing.
