"""Score a reviewer-signed curriculum query set.

Recall and insufficient-evidence correctness are reported from that set. They are not
educational-effectiveness claims. `k` is the manifest limit. This module does not choose it
and does not invent relevance labels.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.curriculum.application.retrieval import (
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumRetriever,
    CurriculumReviewStatus,
    IngestionStatus,
    NonBlankText,
    RetrievalPurpose,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
    validate_retrieval_result_for_request,
)

NO_PASSAGE_STATUSES = {
    CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES,
    CurriculumRetrievalStatus.NO_APPROVED_SOURCE,
}
PURPOSES: tuple[RetrievalPurpose, ...] = ("CONTENT_AUTHORING", "TUTOR_ANSWER")


class EvaluationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: NonBlankText
    purpose: RetrievalPurpose
    learner_question: NonBlankText
    grade: Literal[5]
    subject: NonBlankText | None = None
    required_language: NonBlankText | None = None
    unit_id: NonBlankText | None = None
    relevant_chunk_ids: tuple[NonBlankText, ...] = ()
    reviewer: NonBlankText | None = None
    reviewed_at: NonBlankText | None = None

    def expects_no_passage(self) -> bool:
        return not self.relevant_chunk_ids


class EvaluationManifest(BaseModel):
    """`limit` is k. For the fractions pilot it is the number of MAT-FRC chunks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: NonBlankText
    grade: Literal[5]
    limit: int | None = Field(default=None, strict=True)
    frozen: bool = False


class PurposeScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_count: int
    recall_query_count: int
    recalled_count: int
    recall_at_k: float | None
    no_passage_query_count: int
    insufficient_evidence_correct_count: int
    insufficient_evidence_correctness: float | None


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: str
    k: int | None
    frozen: bool
    reviewed: bool
    chunk_manifest_sha256: str
    retriever_version: str | None
    retriever_invoked: bool
    tutor_queries_present: bool
    query_ids: tuple[str, ...]
    returned_chunk_ids: tuple[str, ...]
    returned_passage_count: int
    filter_violation_count: int
    filter_violation_rate: float | None
    filter_check_passed: bool | None
    insufficient_evidence_passed: bool | None
    by_purpose: dict[str, PurposeScore]
    notes: str


def load_evaluation_manifest(path: Path) -> EvaluationManifest:
    return EvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_evaluation_queries(
    path: Path,
    *,
    expected_purpose: RetrievalPurpose | None = None,
) -> tuple[EvaluationQuery, ...]:
    queries: list[EvaluationQuery] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError(f"{path}:{line_number} is not a query object")
        if expected_purpose is not None and payload.get("purpose") != expected_purpose:
            raise ValueError("query purpose does not match the query file")
        try:
            queries.append(EvaluationQuery.model_validate(payload))
        except ValidationError as error:
            raise ValueError(f"{path}:{line_number} is not a valid query") from error
    return tuple(queries)


def load_optional_query_file(
    path: Path,
    *,
    expected_purpose: RetrievalPurpose,
) -> tuple[EvaluationQuery, ...] | None:
    if not path.is_file():
        return None
    return load_evaluation_queries(path, expected_purpose=expected_purpose)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def passage_is_filter_violation(
    request: CurriculumRetrievalRequest,
    passage: RetrievedCurriculumPassage,
) -> bool:
    """A passage violates the check when trust fails or it misses the request filters."""

    source = passage.source
    chunk = passage.chunk
    trusted = (
        source.review_status is not CurriculumReviewStatus.REJECTED
        and chunk.review_status is not CurriculumReviewStatus.REJECTED
        and source.usage_rights_status is not UsageRightsStatus.RESTRICTED
        and source.ingestion_status is not IngestionStatus.FAILED
        and chunk.source_id == source.source_id
        and source.source_version == chunk.source_version
    )
    if not trusted:
        return True
    try:
        validate_retrieval_result_for_request(
            request,
            CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.FOUND,
                passages=(passage,),
                retriever_version="evaluation-probe",
            ),
        )
    except ValueError:
        return True
    return False


