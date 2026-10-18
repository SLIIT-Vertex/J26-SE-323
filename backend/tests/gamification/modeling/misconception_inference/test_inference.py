from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.gamification.domain.types import AssistanceState, MeasurementRole
from app.gamification.modeling.misconception_inference.inference import (
    CATALOGUE_CODES,
    CATALOGUE_VERSION,
    FEATURE_SCHEMA_VERSION,
    MODEL_VERSION,
    AuthoredPriorBaseline,
    InferenceEvidence,
    InteractionSummary,
    Model1Artifact,
    Model1ArtifactRegistry,
    Model1DatasetManifest,
    Model1DatasetRow,
    Model1Error,
    Model1FeatureBuilder,
    Model1InferenceInput,
    OptionalEvidence,
    candidate_from_artifact,
    development_curriculum_candidate,
    evaluate_model1,
    fit_model1_candidate,
    replay_inference,
)

AT = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
LEARNER = UUID("00000000-0000-4000-8000-000000000401")
EPISODE = UUID("00000000-0000-4000-8000-000000000402")
PRESENTATION = UUID("00000000-0000-4000-8000-000000000403")
ARTIFACT_HASH = "a" * 64


def evidence(**changes: object) -> InferenceEvidence:
    values: dict[str, object] = {
        "evidence_id": uuid4(),
        "event_ids": (uuid4(),),
        "attempt_id": uuid4(),
        "episode_id": EPISODE,
        "presentation_id": PRESENTATION,
        "item_revision_id": "G5-MAT-HALF-I01@v1",
        "content_version": "g5-mat-half-items-v1",
        "observed_at": AT - timedelta(seconds=1),
        "measurement_role": MeasurementRole.UNSUPPORTED_BEFORE,
        "assistance_state": AssistanceState.NONE,
        "earned_score": 0.0,
        "maximum_score": 1.0,
        "selected_response": "A",
        "distractor_misconception_code": "subtracts_two",
        "structured_error_code": "subtracts_two",
        "attempt_number": 1,
        "active_response_ms": 1_500,
        "wall_clock_ms": 2_000,
        "inactivity_ms": 500,
        "interactions": InteractionSummary(changes=1, moves=2),
        "quality": "high",
    }
    values.update(changes)
    return InferenceEvidence(**values)  # type: ignore[arg-type]


def inference_input(**changes: object) -> Model1InferenceInput:
    values: dict[str, object] = {
        "learner_id": LEARNER,
        "pseudonymous": True,
        "grade": 5,
        "medium": "si",
        "skill_id": "G5-MAT-C03-L01-O01",
        "skill_version": "g5-mat-c03-l01-o01-v1",
        "episode_id": EPISODE,
        "presentation_id": PRESENTATION,
        "item_revision_id": "G5-MAT-HALF-I01@v1",
        "inference_at": AT,
        "evidence_window_version": "model1-window-v1",
        "evidence": (evidence(),),
        "recent_same_skill_errors": ("subtracts_two",),
        "recent_error_evidence_ids": (uuid4(),),
        "recent_errors_as_of": AT - timedelta(seconds=2),
        "previous_beliefs": {},
        "previous_belief_snapshot_id": None,
        "previous_belief_at": None,
        "optional_evidence": (),
        "mapping_version": CATALOGUE_VERSION,
        "model_version": MODEL_VERSION,
        "development_mode": True,
    }
    values.update(changes)
    return Model1InferenceInput(**values)  # type: ignore[arg-type]


def model():
    return development_curriculum_candidate(artifact_sha256=ARTIFACT_HASH, allow_draft=True)


def test_complete_normalized_distribution_and_non_definitive_distractor() -> None:
    snapshot, belief = replay_inference(inference_input(), model())
    assert snapshot.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert snapshot.values["interaction_move_ratio"] == pytest.approx(2 / 3)
    assert snapshot.values["recent_error_count:subtracts_two"] == 1
    assert tuple(belief.probabilities) == CATALOGUE_CODES
    assert sum(belief.probabilities.values()) == pytest.approx(1.0, abs=1e-12)
    assert all(math.isfinite(value) and value >= 0 for value in belief.probabilities.values())
    assert 0 < belief.probabilities["subtracts_two"] < 1
    assert belief.evidence_event_ids
    assert belief.attempt_ids


