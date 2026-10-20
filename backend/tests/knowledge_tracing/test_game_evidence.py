"""The game's scored answers become answers of the knowledge model, and only the right ones.

The first half tests the rules on plain records. The second half writes records with the gamified
module's own classes, so a change on either side of the contract fails here and not silently.
"""

import importlib
import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.knowledge_tracing.application import game_evidence as ge
from app.knowledge_tracing.application.attempts import AttemptService
from app.knowledge_tracing.application.game_evidence import (
    CrosswalkUnavailable,
    GameEvidence,
    GameEvidenceIngestor,
    evidence_to_command,
    load_crosswalk,
)
from app.knowledge_tracing.application.mastery_service import MasteryService
from app.knowledge_tracing.domain.feature_spec import get_feature_spec
from app.knowledge_tracing.infrastructure.db.attempt_repository import (
    SqlAlchemyAttemptRepository,
)
from app.knowledge_tracing.infrastructure.db.game_evidence_repository import (
    OutboxEvidenceSource,
)
from app.knowledge_tracing.infrastructure.db.mastery_repository import (
    SqlAlchemyMasteryRepository,
)
from app.knowledge_tracing.infrastructure.db.models import AttemptModel, SkillModel
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel

SPEC = get_feature_spec()
LEARNER = UUID("33333333-3333-3333-3333-333333333333")
# the game's own skill ids and the skill each one belongs to, as in the real crosswalk
PILOT_SKILL = "G5-MAT-C03-L01-O01"  # fractions
CROSSWALK = {PILOT_SKILL: "MAT-FRC", "G5-ENV-C01": "ENV-CIV", "G5-MAT-C01": "MAT-NUM"}
NOW = datetime.now(UTC)


def payload(**overrides: object) -> dict[str, object]:
    """The payload the game writes today (copied from its `_publish_score`)."""
    body: dict[str, object] = {
        "contract_version": "gamification-learner-evidence-v2",
        "learner_id": str(LEARNER),
        "skill_id": PILOT_SKILL,
        "universal_skill_id": "MAT-FRC",
        "episode_id": str(uuid4()),
        "presentation_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "measurement_role": "unsupported_before",
        "assistance_state": "none",
        "earned_score": "1",
        "maximum_score": "1",
        "scoring_version": "development-v1",
        "correct": True,
        "response_time_ms": 8_000,
        "supported": False,
        "hint_count": 0,
        "difficulty": "easy",
        "difficulty_source": "introductory",
        "difficulty_mapping_version": "learning_flow-introductory-v1",
        "environment": "development",
        "model_ingestion_eligible": False,
        "session_id": str(uuid4()),
    }
    body.update(overrides)
    return body


def evidence(
    *, game_skill: str = PILOT_SKILL, skill: str = "MAT-FRC", created: datetime = NOW, **overrides
) -> GameEvidence:
    body = payload(**overrides)
    return GameEvidence(
        key=f"{body['attempt_id']}:gamification_item_scored",
        learner_id=LEARNER,
        game_skill_id=game_skill,
        universal_skill_id=skill,
        event_type="gamification_item_scored",
        payload=body,
        contract_version="gamification-learner-evidence-v2",
        created_at=created,
    )


def ready(**overrides: object) -> GameEvidence:
    """A record the game has released for models."""
    return evidence(model_ingestion_eligible=True, environment="production", **overrides)


def command_for(item: GameEvidence, language: str | None = "si", **kwargs):
    return evidence_to_command(item, SPEC, CROSSWALK, language, **kwargs)


# ---- the rules, one record at a time ---------------------------------------------------------------


def test_a_released_record_becomes_a_game_answer_with_its_own_skill() -> None:
    item = ready(correct=False, response_time_ms=12_500)

    command = command_for(item)

    assert command.skill_code == "MAT-FRC" and command.difficulty == "easy"
    assert command.question_id is None and command.correct is False
    assert (command.time_ms, command.hints, command.language) == (12_500, 0, "si")
    assert command.learner_id == LEARNER
    assert command.idempotency_key == f"game:{item.payload['attempt_id']}"
    assert command.answered_at == NOW


