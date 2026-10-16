"""The whole journey of one child, from the first paper to the next week's paper.

    new child -> first (diagnostic) paper -> game answers -> the parent photographs the paper ->
    marking and a parent's decision -> mastery -> result report -> the next week's paper, which
    is built from what was learned.

Everything runs through the real endpoints and services. Only two things are scripted: the vision
reader (a mock that returns what the "child" wrote) and the clock for the second week.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.paper_generation import PaperRequest
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.models import QuestionModel
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading
from tests.knowledge_tracing import test_submissions as ts
from tests.knowledge_tracing import test_weekly_paper as weekly

world = ts.world
env = ts.env
SPEC = get_feature_spec()
FORBIDDEN = ("correct_option", "accepted_answers", "answer_key", "alternatives", "answer_list")


def game_questions(env: ts.Env) -> dict[str, list[str]]:
    """Question ids by skill, from the question bank."""
    with Session(env.engine) as session:
        rows = session.execute(
            select(QuestionModel.skill_code, QuestionModel.id).order_by(QuestionModel.id)
        ).all()
    by_skill: dict[str, list[str]] = {}
    for skill, question_id in rows:
        by_skill.setdefault(skill, []).append(question_id)
    return by_skill


def play(
    env: ts.Env, learner: str, skill_index: int, outcomes: list[bool], by_skill: dict
) -> list[str]:
    """The child answers questions of one skill in the game; each answer is logged."""
    ids = by_skill[SPEC.skills[skill_index]][: len(outcomes)]
    start = datetime.now(UTC) - timedelta(hours=8) + timedelta(minutes=skill_index * 10)
    for n, (question_id, correct) in enumerate(zip(ids, outcomes, strict=True)):
        response = env.client.post(
            "/api/v1/attempts",
            json={
                "learner_id": learner,
                "question_id": question_id,
                "language": "si",
                "correct": correct,
                "time_ms": 11000 + 500 * n,
                "hints": 0 if correct else 1,
                "answered_at": (start + timedelta(minutes=n)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
    return ids


def mastery(env: ts.Env, learner: str) -> dict:
    response = env.client.get(f"/api/v1/learners/{learner}/mastery")
    assert response.status_code == 200, response.text
    return response.json()


def test_one_childs_whole_journey(env: ts.Env, monkeypatch) -> None:
    # mastery is normally cached for 30 s; this test reads it right after every change
    from app.knowledge_tracing.application import mastery_service

    monkeypatch.setattr(mastery_service, "RECOMPUTE_INTERVAL", timedelta(0))
    monkeypatch.setattr(mastery_service, "FORCED_INTERVAL", timedelta(0))
    transcript: list[str] = []  # every client-facing body, to check no key leaks

    # --- 1. a new child gets a diagnostic paper ------------------------------------------------
    ts.start(env, questions=15)
    learner = env.learner_id
    week1 = env.paper
    assert week1 is not None
    transcript.append(str(week1))
    assert week1["mode"] == "diagnostic"
    assert week1["question_count"] >= 5
    assert all(item["role"] == "diagnostic" for item in week1["items"])
    start_mastery = mastery(env, learner)
    assert start_mastery["n_attempts"] == 0
    assert all(s["mastery"] is None for s in start_mastery["skills"])

    # --- 2. the child plays the game -----------------------------------------------------------
    by_skill = game_questions(env)
    answered_in_game: set[str] = set()
    for index in range(6):  # six skills the child finds hard
        answered_in_game |= set(play(env, learner, index, [False, False, True, False], by_skill))
    for index in range(6, 12):  # six skills that go well in the game
        answered_in_game |= set(play(env, learner, index, [True] * 4, by_skill))
    for index in range(12, 24):  # twelve more, mixed
        answered_in_game |= set(play(env, learner, index, [True, False, True, True], by_skill))

    after_game = mastery(env, learner)
    known = [s for s in after_game["skills"] if s["mastery"] is not None]
    assert after_game["n_attempts"] == 24 * 4
    assert len(known) >= 20  # a skill becomes known after three answers
    assert all(0.0 <= s["mastery"] <= 1.0 for s in known)
    transcript.append(str(after_game))

    # --- 3. the parent photographs the paper; marking and one decision -------------------------
    pages = week1["page_count"]
    unsure_first_question = True
    for page in range(1, pages + 1):
        on_page = ts.keys_on_page(env, page)
        readings = ts.answers_for(
            env, page, lambda position: {0: "right", 1: "wrong", 2: "blank"}[position % 3]
        )
        if page == 1 and unsure_first_question:
            readings[0] = reading(*[("1", 0.2)] * len(on_page[0][2]))  # the reader was unsure
        env.provider_ref[0] = MockProvider(*readings)
        response = ts.upload(env, page)
        assert response.status_code == 202, response.text
        body = ts.submission(env, response.json()["submission_id"])
        transcript.append(str(body))
        assert body["status"] in ("graded", "needs_review")
        if body["status"] == "needs_review":
            decisions = [
                {"paper_item_id": r["paper_item_id"], "part_no": r["part_no"], "selected": "1"}
                for r in body["review_items"]
            ]
            confirmed = env.client.post(
                f"/api/v1/submissions/{body['submission_id']}/confirm",
                json={"decisions": decisions},
            )
            assert confirmed.status_code == 200, confirmed.text
            transcript.append(str(confirmed.json()))
            assert confirmed.json()["status"] == "confirmed"

    # --- 4. the paper answers are in the learning record, marked as paper ----------------------
    records = ts.attempts(env)
    paper_attempts = [a for a in records if a.source == 0]
    game_attempts = [a for a in records if a.source == 1]
    assert len(game_attempts) == 24 * 4
    assert paper_attempts, "marked paper answers should have become attempts"
    assert all(a.paper_item_id is not None for a in paper_attempts)
    assert all(a.paper_item_id is None for a in game_attempts)
    assert len({a.paper_item_id for a in paper_attempts}) == len(paper_attempts)  # one per question

    # --- 5. mastery now uses both kinds of evidence --------------------------------------------
    after_paper = mastery(env, learner)
    assert after_paper["n_attempts"] == len(records)
    changed = [
        a["code"]
        for a, b in zip(after_game["skills"], after_paper["skills"], strict=True)
        if a["mastery"] != b["mastery"]
    ]
    assert changed, "paper answers should move at least one skill's mastery"

    # --- 6. the result report ---------------------------------------------------------------------
    report = env.client.get(f"/api/v1/papers/{week1['paper_id']}/report").json()
    assert report["summary"]["marked"] > 0
    assert report["complete"] is True
    assert report["summary"]["waiting_for_parent"] == 0
    for mistake in report["mistakes"]:
        assert mistake["result"] in ("wrong", "blank")
    assert {a["position"] for a in report["answer_list"]} == {
        m["position"] for m in report["mistakes"]
    }

    # --- 7. the next week's paper is built from what was learned ---------------------------------
    next_week = datetime.now(UTC) + timedelta(days=7)
    service = weekly.service(env.world, next_week)
    second = service.generate_weekly(UUID(learner), PaperRequest(seed=11))

    assert second.created
    assert second.paper.mode == "practice"  # there is enough history now
    assert second.paper.week_start.isoformat() > week1["week_start"]  # a later week
    first_week_questions = {item["question_id"] for item in week1["items"]}
    second_questions = {i.question_id for i in second.items}
    assert not second_questions & first_week_questions  # nothing repeated from the last paper
    assert not second_questions & answered_in_game  # nor anything answered in the game this month

    roles = {i.role for i in second.items}
    assert "weak" in roles
    weak_skills = set(second.paper.params["weak_skills"])
    verify_skills = set(second.paper.params["verify_skills"])
    assert weak_skills, "the child has weak skills, so the paper must target them"
    assert verify_skills, "skills that go well in the game must be checked on paper"
    # the skills that went well in the game, and have no paper answers, are the ones to verify
    strong_in_game = {SPEC.skills[i] for i in range(6, 12)}
    assert verify_skills & strong_in_game
    on_paper = {i.skill_code for i in second.items}
    assert on_paper & weak_skills
    # The test bank has only 6 questions per skill and the child has used most of them, so the
    # 70/30 split cannot be reached here (that is checked on a full bank in test_paper_selection);
    # what must hold is that the strong slots went to verification and weak skills are covered.
    verify_items = [i for i in second.items if i.role == "verify"]
    assert verify_items and all(i.skill_code in verify_skills for i in verify_items)
    assert all(i.skill_code in strong_in_game | verify_skills for i in verify_items)
    assert {i.skill_code for i in second.items if i.role == "weak"} <= weak_skills

    # --- 8. across the whole journey, no client body carried the answer key ----------------------
    text = "\n".join(transcript).lower()
    for forbidden in FORBIDDEN:
        assert forbidden not in text, forbidden