def test_zero_missing_sparse_and_low_quality_evidence_safely_abstains() -> None:
    empty = inference_input(
        evidence=(),
        recent_same_skill_errors=(),
        recent_error_evidence_ids=(),
        recent_errors_as_of=None,
    )
    snapshot, belief = replay_inference(empty, model())
    assert snapshot.values["evidence_count"] == 0
    assert belief.top_hypothesis == "unknown_or_other"
    assert belief.probabilities["unknown_or_other"] == pytest.approx(0.8)
    assert belief.abstained and belief.low_confidence
    assert not belief.narrow_exploitation_allowed

    low = inference_input(evidence=(evidence(quality="low"),))
    assert replay_inference(low, model())[1].abstained


def test_contradictory_evidence_prioritizes_unknown() -> None:
    row = evidence(
        distractor_misconception_code="subtracts_two",
        structured_error_code="whole_set_as_half",
    )
    belief = replay_inference(inference_input(evidence=(row,)), model())[1]
    assert belief.top_hypothesis == "unknown_or_other"
    assert "CONTRADICTORY_EVIDENCE" in belief.reason_codes


@pytest.mark.parametrize(
    "changes",
    [
        {"earned_score": float("nan")},
        {"maximum_score": 0.0},
        {"active_response_ms": -1},
        {"quality": "invented"},
    ],
)
def test_malformed_evidence_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(Model1Error):
        evidence(**changes)


@pytest.mark.parametrize(
    "beliefs",
    [
        {"whole_set_as_half": float("nan"), "subtracts_two": 0.0, "unknown_or_other": 1.0},
        {"whole_set_as_half": -0.1, "subtracts_two": 0.1, "unknown_or_other": 1.0},
        {"whole_set_as_half": 0.1, "subtracts_two": 0.1, "unknown_or_other": 0.1},
    ],
)
def test_malformed_prior_distributions_are_rejected(beliefs: dict[str, float]) -> None:
    with pytest.raises(Model1Error, match="normalized finite"):
        Model1FeatureBuilder().build(
            inference_input(
                previous_beliefs=beliefs,
                previous_belief_snapshot_id=uuid4(),
                previous_belief_at=AT - timedelta(seconds=2),
            )
        )


def test_optional_evidence_missing_stale_and_fresh_provenance() -> None:
    missing = OptionalEvidence(
        "knowledge_tracing", "kt-v1", None, None, None, None, True, True, {}
    )
    stale = OptionalEvidence(
        "multimodal_learner_state", "ls-v1", AT - timedelta(days=2), AT,
        0.8, "consent-ref", True, False, {"support_need": 0.7}
    )
    fresh = OptionalEvidence(
        "prerequisite_skill", "prereq-v1", AT - timedelta(minutes=1), AT + timedelta(minutes=1),
        0.9, "consent-ref", True, False, {"mastery": 0.6}
    )
    snapshot = Model1FeatureBuilder().build(
        inference_input(optional_evidence=(missing, stale, fresh))
    )
    assert snapshot.optional_freshness == {
        "knowledge_tracing": "missing",
        "multimodal_learner_state": "stale",
        "prerequisite_skill": "fresh",
    }
    assert snapshot.missingness["optional:knowledge_tracing"]
    assert snapshot.missingness["optional:multimodal_learner_state"]
    assert not snapshot.missingness["optional:prerequisite_skill"]


def test_optional_ownership_port_envelope_preserves_missingness() -> None:
    from app.gamification.application.ownership_ports import ExternalEvidence

    port_value = ExternalEvidence(
        source="accessibility_accommodation",
        source_version="access-v1",
        observed_at=None,
        expires_at=None,
        reliability=None,
        missing=True,
    )
    optional = OptionalEvidence.from_ownership_port(port_value)
    assert optional.missing
    assert optional.values == {}


def test_assistance_and_measurement_role_are_preserved_not_merged() -> None:
    supported = evidence(
        measurement_role=MeasurementRole.SUPPORTED_PRACTICE,
        assistance_state=AssistanceState.SCAFFOLD_ACTIVE,
    )
    snapshot = Model1FeatureBuilder().build(inference_input(evidence=(supported,)))
    assert snapshot.values["measurement_role"] == "supported_practice"
    assert snapshot.values["assistance_state"] == "scaffold_active"
    belief = model().predict(snapshot)
    assert "ASSISTED_EVIDENCE_PRESERVED" in belief.reason_codes


