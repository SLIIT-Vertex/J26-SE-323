from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.gamification.domain.types import AssistanceState, ExperimentMode, MeasurementRole
from app.gamification.modeling.independence_gain.phase3 import (
    FORMULA_VERSION,
    IndependenceMeasurement,
    PolicyUpdateStatus,
    ScoreTotal,
)
from app.gamification.modeling.misconception_inference.phase4 import replay_inference
from app.gamification.modeling.support_selection.phase5 import (
    ACTION_TYPES,
    CONTEXT_SCHEMA_VERSION,
    ArtifactLifecycle,
    ContextualScaffoldPolicy,
    DifficultyEvidence,
    EligibilityInput,
    EpisodeMetadata,
    EvaluationRow,
    ItemMetadata,
    Model2Artifact,
    Model2ArtifactRegistry,
    Model2ContextBuilder,
    Model2ContextInput,
    Model2Error,
    PolicyMode,
    PolicyProgression,
    PolicyStage,
    PriorScaffoldOutcome,
    RewardLinker,
    ScaffoldCandidate,
    SelectionKind,
    UnsupportedEvidence,
    delivery_failure_fallback,
    development_phase2_scaffolds,
    evaluate_context_ablation,
    evaluate_model2,
    evaluate_off_policy,
    run_phase5_simulation,
    time_split_evaluation_rows,
)
from tests.gamification.modeling.misconception_inference.test_phase4_model1 import (
    inference_input as model1_input,
)
from tests.gamification.modeling.misconception_inference.test_phase4_model1 import (
    model as model1_model,
)

AT = datetime(2026, 10, 15, 12, tzinfo=UTC)
LEARNER = UUID("00000000-0000-4000-8000-000000000501")
EPISODE = UUID("00000000-0000-4000-8000-000000000502")
PRESENTATION = UUID("00000000-0000-4000-8000-000000000503")
ARTIFACT_HASH = "5" * 64


def belief(**changes):
    _, result = replay_inference(
        replace(
            model1_input(),
            learner_id=LEARNER,
            episode_id=EPISODE,
            presentation_id=PRESENTATION,
            inference_at=AT - timedelta(seconds=3),
            evidence=(),
            recent_same_skill_errors=(),
            recent_error_evidence_ids=(),
            recent_errors_as_of=None,
        ),
        model1_model(),
    )
    return replace(result, **changes)


def unsupported(**changes) -> UnsupportedEvidence:
    values = {
        "evidence_id": uuid4(),
        "presentation_id": PRESENTATION,
        "episode_id": EPISODE,
        "observed_at": AT - timedelta(seconds=5),
        "measurement_role": MeasurementRole.UNSUPPORTED_BEFORE,
        "assistance_state": AssistanceState.NONE,
        "earned_score": Decimal(0),
        "maximum_score": Decimal(1),
        "attempt_count": 2,
        "error_persistence": 1,
        "item_revision_id": "G5-MAT-HALF-I01@v1",
    }
    values.update(changes)
    return UnsupportedEvidence(**values)


def context_input(**changes) -> Model2ContextInput:
    current = unsupported()
    values = {
        "learner_id": LEARNER,
        "pseudonymous": True,
        "grade": 5,
        "medium": "si",
        "skill_id": "G5-MAT-C03-L01-O01",
        "skill_version": "g5-mat-c03-l01-o01-v1",
        "episode_id": EPISODE,
        "presentation_id": PRESENTATION,
        "decision_at": AT,
        "current_unsupported": current,
        "recent_unsupported": (replace(current, evidence_id=uuid4()),),
        "difficulty": DifficultyEvidence(
            uuid4(), True, 0.8, "difficulty-trigger-v1", (uuid4(),), AT - timedelta(seconds=4)
        ),
        "belief": belief(),
        "prior_outcomes": (
            PriorScaffoldOutcome(
                uuid4(),
                uuid4(),
                "visual_guidance",
                Decimal("0.25"),
                AT - timedelta(days=1),
                FORMULA_VERSION,
                True,
            ),
        ),
        "recent_support_count": 1,
        "support_dependency_rate": 0.25,
        "support_dependency_as_of": AT - timedelta(minutes=5),
        "item": ItemMetadata(
            "G5-MAT-HALF-I01@v1",
            "g5-mat-half-items-v1",
            0.3,
            "single_choice",
            "choice_quest",
            "G5-MAT-HALF-PF01",
        ),
        "episode": EpisodeMetadata(
            "adaptive-episode-v1",
            ExperimentMode.PROPOSED,
            7,
            1,
            4,
            8,
            "G5-MAT-HALF-I03@v1",
            "G5-MAT-HALF-PF01",
        ),
        "optional_evidence": (),
        "extra_metadata": {"device_class_code": 1},
        "development_mode": True,
    }
    values.update(changes)
    return Model2ContextInput(**values)


