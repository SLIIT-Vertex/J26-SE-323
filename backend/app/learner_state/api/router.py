from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.learner_state.api.schemas import (
    ConfusionResult,
    DisengagementResult,
    LearnerStateRequest,
    LearnerStateResponse,
)
from app.learner_state.application.recording import (
    LearnerStateRecorder,
    UnknownLearnerError,
    get_learner_state_service,
)
from app.learner_state.application.service import (
    LearnerStateWindow,
    VisualObservation,
    WindowOrderError,
)
from app.learner_state.infrastructure.db.repository import (
    SqlAlchemyLearnerSkillStateRepository,
)
from app.learner_state.infrastructure.feature_builder import (
    BehaviorObservation,
)
from app.shared.database.session import get_db
from app.shared.learner.repository import SqlAlchemyLearnerRepository

router = APIRouter(
    prefix="/learner-state",
    tags=["learner-state"],
)


def get_recorder(
    session: Annotated[Session, Depends(get_db)],
) -> LearnerStateRecorder:
    learners = SqlAlchemyLearnerRepository(session)
    return LearnerStateRecorder(
        # Shared with in-process callers so that session history is kept in one place.
        service=get_learner_state_service(),
        learner_exists=lambda learner_id: learners.get(learner_id) is not None,
        skill_states=SqlAlchemyLearnerSkillStateRepository(session),
    )


@router.post(
    "",
    response_model=LearnerStateResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_learner_state(
    request: LearnerStateRequest,
    recorder: Annotated[
        LearnerStateRecorder,
        Depends(get_recorder),
    ],
) -> LearnerStateResponse:
    window = LearnerStateWindow(
        session_id=request.session_id,
        learner_id=request.learner_id,
        window_id=request.window_id,
        timestamp=request.timestamp,
        visual=VisualObservation(
            mean_eye_openness=request.visual.mean_eye_openness,
            std_eye_openness=request.visual.std_eye_openness,
            mean_gaze_ratio=request.visual.mean_gaze_ratio,
            std_gaze_ratio=request.visual.std_gaze_ratio,
            mean_pitch=request.visual.mean_pitch,
            mean_yaw=request.visual.mean_yaw,
            mean_roll=request.visual.mean_roll,
            mean_abs_pitch=request.visual.mean_abs_pitch,
            mean_abs_yaw=request.visual.mean_abs_yaw,
            mean_abs_roll=request.visual.mean_abs_roll,
            face_visibility_ratio=(
                request.visual.face_visibility_ratio
            ),
        ),
        behavior=BehaviorObservation(
            correct=request.behaviour.correct,
            bottom_hint=request.behaviour.bottom_hint,
            hint_count=request.behaviour.hint_count,
            attempt_count=request.behaviour.attempt_count,
            ms_first_response=(
                request.behaviour.ms_first_response
            ),
            overlap_time=request.behaviour.overlap_time,
            original=request.behaviour.original,
        ),
        task_progress=request.task_progress,
    )

    try:
        result = recorder.record(window, skill_id=request.skill_id)
    except UnknownLearnerError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learner not found",
        ) from error
    except WindowOrderError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return LearnerStateResponse(
        session_id=result.session_id,
        learner_id=result.learner_id,
        window_id=result.window_id,
        skill_id=request.skill_id,
        confusion=ConfusionResult(
            visual_probability=(
                result.confusion.visual_probability
            ),
            behavior_probability=(
                result.confusion.behavior_probability
            ),
            visual_reliability=(
                result.confusion.visual_reliability
            ),
            behavior_reliability=(
                result.confusion.behavior_reliability
            ),
            fused_evidence=(
                result.confusion.fused_evidence
            ),
            confidence=result.confusion.confidence,
            temporal_score=result.confusion.temporal_score,
            average_confidence=(
                result.confusion.average_confidence
            ),
            persistent_count=result.confusion.persistent_count,
            state=result.confusion.state,
            support_need=result.confusion.support_need,
        ),
        disengagement=DisengagementResult(
            visual_probability=(
                result.disengagement.visual_probability
            ),
            behavior_probability=(
                result.disengagement.behavior_probability
            ),
            visual_reliability=(
                result.disengagement.visual_reliability
            ),
            behavior_reliability=(
                result.disengagement.behavior_reliability
            ),
            fused_evidence=(
                result.disengagement.fused_evidence
            ),
            confidence=result.disengagement.confidence,
            temporal_score=result.disengagement.temporal_score,
            average_confidence=(
                result.disengagement.average_confidence
            ),
            persistent_count=result.disengagement.persistent_count,
            state=result.disengagement.state,
            support_need=result.disengagement.support_need,
        ),
        recommended_action=result.recommended_action,
    )