"""The checked-in pilot contract is the gamification router, not the whole application."""

import json
from pathlib import Path

from fastapi import FastAPI

from app.gamification.api.router import ResponseRequest, router

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


def test_invalid_optional_visual_is_discarded_without_rejecting_answer() -> None:
    request = ResponseRequest.model_validate(
        {
            "episode_id": "00000000-0000-4000-8000-000000000001",
            "selected_option_id": "A",
            "response_time_ms": 1200,
            "visual": {"face_visibility_ratio": 2.0},
        }
    )

    assert request.visual is None
