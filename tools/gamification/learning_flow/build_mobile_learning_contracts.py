"""Build/check the development-only OpenAPI and JSON-schema contract artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.gamification.api.learning_flow_router import development_router, router
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs" / "adaptive-gamified-learning" / "mobile-learning-contracts-v1.json"


def build() -> dict[str, object]:
    app = FastAPI(title="MindBridge development contract", version="1.0.0")
    app.include_router(router, prefix="/api/v1")
    app.include_router(development_router, prefix="/api/v1")
    schema = app.openapi()
    return {
        "contract_version": "mobile-learning-contracts-v1",
        "development_only": True,
        "production_child_delivery": "blocked_pending_human_approval",
        "openapi": schema,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    contract = build()
    if args.check:
        # Compare content, not bytes: key order and formatting do not change the contract.
        current = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
        return 0 if current == json.loads(json.dumps(contract)) else 1
    rendered = json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