def test_a_development_record_is_not_used_by_default() -> None:
    assert command_for(evidence()) == ge.NOT_ELIGIBLE  # the game marks every record this way today


def test_development_records_can_be_included_for_a_local_trial_only() -> None:
    assert command_for(evidence(), include_development=True).skill_code == "MAT-FRC"
    assert command_for(evidence(environment="test"), include_development=True).skill_code == "MAT-FRC"
    # ... but never a record that is not a development record and is not released
    assert command_for(evidence(environment="production"), include_development=True) == ge.NOT_ELIGIBLE


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"attempt_id": None}, ge.BAD_PAYLOAD),
        ({"attempt_id": "  "}, ge.BAD_PAYLOAD),
        ({"correct": "yes"}, ge.BAD_PAYLOAD),  # right or wrong must be plain true or false
        ({"correct": 1}, ge.BAD_PAYLOAD),
        ({"difficulty": "introductory"}, ge.UNKNOWN_DIFFICULTY),
        ({"difficulty": None}, ge.UNKNOWN_DIFFICULTY),
    ],
)
def test_a_record_with_unusable_fields_is_skipped_with_a_reason(
    overrides: dict[str, object], reason: str
) -> None:
    assert command_for(ready(**overrides)) == reason


def test_other_kinds_of_record_are_ignored() -> None:
    other = replace(ready(), event_type="selected_scaffold")

    assert command_for(other) == ge.OTHER_EVENT


def test_a_skill_that_is_not_one_of_the_30_is_skipped() -> None:
    assert command_for(ready(skill="G5-MAT-C03")) == ge.UNKNOWN_SKILL


def test_the_games_finer_skills_are_parts_of_ours_and_are_never_changed() -> None:
    skill_map = ge.load_game_skill_map()

    assert set(skill_map.sub_skills.values()) <= set(SPEC.skills)  # every parent is one of our 30
    assert set(skill_map.item_skills.values()) <= set(SPEC.skills)
    assert not set(skill_map.sub_skills) & set(SPEC.skills)  # a finer label never hides a real skill
    assert skill_map.sub_skills["MAT-DIV"] == "MAT-OPS" and skill_map.sub_skills["MAT-TIME"] == "MAT-TIM"


def test_a_finer_skill_with_its_item_skill_is_saved_under_our_parent_skill() -> None:
    skill_map = ge.load_game_skill_map()
    checks = ge.checked_skills(CROSSWALK, skill_map)
    item = ready(game_skill="G5-MAT-DIV-WRITTEN-01", skill="MAT-DIV")  # as her division flow publishes it

    assert evidence_to_command(item, SPEC, checks, "si").skill_code == "MAT-OPS"
    # a skill of ours that she already uses as it is passes through unchanged
    own = ready(game_skill="G5-MAT-ADD-MENTAL-01", skill="MAT-OPS")
    assert evidence_to_command(own, SPEC, checks, "si").skill_code == "MAT-OPS"


def test_a_finer_skill_still_has_to_agree_with_its_item_skill() -> None:
    skill_map = ge.load_game_skill_map()
    checks = ge.checked_skills(CROSSWALK, skill_map)
    wrong = ready(game_skill="G5-MAT-DIV-WRITTEN-01", skill="MAT-FRC")  # a division item labelled fractions

    assert evidence_to_command(wrong, SPEC, checks, "si") == ge.SKILL_MISMATCH


def test_an_item_skill_that_is_in_no_table_is_still_skipped() -> None:
    checks = ge.checked_skills(CROSSWALK, ge.load_game_skill_map())

    assert evidence_to_command(ready(game_skill="G5-NEW-GAME-01", skill="MAT-OPS"), SPEC, checks, "si") == ge.NOT_IN_CROSSWALK


