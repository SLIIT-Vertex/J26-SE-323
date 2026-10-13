from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import (
    AdaptiveEpisodeModel,
    FeatureSnapshotModel,
    GameSessionModel,
    IndependenceOutcomeModel,
    ItemResponseModel,
    MisconceptionInferenceModel,
    MisconceptionProbabilityModel,
    ModelVersionModel,
    SupportCandidateModel,
    SupportDecisionModel,
    SupportExposureModel,
    VerificationPairModel,
)
from app.knowledge_tracing.infrastructure.db.models import SkillModel
from app.shared.learner.model import LearnerModel

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
LEARNER_ID = UUID("00000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000002")
BASELINE_RESPONSE_ID = UUID("00000000-0000-4000-8000-000000000003")
VERIFICATION_RESPONSE_ID = UUID("00000000-0000-4000-8000-000000000004")
EPISODE_ID = UUID("00000000-0000-4000-8000-000000000005")
SNAPSHOT_ID = UUID("00000000-0000-4000-8000-000000000006")
MODEL_ID = UUID("00000000-0000-4000-8000-000000000007")
INFERENCE_ID = UUID("00000000-0000-4000-8000-000000000008")
DECISION_ID = UUID("00000000-0000-4000-8000-000000000009")
EXPOSURE_ID = UUID("00000000-0000-4000-8000-00000000000a")
PAIR_ID = UUID("00000000-0000-4000-8000-00000000000b")
OUTCOME_ID = UUID("00000000-0000-4000-8000-00000000000c")
SKILL_CODE = "SYN-001"


@dataclass(frozen=True)
class SyntheticEpisodeIds:
    learner_id: UUID = LEARNER_ID
    session_id: UUID = SESSION_ID
    episode_id: UUID = EPISODE_ID
    snapshot_id: UUID = SNAPSHOT_ID
    decision_id: UUID = DECISION_ID