def evaluate_queries(
    queries: Sequence[EvaluationQuery],
    retriever: CurriculumRetriever,
    *,
    manifest: EvaluationManifest,
    retriever_version: str,
    chunk_manifest_sha256: str,
    tutor_queries_present: bool,
) -> EvaluationReport:
    if not manifest.frozen or manifest.limit is None:
        raise ValueError("evaluation manifest has no frozen limit; k is not chosen in code")
    if manifest.limit < 1 or manifest.limit > 10:
        raise ValueError("frozen limit is outside the retriever contract of 1 to 10")
    k = manifest.limit
    counts: dict[str, dict[str, int]] = {purpose: _zero_counts() for purpose in PURPOSES}
    violations = 0
    returned = 0
    returned_ids: list[str] = []
    no_passage_failures = 0
    for query in queries:
        request = _request(query, manifest.skill_id, k)
        result = retriever.retrieve(request)
        bucket = counts[query.purpose]
        bucket["query_count"] += 1
        for passage in result.passages:
            returned += 1
            returned_ids.append(passage.chunk.chunk_id)
            if passage_is_filter_violation(request, passage):
                violations += 1
        if query.expects_no_passage():
            bucket["no_passage_query_count"] += 1
            if _no_passage_correct(result):
                bucket["insufficient_evidence_correct_count"] += 1
            else:
                no_passage_failures += 1
            continue
        bucket["recall_query_count"] += 1
        visible = [passage.chunk.chunk_id for passage in result.passages[:k]]
        if all(chunk_id in visible for chunk_id in query.relevant_chunk_ids):
            bucket["recalled_count"] += 1
    rate = None if returned == 0 else violations / returned
    no_passage_total = sum(bucket["no_passage_query_count"] for bucket in counts.values())
    signed = bool(queries) and all(query.reviewer for query in queries)
    notes = (
        "Recall is the share of queries whose listed chunks all appear in the top k. "
        "It is not an educational-effectiveness claim."
        if signed
        else (
            "No reviewer signed this query. The listed chunk ids are the skill's pilot "
            "amount. Recall only says whether those ids came back. It is not an "
            "educational-effectiveness claim."
        )
    )
    return _report(
        manifest=manifest,
        retriever_version=retriever_version,
        chunk_manifest_sha256=chunk_manifest_sha256,
        tutor_queries_present=tutor_queries_present,
        reviewed=signed,
        retriever_invoked=True,
        query_ids=tuple(query.query_id for query in queries),
        returned_chunk_ids=tuple(returned_ids),
        returned_passage_count=returned,
        filter_violation_count=violations,
        filter_violation_rate=rate,
        filter_check_passed=rate == 0.0,
        insufficient_evidence_passed=None if no_passage_total == 0 else no_passage_failures == 0,
        counts=counts,
        notes=notes,
    )


def report_without_signed_queries(
    *,
    manifest: EvaluationManifest,
    retriever_version: str | None,
    chunk_manifest_sha256: str,
    tutor_queries_present: bool,
) -> EvaluationReport:
    return _report(
        manifest=manifest,
        retriever_version=retriever_version,
        chunk_manifest_sha256=chunk_manifest_sha256,
        tutor_queries_present=tutor_queries_present,
        reviewed=False,
        retriever_invoked=False,
        query_ids=(),
        returned_chunk_ids=(),
        returned_passage_count=0,
        filter_violation_count=0,
        filter_violation_rate=None,
        filter_check_passed=None,
        insufficient_evidence_passed=None,
        counts={purpose: _zero_counts() for purpose in PURPOSES},
        notes=(
            "No reviewer-signed queries. Recall and insufficient-evidence correctness are "
            "not computed. The filter-violation rate is not computed because no passage was "
            "returned. This run does not claim educational effectiveness."
        ),
    )


def write_evaluation_report(path: Path, report: EvaluationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _request(query: EvaluationQuery, skill_id: str, limit: int) -> CurriculumRetrievalRequest:
    return CurriculumRetrievalRequest(
        learner_question=query.learner_question,
        skill_id=skill_id,
        grade=query.grade,
        subject=query.subject,
        required_language=query.required_language,
        unit_id=query.unit_id,
        purpose=query.purpose,
        limit=limit,  # type: ignore[arg-type]
    )


def _no_passage_correct(result: CurriculumRetrievalResult) -> bool:
    return result.status in NO_PASSAGE_STATUSES and not result.passages


def _zero_counts() -> dict[str, int]:
    return {
        "query_count": 0,
        "recall_query_count": 0,
        "recalled_count": 0,
        "no_passage_query_count": 0,
        "insufficient_evidence_correct_count": 0,
    }


def _report(
    *,
    manifest: EvaluationManifest,
    retriever_version: str | None,
    chunk_manifest_sha256: str,
    tutor_queries_present: bool,
    reviewed: bool,
    retriever_invoked: bool,
    query_ids: tuple[str, ...],
    returned_chunk_ids: tuple[str, ...],
    returned_passage_count: int,
    filter_violation_count: int,
    filter_violation_rate: float | None,
    filter_check_passed: bool | None,
    insufficient_evidence_passed: bool | None,
    counts: Mapping[str, Mapping[str, int]],
    notes: str,
) -> EvaluationReport:
    by_purpose = {purpose: _purpose_score(counts[purpose]) for purpose in PURPOSES}
    return EvaluationReport(
        skill_id=manifest.skill_id,
        k=manifest.limit,
        frozen=manifest.frozen,
        reviewed=reviewed,
        chunk_manifest_sha256=chunk_manifest_sha256,
        retriever_version=retriever_version,
        retriever_invoked=retriever_invoked,
        tutor_queries_present=tutor_queries_present,
        query_ids=query_ids,
        returned_chunk_ids=returned_chunk_ids,
        returned_passage_count=returned_passage_count,
        filter_violation_count=filter_violation_count,
        filter_violation_rate=filter_violation_rate,
        filter_check_passed=filter_check_passed,
        insufficient_evidence_passed=insufficient_evidence_passed,
        by_purpose=by_purpose,
        notes=notes,
    )


def _purpose_score(counts: Mapping[str, int]) -> PurposeScore:
    recall_queries = counts["recall_query_count"]
    no_passage = counts["no_passage_query_count"]
    return PurposeScore(
        query_count=counts["query_count"],
        recall_query_count=recall_queries,
        recalled_count=counts["recalled_count"],
        recall_at_k=None if recall_queries == 0 else counts["recalled_count"] / recall_queries,
        no_passage_query_count=no_passage,
        insufficient_evidence_correct_count=counts["insufficient_evidence_correct_count"],
        insufficient_evidence_correctness=(
            None if no_passage == 0 else counts["insufficient_evidence_correct_count"] / no_passage
        ),
    )
