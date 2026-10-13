from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.gamification.domain.types import (
    ActionId,
    EpisodeId,
    EvidenceSupportState,
    ProtocolVersion,
    SkillId,
    SupportActionType,
    TaxonomyVersion,
)
from app.gamification.modeling.independence_gain import (
    EquivalenceEvidence,
    IndependenceGainInput,
)
from app.gamification.modeling.misconception_inference import (
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.offline import DatasetRow
from app.gamification.modeling.shared import DecisionFeatureInput
from app.gamification.modeling.support_selection import SupportCandidate

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)
LEARNER = UUID("10000000-0000-4000-8000-000000000001")
EPISODE = EpisodeId(UUID("10000000-0000-4000-8000-000000000002"))


def feature_input(**changes) -> DecisionFeatureInput:
    base = DecisionFeatureInput(
        learner_id=LEARNER,
        skill_id=SkillId("opaque-skill-1"),
        captured_at=NOW,
        protocol_version=ProtocolVersion("adaptive-episode-v1"),
        skill_taxonomy_version=TaxonomyVersion("provisional-v1"),
        misconception_catalogue_version="provisional-misconceptions-v1",
        support_catalogue_version="provisional-support-v1",
        current_score=0.25,
        recent_correctness=(False, True),
        attempt_count=2,
        structured_error_code="error-a",
        mastery_probability=0.4,
        source_as_of={"mastery": NOW - timedelta(seconds=1)},
    )
    return replace(base, **changes)


def misconception_model() -> ProbabilisticMisconceptionModel:
    return ProbabilisticMisconceptionModel(
        catalogue_version="provisional-misconceptions-v1",
        error_likelihoods={"error-a": {"m-a": 4.0}},
        class_priors={"m-a": 0.5, "m-b": 0.45},
        abstain_threshold=0.6,
    )


def support_candidates() -> tuple[SupportCandidate, ...]:
    return (
        SupportCandidate(
            ActionId("a-hint"),
            SupportActionType.CONCEPTUAL_HINT,
            ("si",),
            ("opaque-skill-1",),
            ("m-a",),
            True,
        ),
        SupportCandidate(
            ActionId("b-worked"),
            SupportActionType.SIMILAR_WORKED_EXAMPLE,
            ("si",),
            ("opaque-skill-1",),
            ("m-a",),
            True,
        ),
        SupportCandidate(
            ActionId("blocked"),
            SupportActionType.FULL_EXPLANATION,
            ("en",),
            ("opaque-skill-1",),
            (),
            False,
        ),
    )


def equivalence_evidence() -> EquivalenceEvidence:
    return EquivalenceEvidence(
        primary_skill_match=True,
        cognitive_operation_match=True,
        difficulty_band_match=True,
        response_format_match=True,
        language_reviewed=True,
        expected_time_match=True,
        unseen_verification_item=True,
        answer_overlap_acceptable=True,
        equivalence_version="provisional-equivalence-v1",
        approved=True,
    )


def gain_input(**changes) -> IndependenceGainInput:
    base = IndependenceGainInput(
        baseline_score=0.25,
        verification_score=0.75,
        baseline_support_state=EvidenceSupportState.UNSUPPORTED,
        verification_support_state=EvidenceSupportState.UNSUPPORTED,
        equivalence=equivalence_evidence(),
        support_delivered=True,
        support_completed=True,
        support_withdrawn_at=NOW,
        verification_started_at=NOW + timedelta(seconds=1),
        idle_time_ms=100,
        maximum_idle_time_ms=1000,
    )
    return replace(base, **changes)


def dataset_rows() -> list[DatasetRow]:
    return [
        DatasetRow(f"e{i}", f"l{i}", {"score": i / 10}, "a-hint", 0.5, 0.5, True)
        for i in range(10)
    ]
