import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.adaptive_tutor import application as adaptive_application
from app.adaptive_tutor.application import curriculum_request_for_mapping
from app.adaptive_tutor.application import curriculum_retrieval as adaptive_curriculum
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure import XlsxSkillTaxonomyCatalog
from app.curriculum import application as shared_curriculum
from app.curriculum.application import (
    RETRIEVER_CONTRACT_VERSION,
    CurriculumChunk,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    CurriculumRetriever,
    CurriculumReviewStatus,
    CurriculumSourceRecord,
    IngestionStatus,
    MetadataStatus,
    RetrievedCurriculumPassage,
    UsageRightsStatus,
    validate_curriculum_skill_ids,
    validate_retrieval_result_for_request,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def valid_skill_ids() -> set[str]:
    return {
        node.skill_id
        for node in XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    }


def source_record(**overrides: object) -> CurriculumSourceRecord:
    data: dict[str, object] = {
        "source_id": "SRC-001",
        "title": "Reviewed curriculum sample",
        "publisher_authority": "Recorded authority",
        "grade": 4,
        "subject": "Mathematics",
        "language": "en",
        "source_type": "teacher-guide",
        "source_location": "repository://curriculum/sample.pdf",
        "source_version": "edition-1",
        "metadata_status": MetadataStatus.VERIFIED,
        "ingestion_status": IngestionStatus.INGESTED,
        "review_status": CurriculumReviewStatus.APPROVED,
        "usage_rights_status": UsageRightsStatus.PERMITTED,
    }
    data.update(overrides)
    return CurriculumSourceRecord.model_validate(data)


def curriculum_chunk(**overrides: object) -> CurriculumChunk:
    data: dict[str, object] = {
        "chunk_id": "SRC-001-C001",
        "source_id": "SRC-001",
        "source_version": "edition-1",
        "content": "A reviewed example passage about fractions.",
        "grade": 4,
        "subject": "Mathematics",
        "language": "en",
        "skill_ids": ["MAT-FRC", "MAT-OPS"],
        "page_number": 12,
        "section_locator": "Fractions / worked examples",
        "review_status": CurriculumReviewStatus.APPROVED,
    }
    data.update(overrides)
    return CurriculumChunk.model_validate(data)


def retrieved_passage(**overrides: object) -> RetrievedCurriculumPassage:
    data: dict[str, object] = {
        "chunk": curriculum_chunk(),
        "source": source_record(),
        "score": 2.4,
    }
    data.update(overrides)
    return RetrievedCurriculumPassage.model_validate(data)


def matched_mapping(skill_id: str = "MAT-FRC") -> SkillMappingResult:
    return SkillMappingResult(
        status=SkillMappingStatus.MATCHED,
        intent=LearningIntent.EXPLANATION_REQUEST,
        skill_id=skill_id,
        confidence=0.9,
        clarification_needed=False,
    )


class FakeCurriculumRetriever:
    def __init__(self, passage: RetrievedCurriculumPassage) -> None:
        self.passage = passage

    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult:
        passages = (
            (self.passage,)
            if request.skill_id in self.passage.chunk.skill_ids
            and request.grade == self.passage.chunk.grade
            else ()
        )
        return CurriculumRetrievalResult(
            status=(
                CurriculumRetrievalStatus.FOUND
                if passages
                else CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES
            ),
            passages=passages,
        )


def run_retrieval(
    retriever: CurriculumRetriever,
    request: CurriculumRetrievalRequest,
) -> CurriculumRetrievalResult:
    return retriever.retrieve(request)


def test_source_record_supports_verified_and_unknown_metadata() -> None:
    verified = source_record()
    unknown = source_record(
        publisher_authority=None,
        grade=None,
        subject=None,
        language=None,
        source_location=None,
        source_version=None,
        metadata_status=MetadataStatus.UNKNOWN,
        ingestion_status=IngestionStatus.NOT_INGESTED,
        review_status=CurriculumReviewStatus.UNREVIEWED,
        usage_rights_status=UsageRightsStatus.UNKNOWN,
    )

    assert verified.metadata_status is MetadataStatus.VERIFIED
    assert unknown.publisher_authority is None
    assert unknown.usage_rights_status is UsageRightsStatus.UNKNOWN


@pytest.mark.parametrize("grade", [3, 6, "4"])
def test_source_rejects_invalid_grade(grade: object) -> None:
    with pytest.raises(ValidationError):
        source_record(grade=grade)


@pytest.mark.parametrize("field", ["source_id", "title", "source_type"])
def test_source_requires_identity_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        source_record(**{field: "   "})


def test_valid_chunk_supports_multiple_unique_skills() -> None:
    chunk = curriculum_chunk()

    validate_curriculum_skill_ids(chunk, valid_skill_ids())
    assert chunk.skill_ids == ("MAT-FRC", "MAT-OPS")


@pytest.mark.parametrize("field", ["chunk_id", "source_id", "source_version", "content"])
def test_chunk_rejects_blank_required_text(field: str) -> None:
    with pytest.raises(ValidationError):
        curriculum_chunk(**{field: "  "})


@pytest.mark.parametrize("grade", [3, 6, "5"])
def test_chunk_rejects_invalid_grade(grade: object) -> None:
    with pytest.raises(ValidationError):
        curriculum_chunk(grade=grade)


@pytest.mark.parametrize("field", ["language", "subject"])
def test_chunk_rejects_blank_language_or_subject(field: str) -> None:
    with pytest.raises(ValidationError):
        curriculum_chunk(**{field: ""})


def test_chunk_rejects_duplicate_skills() -> None:
    with pytest.raises(ValidationError, match="chunk skill IDs must be unique"):
        curriculum_chunk(skill_ids=["MAT-FRC", "MAT-FRC"])


def test_chunk_requires_at_least_one_skill() -> None:
    with pytest.raises(ValidationError):
        curriculum_chunk(skill_ids=[])


def test_taxonomy_validation_rejects_unknown_chunk_and_request_skills() -> None:
    chunk = curriculum_chunk(skill_ids=["MAT-FRC", "NOT-REAL"])
    request = CurriculumRetrievalRequest(
        learner_question="Explain this topic",
        skill_id="NOT-REAL",
        grade=4,
    )

    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        validate_curriculum_skill_ids(chunk, valid_skill_ids())
    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        validate_curriculum_skill_ids(request, valid_skill_ids())


def test_chunk_contract_is_immutable() -> None:
    chunk = curriculum_chunk()

    with pytest.raises(ValidationError):
        chunk.content = "replacement"  # type: ignore[misc]


def test_retrieved_passage_requires_matching_source_reference() -> None:
    with pytest.raises(ValidationError, match="source_id does not match"):
        retrieved_passage(source=source_record(source_id="SRC-OTHER"))
    with pytest.raises(ValidationError, match="source_version does not match"):
        retrieved_passage(source=source_record(source_version="edition-2"))


@pytest.mark.parametrize(
    "source",
    [
        source_record(metadata_status=MetadataStatus.PROVISIONAL),
        source_record(review_status=CurriculumReviewStatus.REVIEW_PENDING),
        source_record(usage_rights_status=UsageRightsStatus.UNKNOWN),
        source_record(ingestion_status=IngestionStatus.NOT_INGESTED),
    ],
)
def test_pending_source_can_be_retrieved(source: CurriculumSourceRecord) -> None:
    assert retrieved_passage(source=source).source == source


def test_rejected_or_restricted_source_cannot_be_retrieved() -> None:
    with pytest.raises(ValidationError, match="must not be rejected"):
        retrieved_passage(source=source_record(review_status=CurriculumReviewStatus.REJECTED))
    with pytest.raises(ValidationError, match="must not be restricted"):
        retrieved_passage(source=source_record(usage_rights_status=UsageRightsStatus.RESTRICTED))


def test_pending_chunk_can_be_retrieved() -> None:
    passage = retrieved_passage(
        chunk=curriculum_chunk(review_status=CurriculumReviewStatus.REVIEW_PENDING)
    )

    assert passage.chunk.review_status is CurriculumReviewStatus.REVIEW_PENDING


@pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
def test_retrieval_score_must_be_finite(score: float) -> None:
    with pytest.raises(ValidationError):
        retrieved_passage(score=score)


def test_found_result_requires_passages() -> None:
    with pytest.raises(ValidationError, match="FOUND requires"):
        CurriculumRetrievalResult(status=CurriculumRetrievalStatus.FOUND)


@pytest.mark.parametrize(
    "status",
    [
        CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES,
        CurriculumRetrievalStatus.NO_APPROVED_SOURCE,
        CurriculumRetrievalStatus.PROVIDER_UNAVAILABLE,
        CurriculumRetrievalStatus.PROVIDER_ERROR,
    ],
)
def test_empty_and_failure_results_do_not_fabricate_passages(
    status: CurriculumRetrievalStatus,
) -> None:
    result = CurriculumRetrievalResult(status=status)

    assert result.passages == ()


def test_non_found_result_rejects_passages() -> None:
    with pytest.raises(ValidationError, match="only FOUND may contain passages"):
        CurriculumRetrievalResult(
            status=CurriculumRetrievalStatus.PROVIDER_ERROR,
            passages=[retrieved_passage()],
        )


def test_result_is_checked_against_request_grade_skill_and_limit() -> None:
    request = CurriculumRetrievalRequest(
        learner_question="How do I add fractions?",
        skill_id="MAT-FRC",
        grade=4,
        limit=1,
    )
    valid = CurriculumRetrievalResult(
        status=CurriculumRetrievalStatus.FOUND,
        passages=[retrieved_passage()],
    )

    validate_retrieval_result_for_request(request, valid)
    with pytest.raises(ValueError, match="exceeds requested limit"):
        validate_retrieval_result_for_request(
            request,
            CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.FOUND,
                passages=[retrieved_passage(), retrieved_passage()],
            ),
        )
    with pytest.raises(ValueError, match="grade does not match"):
        validate_retrieval_result_for_request(
            request,
            CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.FOUND,
                passages=[retrieved_passage(chunk=curriculum_chunk(grade=5))],
            ),
        )
    with pytest.raises(ValueError, match="does not include requested skill"):
        validate_retrieval_result_for_request(
            request,
            CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.FOUND,
                passages=[retrieved_passage(chunk=curriculum_chunk(skill_ids=["MAT-OPS"]))],
            ),
        )


