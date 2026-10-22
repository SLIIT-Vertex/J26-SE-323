"""Development reads of the draft mission catalog stay off the public router."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gamification.api.dependencies import NOT_FOR_PRODUCTION
from app.gamification.api.learning_flow_router import development_router, legacy_router, router
from app.gamification.api.router import router as public_router

LIST_PATH = "/api/v1/learning-flow/draft-missions"
BLOCKED_AREA_IDS = ("G5-AREA-SIN-11", "G5-AREA-SIN-12")
ANSWER_KEY_FIELDS = {
    "accepted_response",
    "answer_key",
    "correct_option_id",
    "server_answer_keys",
}
REMOVED_FIELDS = {
    "allow_draft",
    "development_only",
    "publication_status",
    "review_status",
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
        assert REMOVED_FIELDS.isdisjoint(value)
        for child in value.values():
            _forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _forbidden_keys(child)


def test_learning_list_returns_54_missions_without_answer_keys() -> None:
    response = _client().get(LIST_PATH, headers=HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    missions = body["missions"]
    area_ids = [mission["area_id"] for mission in missions]
    assert len(missions) == 54
    assert len(set(area_ids)) == 54
    assert BLOCKED_AREA_IDS[0] not in area_ids
    assert BLOCKED_AREA_IDS[1] not in area_ids
    _forbidden_keys(body)
    assert "correct_option_id" not in response.text


def test_blocked_area_fetches_are_not_found() -> None:
    client = _client()

    for area_id in BLOCKED_AREA_IDS:
        response = client.get(
            f"{LIST_PATH}/{area_id}", headers=HEADERS
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "DRAFT_MISSION_NOT_FOUND"
        _forbidden_keys(response.json())

    present = client.get(
        f"{LIST_PATH}/G5-AREA-MAT-05", headers=HEADERS
    )
    assert present.status_code == 200, present.text
    mission = present.json()
    assert mission["area_id"] == "G5-AREA-MAT-05"
    assert mission["cited_node_id"] == "G5-MAT-C03"
    assert mission["template_id"] == "half_set"
    _forbidden_keys(mission)


def test_area_support_types_follow_the_provisional_catalog() -> None:
    client = _client()
    fractions = client.get(
        f"{LIST_PATH}/G5-AREA-MAT-05/support-types",
        headers=HEADERS,
    )
    riddle = client.get(
        f"{LIST_PATH}/G5-AREA-SIN-03/support-types",
        headers=HEADERS,
    )
    blocked = client.get(
        f"{LIST_PATH}/G5-AREA-SIN-11/support-types",
        headers=HEADERS,
    )

    assert fractions.status_code == 200, fractions.text
    # Mathematics runs the multi-help loop over every type in the shared contract.
    assert fractions.json()["eligible_support_types"] == [
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
        "simpler_same_game",
        "prerequisite_repair",
        "conceptual_reexplanation",
    ]
    assert fractions.json()["authoring_basis"] == "provisional_development_assumption"
    assert riddle.status_code == 200, riddle.text
    # Riddles now register visual guidance too, pointed at the learner's own clue selections.
    assert riddle.json()["eligible_support_types"] == [
        "visual_guidance",
        "worked_parallel_example",
        "step_by_step_guidance",
    ]
    assert riddle.json()["rule"] == "riddle_inference"
    assert blocked.status_code == 404, blocked.text
    assert blocked.json()["detail"]["code"] == "AREA_SUPPORT_NOT_FOUND"
    _forbidden_keys(fractions.json())


def test_game_routes_are_only_on_the_learning_router() -> None:
    public = FastAPI()
    public.include_router(public_router, prefix="/api/v1")
    development = FastAPI()
    development.include_router(development_router, prefix="/api/v1")
    hidden = FastAPI()
    hidden.include_router(legacy_router, prefix="/api/v1")

    assert all("draft-missions" not in path for path in public.openapi()["paths"])
    assert all("draft-missions" not in path for path in development.openapi()["paths"])
    assert all("fixture-rounds" not in path for path in development.openapi()["paths"])
    assert all("draft-missions" not in path for path in hidden.openapi()["paths"])
    paths = _client().app.openapi()["paths"]
    assert LIST_PATH in paths
    assert f"{LIST_PATH}/{{area_id}}" in paths
    assert f"{LIST_PATH}/{{area_id}}/support-types" in paths
    assert "/api/v1/learning-flow/fixture-rounds" in paths
    assert "/api/v1/learning-flow/fixture-rounds/{episode_id}/answer" in paths
    assert "/api/v1/learning-flow/fixture-rounds/{episode_id}/continue" in paths
    assert "allow_draft" not in str(_client().app.openapi())
