# MindBridge

MindBridge is a university research project supporting Sri Lankan Grade 4–5 scholarship
learners. This repository contains only the shared technical foundation: a modular-monolith API,
a shared learner identity, PostgreSQL with pgvector readiness, and a minimal mobile-ready web app.

The four research algorithms are intentionally not implemented.

## Architecture

- **Frontend:** React, TypeScript, Vite, and Capacitor
- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, and Alembic
- **Database:** one PostgreSQL 16 database with pgvector
- **Shape:** modular monolith with lightweight Clean Architecture boundaries
- **API:** REST under `/api/v1`; OpenAPI at `/docs`

The shared layer owns the learner profile and UUID. Each research module will own its own state
and tables, linked by `learner_id`; modules must use explicit public contracts rather than import
each other's infrastructure. See [docs/architecture.md](docs/architecture.md).

## Repository structure

```text
backend/
  app/shared/                 # Database, auth boundary, shared learner
  app/knowledge_tracing/      # Empty Clean Architecture boundary
  app/learner_state/          # Empty Clean Architecture boundary
  app/adaptive_tutor/         # Empty Clean Architecture boundary
  app/gamification/           # Empty Clean Architecture boundary
  alembic/                    # Database migrations
  tests/                      # API tests
frontend/
  src/api/                    # HTTP client
  src/features/               # Feature-owned UI
docs/                         # Architecture documentation
research/                     # Research notes and non-runtime artifacts
docker-compose.yml            # Local PostgreSQL only
```

## Local setup

Prerequisites: Python 3.11+, Node.js 20+, npm, and Docker.

### 1. Start PostgreSQL

```bash
cp .env.example .env
# Replace the example password in .env.
docker compose up -d database
```

### 2. Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Set DATABASE_URL with the same local PostgreSQL credentials used above.
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`, with Swagger UI at
`http://localhost:8000/docs`.

Backend environment variables:

| Variable | Purpose | Example |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL | `postgresql+psycopg://mindbridge:password@localhost:5432/mindbridge` |
| `FRONTEND_ORIGIN` | Browser origin allowed by CORS | `http://localhost:5173` |

Run backend checks from `backend/`:

```bash
pytest
ruff check .
```

### 3. Run the frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend runs at `http://localhost:5173` and calls the versioned health endpoint. Set
`VITE_API_URL` if the backend is hosted elsewhere.

Build and type-check it with:

```bash
npm run build
npm run typecheck
```

`npm run build` creates the web bundle and synchronizes every installed Capacitor platform.

### Optional native projects

Capacitor configuration is ready, but generated native projects are not committed. With Android
Studio or Xcode installed, generate the targets once from `frontend/`:

```bash
npm run build:web
npx cap add ios
npx cap add android
```

After that, use:

```bash
npm run build          # Build web and sync both installed platforms
npm run build:ios      # Build web and sync iOS only
npm run build:android  # Build web and sync Android only
npm run ios            # Build, sync, and run iOS
npm run android        # Build, sync, and run Android
npm run open:ios       # Open the Xcode project
npm run open:android   # Open the Android Studio project
```

## Current API

- `GET /api/v1/health`
- `POST /api/v1/learners`
- `GET /api/v1/learners`
- `GET /api/v1/learners/{learner_id}`

The learner stores only `id`, `grade`, `preferred_language`, `created_at`, and `updated_at`.
Authentication and all research algorithms remain intentionally deferred.
