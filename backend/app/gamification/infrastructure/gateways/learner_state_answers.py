"""Learner State answer recording through its published in-process contract.

`GameAnswerRecorder` already has the signature of `LearnerStateAnswerGateway`. It opens its own
database session, so recording never commits or rolls back the game's own transaction.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.gamification.application.session_play import LearnerStateAnswerGateway
from app.learner_state.application.answer_recording import GameAnswerRecorder


def learner_state_answer_gateway(
    session_factory: Callable[[], Session],
) -> LearnerStateAnswerGateway:
    return GameAnswerRecorder(session_factory=session_factory)
