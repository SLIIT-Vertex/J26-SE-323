"""One development fixture loop per shared template, scored only on the server."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.gamification.application.fixture_round import (
    PROHIBITED_LEARNER_STATE_FIELDS,
    FixtureRoundService,
    reset_fixture_rounds,
)
from app.gamification.content.playable_area_package import load_playable_area_package

FIXTURES = (
    "G5-AREA-MAT-01",
    "G5-AREA-MAT-02",
    "G5-AREA-MAT-04",
    "G5-AREA-MAT-05",
    "G5-AREA-MAT-06",
    "G5-AREA-MAT-08",
    "G5-AREA-MAT-10",
    "G5-AREA-MAT-15",
    "G5-AREA-MAT-03",
    "G5-AREA-MAT-07",
    "G5-AREA-MAT-16",
    "G5-AREA-SIN-07",
    "G5-AREA-SIN-11",
    "G5-AREA-SIN-12",
    "G5-AREA-SIN-13",
    "G5-AREA-ENV-01",
    "G5-AREA-ENV-02",
    "G5-AREA-ENV-03",
    "G5-AREA-ENV-04",
    "G5-AREA-ENV-05",
    "G5-AREA-ENV-06",
    "G5-AREA-ENV-07",
    "G5-AREA-ENV-08",
)


def _play(service: FixtureRoundService, area_id: str, *, correct: bool) -> dict[str, object]:
    learner_id = uuid4()
    opened = service.open_round(
        area_id=area_id,
        learner_id=learner_id,
        session_id=uuid4(),
        grade=5,
        medium="si",
    )
    if area_id in {"G5-AREA-SIN-11", "G5-AREA-SIN-12"}:
        assert "5 ශ්‍රේණියේ මූලාශ්‍රයක් නොමැත" in str(opened["notice_si"])
    episode_id = UUID(str(opened["episode_id"]))
    _assert_public(opened)
    before = _answer(service, episode_id, learner_id, opened, correct=correct)
    assert before["phase"] == "support"
    assert before["support"]["support_type"]
    practice = service.continue_round(episode_id, learner_id=learner_id)
    assert practice["phase"] == "supported_practice"
    assert practice["assistance_state"] == "scaffold_active"
    assert practice["support"] is not None
    practiced = _answer(service, episode_id, learner_id, practice, correct=True)
    assert practiced["phase"] == "withdraw"
    assert practiced["support"] is None
    after = service.continue_round(episode_id, learner_id=learner_id)
    assert after["phase"] == "unsupported_after"
    assert after["assistance_state"] == "none"
    assert after["support"] is None
    assert after["prompt_si"] != opened["prompt_si"]
    finished = _answer(service, episode_id, learner_id, after, correct=True)
    assert finished["phase"] == "completed"
    assert len(finished["server_scores"]) == 3
    assert finished["reward"] == {"points": 1, "reason_code": "episode_complete"}
    assert finished["server_scores"][0]["earned_score"] == ("1" if correct else "0")
    evidence = service.evidence(episode_id)
    assert len(evidence) == 3
    for record in evidence:
        assert record["model_ingestion_eligible"] is False
        assert record["event_type"] == "gamification_item_scored"
        assert record["skill_id"] == area_id
        assert record["skill_id"] != "G5-MAT-C03-L01-O01"
        assert record["curriculum_passage_status"] == "NO_RELEVANT_PASSAGES"
        assert record["mastery"] is None
        assert record["learner_state"] is None
        assert set(PROHIBITED_LEARNER_STATE_FIELDS).isdisjoint(record)
    if area_id == "G5-AREA-SIN-13":
        assert all(record["universal_skill_id"] is None for record in evidence)
    return finished


def _answer(service, episode_id, learner_id, view, *, correct: bool):
    package = load_playable_area_package()
    row = next(area for area in package.areas if area.area_id == view["area_id"])
    item = next(candidate for candidate in row.items if candidate.prompt_si == view["prompt_si"])
    option_id = next(
        option["option_id"]
        for option in view["options"]
        if (option["text_si"] == item.correct_response) is correct
    )
    scored = service.answer(episode_id, option_id=option_id, learner_id=learner_id)
    _assert_public(scored)
    assert scored["server_score"]["server_authoritative"] is True
    assert scored["server_score"]["scoring_version"] == item.rubric.scoring_version
    assert scored["server_score"]["maximum_score"] == str(item.rubric.maximum_score)
    assert scored["server_score"]["earned_score"] == ("1" if correct else "0")
    return scored


def _assert_public(view: dict[str, object]) -> None:
    assert "සමාලෝචනය නොකළ" in str(view["notice_si"])
    encoded = json.dumps(view)
    for token in (
        "allow_draft",
        "development_only",
        "publication_status",
        "review_status",
        "unreviewed",
    ):
        assert token not in encoded
    keys: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            keys.extend(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(view)
    for secret in ("correct_response", "correct_option_id", "answer_key", "rubric"):
        assert secret not in keys


def test_each_shared_template_fixture_finishes_without_external_results() -> None:
    service = FixtureRoundService(store={})
    finished = [_play(service, area_id, correct=False) for area_id in FIXTURES]
    assert len(finished) == 23


def test_fractions_round_uses_the_same_fields() -> None:
    service = FixtureRoundService(store={})
    opened = service.open_round(
        area_id="G5-AREA-MAT-05",
        learner_id=uuid4(),
        session_id=uuid4(),
        grade=5,
        medium="si",
    )
    other = service.open_round(
        area_id="G5-AREA-ENV-01",
        learner_id=uuid4(),
        session_id=uuid4(),
        grade=5,
        medium="si",
    )
    assert opened["template_id"] == "half_set"
    assert set(opened) == set(other)


def test_fixture_http_score_comes_from_the_server(client: TestClient) -> None:
    reset_fixture_rounds()
    learner = client.post("/api/v1/learners", json={"grade": 5, "preferred_language": "si"}).json()
    headers = {
        "X-Dev-Principal": "NOT_FOR_PRODUCTION",
        "X-Dev-Role": "learner",
        "X-Learner-Id": learner["id"],
    }
    opened = client.post(
        "/api/v1/learning-flow/fixture-rounds",
        headers=headers,
        json={
            "area_id": "G5-AREA-MAT-01",
            "learner_id": learner["id"],
            "session_id": str(uuid4()),
            "grade": 5,
            "medium": "si",
        },
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()
    _assert_public(body)
    assert "correct_option_id" not in opened.text
    assert "correct_response" not in opened.text
    episode_id = body["episode_id"]
    wrong = next(option["option_id"] for option in body["options"] if option["text_si"] != "දෙක")
    scored = client.post(
        f"/api/v1/learning-flow/fixture-rounds/{episode_id}/answer",
        headers=headers,
        json={"option_id": wrong},
    )
    assert scored.status_code == 200, scored.text
    assert scored.json()["server_score"] == {
        "earned_score": "0",
        "maximum_score": "1",
        "scoring_version": "fixture-rubric-v1",
        "server_authoritative": True,
        "measurement_role": "unsupported_before",
    }
    fractions = client.post(
        "/api/v1/learning-flow/fixture-rounds",
        headers=headers,
        json={
            "area_id": "G5-AREA-MAT-05",
            "learner_id": learner["id"],
            "session_id": str(uuid4()),
            "grade": 5,
            "medium": "si",
        },
    )
    assert fractions.status_code == 200, fractions.text
    assert set(fractions.json()) == set(body)
    assert fractions.json()["template_id"] == "half_set"
