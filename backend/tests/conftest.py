import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
# Tests feed the reader scripted readings in order; the blank re-check (on in the app) would use up
# the next one, so it is off here and tested on its own.
os.environ.setdefault("GRADING_RECHECK_BLANKS", "false")
# Settings a developer changes in their own backend/.env for demos and trials (no waiting for the weekly
# paper, reading the game's development answers by itself) must not change what the tests expect: an
# environment variable beats the .env file, so the defaults are pinned here. Tests that need another
# value set it themselves.
os.environ.setdefault("PAPER_MIN_DAYS_AFTER_JOINING", "7")
os.environ.setdefault("PAPER_DEFAULT_MODE", "auto")
os.environ.setdefault("GAME_EVIDENCE_AUTO_READ", "false")
os.environ.setdefault("GAME_EVIDENCE_INCLUDE_DEVELOPMENT", "false")

from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import get_db


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
