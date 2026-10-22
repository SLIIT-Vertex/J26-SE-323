"""Serve the real research API with a FAKE Gemini client for browser end-to-end checks.

Everything is the normal local research composition (E5 Skill Mapper, KT, Learner State,
assessment ledger, history, Controller V1) except that experimental drafts come from a canned
fake client, so no browser session can trigger a real Gemini call. Loopback only.

  cd backend
  .venv/bin/python -m scripts.serve_research_fake_gemini              # DATABASE_URL from .env
  .venv/bin/python -m scripts.serve_research_fake_gemini --database sqlite --learner-id <uuid>

Defaults to port 8001 so it never shadows a real-Gemini server on 8000. Point the frontend at it:
  VITE_API_URL=http://localhost:8001/api/v1 npm --prefix frontend run dev
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse
from uuid import UUID

import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.adaptive_tutor.api.router import get_research_tutor_service
from app.adaptive_tutor.infrastructure.local_research import build_local_research_tutor_service
from app.config import Settings
from app.main import app
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from scripts.pp1_multiturn_demo import CallLog, FakeRehearsalProvider

FAKE_MARKER_PATH = "/__fake-gemini"


def open_session(database: str, learner_id: UUID | None) -> Session:
    if database == "configured":
        from app.shared.database.session import SessionLocal

        return SessionLocal()
    if learner_id is None:
        raise ValueError("--learner-id is required with --database sqlite")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(LearnerModel(id=learner_id, grade=5, preferred_language="en"))
    session.commit()
    return session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", choices=("configured", "sqlite"), default="configured")
    parser.add_argument("--learner-id", type=UUID)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    settings = Settings()
    log = CallLog()
    service = build_local_research_tutor_service(
        settings,
        open_session(args.database, args.learner_id),
        llm_provider=FakeRehearsalProvider(log),
    )
    app.dependency_overrides[get_research_tutor_service] = lambda: service

    @app.get(FAKE_MARKER_PATH, include_in_schema=False)
    def fake_gemini_marker() -> dict[str, str]:
        """Exists only in this process, so clients can confirm they are not on a real server."""

        return {"provider": "FAKE_GEMINI"}

    print("FAKE GEMINI research server: drafts are canned, no Gemini requests are possible.")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
