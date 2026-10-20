"""Records one scored answer as learner-state evidence, after the answer itself is stored.

Learner-state is optional evidence: a missing gateway, missing consent or any gateway error never
changes or rejects the answer. The game's own decisions do not use the result yet (silent mode,
docs/learner-state/12_PILOT_STUDY_PLAN.md).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from app.gamification.application.ports import ConsentStore
from app.gamification.application.session_play import LearnerStateAnswerGateway

LEARNER_STATE_CAMERA_PURPOSE = "learner_state_camera"
LEARNER_STATE_CAMERA_CONSENT_VERSION = "learner-state-camera-v1"

logger = logging.getLogger(__name__)


def camera_consent_granted(
    consent: ConsentStore | None, *, learner_id: UUID, at: datetime
) -> bool:
    if consent is None:
        return False
    try:
        decision = consent.get_consent(learner_id=learner_id, purpose=LEARNER_STATE_CAMERA_PURPOSE)
    except LookupError:
        return False
    return (
        decision.granted
        and decision.decided_at <= at
        and (decision.expires_at is None or decision.expires_at > at)
    )


def record_scored_answer(
    gateway: LearnerStateAnswerGateway | None,
    consent: ConsentStore | None,
    *,
    session_id: UUID,
    learner_id: UUID,
    skill_id: str,
    at: datetime,
    correct: bool,
    response_time_ms: int | None,
    visual: Mapping[str, float] | None,
) -> str | None:
    """Return the learner-state `recommended_action`, or None when nothing was recorded."""
    if gateway is None:
        return None
    try:
        # Camera values leave the game only with current camera consent; the answer behaviour is
        # recorded either way and fusion then gives the visual models zero weight.
        allowed_visual = (
            dict(visual)
            if visual is not None and camera_consent_granted(consent, learner_id=learner_id, at=at)
            else None
        )
        return gateway.record_answer(
            session_id=session_id,
            learner_id=learner_id,
            # Milliseconds of the scoring time: increasing within a session, so later answers
            # always get a later window, also across episodes and process restarts.
            window_id=int(at.timestamp() * 1000),
            skill_id=skill_id,
            observed_at=at,
            correct=correct,
            response_time_ms=response_time_ms,
            # Only unsupported answers are scored in the adaptive flows: no support was shown.
            supported=False,
            hint_count=0,
            visual=allowed_visual,
        )
    except Exception:  # optional evidence never fails answer storage
        logger.warning("learner-state evidence was not recorded", exc_info=True)
        return None
