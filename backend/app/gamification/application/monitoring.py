"""In-process evaluation counters. Rates are engineering signals, not pilot results."""

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class EvaluationMonitor:
    episodes: int = 0
    invalid_by_reason: Counter[str] = field(default_factory=Counter)
    valid_outcomes: int = 0
    fallbacks: int = 0
    decisions: int = 0
    actions_by_arm: dict[str, Counter[str]] = field(default_factory=dict)
    verification_available: int = 0
    verification_unavailable: int = 0
    abstentions: int = 0
    belief_draws: int = 0

    def record_decision(self, *, arm: str, action_id: str, fallback: bool, abstained: bool) -> None:
        self.decisions += 1
        self.actions_by_arm.setdefault(arm, Counter())[action_id] += 1
        if fallback:
            self.fallbacks += 1
        self.belief_draws += 1
        if abstained:
            self.abstentions += 1

    def record_verification(self, available: bool) -> None:
        if available:
            self.verification_available += 1
        else:
            self.verification_unavailable += 1

    def record_outcome(self, *, valid: bool, invalid_reason: str | None) -> None:
        self.episodes += 1
        if valid:
            self.valid_outcomes += 1
            return
        for reason in (invalid_reason or "UNSPECIFIED").split(","):
            if reason:
                self.invalid_by_reason[reason] += 1

    def snapshot(self) -> dict[str, object]:
        invalid = self.episodes - self.valid_outcomes
        return {
            "episodes": self.episodes,
            "invalid_episode_rate_by_reason": {
                reason: count / self.episodes
                for reason, count in sorted(self.invalid_by_reason.items())
            },
            "invalid_episodes": invalid,
            "fallback_rate": self.fallbacks / self.decisions if self.decisions else 0.0,
            "action_coverage_by_arm": {
                arm: dict(sorted(counts.items()))
                for arm, counts in sorted(self.actions_by_arm.items())
            },
            "verification_availability": (
                self.verification_available
                / (self.verification_available + self.verification_unavailable)
                if self.verification_available + self.verification_unavailable
                else 0.0
            ),
            "abstention_rate": self.abstentions / self.belief_draws if self.belief_draws else 0.0,
            "inputs": "in-process engineering counters",
        }
