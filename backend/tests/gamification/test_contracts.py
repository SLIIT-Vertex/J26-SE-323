from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.gamification.api.contracts import (
    BOUNDARY_CONTRACT_VERSION,
    ConsentDecisionContract,
    EpisodeStateContract,
    FeatureSnapshotContract,
    IndependenceOutcomeContract,
    PolicyCandidateContract,
    PolicyDecisionContract,
    SkillMasterySnapshot,
    SupportAssetRequestContract,
)


def mastery_snapshot_data() -> dict[str, object]:
    return {
        "contract_version": BOUNDARY_CONTRACT_VERSION,
        "learner_id": str(uuid4()),
        "skill_id": "skill-provisional-01",
        "skill_taxonomy_version": "provisional-v1",
        "mastery_probability": 0.5,
        "uncertainty": 0.2,
        "model_version": "gamification-mastery-v1",
        "observed_at": "2026-10-13T09:00:00Z",
    }


def test_contract_rejects_unknown_fields() -> None:
    data = mastery_snapshot_data()
    data["raw_child_answer"] = "must-not-be-accepted"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SkillMasterySnapshot.model_validate(data)


@pytest.mark.parametrize("field", ["mastery_probability", "uncertainty"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_probability_ranges_are_strict(field: str, value: float) -> None:
    data = mastery_snapshot_data()
    data[field] = value

    with pytest.raises(ValidationError):
        SkillMasterySnapshot.model_validate(data)


def test_numeric_contract_fields_do_not_coerce_strings() -> None:
    data = mastery_snapshot_data()
    data["mastery_probability"] = "0.5"

    with pytest.raises(ValidationError):
        SkillMasterySnapshot.model_validate(data)


def test_timestamps_must_include_an_offset() -> None:
    data = mastery_snapshot_data()
    data["observed_at"] = "2026-10-13T09:00:00"

    with pytest.raises(ValidationError):
        SkillMasterySnapshot.model_validate(data)


@pytest.mark.parametrize("version", ["", "V1", "gamification-boundary", "bad version-v1"])
def test_contract_version_has_explicit_version_shape(version: str) -> None:
    data = mastery_snapshot_data()
    data["contract_version"] = version

    with pytest.raises(ValidationError):
        SkillMasterySnapshot.model_validate(data)


def test_consent_expiry_must_follow_decision() -> None:
    with pytest.raises(ValidationError, match="expires_at must be later"):
        ConsentDecisionContract.model_validate(
            {
                "contract_version": BOUNDARY_CONTRACT_VERSION,
                "learner_id": str(uuid4()),
                "purpose": "adaptive-learning",
                "granted": True,
                "consent_version": "consent-v1",
                "decided_at": "2026-10-13T09:00:00Z",
                "expires_at": "2026-10-13T08:00:00Z",
            }
        )


def test_misconception_beliefs_must_be_unique_and_sum_to_one() -> None:
    base = {
        "contract_version": BOUNDARY_CONTRACT_VERSION,
        "learner_id": str(uuid4()),
        "skill_id": "skill-provisional-01",
        "skill_taxonomy_version": "provisional-v1",
        "action_type": "conceptual_hint",
        "misconception_catalogue_version": "misconceptions-v1",
        "approved_evidence_ids": [],
        "prohibited_content": ["current-answer", "answer-equivalent"],
    }
    with pytest.raises(ValidationError, match="must sum to 1"):
        SupportAssetRequestContract.model_validate(
            {
                **base,
                "beliefs": [
                    {"misconception_id": "m1", "probability": 0.4},
                    {"misconception_id": "unknown", "probability": 0.4},
                ],
            }
        )

    with pytest.raises(ValidationError, match="must be unique"):
        SupportAssetRequestContract.model_validate(
            {
                **base,
                "beliefs": [
                    {"misconception_id": "m1", "probability": 0.5},
                    {"misconception_id": "m1", "probability": 0.5},
                ],
            }
        )


def test_policy_decision_requires_complete_probability_distribution() -> None:
    candidate = PolicyCandidateContract(
        action_id="hint-1",
        action_type="conceptual_hint",
        propensity=0.8,
        eligible=True,
        reason_codes=("ELIGIBLE",),
    )

    with pytest.raises(ValidationError, match="must sum to 1"):
        PolicyDecisionContract(
            contract_version=BOUNDARY_CONTRACT_VERSION,
            decision_id=uuid4(),
            feature_snapshot_id=uuid4(),
            selected_action_id="hint-1",
            mode="deterministic_reference",
            policy_version="reference-v1",
            support_catalogue_version="support-v1",
            candidates=(candidate,),
            reason_codes=("REFERENCE_POLICY",),
            decided_at=datetime(2026, 10, 13, tzinfo=UTC),
        )


def test_policy_decision_rejects_ineligible_selection() -> None:
    candidates = (
        PolicyCandidateContract(
            action_id="hint-1",
            action_type="conceptual_hint",
            propensity=1.0,
            eligible=True,
            reason_codes=("ELIGIBLE",),
        ),
        PolicyCandidateContract(
            action_id="hint-2",
            action_type="targeted_hint",
            propensity=0.0,
            eligible=False,
            reason_codes=("LANGUAGE_UNAVAILABLE",),
        ),
    )

    with pytest.raises(ValidationError, match="selected action must be an eligible"):
        PolicyDecisionContract(
            contract_version=BOUNDARY_CONTRACT_VERSION,
            decision_id=uuid4(),
            feature_snapshot_id=uuid4(),
            selected_action_id="hint-2",
            mode="deterministic_reference",
            policy_version="reference-v1",
            support_catalogue_version="support-v1",
            candidates=candidates,
            reason_codes=("REFERENCE_POLICY",),
            decided_at=datetime(2026, 10, 13, tzinfo=UTC),
        )


def test_feature_snapshot_is_frozen_and_bounded() -> None:
    snapshot = FeatureSnapshotContract(
        contract_version=BOUNDARY_CONTRACT_VERSION,
        snapshot_id=uuid4(),
        learner_id=uuid4(),
        skill_id="skill-provisional-01",
        captured_at=datetime(2026, 10, 13, tzinfo=UTC),
        protocol_version="adaptive-episode-v1",
        taxonomy_version="provisional-v1",
        feature_definition_version="feature-v1",
        values={"mastery": 0.5, "learner_state_missing": True},
    )

    with pytest.raises(ValidationError):
        snapshot.skill_id = "other"


def test_valid_outcome_requires_two_unsupported_measurements() -> None:
    with pytest.raises(ValidationError, match="unsupported baseline and verification"):
        IndependenceOutcomeContract(
            contract_version=BOUNDARY_CONTRACT_VERSION,
            outcome_id=uuid4(),
            episode_id=uuid4(),
            validity="valid",
            formula_version="independence-gain-v1",
            baseline_support_state="supported",
            verification_support_state="unsupported",
            independence_gain=0.25,
            recorded_at=datetime(2026, 10, 13, tzinfo=UTC),
        )


def test_invalid_outcome_requires_reason_and_cannot_publish_gain() -> None:
    with pytest.raises(ValidationError, match="require invalid_reason"):
        IndependenceOutcomeContract(
            contract_version=BOUNDARY_CONTRACT_VERSION,
            outcome_id=uuid4(),
            episode_id=uuid4(),
            validity="invalid",
            formula_version="independence-gain-v1",
            baseline_support_state="unsupported",
            verification_support_state="unknown",
            recorded_at=datetime(2026, 10, 13, tzinfo=UTC),
        )


def test_episode_boundary_requires_reason_only_for_early_terminal_states() -> None:
    base = {
        "contract_version": BOUNDARY_CONTRACT_VERSION,
        "episode_id": uuid4(),
        "learner_id": uuid4(),
        "skill_id": "skill-provisional-01",
        "protocol_version": "adaptive-episode-v1",
        "created_at": datetime(2026, 10, 13, tzinfo=UTC),
        "transitioned_at": datetime(2026, 10, 13, tzinfo=UTC),
    }
    with pytest.raises(ValidationError, match="require a terminal reason"):
        EpisodeStateContract(**base, phase="invalidated")

    with pytest.raises(ValidationError, match="only valid"):
        EpisodeStateContract(**base, phase="completed", terminal_reason="NOT_APPLICABLE")

