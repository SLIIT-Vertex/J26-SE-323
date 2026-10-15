"""Checked-in development contract must rebuild exactly from the development router."""

import json
from pathlib import Path

from fastapi import FastAPI

from app.gamification.api.phase6_router import router

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs" / "adaptive-gamified-learning" / "phase6-mobile-contracts-v1.json"


def test_phase6_openapi_and_frontend_json_schema_are_current() -> None:
    app = FastAPI(title="MindBridge development contract", version="1.0.0")
    app.include_router(router, prefix="/api/v1")
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract_version": "phase6-mobile-contracts-v1",
        "development_only": True,
        "production_child_delivery": "blocked_pending_human_approval",
        "openapi": app.openapi(),
    }


def test_phase6_contract_exposes_no_server_answer_keys() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "correct_option_id" not in text
    assert "server_answer_keys" not in text
    assert "raw_independence_gain" not in text
    assert "policy_update_status" not in text
    assert "exclusion_reasons" not in text
