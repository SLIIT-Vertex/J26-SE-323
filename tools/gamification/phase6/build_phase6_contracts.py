"""Build/check the development-only OpenAPI and JSON-schema contract artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI

from app.gamification.api.phase6_router import router

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs" / "adaptive-gamified-learning" / "phase6-mobile-contracts-v1.json"


def build() -> dict[str, object]:
    app = FastAPI(title="MindBridge development contract", version="1.0.0")
    app.include_router(router, prefix="/api/v1")
    schema = app.openapi()
    return {
        "contract_version": "phase6-mobile-contracts-v1",
        "development_only": True,
        "production_child_delivery": "blocked_pending_human_approval",
        "openapi": schema,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        return 0 if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") == rendered else 1
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