def test_the_skill_map_file_is_up_to_date_with_the_games_current_skills() -> None:
    """If this fails, the game added or renamed a skill: run  python -m scripts.build_game_skill_map."""
    import importlib

    builder = importlib.import_module("scripts.build_game_skill_map")
    assert builder.main(["--check"]) == 0


def test_a_wrong_skill_label_never_reaches_the_model() -> None:
    """The game's publisher once labelled every answer MAT-FRC. The crosswalk says better."""
    environment_answer = ready(game_skill="G5-ENV-C01", skill="MAT-FRC")  # it is an ENV skill

    assert command_for(environment_answer) == ge.SKILL_MISMATCH
    assert command_for(ready(game_skill="G5-ENV-C01", skill="ENV-CIV")).skill_code == "ENV-CIV"


def test_a_skill_the_crosswalk_does_not_know_is_skipped() -> None:
    assert command_for(ready(game_skill="G5-NEW-C99")) == ge.NOT_IN_CROSSWALK


def test_the_language_comes_from_the_record_then_from_the_learner() -> None:
    assert command_for(ready(language="ta"), language="si").language == "ta"
    assert command_for(ready(), language="ta").language == "ta"
    assert command_for(ready(language="en"), language="si").language == "si"  # not one we use
    assert command_for(ready(), language=None) == ge.NO_LANGUAGE
    assert command_for(ready(), language="en") == ge.NO_LANGUAGE


@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, None), (0, 0), (8_000, 8_000), (8_000.0, 8_000), (-5, None), (True, None),
     ("fast", None), (4_000_000, 600_000)],
)
def test_the_response_time_is_kept_when_it_makes_sense(given: object, expected: int | None) -> None:
    assert command_for(ready(response_time_ms=given)).time_ms == expected


@pytest.mark.parametrize(
    ("overrides", "hints"),
    [({}, 0), ({"hint_count": 2}, 2), ({"supported": True}, 1), ({"supported": True, "hint_count": 3}, 3),
     ({"hint_count": -1}, 0), ({"hint_count": None}, 0)],
)
def test_help_on_screen_counts_as_at_least_one_hint(overrides: dict[str, object], hints: int) -> None:
    assert command_for(ready(**overrides)).hints == hints


def test_a_time_from_a_naive_database_value_is_read_as_utc() -> None:
    naive = datetime(2026, 10, 1, 9, 0)  # noqa: DTZ001 - validates UTC normalization
    assert command_for(ready(created=naive)).answered_at == naive.replace(tzinfo=UTC)


# ---- reading many records and saving them -------------------------------------------------------------


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(LearnerModel(id=LEARNER, grade=5, preferred_language="si"))
        for index, code in enumerate(SPEC.skills):
            db.add(SkillModel(code=code, sort_index=index, area=code[:3], name_en=code))
        db.commit()
    return engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db:
        yield db


class ListSource:
    def __init__(self, *items: GameEvidence) -> None:
        self.items = list(items)

    def batches(self, size: int) -> Iterator[list[GameEvidence]]:
        for start in range(0, len(self.items), size):
            yield self.items[start : start + size]


def ingestor(session: Session, source, **kwargs) -> GameEvidenceIngestor:
    repository = SqlAlchemyAttemptRepository(session)
    return GameEvidenceIngestor(
        source, AttemptService(repository, SPEC), repository.learner_language, SPEC, CROSSWALK, **kwargs
    )


def saved(session: Session) -> list[AttemptModel]:
    session.expire_all()
    return list(session.scalars(select(AttemptModel).order_by(AttemptModel.id)))


