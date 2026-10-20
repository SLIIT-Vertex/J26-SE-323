"""The shared index stores the fractions pilot but cannot approve it for use."""

from pathlib import Path

from app.curriculum.application.retrieval import CurriculumRetrievalStatus
from app.curriculum.infrastructure.skill_index import open_skill_retriever
from app.gamification.infrastructure.curriculum_adapter import SharedCurriculumAdapter

ROOT = Path(__file__).resolve().parents[3]
CHUNKS = ROOT / "data/curriculum/chunks/v1/chunks.jsonl"
REGISTRY = ROOT / "data/curriculum/registry/v1/sources.jsonl"
FINE = "G5-MAT-C03-L01-O01"
PARENT = "MAT-FRC"


def test_adapter_blocks_the_unapproved_fraction_passages(tmp_path: Path) -> None:
    database = f"sqlite:///{tmp_path / 'fractions.sqlite'}"
    engine, session, retriever, loaded = open_skill_retriever(database, CHUNKS, REGISTRY, PARENT)
    try:
        adapter = SharedCurriculumAdapter(retriever, {FINE: PARENT})
        result = adapter.retrieve(
            learner_question="Grade 5 fractions",
            skill_id=FINE,
            grade=5,
            requested_language="si",
            limit=4,
        )
    finally:
        session.close()
        engine.dispose()

    assert loaded == 4
    assert adapter.requested_skill_ids == [PARENT]
    assert result.status is CurriculumRetrievalStatus.NO_APPROVED_SOURCE
    assert result.passages == ()
