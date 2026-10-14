from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.adaptive_tutor.application import mastery_request_for_mapping
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingResult
from app.adaptive_tutor.domain import LearningIntent, SkillMappingStatus
from app.adaptive_tutor.infrastructure import XlsxSkillTaxonomyCatalog
from app.knowledge_tracing.application import (
    MasteryProvider,
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
    validate_mastery_request_against_taxonomy,
    validate_mastery_result_identity,
)

LEARNER_ID = UUID("00000000-0000-4000-8000-000000000001")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def valid_skill_ids() -> set[str]:
    return {
        node.skill_id
        for node in XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    }


def matched_mapping(skill_id: str = "MAT-FRC") -> SkillMappingResult:
    return SkillMappingResult(
        status=SkillMappingStatus.MATCHED,
        intent=LearningIntent.EXPLANATION_REQUEST,
        skill_id=skill_id,
        confidence=0.9,
        clarification_needed=False,
    )


class FakeMasteryProvider:
    def __init__(self, estimates: dict[tuple[UUID, str], float]) -> None:
        self.estimates = estimates

    def get_mastery(self, request: MasteryRetrievalRequest) -> MasteryResult:
        mastery = self.estimates.get((request.learner_id, request.skill_id))
        return MasteryResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=MasteryStatus.AVAILABLE if mastery is not None else MasteryStatus.NOT_FOUND,
            mastery=mastery,
        )


def read_mastery(provider: MasteryProvider, request: MasteryRetrievalRequest) -> MasteryResult:
    return provider.get_mastery(request)


def test_request_uses_shared_learner_uuid_and_authoritative_skill() -> None:
    request = MasteryRetrievalRequest(
        learner_id=str(LEARNER_ID),
        skill_id="MAT-FRC",
    )

    validate_mastery_request_against_taxonomy(request, valid_skill_ids())
    assert request.learner_id == LEARNER_ID


@pytest.mark.parametrize("learner_id", ["not-a-uuid", "", None])
def test_request_rejects_invalid_learner_uuid(learner_id: object) -> None:
    with pytest.raises(ValidationError):
        MasteryRetrievalRequest(learner_id=learner_id, skill_id="MAT-FRC")


@pytest.mark.parametrize("skill_id", ["", "   "])
def test_request_rejects_blank_skill_id(skill_id: str) -> None:
    with pytest.raises(ValidationError):
        MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id=skill_id)


def test_taxonomy_validation_rejects_unknown_skill_id() -> None:
    request = MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id="NOT-REAL")

    with pytest.raises(ValueError, match="unknown skill ID: NOT-REAL"):
        validate_mastery_request_against_taxonomy(request, valid_skill_ids())


@pytest.mark.parametrize("mastery", [0.0, 0.5, 1.0])
def test_available_mastery_accepts_normalized_boundaries(mastery: float) -> None:
    result = MasteryResult(
        learner_id=LEARNER_ID,
        skill_id="MAT-FRC",
        status=MasteryStatus.AVAILABLE,
        mastery=mastery,
    )

    assert result.mastery == mastery


@pytest.mark.parametrize("mastery", [-0.01, 1.01, float("nan"), float("inf"), float("-inf")])
def test_mastery_rejects_out_of_range_or_non_finite_values(mastery: float) -> None:
    with pytest.raises(ValidationError):
        MasteryResult(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=MasteryStatus.AVAILABLE,
            mastery=mastery,
        )


def test_available_status_requires_mastery() -> None:
    with pytest.raises(ValidationError, match="AVAILABLE requires mastery"):
        MasteryResult(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=MasteryStatus.AVAILABLE,
        )


@pytest.mark.parametrize(
    "status",
    [
        MasteryStatus.NOT_FOUND,
        MasteryStatus.PROVIDER_UNAVAILABLE,
        MasteryStatus.PROVIDER_ERROR,
    ],
)
def test_unavailable_statuses_reject_fabricated_mastery(status: MasteryStatus) -> None:
    with pytest.raises(ValidationError, match="only AVAILABLE may contain mastery"):
        MasteryResult(
            learner_id=LEARNER_ID,
            skill_id="MAT-FRC",
            status=status,
            mastery=0.5,
        )


@pytest.mark.parametrize(
    "status",
    [
        MasteryStatus.NOT_FOUND,
        MasteryStatus.PROVIDER_UNAVAILABLE,
        MasteryStatus.PROVIDER_ERROR,
    ],
)
def test_missing_and_failure_results_keep_mastery_absent(status: MasteryStatus) -> None:
    result = MasteryResult(
        learner_id=LEARNER_ID,
        skill_id="MAT-FRC",
        status=status,
    )

    assert result.mastery is None


@pytest.mark.parametrize(
    ("learner_id", "skill_id"),
    [(uuid4(), "MAT-FRC"), (LEARNER_ID, "MAT-OPS")],
)
def test_result_identity_must_match_request(learner_id: UUID, skill_id: str) -> None:
    request = MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id="MAT-FRC")
    result = MasteryResult(
        learner_id=learner_id,
        skill_id=skill_id,
        status=MasteryStatus.NOT_FOUND,
    )

    with pytest.raises(ValueError, match="identity does not match request"):
        validate_mastery_result_identity(request, result)


def test_fake_provider_is_deterministic_and_represents_missing_estimate() -> None:
    provider = FakeMasteryProvider({(LEARNER_ID, "MAT-FRC"): 0.7})
    available_request = MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id="MAT-FRC")
    missing_request = MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id="MAT-OPS")

    first = read_mastery(provider, available_request)
    second = read_mastery(provider, available_request)
    missing = read_mastery(provider, missing_request)

    assert first == second
    assert first.mastery == 0.7
    assert missing.status is MasteryStatus.NOT_FOUND
    assert missing.mastery is None


def test_confirmed_valid_mapping_is_eligible_for_mastery_retrieval() -> None:
    request = mastery_request_for_mapping(LEARNER_ID, matched_mapping(), valid_skill_ids())

    assert request == MasteryRetrievalRequest(learner_id=LEARNER_ID, skill_id="MAT-FRC")


def test_confirmed_unknown_skill_is_rejected_before_provider_use() -> None:
    with pytest.raises(ValueError, match="unknown skill ID: NOT-REAL"):
        mastery_request_for_mapping(LEARNER_ID, matched_mapping("NOT-REAL"), valid_skill_ids())


@pytest.mark.parametrize(
    "mapping",
    [
        SkillMappingResult(
            status=SkillMappingStatus.AMBIGUOUS,
            intent=LearningIntent.EXPLANATION_REQUEST,
            candidate_skills=[{"skill_id": "MAT-FRC", "confidence": 0.7}],
            clarification_needed=True,
            clarification_question="Which skill do you mean?",
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
def test_non_matched_mapping_is_not_eligible(mapping: SkillMappingResult) -> None:
    assert mastery_request_for_mapping(LEARNER_ID, mapping, valid_skill_ids()) is None
