import json
from pathlib import Path

import pytest

from app.curriculum.application.chunking import (
    CHUNKING_VERSION,
    ChunkSource,
    ExtractedPage,
    TraceNode,
    apply_universal_skill_links,
    build_manifest,
    chunk_curriculum,
    read_curriculum_jsonl,
    render_jsonl,
    sha256_text,
)
from app.curriculum.application.retrieval import CurriculumReviewStatus

TRACE = (
    Path(__file__).resolve().parents[3]
    / "data/curriculum/grade5-curriculum-trace/v1/curriculum_nodes.jsonl"
)


def _source() -> ChunkSource:
    return ChunkSource(
        source_id="SRC-FIX",
        source_version="2019",
        subject="Mathematics",
        language="si",
        grade=5,
        document_sha256="abc",
    )


def _hierarchy() -> tuple[TraceNode, TraceNode, TraceNode]:
    unit = TraceNode(
        curriculum_node_id="G5-MAT-C03",
        node_type="competency",
        parent_node_id="",
        text_primary="Fractions",
        source_id="SRC-FIX",
    )
    lesson = TraceNode(
        curriculum_node_id="G5-MAT-C03-L01",
        node_type="lesson",
        parent_node_id="G5-MAT-C03",
        text_primary="Unit fractions",
        source_id="SRC-FIX",
        source_page_from=4,
        source_page_to=4,
    )
    outcome = TraceNode(
        curriculum_node_id="G5-MAT-C03-L01-O01",
        node_type="learning_outcome",
        parent_node_id="G5-MAT-C03-L01",
        text_primary="Identifies a unit fraction.",
        source_id="SRC-FIX",
        source_page_from=4,
        source_page_to=4,
        skill_ids=("MAT-FRC",),
    )
    return unit, lesson, outcome


def test_two_paragraphs_on_one_page_keep_the_outcome_universal_id() -> None:
    unit, lesson, outcome = _hierarchy()
    page = ExtractedPage(
        source_id="SRC-FIX",
        page_number=4,
        text="First paragraph about halves.\n\nSecond paragraph about quarters.",
        conversion_status="preserved_needs_review",
        source_sha256="abc",
    )
    result = chunk_curriculum((unit, lesson, outcome), (_source(),), (page,))
    page_chunks = [row for row in result.chunks if row.transcription_method == "extracted_page"]
    assert [row.content for row in page_chunks] == [
        "First paragraph about halves.",
        "Second paragraph about quarters.",
    ]
    assert {row.page_number for row in page_chunks} == {4}
    assert {row.skill_ids for row in page_chunks} == {("MAT-FRC",)}
    assert {row.unit_id for row in page_chunks} == {"G5-MAT-C03"}
    assert {row.learning_outcome_id for row in page_chunks} == {"G5-MAT-C03-L01-O01"}
    assert {row.review_status for row in result.chunks} == {CurriculumReviewStatus.REVIEW_PENDING}
    assert {row.chunking_version for row in result.chunks} == {CHUNKING_VERSION}
    statement = next(row for row in result.chunks if row.transcription_method == "visual_read")
    assert statement.skill_ids == ("MAT-FRC",)
    assert statement.contract_chunk().skill_ids == ("MAT-FRC",)


def test_unresolved_parent_is_quarantined_and_absent_from_chunks() -> None:
    outcome = TraceNode(
        curriculum_node_id="G5-MAT-C03-L00-O01",
        node_type="learning_outcome",
        parent_node_id="G5-MAT-C03-L00",
        text_primary="A statement with no parent.",
        source_id="SRC-FIX",
        source_page_from=4,
        source_page_to=4,
        skill_ids=("MAT-FRC",),
    )
    result = chunk_curriculum((outcome,), (_source(),), ())
    assert result.chunks == ()
    assert result.quarantine[0].reason == "unresolved_parent"
    assert result.quarantine[0].curriculum_node_id == "G5-MAT-C03-L00-O01"
    rendered = render_jsonl(result.chunks)
    assert "G5-MAT-C03-L00-O01" not in rendered


def test_conversion_unavailable_page_produces_no_chunk() -> None:
    unit, lesson, outcome = _hierarchy()
    page = ExtractedPage(
        source_id="SRC-FIX",
        page_number=4,
        text=None,
        conversion_status="conversion_unavailable",
        source_sha256="abc",
    )
    result = chunk_curriculum((unit, lesson, outcome), (_source(),), (page,))
    assert all(row.transcription_method != "extracted_page" for row in result.chunks)
    assert any(row.reason == "conversion_unavailable" for row in result.quarantine)
    assert all(
        row.page_number != 4 or row.transcription_method != "extracted_page"
        for row in result.chunks
    )