def candidates() -> tuple[ScaffoldCandidate, ...]:
    return development_phase2_scaffolds(allow_draft=True)


def eligibility(*, child_facing: bool = False, allow_draft: bool = True):
    return EligibilityInput(("screen_reader",), allow_draft, child_facing)


def policy() -> ContextualScaffoldPolicy:
    return ContextualScaffoldPolicy(
        artifact_version="model2-synthetic-v1", artifact_sha256=ARTIFACT_HASH
    )


def decide(
    *,
    mode: PolicyMode = PolicyMode.PROPOSED_SHADOW,
    data: Model2ContextInput | None = None,
    rows: tuple[ScaffoldCandidate, ...] | None = None,
    gate: EligibilityInput | None = None,
    active_policy: ContextualScaffoldPolicy | None = None,
):
    return (active_policy or policy()).decide(
        mode=mode,
        context_input=data or context_input(),
        candidates=rows or candidates(),
        eligibility=gate or eligibility(),
        seed=17,
        assignment_token="synthetic-assignment-17",
    )


def test_context_is_versioned_complete_and_predecision() -> None:
    snapshot = Model2ContextBuilder().build(context_input())
    assert snapshot.schema_version == CONTEXT_SCHEMA_VERSION
    assert set(snapshot.values) >= {
        "unsupported_before_score",
        "recent_unsupported_mean",
        "attempt_count",
        "error_persistence",
        "difficulty_severity",
        "belief:whole_set_as_half",
        "belief:subtracts_two",
        "belief:unknown_or_other",
        "belief_confidence",
        "belief_entropy",
        "belief_abstained",
        "prior_ig:visual_guidance",
        "recent_support_count",
        "support_dependency",
        "item_difficulty",
        "format_single_choice",
        "template_hash",
        "episode_sequence",
    }
    assert snapshot.belief_snapshot_id is not None
    assert len(snapshot.evidence_ids) >= 4
    assert set(snapshot.feature_definitions) == set(snapshot.values)
    assert snapshot.provenance["difficulty"]["source_version"] == "difficulty-trigger-v1"


def test_baseline_requires_difficulty_but_not_model1_and_never_explores() -> None:
    data = context_input(
        belief=None,
        episode=replace(context_input().episode, experiment_mode=ExperimentMode.BASELINE),
    )
    _, decision = decide(mode=PolicyMode.DETERMINISTIC_BASELINE, data=data)
    assert decision.selection_kind is SelectionKind.BASELINE
    assert decision.selected_scaffold_id is not None
    assert sum(row.propensity for row in decision.candidates if row.eligible) == 1
    assert all(row.predicted_raw_ig is None for row in decision.candidates)
    assert "NO_IG_UPDATE" in decision.reason_codes

    no_trigger = replace(data, difficulty=replace(data.difficulty, detected=False))
    assert (
        decide(mode=PolicyMode.DETERMINISTIC_BASELINE, data=no_trigger)[1].mode
        is PolicyMode.SAFE_FALLBACK
    )
    with pytest.raises(Model2Error, match="experiment condition"):
        decide(mode=PolicyMode.PROPOSED_SHADOW, data=data)


def test_shadow_logs_every_candidate_prediction_and_does_not_control_delivery() -> None:
    active = policy()
    active.reward_count = 3
    data = context_input()
    first_context, first = decide(active_policy=active, data=data)
    second_context, second = decide(active_policy=active, data=data)
    assert first_context == second_context
    assert first == second
    assert len(first.candidates) == 3
    assert all(row.predicted_raw_ig is not None for row in first.candidates)
    assert sum(row.propensity for row in first.candidates if row.eligible) == pytest.approx(1)
    assert first.selection_kind is SelectionKind.SHADOW
    assert first.shadow_scaffold_id is not None
    assert first.selected_scaffold_id != "" and "SHADOW_REFERENCE_DELIVERY" in first.reason_codes