def test_request_validates_question_grade_language_and_limit() -> None:
    request = CurriculumRetrievalRequest(
        learner_question="භාගයක් පැහැදිලි කරන්න",
        skill_id="MAT-FRC",
        grade=5,
        requested_language="si",
        limit=3,
    )

    assert request.requested_language == "si"
    for field, value in (
        ("learner_question", ""),
        ("requested_language", " "),
        ("grade", 6),
        ("limit", 0),
        ("limit", 11),
    ):
        data = request.model_dump()
        data[field] = value
        with pytest.raises(ValidationError):
            CurriculumRetrievalRequest.model_validate(data)


def test_confirmed_skill_mapping_is_eligible() -> None:
    request = curriculum_request_for_mapping(
        "Explain fractions",
        matched_mapping(),
        4,
        valid_skill_ids(),
        requested_language="en",
    )

    assert request is not None
    assert request.skill_id == "MAT-FRC"


def test_confirmed_unknown_skill_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown skill IDs: NOT-REAL"):
        curriculum_request_for_mapping(
            "Explain this",
            matched_mapping("NOT-REAL"),
            4,
            valid_skill_ids(),
        )


@pytest.mark.parametrize(
    "mapping",
    [
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.EXPLANATION_REQUEST,
            candidate_skills=[{"skill_id": "MAT-FRC", "confidence": 0.7}],
            clarification_needed=True,
            clarification_question="Which topic do you mean?",
        ),
        SkillMappingResult(
            status=SkillMappingStatus.NO_MATCH,
            intent=LearningIntent.EXPLANATION_REQUEST,
            clarification_needed=False,
        ),
        SkillMappingResult(
            status=SkillMappingStatus.NOT_SKILL_RELATED,
            intent=LearningIntent.OFF_TOPIC,
            clarification_needed=False,
        ),
    ],
)
def test_uncertain_mapping_is_not_eligible(mapping: SkillMappingResult) -> None:
    assert curriculum_request_for_mapping("Help", mapping, 4, valid_skill_ids()) is None


