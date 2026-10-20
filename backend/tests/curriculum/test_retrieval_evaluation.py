import json
from pathlib import Path

from app.curriculum.application.retrieval import (
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
)
from app.curriculum.application.retrieval_evaluation import (
    EvaluationManifest,
    evaluate_queries,
    load_evaluation_manifest,
    load_evaluation_queries,
    load_optional_query_file,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVALUATION = REPOSITORY_ROOT / "data/curriculum/evaluation/v1"


class MapRetriever:
    def __init__(self, results: dict[str, CurriculumRetrievalResult]) -> None:
        self.results = results
        self.limits: list[int] = []

    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult:
        self.limits.append(request.limit)
        return self.results[request.learner_question]


def _source() -> CurriculumSourceRecord:
    return CurriculumSourceRecord(
        source_id="SRC-FIXTURE",
        title="Fixture source",
        publisher_authority="Fixture",
        grade=5,
        subject="Mathematics",
        language="si",
        source_type="textbook",
        source_location="repository://synthetic/retrieval-evaluation.pdf",
        source_version="fixture-v1",
        metadata_status=MetadataStatus.VERIFIED,
        ingestion_status=IngestionStatus.INGESTED,
        review_status=CurriculumReviewStatus.APPROVED,
        usage_rights_status=UsageRightsStatus.PERMITTED,
    )


def _passage(chunk_id: str, *, grade: int = 5) -> RetrievedCurriculumPassage:
    return RetrievedCurriculumPassage(
        chunk=CurriculumChunk(
            chunk_id=chunk_id,
            source_id="SRC-FIXTURE",
            source_version="fixture-v1",
            content="Fixture passage.",
            grade=grade,  # type: ignore[arg-type]
            subject="Mathematics",
            language="si",
            skill_ids=("MAT-FRC",),
            page_number=1,
            unit_id="G5-MAT-C03",
            review_status=CurriculumReviewStatus.APPROVED,
        ),
        source=_source().model_copy(update={"grade": grade}),
        score=1.0,
    )


def _found(*chunk_ids: str, grade: int = 5) -> CurriculumRetrievalResult:
    return CurriculumRetrievalResult(
        status=CurriculumRetrievalStatus.FOUND,
        passages=tuple(_passage(chunk_id, grade=grade) for chunk_id in chunk_ids),
        retriever_version="fixture",
    )


def _query(query_id: str, question: str, relevant: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        "query_id": query_id,
        "purpose": "CONTENT_AUTHORING",
        "learner_question": question,
        "grade": 5,
        "subject": "Mathematics",
        "required_language": "si",
        "unit_id": "G5-MAT-C03",
        "relevant_chunk_ids": list(relevant),
        "reviewer": "fixture-reviewer",
        "reviewed_at": "2026-10-15",
    }


def _manifest(limit: int = 2) -> EvaluationManifest:
    return EvaluationManifest(skill_id="MAT-FRC", grade=5, limit=limit, frozen=True)


def test_fixture_recall_matches_the_known_relevant_ids(tmp_path: Path) -> None:
    hit = "Which fixture chunk states the definition?"
    miss = "Which fixture chunk is absent?"
    empty = "Which fixture query should return nothing?"
    path = tmp_path / "queries.jsonl"
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n"
            for row in (
                _query("q-hit", hit, ("chunk-a", "chunk-b")),
                _query("q-miss", miss, ("chunk-c",)),
                _query("q-empty", empty, ()),
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    queries = load_evaluation_queries(path, expected_purpose="CONTENT_AUTHORING")
    retriever = MapRetriever(
        {
            hit: _found("chunk-a", "chunk-b"),
            miss: _found("chunk-z"),
            empty: CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES,
                retriever_version="fixture",
            ),
        }
    )
    report = evaluate_queries(
        queries,
        retriever,
        manifest=_manifest(2),
        retriever_version="fixture-retriever",
        chunk_manifest_sha256="abc",
        tutor_queries_present=False,
    )

    authored = report.by_purpose["CONTENT_AUTHORING"]
    assert retriever.limits == [2, 2, 2]
    assert authored.recall_at_k == 0.5
    assert authored.recall_query_count == 2
    assert authored.insufficient_evidence_correctness == 1.0
    assert report.by_purpose["TUTOR_ANSWER"].recall_at_k is None
    assert report.filter_violation_rate == 0.0
    assert report.filter_check_passed is True
    assert report.insufficient_evidence_passed is True
    assert report.query_ids == ("q-hit", "q-miss", "q-empty")


def test_wrong_grade_passage_fails_the_filter_check(tmp_path: Path) -> None:
    question = "Which fixture chunk is the wrong grade?"
    path = tmp_path / "queries.jsonl"
    path.write_text(
        json.dumps(_query("q-grade", question, ("chunk-a",))) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    queries = load_evaluation_queries(path)
    retriever = MapRetriever({question: _found("chunk-a", grade=4)})

    report = evaluate_queries(
        queries,
        retriever,
        manifest=_manifest(),
        retriever_version="fixture-retriever",
        chunk_manifest_sha256="abc",
        tutor_queries_present=False,
    )

    assert report.filter_violation_count == 1
    assert report.filter_violation_rate == 1.0
    assert report.filter_check_passed is False


def test_found_result_fails_insufficient_evidence_for_a_no_passage_query(tmp_path: Path) -> None:
    question = "This reviewer expects no passage."
    path = tmp_path / "queries.jsonl"
    path.write_text(
        json.dumps(_query("q-none", question, ())) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    queries = load_evaluation_queries(path)
    retriever = MapRetriever({question: _found("chunk-a")})

    report = evaluate_queries(
        queries,
        retriever,
        manifest=_manifest(),
        retriever_version="fixture-retriever",
        chunk_manifest_sha256="abc",
        tutor_queries_present=False,
    )

    authored = report.by_purpose["CONTENT_AUTHORING"]
    assert authored.recall_query_count == 0
    assert authored.insufficient_evidence_correctness == 0.0
    assert report.insufficient_evidence_passed is False


def test_a_query_file_without_a_reviewer_still_loads(tmp_path: Path) -> None:
    row = _query("q-unsigned", "Unsigned question", ("chunk-a",))
    del row["reviewer"]
    del row["reviewed_at"]
    path = tmp_path / "queries.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8", newline="\n")

    queries = load_evaluation_queries(path)

    assert queries[0].query_id == "q-unsigned"
    assert queries[0].reviewer is None


def test_missing_tutor_query_file_does_not_fail(tmp_path: Path) -> None:
    missing = tmp_path / "tutor-queries.jsonl"

    assert load_optional_query_file(missing, expected_purpose="TUTOR_ANSWER") is None


def test_grade5_pilot_query_lists_the_four_fraction_chunks() -> None:
    manifest = load_evaluation_manifest(EVALUATION / "manifest.json")
    queries = load_evaluation_queries(
        EVALUATION / "gamification-queries.jsonl",
        expected_purpose="CONTENT_AUTHORING",
    )
    tutor = load_optional_query_file(
        EVALUATION / "tutor-queries.jsonl",
        expected_purpose="TUTOR_ANSWER",
    )

    assert tutor is None
    assert manifest.skill_id == "MAT-FRC"
    assert manifest.frozen is True
    assert manifest.limit == 4
    assert len(queries) == 1
    assert queries[0].query_id == "MAT-FRC-PILOT"
    assert queries[0].reviewer is None
    assert len(queries[0].relevant_chunk_ids) == 4
