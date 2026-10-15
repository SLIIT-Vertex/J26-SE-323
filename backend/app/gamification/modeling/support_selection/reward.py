"""Valid Independence Gain is the only support-selection reward.

The structural fields are ``validity`` and ``raw_gain``. This module does not import
the Independence Gain implementation.
"""

from app.gamification.domain.types import OutcomeValidity

REWARD_VERSION = "raw-ig-reward-v1"


class IndependenceGainReward:
    version = REWARD_VERSION

    def __call__(self, result: object) -> float:
        validity = getattr(result, "validity", None)
        raw_gain = getattr(result, "raw_gain", None)
        if validity is not OutcomeValidity.VALID or raw_gain is None:
            raise ValueError("reward requires a valid independence gain")
        return float(raw_gain)