def test_offline_seeded_exploration_is_deterministic_and_normalized() -> None:
    active = policy()
    active.reward_count = 3
    data = context_input()
    _, first = decide(mode=PolicyMode.PROPOSED_OFFLINE, active_policy=active, data=data)
    _, second = decide(mode=PolicyMode.PROPOSED_OFFLINE, active_policy=active, data=data)
    assert first == second
    assert first.selection_kind in {SelectionKind.EXPLORE, SelectionKind.EXPLOIT}
    assert sum(row.propensity for row in first.candidates if row.eligible) == pytest.approx(1)
    assert all(0 <= row.propensity <= 1 for row in first.candidates)


def test_cold_start_abstention_and_high_unknown_use_conservative_reference() -> None:
    for altered in (
        context_input(),
        context_input(belief=belief(abstained=True, low_confidence=True)),
        context_input(
            belief=belief(
                probabilities={
                    "whole_set_as_half": 0.1,
                    "subtracts_two": 0.1,
                    "unknown_or_other": 0.8,
                },
                top_hypothesis="unknown_or_other",
                confidence=0.8,
                abstained=True,
                low_confidence=True,
            )
        ),
    ):
        _, decision = decide(mode=PolicyMode.PROPOSED_OFFLINE, data=altered)
        assert "CONSERVATIVE_COLD_OR_UNCERTAIN_REFERENCE" in decision.reason_codes
        assert sorted(row.propensity for row in decision.candidates) == [0.0, 0.0, 1.0]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda row: replace(row, skill_id="wrong"), "WRONG_SKILL"),
        (lambda row: replace(row, medium="ta"), "WRONG_MEDIUM"),
        (lambda row: replace(row, mapping_version="wrong"), "MAPPING_VERSION_MISMATCH"),
        (lambda row: replace(row, lifecycle_status="retired"), "RETIRED_SCAFFOLD"),
        (lambda row: replace(row, safety_status="unsafe"), "UNSAFE_SCAFFOLD"),
        (lambda row: replace(row, revision_id="bad@v2"), "WRONG_SCAFFOLD_VERSION"),
        (lambda row: replace(row, supported_accommodations=()), "ACCESSIBILITY_INCOMPATIBLE"),
        (lambda row: replace(row, maximum_steps=9), "ASSISTANCE_BUDGET_EXCEEDED"),
        (lambda row: replace(row, answer_revealing=True), "ANSWER_REVEALING"),
        (
            lambda row: replace(row, compatible_probe_family_ids=("wrong",)),
            "RESERVED_PROBE_INCOMPATIBLE",
        ),
        (
            lambda row: replace(row, compatible_protocol_versions=("wrong",)),
            "EPISODE_PROTOCOL_INCOMPATIBLE",
        ),
        (lambda row: replace(row, available_asset_ids=()), "REQUIRED_ASSET_UNAVAILABLE"),
        (lambda row: replace(row, disclosure_level=9), "DISCLOSURE_CEILING_EXCEEDED"),
    ],
)
def test_each_candidate_exclusion_is_logged(mutate, expected: str) -> None:
    rows = list(candidates())
    rows[0] = mutate(rows[0])
    _, decision = decide(rows=tuple(rows))
    excluded = next(row for row in decision.candidates if row.scaffold_id == rows[0].scaffold_id)
    assert not excluded.eligible
    assert expected in excluded.reason_codes
    assert excluded.propensity == 0


def test_draft_child_session_budget_and_no_action_exclusions_fallback() -> None:
    _, draft = decide(gate=eligibility(allow_draft=False))
    assert all("DRAFT_OVERRIDE_REQUIRED" in row.reason_codes for row in draft.candidates)
    assert draft.mode is PolicyMode.SAFE_FALLBACK

    _, child = decide(gate=eligibility(child_facing=True))
    assert all("UNAPPROVED_FOR_CHILD_DELIVERY" in row.reason_codes for row in child.candidates)

    data = context_input(episode=replace(context_input().episode, session_support_count=4))
    _, budget = decide(data=data)
    assert all("SESSION_BUDGET_EXCEEDED" in row.reason_codes for row in budget.candidates)
    assert budget.selected_scaffold_id is None