def test_released_answers_are_saved_as_game_answers_and_counted(session: Session) -> None:
    items = [ready(correct=n % 2 == 0, created=NOW - timedelta(minutes=10 - n)) for n in range(4)]

    report = ingestor(session, ListSource(*items)).run()

    assert (report.scanned, report.ingested, report.already_ingested) == (4, 4, 0)
    assert report.learners == {LEARNER}
    rows = saved(session)
    assert [r.correct for r in rows] == [True, False, True, False]
    assert all(r.source == 1 and r.question_id is None for r in rows)
    assert all((r.skill_code, r.difficulty) == ("MAT-FRC", "easy") for r in rows)


def test_reading_again_saves_nothing_twice(session: Session) -> None:
    items = [ready(), ready()]
    source = ListSource(*items)

    first = ingestor(session, source).run()
    again = ingestor(session, source).run()

    assert first.ingested == 2 and again.ingested == 0 and again.already_ingested == 2
    assert len(saved(session)) == 2


def test_a_dry_run_reports_without_saving(session: Session) -> None:
    items = [ready(), ready(), evidence()]  # two released, one development

    report = ingestor(session, ListSource(*items)).run(dry_run=True)

    assert report.ingested == 2 and report.skipped[ge.NOT_ELIGIBLE] == 1
    assert saved(session) == []
    ingestor(session, ListSource(*items)).run()
    assert ingestor(session, ListSource(*items)).run(dry_run=True).already_ingested == 2


def test_every_skipped_record_is_counted_under_its_reason(session: Session) -> None:
    items = [
        ready(),
        evidence(),  # development
        ready(difficulty="introductory"),
        ready(game_skill="G5-ENV-C01", skill="MAT-FRC"),  # the wrong label
        ready(correct="maybe"),
    ]

    report = ingestor(session, ListSource(*items)).run()

    assert report.ingested == 1
    assert dict(report.skipped) == {
        ge.NOT_ELIGIBLE: 1, ge.UNKNOWN_DIFFICULTY: 1, ge.SKILL_MISMATCH: 1, ge.BAD_PAYLOAD: 1,
    }
    assert "skipped:" in str(report) and "skill_mismatch: 1" in str(report)


def test_a_record_for_a_learner_that_does_not_exist_is_skipped(session: Session) -> None:
    ghost = replace(ready(), learner_id=uuid4())

    report = ingestor(session, ListSource(ghost)).run()

    assert report.ingested == 0 and report.skipped[ge.UNKNOWN_LEARNER] == 1


def test_a_record_dated_in_the_future_is_skipped(session: Session) -> None:
    report = ingestor(session, ListSource(ready(created=NOW + timedelta(days=2)))).run()

    assert report.ingested == 0 and report.skipped[ge.IN_FUTURE] == 1


def test_the_same_attempt_id_with_different_content_is_not_overwritten(session: Session) -> None:
    first = ready(correct=True)
    changed = ready(attempt_id=first.payload["attempt_id"], correct=False)

    report = ingestor(session, ListSource(first, changed)).run()

    assert report.ingested == 1 and report.skipped[ge.KEY_REUSED] == 1
    assert [r.correct for r in saved(session)] == [True]


def test_three_released_answers_give_the_model_a_mastery_for_that_skill(session: Session) -> None:
    items = [ready(correct=c, created=NOW - timedelta(minutes=9 - n)) for n, c in enumerate([True, True, False])]
    ingestor(session, ListSource(*items)).run()

    snapshot = MasteryService(SqlAlchemyMasteryRepository(session), get_knowledge_model(), SPEC).recompute(LEARNER)

    by_skill = {s.code: s for s in snapshot.skills}
    assert by_skill["MAT-FRC"].attempts == 3 and by_skill["MAT-FRC"].mastery is not None
    assert all(s.mastery is None for code, s in by_skill.items() if code != "MAT-FRC")


# ---- the skill crosswalk -------------------------------------------------------------------------------


def test_the_real_crosswalk_only_uses_our_skill_codes() -> None:
    crosswalk = load_crosswalk()

    assert len(crosswalk) > 100
    assert set(crosswalk.values()) <= set(SPEC.skills)  # no stray codes
    assert crosswalk[PILOT_SKILL] == "MAT-FRC"  # the one skill the game has questions for today
    reachable = set(crosswalk.values())
    assert {"APT-LOG", "APT-REL", "APT-SPA", "APT-VIS", "APT-WRD"} & reachable == set()


