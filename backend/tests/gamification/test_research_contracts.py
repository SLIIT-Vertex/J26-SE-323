from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.gamification.api.research_contracts import (
    RAW_IG_FORMULA_VERSION,
    RESEARCH_CONTRACT_VERSION,
    AttemptContract,
    BaselinePolicyContract,
    DifficultyEvidenceContract,
    DifficultyTriggerContract,
    EpisodeContract,
    EventEnvelopeContract,
    ExperimentAssignmentContract,
    ExternalEvidenceContract,
    IndependenceGainResultContract,
    IndependentEvidenceContract,
    LearnerEligibilityContract,
    LearningSessionContract,
    MisconceptionBeliefContract,
    ParticipationRewardContract,
    PolicyUpdateAuthorizationContract,
    PresentationContract,
    ProbeReservationContract,
    ScaffoldCandidateContract,
    ScaffoldDecisionContract,
    ScaffoldExposureContract,
    ScaffoldPredictionContract,
    ScoreComponentContract,
    ScoreInputContract,
    ScoreResultContract,
    SupportWithdrawalContract,
)
from app.gamification.application.baseline_policy import (
    BaselinePolicyDefinition,
    ConventionalBaselinePolicy,
)
from app.gamification.domain.types import ExperimentMode
from tests.gamification.helpers.research_contract_fixtures import (
    AT,
    EPISODE_ID,
    LEARNER_ID,
    PRESENTATION_ID,
    SESSION_ID,
    event,
)


def test_grade5_sinhala_pseudonymous_eligibility_round_trips() -> None:
    contract = LearnerEligibilityContract(
        learner_id=LEARNER_ID,
        grade=5,
        curriculum_medium="si",
        pseudonymous=True,
        consent_eligibility_reference="synthetic-consent-ref",
        research_eligible=False,
        checked_at=AT,
    )

    restored = LearnerEligibilityContract.model_validate_json(contract.model_dump_json())

    assert restored == contract
    assert restored.contract_version == RESEARCH_CONTRACT_VERSION