def test_missing_and_stale_external_context_are_explicit_and_safe() -> None:
    from app.gamification.modeling.misconception_inference.phase4 import OptionalEvidence

    missing = OptionalEvidence("knowledge_tracing", "kt-v1", None, None, None, None, True, True, {})
    stale = OptionalEvidence(
        "multimodal_learner_state",
        "state-v1",
        AT - timedelta(days=2),
        AT,
        0.8,
        "consent-ref",
        True,
        False,
        {"support_need": 0.7},
    )
    snapshot = Model2ContextBuilder().build(context_input(optional_evidence=(missing, stale)))
    assert snapshot.optional_freshness == {
        "knowledge_tracing": "missing",
        "multimodal_learner_state": "stale",
    }
    assert snapshot.missingness["optional:knowledge_tracing"]
    assert snapshot.missingness["optional:multimodal_learner_state"]


@pytest.mark.parametrize(
    "change",
    [
        {"current_unsupported": unsupported(observed_at=AT + timedelta(seconds=1))},
        {"difficulty": DifficultyEvidence(uuid4(), True, 0.5, "v1", (), AT + timedelta(seconds=1))},
        {"support_dependency_as_of": AT + timedelta(seconds=1)},
        {
            "prior_outcomes": (
                PriorScaffoldOutcome(
                    uuid4(),
                    uuid4(),
                    "visual_guidance",
                    Decimal("0.1"),
                    AT + timedelta(seconds=1),
                    FORMULA_VERSION,
                    True,
                ),
            )
        },
        {"extra_metadata": {"answer_key": 1}},
        {"extra_metadata": {"camera_frame": 1}},
    ],
)
def test_future_postdecision_answer_and_personal_leakage_is_rejected(change) -> None:
    with pytest.raises(Model2Error, match="future|forbidden"):
        Model2ContextBuilder().build(context_input(**change))


def test_learned_child_control_and_default_draft_composition_are_blocked() -> None:
    with pytest.raises(PermissionError, match="allow_draft"):
        development_phase2_scaffolds()
    _, decision = decide(
        mode=PolicyMode.LEARNED_DELIVERY,
        gate=eligibility(child_facing=True),
    )
    assert decision.mode is PolicyMode.SAFE_FALLBACK
    assert "LEARNED_CHILD_CONTROL_BLOCKED" in " ".join(decision.reason_codes) or all(
        "UNAPPROVED_FOR_CHILD_DELIVERY" in row.reason_codes for row in decision.candidates
    )

    progression = PolicyProgression().advance(
        PolicyStage.SHADOW, evidence_reference="sha256:synthetic-shadow-evidence"
    )
    progression = progression.advance(
        PolicyStage.CONSTRAINED_OFFLINE,
        evidence_reference="sha256:synthetic-offline-evidence",
    )
    with pytest.raises(PermissionError, match="exact-hash"):
        progression.advance(
            PolicyStage.LEARNED_CHILD_CONTROL,
            evidence_reference="sha256:synthetic-not-approval",
        )


def test_delivery_failure_becomes_neutral_logged_fallback() -> None:
    source = context_input()
    data = replace(
        source,
        episode=replace(source.episode, experiment_mode=ExperimentMode.BASELINE),
    )
    _, decision = decide(mode=PolicyMode.DETERMINISTIC_BASELINE, data=data)
    failed = delivery_failure_fallback(
        decision, failed_at=AT + timedelta(seconds=1), reason_code="ASSET_TIMEOUT"
    )
    assert failed.selected_scaffold_id is None
    assert failed.mode is PolicyMode.SAFE_FALLBACK
    assert "DELIVERY_FAILURE:ASSET_TIMEOUT" in failed.reason_codes


def measurement(decision_id: UUID, **changes) -> IndependenceMeasurement:
    values = {
        "measurement_id": uuid4(),
        "episode_id": EPISODE,
        "decision_id": decision_id,
        "before": ScoreTotal((uuid4(),), Decimal(0), Decimal(1)),
        "after": ScoreTotal((uuid4(),), Decimal("0.5"), Decimal(1)),
        "raw_independence_gain": Decimal("0.5"),
        "percentage_point_value": Decimal(50),
        "formula_version": FORMULA_VERSION,
        "scoring_versions": ("scoring-v1",),
        "rubric_versions": ("rubric-v1",),
        "equivalence_version": "g5-mat-half-equivalence-v1",
        "valid": True,
        "exclusion_reasons": (),
        "policy_update_status": PolicyUpdateStatus.AUTHORIZED_DELAYED,
        "measurement_version": "independence-measurement-v1",
        "calculated_at": AT + timedelta(minutes=1),
    }
    values.update(changes)
    return IndependenceMeasurement(**values)


