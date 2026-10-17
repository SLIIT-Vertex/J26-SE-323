"""Seed and run the real FastAPI app for mobile-learning end-to-end clients."""

import os
from datetime import UTC, datetime
from uuid import UUID

import uvicorn
from sqlalchemy.orm import Session

from app.main import app
from app.shared.database.base import Base
from app.shared.database.session import engine
from app.shared.learner.model import LearnerModel

LEARNER_IDS = (
    UUID("00000000-0000-4000-8000-000000000721"),
    UUID("00000000-0000-4000-8000-000000000722"),
)


def seed() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for learner_id in LEARNER_IDS:
            if session.get(LearnerModel, learner_id) is not None:
                continue
            now = datetime.now(UTC)
            session.add(
                LearnerModel(
                    id=learner_id,
                    grade=5,
                    preferred_language="si",
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()


if __name__ == "__main__":
    seed()
    uvicorn.run(
        app,
        host=os.environ.get("MOBILE_LEARNING_E2E_HOST", "127.0.0.1"),
        port=int(os.environ.get("MOBILE_LEARNING_E2E_PORT", "8765")),
        log_level="warning",
    )