def seed_complete_synthetic_episode(session: Session) -> SyntheticEpisodeIds:
    """Create deterministic engineering evidence with no real child or curriculum data."""
    session.add(
        LearnerModel(
            id=LEARNER_ID,
            grade=5,
            preferred_language="si",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        SkillModel(
            code=SKILL_CODE,
            sort_index=0,
            area="MAT",
            name_en="Synthetic skill",
            name_si=None,
            description="Engineering-only fixture",
        )
    )
    session.flush()
    session.add(
        GameSessionModel(
            id=SESSION_ID,
            learner_id=LEARNER_ID,
            client_session_id=UUID("00000000-0000-4000-8000-000000000010"),
            idempotency_key="synthetic-session-1",
            status="completed",
            language="si",
            app_version="test-v1",
            device_class="test",
            started_at=NOW,
            ended_at=NOW + timedelta(minutes=5),
            last_event_sequence=4,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    baseline = ItemResponseModel(
        id=BASELINE_RESPONSE_ID,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        item_id="synthetic-baseline",
        item_version="item-v1",
        skill_code=SKILL_CODE,
        skill_taxonomy_version="provisional-v1",
        attempt_no=1,
        phase="baseline",
        support_state="unsupported",
        answer_json={"choice": "synthetic-wrong"},
        is_correct=False,
        score=Decimal("0.0000"),
        hint_count=0,
        idempotency_key="response-baseline-1",
        submitted_at=NOW + timedelta(seconds=30),
        created_at=NOW + timedelta(seconds=30),
    )
    verification = ItemResponseModel(
        id=VERIFICATION_RESPONSE_ID,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        item_id="synthetic-verification",
        item_version="item-v1",
        skill_code=SKILL_CODE,
        skill_taxonomy_version="provisional-v1",
        attempt_no=1,
        phase="verification",
        support_state="unsupported",
        answer_json={"choice": "synthetic-correct"},
        is_correct=True,
        score=Decimal("1.0000"),
        hint_count=0,
        idempotency_key="response-verification-1",
        submitted_at=NOW + timedelta(minutes=4),
        created_at=NOW + timedelta(minutes=4),
    )
    session.add_all([baseline, verification])
    session.flush()
    session.add(
        AdaptiveEpisodeModel(
            id=EPISODE_ID,
            session_id=SESSION_ID,
            learner_id=LEARNER_ID,
            skill_code=SKILL_CODE,
            skill_taxonomy_version="provisional-v1",
            phase="completed",
            trigger_type="synthetic_rule",
            baseline_response_id=BASELINE_RESPONSE_ID,
            verification_response_id=VERIFICATION_RESPONSE_ID,
            episode_protocol_version="adaptive-episode-v1",
            opened_at=NOW,
            transitioned_at=NOW + timedelta(minutes=5),
            support_withdrawn_at=NOW + timedelta(minutes=3),
            closed_at=NOW + timedelta(minutes=5),
            terminal_reason=None,
            revision=13,
            created_at=NOW,
        )
    )
    session.add(
        FeatureSnapshotModel(
            id=SNAPSHOT_ID,
            learner_id=LEARNER_ID,
            skill_code=SKILL_CODE,
            captured_at=NOW + timedelta(minutes=1),
            protocol_version="adaptive-episode-v1",
            taxonomy_version="provisional-v1",
            definition_version="feature-v1",
            purpose="policy_decision",
            features_json={"mastery": 0.4, "support_need": 0.7},
            missingness_json={"learner_state": False},
            source_as_of_json={"mastery": "2026-10-13T09:00:30Z"},
            created_at=NOW + timedelta(minutes=1),
        )
    )
    session.add(
        ModelVersionModel(
            id=MODEL_ID,
            model_name="synthetic-misconception",
            model_role="misconception",
            semantic_version="0.0.1-test",
            artifact_uri="test://synthetic-only",
            artifact_sha256="0" * 64,
            feature_definition_version="feature-v1",
            training_dataset_id="synthetic-dataset-v1",
            metrics_json={"engineering_only": True},
            approval_status="validated",
            created_at=NOW,
        )
    )
    session.flush()
    session.add(
        MisconceptionInferenceModel(
            id=INFERENCE_ID,
            episode_id=EPISODE_ID,
            model_version_id=MODEL_ID,
            feature_snapshot_id=SNAPSHOT_ID,
            misconception_catalogue_version="synthetic-catalogue-v1",
            top_misconception_code="synthetic-m1",
            entropy=0.5,
            confidence=0.7,
            abstained=False,
            reason_codes_json=["SYNTHETIC_RULE"],
            inferred_at=NOW + timedelta(minutes=1),
        )
    )
    session.flush()
    session.add_all(
        [
            MisconceptionProbabilityModel(
                inference_id=INFERENCE_ID,
                misconception_code="synthetic-m1",
                probability=0.7,
                rank=1,
            ),
            MisconceptionProbabilityModel(
                inference_id=INFERENCE_ID,
                misconception_code="unknown",
                probability=0.3,
                rank=2,
            ),
        ]
    )
    session.add(
        SupportDecisionModel(
            id=DECISION_ID,
            episode_id=EPISODE_ID,
            feature_snapshot_id=SNAPSHOT_ID,
            selected_action_id="synthetic-hint",
            selected_action_type="conceptual_hint",
            selection_probability=1.0,
            decision_mode="deterministic_reference",
            policy_version="reference-v1",
            support_catalogue_version="synthetic-support-v1",
            reason_codes_json=["REFERENCE_POLICY"],
            random_seed=42,
            decided_at=NOW + timedelta(minutes=2),
        )
    )
    session.flush()
    session.add(
        SupportCandidateModel(
            decision_id=DECISION_ID,
            action_id="synthetic-hint",
            action_type="conceptual_hint",
            eligible=True,
            ineligibility_reasons_json=[],
            propensity=1.0,
            rank=1,
        )
    )
    session.add(
        SupportExposureModel(
            id=EXPOSURE_ID,
            decision_id=DECISION_ID,
            action_id="synthetic-hint",
            presented_at=NOW + timedelta(minutes=2),
            completed_at=NOW + timedelta(minutes=3),
            duration_ms=60_000,
            interaction_count=1,
            delivery_status="completed",
            render_version="render-v1",
        )
    )
    session.add(
        VerificationPairModel(
            id=PAIR_ID,
            episode_id=EPISODE_ID,
            baseline_item_id="synthetic-baseline",
            baseline_item_version="item-v1",
            verification_item_id="synthetic-verification",
            verification_item_version="item-v1",
            skill_code=SKILL_CODE,
            equivalence_version="synthetic-equivalence-v1",
            difficulty_delta=0.0,
            surface_similarity=0.2,
            answer_overlap=0.0,
            review_status="approved",
            reviewed_by="synthetic-reviewer",
            reviewed_at=NOW,
            created_at=NOW,
        )
    )
    session.flush()
    session.add(
        IndependenceOutcomeModel(
            id=OUTCOME_ID,
            episode_id=EPISODE_ID,
            verification_pair_id=PAIR_ID,
            baseline_score=Decimal("0.0000"),
            verification_score=Decimal("1.0000"),
            raw_independence_gain=Decimal("1.00000"),
            validity="valid",
            baseline_support_state="unsupported",
            verification_support_state="unsupported",
            formula_version="raw-difference-provisional-v1",
            calculated_at=NOW + timedelta(minutes=5),
        )
    )
    session.flush()
    return SyntheticEpisodeIds()