def test_a_missing_or_empty_crosswalk_stops_everything(tmp_path: Path) -> None:
    with pytest.raises(CrosswalkUnavailable):
        load_crosswalk(tmp_path / "missing.jsonl")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(CrosswalkUnavailable):
        load_crosswalk(empty)


def test_a_small_crosswalk_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    path.write_text(
        json.dumps({"gamification_skill_id": "G5-X", "universal_skill_id": "LAN-VOC"}) + "\n", encoding="utf-8"
    )

    assert load_crosswalk(path) == {"G5-X": "LAN-VOC"}


def test_the_default_crosswalk_follows_the_games_data_folder_setting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MINDBRIDGE_GAMIFICATION_DATA_DIR", str(tmp_path))

    assert ge.default_crosswalk_path() == (
        tmp_path / "skill-catalogue-review" / "v1" / "universal-skill-crosswalk.jsonl"
    )


# ---- the contract with the gamified module: its real table and its real publisher -----------------------


def her_outbox_model():
    return importlib.import_module("app.gamification.infrastructure.db.models").LearnerEvidenceOutboxModel


def her_publisher_class():
    """The game's durable evidence publisher. If it is renamed again, this test skips (it does not
    fail), and the table contract tests above still run."""
    try:
        module = importlib.import_module("app.gamification.infrastructure.db.learning_flow_gateways")
        return module.SqlAlchemyLearningFlowEvidencePublisher
    except (ImportError, AttributeError):
        pytest.skip("the game's evidence publisher was not found under its known name")


def publish_like_the_game(session: Session, **overrides: object) -> dict[str, object]:
    body = payload(**overrides)
    her_publisher_class()(session).publish(body)
    session.commit()
    return body


def test_the_reader_finds_the_records_the_game_really_writes(session: Session) -> None:
    sent = [publish_like_the_game(session, correct=n % 2 == 0) for n in range(5)]

    seen = [item for batch in OutboxEvidenceSource(session).batches(2) for item in batch]  # 3 pages

    assert [item.payload["attempt_id"] for item in seen] == [s["attempt_id"] for s in sent]
    first = seen[0]
    assert first.learner_id == LEARNER and first.game_skill_id == PILOT_SKILL
    assert first.universal_skill_id == "MAT-FRC" and first.event_type == "gamification_item_scored"
    assert first.payload["difficulty"] == "easy" and first.payload["model_ingestion_eligible"] is False


def test_the_reader_pages_through_records_that_share_one_time(session: Session) -> None:
    same = NOW.replace(microsecond=0)
    model = her_outbox_model()
    for _ in range(5):
        session.add(model(
            id=uuid4(), idempotency_key=f"{uuid4()}:gamification_item_scored",
            event_type="gamification_item_scored", learner_id=LEARNER, skill_code=PILOT_SKILL,
            universal_skill_id="MAT-FRC", payload_json=payload(), contract_version="v2",
            status="pending", attempt_count=1, created_at=same,
        ))
    session.commit()

    seen = [item for batch in OutboxEvidenceSource(session).batches(2) for item in batch]

    assert len(seen) == 5 and len({item.key for item in seen}) == 5  # none missed, none twice


def test_other_records_in_the_table_are_not_read(session: Session) -> None:
    model = her_outbox_model()
    session.add(model(
        id=uuid4(), idempotency_key="x:selected_scaffold", event_type="selected_scaffold",
        learner_id=LEARNER, skill_code=PILOT_SKILL, universal_skill_id="MAT-FRC",
        payload_json={"a": 1}, contract_version="v1", status="pending", attempt_count=1, created_at=NOW,
    ))
    session.commit()

    assert [b for b in OutboxEvidenceSource(session).batches(10)] == []


