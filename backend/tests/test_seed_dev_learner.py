"""The shared development learner: one id for the game and the practice screens."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.shared.database.base import Base
from app.shared.learner.model import LearnerModel
from scripts import seed_dev_learner as command

REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(engine)
    monkeypatch.setattr(command, "SessionLocal", maker)
    yield maker


def run(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
    monkeypatch.setattr("sys.argv", ["seed_dev_learner", *arguments])
    return command.main()


def test_it_creates_the_shared_learner(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(monkeypatch) == 0

    with database() as session:
        [learner] = session.scalars(select(LearnerModel)).all()
    assert str(learner.id) == command.DEFAULT_LEARNER_ID
    assert (learner.grade, learner.preferred_language) == (5, "si")  # the game's only content
    assert "created" in capsys.readouterr().out


def test_running_it_again_changes_nothing(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run(monkeypatch)
    capsys.readouterr()

    assert run(monkeypatch, "--grade", "4", "--language", "ta") == 0

    with database() as session:
        assert session.scalar(select(func.count()).select_from(LearnerModel)) == 1
        learner = session.scalars(select(LearnerModel)).one()
    assert (learner.grade, learner.preferred_language) == (5, "si")  # the existing one is not edited
    assert "already exists, nothing changed" in capsys.readouterr().out


def test_an_earlier_joining_date_can_be_recorded(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    run(monkeypatch, "--joined-days-ago", "14")

    with database() as session:
        joined = session.scalars(select(LearnerModel)).one().created_at
    joined = joined if joined.tzinfo else joined.replace(tzinfo=UTC)
    assert abs((datetime.now(UTC) - joined) - timedelta(days=14)) < timedelta(minutes=1)


def test_bad_input_is_refused_and_nothing_is_created(
    database: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(monkeypatch, "--id", "not-a-uuid") == 2
    assert run(monkeypatch, "--joined-days-ago", "-3") == 2

    with database() as session:
        assert session.scalar(select(func.count()).select_from(LearnerModel)) == 0


def test_the_default_id_is_the_one_both_frontends_use() -> None:
    """The papers screens and the game must point at the same learner, or their answers never meet."""
    papers = (REPOSITORY / "frontend/src/features/papers/hooks.ts").read_text(encoding="utf-8")
    game = (REPOSITORY / "frontend/src/features/mobile-learning-flow/MobileLearningApp.tsx").read_text(
        encoding="utf-8"
    )

    in_papers = re.search(r'DEFAULT_SHARED_LEARNER_ID\s*=\s*"([0-9a-f-]{36})"', papers)
    assert in_papers
    assert in_papers.group(1) == command.DEFAULT_LEARNER_ID
    assert re.search(r'import\s*\{\s*SHARED_LEARNER_ID\s*\}\s*from\s*"\.\./papers/hooks"', game)
    assert re.search(r'learnerId\s*=\s*SHARED_LEARNER_ID\b', game)