def test_foundation_execution_contracts_are_strict_versioned_and_serializable() -> None:
    session = LearningSessionContract(
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        grade=5,
        curriculum_medium="si",
        app_version="mobile-v1",
        started_at=AT,
        offline_capable=True,
    )
    episode = EpisodeContract(
        episode_id=EPISODE_ID,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        skill_id="synthetic-skill",
        skill_version="synthetic-skill-v1",
        protocol_version="adaptive-episode-v1",
        experiment_mode="proposed",
        phase="created",
        server_authoritative=True,
        created_at=AT,
        transitioned_at=AT,
    )
    attempt = AttemptContract(
        attempt_id=UUID("31000000-0000-4000-8000-000000000001"),
        presentation_id=PRESENTATION_ID,
        attempt_number=1,
        response={"option_code": "synthetic-a"},
        assistance_state="none",
        measurement_role="unsupported_before",
        active_response_ms=1_000,
        wall_clock_ms=1_100,
        submitted_at=AT,
    )
    score_input = ScoreInputContract(
        scoring_request_id=UUID("31000000-0000-4000-8000-000000000002"),
        attempt_id=attempt.attempt_id,
        item_revision_id="synthetic-item-r1",
        rubric_version="rubric-v1",
        response=attempt.response,
        requested_at=AT,
    )
    difficulty = DifficultyEvidenceContract(
        evidence_id=UUID("31000000-0000-4000-8000-000000000003"),
        episode_id=EPISODE_ID,
        contributing_event_ids=(event(1).event_id,),
        feature_values={"incorrect_attempts": 2},
        missingness={"response_time": False},
        evidence_window_version="difficulty-window-v1",
        captured_at=AT,
    )
    trigger = DifficultyTriggerContract(
        trigger_id=UUID("31000000-0000-4000-8000-000000000004"),
        episode_id=EPISODE_ID,
        evidence_id=difficulty.evidence_id,
        fired=True,
        eligible_for_support=True,
        rule_version="difficulty-rule-v1",
        threshold_values={"incorrect_attempts": 2.0},
        severity=0.6,
        reason_codes=("REPEATED_ERROR",),
        server_authoritative=True,
        evaluated_at=AT,
    )
    candidate = ScaffoldCandidateContract(
        scaffold_id="synthetic-scaffold",
        scaffold_version="scaffold-v1",
        eligible=True,
        reason_codes=("SAFE_AND_ELIGIBLE",),
    )
    prediction = ScaffoldPredictionContract(
        scaffold_id=candidate.scaffold_id,
        predicted_independence_gain=0.25,
        uncertainty=0.1,
        propensity=1.0,
    )
    decision = ScaffoldDecisionContract(
        decision_id=UUID("31000000-0000-4000-8000-000000000005"),
        episode_id=EPISODE_ID,
        feature_schema_version="features-v1",
        context_snapshot_id=UUID("31000000-0000-4000-8000-000000000006"),
        candidates=(candidate,),
        predictions=(prediction,),
        selected_scaffold_id=candidate.scaffold_id,
        policy_version="policy-v1",
        experiment_mode="proposed",
        exploration=False,
        randomization_token=None,
        decided_at=AT,
    )
    exposure = ScaffoldExposureContract(
        exposure_id=UUID("31000000-0000-4000-8000-000000000007"),
        episode_id=EPISODE_ID,
        decision_id=decision.decision_id,
        scaffold_id=candidate.scaffold_id,
        scaffold_version=candidate.scaffold_version,
        rendered_step_ids=("synthetic-step-1",),
        started_at=AT,
        completed_at=AT + timedelta(seconds=10),
    )
    withdrawal = SupportWithdrawalContract(
        confirmation_id=UUID("31000000-0000-4000-8000-000000000008"),
        episode_id=EPISODE_ID,
        exposure_id=exposure.exposure_id,
        all_support_removed=True,
        client_confirmed_at=AT + timedelta(seconds=11),
        server_verified_at=AT + timedelta(seconds=12),
    )
    assignment = ExperimentAssignmentContract(
        assignment_id=UUID("31000000-0000-4000-8000-000000000009"),
        learner_id=LEARNER_ID,
        experiment_id="synthetic-experiment",
        experiment_version="experiment-v1",
        mode="proposed",
        assignment_method="synthetic-seeded",
        assignment_token="synthetic-token",
        assigned_at=AT,
    )
    reservation = ProbeReservationContract(
        reservation_id=UUID("31000000-0000-4000-8000-000000000010"),
        episode_id=EPISODE_ID,
        item_revision_id="synthetic-item-r2",
        parallel_family_id="synthetic-family-v1",
        measurement_role="unsupported_after",
        reservation_version="reservation-v1",
        reserved_at=AT,
        expires_at=AT + timedelta(hours=1),
    )

    contracts = (
        session,
        episode,
        attempt,
        score_input,
        difficulty,
        trigger,
        candidate,
        prediction,
        decision,
        exposure,
        withdrawal,
        assignment,
        reservation,
    )
    for contract in contracts:
        assert type(contract).model_validate_json(contract.model_dump_json()) == contract
        assert contract.contract_version == RESEARCH_CONTRACT_VERSION

    with pytest.raises(ValidationError, match="Extra inputs"):
        EpisodeContract(**episode.model_dump(), unexpected="rejected")


@pytest.mark.parametrize(
    ("field", "value"),
    (("grade", 4), ("curriculum_medium", "ta"), ("pseudonymous", False)),
)
def test_eligibility_rejects_out_of_scope_or_identified_learners(field: str, value: object) -> None:
    values = {
        "learner_id": LEARNER_ID,
        "grade": 5,
        "curriculum_medium": "si",
        "pseudonymous": True,
        "consent_eligibility_reference": "synthetic-consent-ref",
        "research_eligible": False,
        "checked_at": AT,
    }
    values[field] = value
    with pytest.raises(ValidationError):
        LearnerEligibilityContract.model_validate(values)


@pytest.mark.parametrize("role", ("unsupported_before", "unsupported_after", "retention"))
def test_unsupported_roles_reject_assistance(role: str) -> None:
    with pytest.raises(ValidationError, match="assistance_state=none"):
        PresentationContract(
            presentation_id=PRESENTATION_ID,
            episode_id=EPISODE_ID,
            item_revision_id="synthetic-item-r1",
            parallel_family_id="synthetic-family-v1",
            sequence=1,
            measurement_role=role,
            assistance_state="scaffold_active",
            role_assigned_at_presentation=True,
            grade=5,
            curriculum_medium="si",
            opened_at=AT,
        )


def test_supported_practice_requires_explicit_assistance() -> None:
    with pytest.raises(ValidationError, match="requires explicit assistance"):
        PresentationContract(
            presentation_id=PRESENTATION_ID,
            episode_id=EPISODE_ID,
            item_revision_id="synthetic-item-r1",
            parallel_family_id=None,
            sequence=1,
            measurement_role="supported_practice",
            assistance_state="none",
            role_assigned_at_presentation=True,
            grade=5,
            curriculum_medium="si",
            opened_at=AT,
        )


