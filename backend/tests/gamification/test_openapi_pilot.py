"""The checked-in pilot contract is the gamification router, not the whole application."""

import json
from pathlib import Path

from fastapi import FastAPI

from app.gamification.api.router import router

CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "adaptive-gamified-learning"
    / "openapi-pilot-v1.json"
)


def pilot_openapi() -> dict[str, object]:
    application = FastAPI(title="MindBridge pilot", version="0.1.0")
    application.include_router(router, prefix="/api/v1")
    return application.openapi()


def test_checked_in_openapi_matches_the_pilot_router() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == pilot_openapi()
