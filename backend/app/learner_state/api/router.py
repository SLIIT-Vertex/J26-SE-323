from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.learner_state.api.schemas import (
    ConfusionResult,
    DisengagementResult,
    LearnerStateRequest,
    LearnerStateResponse,
)
from app.learner_state.application.service import (
    LearnerStateService,
    LearnerStateWindow,
    VisualObservation,
)
from app.learner_state.infrastructure.feature_builder import (
    BehaviorObservation,
)

router = APIRouter(
    prefix="/learner-state",
    tags=["learner-state"],
)


@lru_cache
def get_service() -> LearnerStateService:
    """
    Keep one learner-state service instance alive so that
    in-memory temporal/session history is preserved across requests.
    """
    return LearnerStateService()


@router.post(
    "",
    response_model=LearnerStateResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_learner_state(
    request: LearnerStateRequest,
    service: Annotated[
        LearnerStateService,
        Depends(get_service),
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
            first_action=request.behaviour.first_action,
            position=request.behaviour.position,
            original=request.behaviour.original,
        ),
        task_progress=request.task_progress,
    )

    try:
        result = service.evaluate(window)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return LearnerStateResponse(
        session_id=result.session_id,
        learner_id=result.learner_id,
        window_id=result.window_id,
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
            state=result.disengagement.state,
            support_need=result.disengagement.support_need,
        ),
        recommended_action=result.recommended_action,
    )