def test_server_authoritative_score_is_bounded_and_versioned() -> None:
    result = ScoreResultContract(
        scoring_request_id=UUID("30000000-0000-4000-8000-000000000001"),
        attempt_id=UUID("30000000-0000-4000-8000-000000000002"),
        score=1.0,
        maximum_score=2.0,
        correct=None,
        rubric_version="rubric-v1",
        scoring_version="scoring-v1",
        server_authoritative=True,
        scored_at=AT,
    )
    assert result.server_authoritative is True
    with pytest.raises(ValidationError, match="cannot exceed"):
        ScoreResultContract(**{**result.model_dump(), "score": 3.0})


def test_misconception_distribution_requires_unknown_and_normalization() -> None:
    base = {
        "belief_snapshot_id": UUID("30000000-0000-4000-8000-000000000003"),
        "learner_id": LEARNER_ID,
        "skill_id": "synthetic-skill",
        "episode_id": EPISODE_ID,
        "item_revision_id": "synthetic-item-r1",
        "evidence_event_ids": (event(1).event_id,),
        "model_version": "misconception-v1",
        "mapping_version": "mapping-v1",
        "evidence_window_version": "window-v1",
        "low_confidence": True,
        "created_at": AT,
    }
    with pytest.raises(ValidationError, match="unknown_or_other"):
        MisconceptionBeliefContract(**base, probabilities={"synthetic-m1": 1.0})
    with pytest.raises(ValidationError, match="sum to 1"):
        MisconceptionBeliefContract(
            **base, probabilities={"synthetic-m1": 0.6, "unknown_or_other": 0.3}
        )


def _score_component(presentation_id: UUID, score: float) -> ScoreComponentContract:
    return ScoreComponentContract(
        presentation_id=presentation_id,
        score=score,
        maximum_score=1.0,
        scoring_version="scoring-v1",
        assistance_state="none",
    )


def test_raw_independence_gain_is_exact_difference() -> None:
    before_id = UUID("30000000-0000-4000-8000-000000000004")
    after_id = UUID("30000000-0000-4000-8000-000000000005")
    result = IndependenceGainResultContract(
        result_id=UUID("30000000-0000-4000-8000-000000000006"),
        episode_id=EPISODE_ID,
        decision_id=UUID("30000000-0000-4000-8000-000000000007"),
        unsupported_before=(_score_component(before_id, 0.25),),
        unsupported_after=(_score_component(after_id, 0.75),),
        raw_independence_gain=0.5,
        valid=True,
        exclusion_reasons=(),
        formula_version=RAW_IG_FORMULA_VERSION,
        equivalence_version="synthetic-equivalence-v1",
        support_withdrawal_confirmation_id=UUID(
            "30000000-0000-4000-8000-000000000008"
        ),
        server_authoritative=True,
        calculated_at=AT,
    )
    assert result.raw_independence_gain == 0.5
    with pytest.raises(ValidationError, match="must equal"):
        IndependenceGainResultContract(**{**result.model_dump(), "raw_independence_gain": 0.6})


def test_invalid_or_contaminated_ig_cannot_publish_reward() -> None:
    before = _score_component(UUID("30000000-0000-4000-8000-000000000009"), 0.0)
    after = _score_component(UUID("30000000-0000-4000-8000-000000000010"), 1.0)
    with pytest.raises(ValidationError, match="cannot authorize"):
        IndependenceGainResultContract(
            result_id=UUID("30000000-0000-4000-8000-000000000011"),
            episode_id=EPISODE_ID,
            decision_id=UUID("30000000-0000-4000-8000-000000000012"),
            unsupported_before=(before,),
            unsupported_after=(after,),
            raw_independence_gain=1.0,
            valid=False,
            exclusion_reasons=("PROBE_CONTAMINATED",),
            formula_version=RAW_IG_FORMULA_VERSION,
            equivalence_version="synthetic-equivalence-v1",
            support_withdrawal_confirmation_id=UUID(
                "30000000-0000-4000-8000-000000000013"
            ),
            server_authoritative=True,
            calculated_at=AT,
        )