def test_valid_delayed_raw_ig_updates_once_and_preserves_exact_value() -> None:
    active = policy()
    active.reward_count = 3
    context, decision = decide(mode=PolicyMode.PROPOSED_OFFLINE, active_policy=active)
    assert context is not None
    result = measurement(decision.decision_id)
    linker = RewardLinker()
    link = linker.link(
        decision,
        result,
        context=context,
        policy=active,
        linked_at=AT + timedelta(minutes=2),
        expected_artifact_sha256=ARTIFACT_HASH,
    )
    assert link.raw_independence_gain == Decimal("0.5")
    assert (
        linker.link(
            decision,
            result,
            context=context,
            policy=active,
            linked_at=AT + timedelta(minutes=2),
            expected_artifact_sha256=ARTIFACT_HASH,
        )
        == link
    )
    with pytest.raises(Model2Error, match="DUPLICATE_REWARD_CONFLICT"):
        linker.link(
            decision,
            replace(result, raw_independence_gain=Decimal("0.4")),
            context=context,
            policy=active,
            linked_at=AT + timedelta(minutes=2),
        )
    with pytest.raises(Model2Error, match="DUPLICATE_REWARD_CONFLICT"):
        linker.link(
            decision,
            measurement(decision.decision_id),
            context=context,
            policy=active,
            linked_at=AT + timedelta(minutes=2),
        )


@pytest.mark.parametrize(
    ("decision_change", "measurement_change", "kwargs", "expected"),
    [
        ({"experiment_mode": ExperimentMode.BASELINE}, {}, {}, "BASELINE_REWARD"),
        (
            {},
            {
                "valid": False,
                "raw_independence_gain": None,
                "percentage_point_value": None,
                "policy_update_status": PolicyUpdateStatus.NOT_AUTHORIZED_INVALID,
                "exclusion_reasons": ("CONTAMINATED",),
            },
            {},
            "INVALID_OR_UNAUTHORIZED",
        ),
        ({}, {"decision_id": uuid4()}, {}, "WRONG_DECISION"),
        ({"policy_version": "wrong"}, {}, {}, "WRONG_POLICY_VERSION"),
        ({}, {"formula_version": "wrong"}, {}, "WRONG_REWARD_FORMULA"),
        ({}, {}, {"expected_context_version": "wrong"}, "WRONG_CONTEXT_VERSION"),
        ({}, {}, {"expected_artifact_sha256": "9" * 64}, "WRONG_ARTIFACT_VERSION"),
    ],
)
def test_invalid_baseline_and_wrong_version_rewards_are_rejected(
    decision_change, measurement_change, kwargs, expected
) -> None:
    active = policy()
    active.reward_count = 3
    context, decision = decide(mode=PolicyMode.PROPOSED_OFFLINE, active_policy=active)
    assert context is not None
    changed_decision = replace(decision, **decision_change)
    measurement_values = dict(measurement_change)
    reward_decision_id = measurement_values.pop("decision_id", decision.decision_id)
    result = measurement(reward_decision_id, **measurement_values)
    with pytest.raises(Model2Error, match=expected):
        RewardLinker().link(
            changed_decision,
            result,
            context=context,
            policy=active,
            linked_at=AT + timedelta(minutes=2),
            **kwargs,
        )


def test_wrong_model_feature_and_catalogue_versions_are_rejected() -> None:
    for changed in (
        belief(model_version="wrong"),
        belief(feature_schema_version="wrong"),
        belief(mapping_version="wrong"),
    ):
        with pytest.raises(Model2Error, match="Model 1"):
            Model2ContextBuilder().build(context_input(belief=changed))