def test_outcome_without_universal_id_is_not_written() -> None:
    unit, lesson, outcome = _hierarchy()
    outcome = outcome.model_copy(update={"skill_ids": ()})
    result = chunk_curriculum((unit, lesson, outcome), (_source(),), ())
    assert result.chunks == ()
    assert result.quarantine[0].reason == "missing_universal_skill_id"


def test_page_covered_by_an_outcome_without_a_universal_id_is_not_chunked() -> None:
    unit, lesson, outcome = _hierarchy()
    outcome = outcome.model_copy(update={"skill_ids": ()})
    page = ExtractedPage(
        source_id="SRC-FIX",
        page_number=4,
        text="First paragraph.\n\nSecond paragraph.",
        conversion_status="preserved_needs_review",
        source_sha256="abc",
    )
    result = chunk_curriculum((unit, lesson, outcome), (_source(),), (page,))
    assert result.chunks == ()
    reasons = {row.reason for row in result.quarantine}
    assert "missing_universal_skill_id" in reasons
    assert "no_covering_outcome" not in reasons


def test_gamification_item_file_is_not_read() -> None:
    missing = Path("data/gamification/grade5-pilot-slice/v1/items.jsonl")
    with pytest.raises(ValueError, match="data/curriculum"):
        read_curriculum_jsonl(missing)


def test_rerunning_the_chunker_reproduces_manifest_hashes() -> None:
    unit, lesson, outcome = _hierarchy()
    page = ExtractedPage(
        source_id="SRC-FIX",
        page_number=4,
        text="First paragraph.\n\nSecond paragraph.",
        conversion_status="preserved_needs_review",
        source_sha256="abc",
    )
    first = chunk_curriculum((unit, lesson, outcome), (_source(),), (page,))
    second = chunk_curriculum((unit, lesson, outcome), (_source(),), (page,))
    first_chunks = render_jsonl(first.chunks)
    second_chunks = render_jsonl(second.chunks)
    first_quarantine = render_jsonl(first.quarantine)
    second_quarantine = render_jsonl(second.quarantine)
    assert first_chunks == second_chunks
    assert sha256_text(first_chunks) == sha256_text(second_chunks)
    manifest_a = build_manifest(
        chunks_text=first_chunks,
        quarantine_text=first_quarantine,
        written_count=len(first.chunks),
        quarantined_count=len(first.quarantine),
        reason_counts={},
        source_document_sha256={"SRC-FIX": "abc"},
    )
    manifest_b = build_manifest(
        chunks_text=second_chunks,
        quarantine_text=second_quarantine,
        written_count=len(second.chunks),
        quarantined_count=len(second.quarantine),
        reason_counts={},
        source_document_sha256={"SRC-FIX": "abc"},
    )
    assert manifest_a["files"] == manifest_b["files"]
    assert manifest_a["ingestion_status"] == "NOT_INGESTED"


def test_recorded_universal_id_is_copied_onto_an_outcome_without_one() -> None:
    unit, lesson, outcome = _hierarchy()
    outcome = outcome.model_copy(update={"skill_ids": ()})
    linked = apply_universal_skill_links(
        (unit, lesson, outcome),
        {outcome.curriculum_node_id: "MAT-FRC"},
    )

    result = chunk_curriculum(linked, (_source(),), ())

    assert result.chunks[0].skill_ids == ("MAT-FRC",)
    assert result.chunks[0].review_status == CurriculumReviewStatus.REVIEW_PENDING


def test_a_skill_link_does_not_rescue_an_unresolved_parent() -> None:
    outcome = TraceNode(
        curriculum_node_id="G5-MAT-C03-L00-O01",
        node_type="learning_outcome",
        parent_node_id="G5-MAT-C03-L00",
        text_primary="A statement with no parent.",
        source_id="SRC-FIX",
        source_page_from=4,
        source_page_to=4,
    )
    linked = apply_universal_skill_links((outcome,), {outcome.curriculum_node_id: "MAT-FRC"})

    result = chunk_curriculum(linked, (_source(),), ())

    assert result.chunks == ()
    assert result.quarantine[0].reason == "unresolved_parent"


def test_grade5_trace_quarantines_unresolved_parents() -> None:
    from app.curriculum.application.chunking import load_trace_nodes

    nodes = load_trace_nodes(TRACE)
    result = chunk_curriculum(nodes, (), ())
    unresolved = [row for row in result.quarantine if row.reason == "unresolved_parent"]
    assert len(unresolved) == 133
    unresolved_ids = {row.curriculum_node_id for row in unresolved}
    written_ids = {row.learning_outcome_id for row in result.chunks}
    assert unresolved_ids.isdisjoint(written_ids)
    assert all(row.review_status == CurriculumReviewStatus.REVIEW_PENDING for row in result.chunks)
    rendered = render_jsonl(result.chunks)
    payload = [json.loads(line) for line in rendered.splitlines() if line.strip()]
    assert all(row["review_status"] == "REVIEW_PENDING" for row in payload)
