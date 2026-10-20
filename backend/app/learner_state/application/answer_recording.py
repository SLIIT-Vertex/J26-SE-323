"""
Published contract for recording scored game answers in process (Option B).

Other components (the game) may import only this module from learner-state to record answers;
`GameAnswerRecorder.record_answer()` maps one scored answer to a learner-state window, records it
with the shared service and returns the window's `recommended_action`
(docs/learner-state/11_GAME_INTEGRATION.md).
"""

from app.learner_state.infrastructure.game_answers import GameAnswerRecorder

__all__ = ["GameAnswerRecorder"]