def test_artifact_hash_shadow_retire_rollback_and_activation_block() -> None:
    with pytest.raises(PermissionError, match="data-authorization"):
        Model2Artifact.create(
            artifact_version="model2-unapproved-real-v1",
            dataset_manifest_sha256="a" * 64,
            evaluation_sha256="b" * 64,
            seed=17,
            parameters={},
            synthetic=False,
        )
    artifact = Model2Artifact.create(
        artifact_version="model2-synthetic-v1",
        dataset_manifest_sha256="a" * 64,
        evaluation_sha256="b" * 64,
        seed=17,
        parameters={"linucb": {"ridge": 1.0}},
        synthetic=True,
    )
    artifact.verify()
    registry = Model2ArtifactRegistry()
    registry.register(artifact)
    registry.activate_shadow(artifact.artifact_sha256)
    assert registry.active_shadow == artifact
    registry.rollback_shadow(artifact.artifact_sha256)
    with pytest.raises(PermissionError, match="exact-hash"):
        registry.activate_learned_delivery(artifact.artifact_sha256, authorization=None)
    registry.retire(artifact.artifact_sha256)
    assert registry.active_shadow is None
    with pytest.raises(Model2Error, match="retired"):
        registry.rollback_shadow(artifact.artifact_sha256)
    assert ArtifactLifecycle.APPROVED.value == "approved"


def evaluation_rows() -> tuple[EvaluationRow, ...]:
    return tuple(
        EvaluationRow(
            episode_id=f"ep-{index}",
            action=ACTION_TYPES[index % 3],
            mode="proposed_offline",
            predicted_ig=(-0.2, 0.0, 0.4)[index % 3],
            observed_raw_ig=(-0.1, 0.0, 0.5)[index % 3],
            valid=True,
            propensity=0.5,
            explored=index % 2 == 0,
            fallback=False,
            support_dependency=0.2,
            delivery_failed=False,
            ranking_group=f"cohort-{index // 3}",
            decision_at=AT + timedelta(minutes=index - 3),
        )
        for index in range(6)
    )


def test_synthetic_evaluation_and_simulation_are_deterministic_and_labelled() -> None:
    report = evaluate_model2(evaluation_rows(), authorized_real_data=False)
    assert report.evidence_status == "synthetic_engineering_only"
    assert report.valid_sample_count == 6
    assert set(report.mean_valid_raw_ig_by_action) == set(ACTION_TYPES)
    assert report.action_coverage == 1
    assert report.propensity_integrity
    assert report.pairwise_ranking_agreement == 1
    assert report.approval_statuses == ("draft_not_child_approved",)
    assert report.mean_valid_raw_ig_by_skill == {
        "g5-mat-c03-l01-o01-v1": pytest.approx(0.13333333333333333)
    }
    with pytest.raises(PermissionError, match="authorization reference"):
        evaluate_model2(evaluation_rows(), authorized_real_data=True)
    assert run_phase5_simulation(seed=31) == run_phase5_simulation(seed=31)
    simulation = run_phase5_simulation(seed=31)
    assert simulation["synthetic"] is True
    assert set(simulation["scenarios"]) >= {
        "cold_start",
        "sparse_actions",
        "missing_model1",
        "model1_abstention",
        "positive_zero_negative_ig",
        "invalid_outcome",
        "action_imbalance",
    }
    assert set(simulation["baselines"]) == {
        "deterministic_educator_authored",
        "random_safe_simulation_only",
        "skill_only_authored",
        "proposed_without_model1_ablation",
    }
    assert simulation["best_action_recovery_rate"] == 1

    active = policy()
    snapshot = Model2ContextBuilder().build(context_input())
    assert evaluate_context_ablation(active, snapshot) == evaluate_context_ablation(
        active, snapshot
    )
    split = time_split_evaluation_rows(evaluation_rows(), cutoff=AT)
    assert len(split.training) == 3
    assert len(split.evaluation) == 3


def test_off_policy_evaluation_refuses_missing_degenerate_and_unsupported_logs() -> None:
    rows = evaluation_rows()
    target = {(row.episode_id, row.action): 0.5 for row in rows} | {
        (row.episode_id, "other"): 0.5 for row in rows
    }
    estimate = evaluate_off_policy(rows, target)
    assert estimate.sample_count == 6
    assert estimate.doubly_robust is None
    with pytest.raises(Model2Error, match="nondegenerate"):
        evaluate_off_policy(tuple(replace(row, propensity=None) for row in rows), target)
    with pytest.raises(Model2Error, match="normalize"):
        evaluate_off_policy(rows, {(row.episode_id, row.action): 0.4 for row in rows})
    unsupported = {(row.episode_id, "other"): 1.0 for row in rows}
    with pytest.raises(Model2Error, match="support assumption"):
        evaluate_off_policy(rows, unsupported)
    with pytest.raises(Model2Error, match="complete reward estimates"):
        evaluate_off_policy(rows, target, reward_estimates={})
