from fastapi.testclient import TestClient


def test_create_and_get_learner(client: TestClient) -> None:
    created = client.post(
        "/api/v1/learners", json={"grade": 4, "preferred_language": "si"}
    )

    assert created.status_code == 201
    learner = created.json()
    assert learner["grade"] == 4
    assert learner["preferred_language"] == "si"

    fetched = client.get(f"/api/v1/learners/{learner['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == learner


def test_missing_learner_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/learners/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Learner not found"}