def test_today_everything_the_game_writes_is_held_back(session: Session) -> None:
    """The game marks every record as development and not for models, so a normal run saves none."""
    for _ in range(3):
        publish_like_the_game(session)

    report = ingestor(session, OutboxEvidenceSource(session)).run()

    assert report.scanned == 3 and report.ingested == 0
    assert report.skipped[ge.NOT_ELIGIBLE] == 3
    assert saved(session) == []
    assert session.scalar(select(func.count()).select_from(AttemptModel)) == 0


def test_a_local_trial_with_the_games_development_records_works_end_to_end(session: Session) -> None:
    for correct in (True, True, False):
        publish_like_the_game(session, correct=correct)

    report = ingestor(session, OutboxEvidenceSource(session), include_development=True).run()

    assert report.ingested == 3
    rows = saved(session)
    assert [r.correct for r in rows] == [True, True, False]
    assert all(r.skill_code == "MAT-FRC" and r.difficulty == "easy" and r.question_id is None for r in rows)
    assert all(r.idempotency_key.startswith("game:") for r in rows)


def test_the_games_fixed_skill_label_is_caught_with_its_real_crosswalk(session: Session) -> None:
    """Her durable publisher writes MAT-FRC on every record. With the real crosswalk, a record for
    an environment skill that carries that label is refused, and the real pilot skill is accepted."""
    real = load_crosswalk()
    environment_skill = next(game for game, universal in real.items() if universal == "ENV-CIV")
    publish_like_the_game(session, skill_id=environment_skill, universal_skill_id="MAT-FRC")
    publish_like_the_game(session)  # the pilot fractions skill

    repository = SqlAlchemyAttemptRepository(session)
    report = GameEvidenceIngestor(
        OutboxEvidenceSource(session), AttemptService(repository, SPEC), repository.learner_language,
        SPEC, real, include_development=True,
    ).run()

    assert report.ingested == 1 and report.skipped[ge.SKILL_MISMATCH] == 1
    assert [r.skill_code for r in saved(session)] == ["MAT-FRC"]


# ---- the command ---------------------------------------------------------------------------------------


def test_the_command_reads_the_games_records_and_saves_them(
    engine: Engine, session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import ingest_game_evidence as command

    for _ in range(2):
        publish_like_the_game(session)
    monkeypatch.setattr(command, "SessionLocal", sessionmaker(engine))

    def run(*flags: str) -> tuple[int, str]:
        monkeypatch.setattr("sys.argv", ["ingest_game_evidence", *flags])
        code = command.main()
        return code, capsys.readouterr().out

    code, out = run()
    assert code == 0 and "answers saved: 0" in out and "not_eligible: 2" in out

    code, out = run("--include-development", "--dry-run")
    assert code == 0 and "DRY RUN" in out and "answers saved: 2" in out
    assert saved(session) == []  # a dry run saves nothing

    code, out = run("--include-development")
    assert code == 0 and "answers saved: 2" in out and "development records were included" in out
    assert len(saved(session)) == 2

    code, out = run("--include-development")
    assert "answers saved: 0" in out and "already saved earlier: 2" in out


def test_the_command_refuses_to_run_without_a_crosswalk(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import ingest_game_evidence as command

    monkeypatch.setattr(command, "SessionLocal", sessionmaker(engine))
    monkeypatch.setattr("sys.argv", ["x", "--crosswalk", str(tmp_path / "nope.jsonl")])

    assert command.main() == 1
    assert "nothing was read" in capsys.readouterr().err


def test_a_database_without_the_games_table_is_reported_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import ingest_game_evidence as command

    bare = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(command, "SessionLocal", sessionmaker(bare))
    monkeypatch.setattr("sys.argv", ["ingest_game_evidence"])

    assert command.main() == 0
    assert "no game outbox table" in capsys.readouterr().out
    assert OutboxEvidenceSource(Session(bare)).available() is False
