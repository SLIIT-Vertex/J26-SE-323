"""Development reads of the draft mission catalog stay off the public router."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION
from app.gamification.api.learning_flow_router import legacy_router, router
from app.gamification.api.router import router as public_router

LIST_PATH = "/api/v1/development/learning-flow/draft-missions"
BLOCKED_AREA_IDS = ("G5-AREA-SIN-11", "G5-AREA-SIN-12")
ANSWER_KEY_FIELDS = {
    "accepted_response",
    "answer_key",
    "correct_option_id",
    "server_answer_keys",
}
HEADERS = {
    "X-Dev-Principal": NOT_FOR_PRODUCTION,
    "X-Dev-Role": "researcher",
}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        assert ANSWER_KEY_FIELDS.isdisjoint(value)
        for child in value.values():
            _forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _forbidden_keys(child)


def test_development_list_returns_55_missions_without_answer_keys() -> None:
    response = _client().get(LIST_PATH, headers=HEADERS, params={"allow_draft": True})

    assert response.status_code == 200, response.text
    body = response.json()
    missions = body["missions"]
    area_ids = [mission["area_id"] for mission in missions]
    assert len(missions) == 55
    assert len(set(area_ids)) == 55
    assert BLOCKED_AREA_IDS[0] not in area_ids
    assert BLOCKED_AREA_IDS[1] not in area_ids
    assert body["development_only"] is True
    assert body["publication_status"] == "blocked"
    assert all(mission["development_only"] is True for mission in missions)
    assert all(mission["publication_status"] == "blocked" for mission in missions)
    _forbidden_keys(body)
    assert "correct_option_id" not in response.text


def test_blocked_area_fetches_are_not_found() -> None:
    client = _client()

    for area_id in BLOCKED_AREA_IDS:
        response = client.get(
            f"{LIST_PATH}/{area_id}", headers=HEADERS, params={"allow_draft": True}
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "DRAFT_MISSION_NOT_FOUND"
        _forbidden_keys(response.json())

    present = client.get(
        f"{LIST_PATH}/G5-AREA-MAT-05", headers=HEADERS, params={"allow_draft": True}
    )
    assert present.status_code == 200, present.text
    mission = present.json()
    assert mission["area_id"] == "G5-AREA-MAT-05"
    assert mission["cited_node_id"] == "G5-MAT-C03"
    assert mission["template_id"] == "half_set"
    assert mission["publication_status"] == "blocked"
    _forbidden_keys(mission)


def test_flag_off_rejects_both_reads() -> None:
    client = _client()
    paths = (LIST_PATH, f"{LIST_PATH}/G5-AREA-MAT-01", f"{LIST_PATH}/G5-AREA-SIN-11")

    for path in paths:
        omitted = client.get(path, headers=HEADERS)
        explicit = client.get(path, headers=HEADERS, params={"allow_draft": False})
        assert omitted.status_code == 403, omitted.text
        assert explicit.status_code == 403, explicit.text
        assert omitted.json()["detail"]["code"] == "DRAFT_CATALOG_BLOCKED"
        assert explicit.json()["detail"]["code"] == "DRAFT_CATALOG_BLOCKED"
        assert "missions" not in omitted.json()
        _forbidden_keys(omitted.json())


def test_draft_mission_reads_are_not_public_routes() -> None:
    public = FastAPI()
    public.include_router(public_router, prefix="/api/v1")
    hidden = FastAPI()
    hidden.include_router(legacy_router, prefix="/api/v1")

    assert all("draft-missions" not in path for path in public.openapi()["paths"])
    assert all("draft-missions" not in path for path in hidden.openapi()["paths"])
    assert LIST_PATH in _client().app.openapi()["paths"]
    assert f"{LIST_PATH}/{{area_id}}" in _client().app.openapi()["paths"]