@pytest.mark.parametrize(
    "change",
    [
        {"evidence": (evidence(measurement_role=MeasurementRole.UNSUPPORTED_AFTER),)},
        {"evidence": (evidence(observed_at=AT + timedelta(seconds=1)),)},
        {"recent_same_skill_errors": ("independence_gain",)},
        {"previous_beliefs": {"policy_reward": 1.0}},
    ],
)
def test_future_and_post_decision_leakage_is_rejected(change: dict[str, object]) -> None:
    if "previous_beliefs" in change:
        change |= {
            "previous_belief_snapshot_id": uuid4(),
            "previous_belief_at": AT - timedelta(seconds=2),
        }
    with pytest.raises(Model1Error, match="forbidden|catalogue"):
        Model1FeatureBuilder().build(inference_input(**change))


def test_future_prior_and_recent_summary_provenance_is_rejected() -> None:
    with pytest.raises(Model1Error, match="future previous-belief"):
        Model1FeatureBuilder().build(
            inference_input(
                previous_beliefs={
                    "whole_set_as_half": 0.2,
                    "subtracts_two": 0.3,
                    "unknown_or_other": 0.5,
                },
                previous_belief_snapshot_id=uuid4(),
                previous_belief_at=AT + timedelta(seconds=1),
            )
        )
    with pytest.raises(Model1Error, match="future recent-error"):
        Model1FeatureBuilder().build(
            inference_input(recent_errors_as_of=AT + timedelta(seconds=1))
        )


def test_future_optional_evidence_and_forbidden_optional_fields_are_rejected() -> None:
    future = OptionalEvidence(
        "knowledge_tracing", "kt-v1", AT + timedelta(seconds=1), None,
        0.8, "consent", True, False, {"mastery": 0.5}
    )
    with pytest.raises(Model1Error, match="future optional"):
        Model1FeatureBuilder().build(inference_input(optional_evidence=(future,)))
    leaking = OptionalEvidence(
        "knowledge_tracing", "kt-v1", AT - timedelta(seconds=1), None,
        0.8, "consent", True, False, {"independence_gain": 1.0}
    )
    with pytest.raises(Model1Error, match="post-decision optional"):
        Model1FeatureBuilder().build(inference_input(optional_evidence=(leaking,)))


def test_replay_is_deterministic_for_identical_input_version_and_artifact() -> None:
    data = inference_input()
    first = replay_inference(data, model())
    second = replay_inference(data, model())
    assert first == second


def test_catalogue_and_mapping_version_mismatch_are_rejected_or_abstain() -> None:
    with pytest.raises(Model1Error, match="mapping version"):
        Model1FeatureBuilder().build(inference_input(mapping_version="wrong"))
    snapshot = Model1FeatureBuilder().build(inference_input())
    mismatched = development_curriculum_candidate(
        artifact_sha256=ARTIFACT_HASH, allow_draft=True
    )
    mismatched.mapping_version = "wrong"
    belief = mismatched.predict(snapshot)
    assert belief.probabilities["unknown_or_other"] == pytest.approx(0.8)
    assert belief.abstained


def synthetic_rows() -> tuple[Model1DatasetRow, ...]:
    rows: list[Model1DatasetRow] = []
    for index, label in enumerate((*CATALOGUE_CODES, *CATALOGUE_CODES)):
        probabilities = {code: 0.1 for code in CATALOGUE_CODES}
        probabilities[label] = 0.8
        rows.append(
            Model1DatasetRow(
                learner_id=f"synthetic-{index}",
                skill_id="G5-MAT-C03-L01-O01",
                label=label,
                score_ratio=0.0,
                structured_error_code=label,
                probabilities=probabilities,
                abstained=label == "unknown_or_other",
            )
        )
    return tuple(rows)


def test_manifest_artifact_hash_shadow_activation_and_rollback() -> None:
    manifest = Model1DatasetManifest.build(
        synthetic_rows(), dataset_id="misconception_inference-synthetic-v1", split_seed=17,
        synthetic=True, authorized_expert_labels=False
    )
    manifest.assert_disjoint()
    assert manifest == Model1DatasetManifest.build(
        synthetic_rows(), dataset_id="misconception_inference-synthetic-v1", split_seed=17,
        synthetic=True, authorized_expert_labels=False
    )
    first = Model1Artifact.create(manifest, seed=17, parameters={"prior": [0.25, 0.25, 0.5]})
    second = Model1Artifact.create(manifest, seed=18, parameters={"prior": [0.2, 0.2, 0.6]})
    first.verify()
    with pytest.raises(Model1Error, match="hash"):
        replace(first, parameters={"tampered": True}).verify()
    registry = Model1ArtifactRegistry()
    registry.register(first)
    registry.register(second)
    registry.activate_shadow(second.artifact_sha256)
    assert registry.active_shadow == second
    registry.rollback_shadow(first.artifact_sha256)
    assert registry.active_shadow == first
    with pytest.raises(PermissionError, match="human approval"):
        registry.activate_for_child_delivery(first.artifact_sha256)
    assert "synthetic_development" in first.model_card()