def test_fake_retriever_is_deterministic_without_external_dependencies() -> None:
    retriever = FakeCurriculumRetriever(retrieved_passage())
    request = CurriculumRetrievalRequest(
        learner_question="Explain fractions",
        skill_id="MAT-FRC",
        grade=4,
    )

    first = run_retrieval(retriever, request)
    second = run_retrieval(retriever, request)

    assert first == second
    assert first.status is CurriculumRetrievalStatus.FOUND


def test_adaptive_tutor_imports_are_thin_shared_aliases() -> None:
    shared_names = (
        "CurriculumChunk",
        "CurriculumRetrievalRequest",
        "CurriculumRetrievalResult",
        "CurriculumRetrievalStatus",
        "CurriculumRetriever",
        "CurriculumReviewStatus",
        "CurriculumSourceRecord",
        "IngestionStatus",
        "MetadataStatus",
        "RetrievedCurriculumPassage",
        "UsageRightsStatus",
        "validate_curriculum_skill_ids",
        "validate_retrieval_result_for_request",
    )

    for name in shared_names:
        assert getattr(adaptive_curriculum, name) is getattr(shared_curriculum, name)
        assert getattr(adaptive_application, name) is getattr(shared_curriculum, name)


def test_game_style_consumer_can_build_shared_request_without_tutor_adapter() -> None:
    request = shared_curriculum.CurriculumRetrievalRequest(
        learner_question="Create an activity about fractions",
        skill_id="MAT-FRC",
        grade=4,
        requested_language="en",
        limit=3,
    )

    validate_curriculum_skill_ids(request, valid_skill_ids())
    assert request.skill_id == "MAT-FRC"


