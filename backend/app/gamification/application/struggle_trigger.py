"""Provisional pre-decision struggle rules. Thresholds are assumptions, not calibrated cutoffs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from app.gamification.modeling.shared.feature_building import reject_future_evidence

TRIGGER_VERSION = "struggle-trigger-v1"


@dataclass(frozen=True, slots=True)
class StruggleTriggerConfig:
    """Versioned thresholds. Every numeric cutoff is a provisional assumption."""

    trigger_version: str = TRIGGER_VERSION
    incorrect_attempt_threshold: int = 2
    response_time_threshold_ms: int = 60_000
    support_need_threshold: float = 0.7
    support_need_max_age_ms: int = 7 * 24 * 60 * 60 * 1000
    thresholds_status: str = "provisional_assumption"


@dataclass(frozen=True, slots=True)
class StruggleEvidence:
    captured_at: datetime
    incorrect_attempt_count: int | None
    response_time_ms: int | None
    selected_option_is_misconception_linked: bool | None
    learner_requested_help: bool | None
    learner_support_need: float | None = None
    learner_state_observed_at: datetime | None = None
    source_as_of: Mapping[str, datetime] | None = None


@dataclass(frozen=True, slots=True)
class TriggerDecision:
    fired: bool
    trigger_type: str
    reason_codes: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    skipped_rules: tuple[str, ...]
    config_version: str

    def as_json(self) -> dict[str, object]:
        return {
            "reasons": list(self.reason_codes),
            "missing_inputs": list(self.missing_inputs),
            "skipped_rules": list(self.skipped_rules),
            "config_version": self.config_version,
        }


class StruggleTrigger:
    def __init__(self, config: StruggleTriggerConfig | None = None) -> None:
        self.config = config or StruggleTriggerConfig()

    def evaluate(self, evidence: StruggleEvidence) -> TriggerDecision:
        reject_future_evidence(
            captured_at=evidence.captured_at,
            source_as_of=evidence.source_as_of or {},
        )
        reasons: list[str] = []
        missing: list[str] = []
        skipped: list[str] = []
        config = self.config

        if evidence.incorrect_attempt_count is None:
            missing.append("incorrect_attempt_count")
        elif evidence.incorrect_attempt_count >= config.incorrect_attempt_threshold:
            reasons.append("TWO_INCORRECT_ATTEMPTS")

        if evidence.response_time_ms is None:
            missing.append("response_time_ms")
        elif evidence.response_time_ms > config.response_time_threshold_ms:
            reasons.append("RESPONSE_TIME_OVER_SKILL_THRESHOLD")

        if evidence.selected_option_is_misconception_linked is None:
            missing.append("selected_option_is_misconception_linked")
        elif evidence.selected_option_is_misconception_linked:
            reasons.append("MISCONCEPTION_LINKED_OPTION_SELECTED")

        if evidence.learner_requested_help is None:
            missing.append("learner_requested_help")
        elif evidence.learner_requested_help:
            reasons.append("LEARNER_REQUESTED_HELP")

        self._apply_support_need(evidence, reasons, missing, skipped)
        return TriggerDecision(
            fired=bool(reasons),
            trigger_type=reasons[0] if reasons else "no_struggle",
            reason_codes=tuple(reasons),
            missing_inputs=tuple(missing),
            skipped_rules=tuple(skipped),
            config_version=config.trigger_version,
        )

    def _apply_support_need(
        self,
        evidence: StruggleEvidence,
        reasons: list[str],
        missing: list[str],
        skipped: list[str],
    ) -> None:
        if evidence.learner_support_need is None:
            missing.append("learner_support_need")
            return
        if evidence.learner_state_observed_at is None:
            missing.append("learner_state_observed_at")
            return
        age_ms = int(
            (evidence.captured_at - evidence.learner_state_observed_at).total_seconds() * 1000
        )
        if age_ms < 0 or age_ms > self.config.support_need_max_age_ms:
            skipped.append("LEARNER_STATE_STALE")
            return
        if evidence.learner_support_need >= self.config.support_need_threshold:
            reasons.append("LEARNER_STATE_SUPPORT_NEED")