@pytest.mark.parametrize(
    ("mode", "valid", "authorized"),
    (("baseline", True, True), ("proposed", False, True), ("proposed", True, False)),
)
def test_policy_update_requires_proposed_mode_and_valid_model3_result(
    mode: str, valid: bool, authorized: bool
) -> None:
    with pytest.raises(ValidationError, match="requires proposed mode"):
        PolicyUpdateAuthorizationContract(
            authorization_id=UUID("30000000-0000-4000-8000-000000000014"),
            episode_id=EPISODE_ID,
            decision_id=UUID("30000000-0000-4000-8000-000000000015"),
            independence_gain_result_id=UUID("30000000-0000-4000-8000-000000000016"),
            experiment_mode=mode,
            valid_model3_result=valid,
            authorized=authorized,
            reason_codes=("SYNTHETIC_CASE",),
            issued_at=AT,
        )


def test_valid_model3_result_authorizes_only_the_proposed_policy() -> None:
    authorization = PolicyUpdateAuthorizationContract(
        authorization_id=UUID("30000000-0000-4000-8000-000000000017"),
        episode_id=EPISODE_ID,
        decision_id=UUID("30000000-0000-4000-8000-000000000018"),
        independence_gain_result_id=UUID("30000000-0000-4000-8000-000000000019"),
        experiment_mode="proposed",
        valid_model3_result=True,
        authorized=True,
        reason_codes=("VALID_RAW_IG",),
        issued_at=AT,
    )
    assert authorization.authorized is True


def test_baseline_policy_never_consumes_beliefs_or_learns_from_ig() -> None:
    contract = BaselinePolicyContract(
        policy_version="baseline-policy-v1",
        experiment_mode=ExperimentMode.BASELINE,
        selection_kind="fixed",
        fixed_scaffold_id="synthetic-neutral-scaffold",
        rule_version=None,
        consumes_misconception_beliefs=False,
        learns_from_independence_gain=False,
    )
    policy = ConventionalBaselinePolicy(
        BaselinePolicyDefinition(
            policy_version=contract.policy_version,
            selection_kind=contract.selection_kind,
            fixed_scaffold_id=contract.fixed_scaffold_id,
        )
    )
    decision = policy.select()
    assert decision.scaffold_id == "synthetic-neutral-scaffold"
    assert decision.consumes_misconception_beliefs is False
    assert decision.authorizes_learning_from_ig is False


def test_participation_reward_and_independent_evidence_are_separate_contracts() -> None:
    reward = ParticipationRewardContract(
        reward_id=UUID("32000000-0000-4000-8000-000000000001"),
        learner_id=LEARNER_ID,
        episode_id=EPISODE_ID,
        reward_type="synthetic-participation",
        amount=5,
        academic_mastery_evidence=False,
        awarded_at=AT,
    )
    evidence = IndependentEvidenceContract(
        evidence_id=UUID("32000000-0000-4000-8000-000000000002"),
        learner_id=LEARNER_ID,
        skill_id="synthetic-skill",
        presentation_id=PRESENTATION_ID,
        score_result_id=UUID("32000000-0000-4000-8000-000000000003"),
        measurement_role="unsupported_after",
        assistance_state="none",
        evidence_version="independent-evidence-v1",
        recorded_at=AT,
    )
    assert reward.academic_mastery_evidence is False
    assert evidence.measurement_role.value == "unsupported_after"


def test_external_evidence_requires_version_freshness_reliability_and_missingness() -> None:
    available = ExternalEvidenceContract(
        source="knowledge_tracing",
        source_version="kt-v1",
        observed_at=AT,
        expires_at=AT + timedelta(minutes=5),
        reliability=0.8,
        missing=False,
        value={"mastery_probability": 0.4},
    )
    assert available.missing is False
    with pytest.raises(ValidationError, match="requires value"):
        ExternalEvidenceContract(
            source="knowledge_tracing",
            source_version="kt-v1",
            observed_at=AT,
            expires_at=None,
            reliability=None,
            missing=False,
            value=None,
        )


def test_event_payload_is_type_specific_and_rejects_pii() -> None:
    original = event(1)
    serialized = original.model_dump_json()
    assert EventEnvelopeContract.model_validate_json(serialized) == original

    with pytest.raises(ValidationError, match="prohibited"):
        EventEnvelopeContract(
            **{
                **original.model_dump(),
                "payload": {
                    "item_revision_id": "synthetic-item-r1",
                    "measurement_role": "unsupported_before",
                    "name": "not-allowed",
                },
            }
        )

    with pytest.raises(ValidationError, match="bounded scalar"):
        EventEnvelopeContract(
            **{
                **original.model_dump(),
                "payload": {
                    "item_revision_id": {"nested": "not-allowed"},
                    "measurement_role": "unsupported_before",
                },
            }
        )