def test_fitting_is_reproducible_train_split_only_and_draft_gated() -> None:
    rows = synthetic_rows()
    manifest = Model1DatasetManifest.build(
        rows,
        dataset_id="misconception_inference-synthetic-fit-v1",
        split_seed=19,
        synthetic=True,
        authorized_expert_labels=False,
    )
    first = fit_model1_candidate(rows, manifest, seed=23)
    second = fit_model1_candidate(rows, manifest, seed=23)
    assert first == second
    assert first.parameters["training_row_count"] < len(rows)
    with pytest.raises(PermissionError, match="allow_draft"):
        candidate_from_artifact(first)
    candidate = candidate_from_artifact(first, allow_draft=True)
    belief = replay_inference(inference_input(), candidate)[1]
    assert sum(belief.probabilities.values()) == pytest.approx(1.0)
    with pytest.raises(Model1Error, match="frozen manifest"):
        fit_model1_candidate(rows[:-1], manifest, seed=23)


def test_synthetic_evaluation_is_labelled_development_only_and_has_three_baselines() -> None:
    report = evaluate_model1(synthetic_rows(), authorized_expert_labels=False)
    assert report == evaluate_model1(synthetic_rows(), authorized_expert_labels=False)
    assert report.evidence_status == "synthetic_development_only"
    assert report.sample_count == 6
    assert report.log_loss >= 0
    assert report.brier_score >= 0
    assert report.calibration_error >= 0
    assert report.reliability_bins
    assert report.top_k_agreement == 1
    assert set(report.per_class_recall) == set(CATALOGUE_CODES)
    assert set(report.confusion_matrix) == set(CATALOGUE_CODES)
    assert report.results_by_skill["G5-MAT-C03-L01-O01"]["approval_status"] == (
        "synthetic_development_only"
    )
    assert set(report.baselines) == {
        "most_frequent_per_skill",
        "deterministic_authored_error_mapping",
        "performance_only",
    }
    assert report.reviewer_agreement is None
    assert not report.adjudication_evidence_present


def test_authorized_evaluation_cannot_omit_review_agreement_or_adjudication() -> None:
    with pytest.raises(Model1Error, match="reviewer agreement"):
        evaluate_model1(synthetic_rows(), authorized_expert_labels=True)
    report = evaluate_model1(
        synthetic_rows(),
        authorized_expert_labels=True,
        reviewer_agreement=0.8,
        adjudication_evidence_present=True,
    )
    assert report.evidence_status == "authorized_expert_labelled"
    assert report.reviewer_agreement == pytest.approx(0.8)


def test_child_payload_excludes_technical_labels_and_probabilities() -> None:
    belief = replay_inference(inference_input(), model())[1]
    payload = belief.child_payload()
    serialized = str(dict(payload))
    assert all(code not in serialized for code in CATALOGUE_CODES)
    assert "probab" not in serialized.lower()


@pytest.mark.parametrize("change", [{"grade": 4}, {"medium": "ta"}, {"medium": "en"}])
def test_grade4_and_non_sinhala_active_content_are_rejected(change: dict[str, object]) -> None:
    with pytest.raises(Model1Error):
        inference_input(**change)


def test_curriculum_draft_requires_explicit_development_composition() -> None:
    with pytest.raises(PermissionError, match="allow_draft"):
        development_curriculum_candidate(artifact_sha256=ARTIFACT_HASH)


def test_authored_prior_baseline_is_complete_and_unknown_first() -> None:
    snapshot = Model1FeatureBuilder().build(inference_input())
    belief = AuthoredPriorBaseline().predict(snapshot, artifact_sha256=ARTIFACT_HASH)
    assert tuple(belief.probabilities) == CATALOGUE_CODES
    assert belief.top_hypothesis == "unknown_or_other"
    assert belief.abstained
