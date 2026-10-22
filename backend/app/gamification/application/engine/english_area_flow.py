"""Base flow for the English area games (G5-AREA-ENG-02 … ENG-18).

English games share one scoring summary (it names the failed mapping column), one allowed
interaction-summary shape, and one missingness rule. Each game supplies only its profile,
``_public_game_data`` and ``_worked_example``. ``ClassroomActionQuestFlow`` (ENG-01) predates this
base and sits directly on :class:`AreaGameFlow`.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow, _attempts


class EnglishAreaFlow(AreaGameFlow):
    # English games count toward the bilingual-language universal skill unless they say otherwise.
    universal_skill_id = "LAN-BIL"

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = AreaGameFlow._summary(state)
        attempts = _attempts(state)
        latest = attempts[-1] if attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            score = response.get("server_score")
            if isinstance(score, dict):
                score["feedback_column"] = str(latest.get("error_code", "mapping"))
        return response

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        allowed = {
            "move_count",
            "correction_count",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "invalid_drop_count",
            "tap_alternative_used",
        }
        if not set(result).issubset(allowed):
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "tap_alternative_used":
                if type(value) is not bool:
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(
        response_time_ms: int | None, summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "first_action_ms", "active_time_ms"):
            if key not in (summary or {}):
                missing.append(key)
        return missing