def test_shared_curriculum_module_has_no_consumer_dependencies() -> None:
    forbidden = (
        "app.adaptive_tutor",
        "app.gamification",
        "app.knowledge_tracing",
        "app.learner_state",
    )
    curriculum_package = REPOSITORY_ROOT / "backend/app/curriculum"

    for path in curriculum_package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules = [
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        imported_modules.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(module.startswith(forbidden) for module in imported_modules), path


def test_request_omitting_v1_1_fields_still_validates() -> None:
    request = CurriculumRetrievalRequest(
        learner_question="Explain fractions",
        skill_id="MAT-FRC",
        grade=4,
    )
    chunk = curriculum_chunk()

    assert request.subject is None
    assert request.required_language is None
    assert request.unit_id is None
    assert request.purpose == "TUTOR_ANSWER"
    assert chunk.unit_id is None
    assert chunk.learning_outcome_id is None
    validate_retrieval_result_for_request(
        request,
        CurriculumRetrievalResult(
            status=CurriculumRetrievalStatus.FOUND,
            passages=[retrieved_passage(chunk=chunk)],
        ),
    )


@pytest.mark.parametrize(
    ("request_fields", "chunk_fields", "message"),
    [
        ({"subject": "Mathematics"}, {"subject": "Science"}, "subject does not match"),
        ({"required_language": "si"}, {"language": "en"}, "language does not match"),
        ({"unit_id": "G5-MAT-C03"}, {"unit_id": "G5-MAT-C01"}, "unit does not match"),
    ],
)
def test_set_filters_reject_a_mismatched_passage(
    request_fields: dict[str, str],
    chunk_fields: dict[str, str],
    message: str,
) -> None:
    request = CurriculumRetrievalRequest(
        learner_question="Explain fractions",
        skill_id="MAT-FRC",
        grade=4,
        **request_fields,
    )
    with pytest.raises(ValueError, match=message):
        validate_retrieval_result_for_request(
            request,
            CurriculumRetrievalResult(
                status=CurriculumRetrievalStatus.FOUND,
                passages=[retrieved_passage(chunk=curriculum_chunk(**chunk_fields))],
            ),
        )


def test_purpose_accepts_only_the_two_literals() -> None:
    authored = CurriculumRetrievalRequest(
        learner_question="Explain fractions",
        skill_id="MAT-FRC",
        grade=5,
        purpose="CONTENT_AUTHORING",
    )
    assert authored.purpose == "CONTENT_AUTHORING"
    with pytest.raises(ValidationError):
        CurriculumRetrievalRequest(
            learner_question="Explain fractions",
            skill_id="MAT-FRC",
            grade=5,
            purpose="GAME_ITEM",  # type: ignore[arg-type]
        )


def test_retriever_version_is_present_on_found_and_empty_results() -> None:
    found = CurriculumRetrievalResult(
        status=CurriculumRetrievalStatus.FOUND,
        passages=[retrieved_passage()],
    )
    empty = CurriculumRetrievalResult(status=CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES)

    assert found.retriever_version == RETRIEVER_CONTRACT_VERSION
    assert empty.retriever_version == RETRIEVER_CONTRACT_VERSION


def test_v1_1_contracts_still_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CurriculumRetrievalRequest(
            learner_question="Explain fractions",
            skill_id="MAT-FRC",
            grade=5,
            answer_key="hidden",  # type: ignore[call-arg]
        )
