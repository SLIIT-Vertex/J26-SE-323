"""Durable distance profile on the shared adaptive episode engine."""
from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.content.distance_adventure import (
    AREA_ID,
    CATALOGUE_VERSION,
    EQUIVALENCE_VERSION,
    FEATURE_VERSION,
    MAPPING_VERSION,
    MODEL_VERSION,
    PACKAGE_VERSION,
    POLICY_VERSION,
    SCORING_VERSION,
    SKILLS,
    DistanceItem,
    correct_response,
    generate_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

DISTANCE_SUPPORT_SEQUENCE = {skill_id: ("visual_guidance", "worked_parallel_example", "step_by_step_guidance") for skill_id in SKILLS}

class DistanceAdventureFlow(NumberWorldFlow):
    area_id = AREA_ID
    experience_id = "distance_adventure"
    universal_skill_id = "MAT-LENGTH"
    contract_version = "distance-adventure-learning-flow-v1"
    context_version = "g5-mat-distance-context-v1"
    measurement_version = "distance-independence-measurement-v1"
    item_schema_version = "distance-adventure-item-v1"
    support_schema_version = "distance-adventure-support-v1"
    package_version = PACKAGE_VERSION; catalogue_version = CATALOGUE_VERSION
    feature_version = FEATURE_VERSION; mapping_version = MAPPING_VERSION; model_version = MODEL_VERSION
    policy_version = POLICY_VERSION; scoring_version = SCORING_VERSION; equivalence_version = EQUIVALENCE_VERSION
    skills = SKILLS; generate_item = staticmethod(generate_item); infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision); package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "DISTANCE_SKILL_NOT_FOUND"; episode_type_error = "DISTANCE_EPISODE_REQUIRED"
    operation_prefix = "distance_adventure"; support_sequences = DISTANCE_SUPPORT_SEQUENCE
    activity_support_memory = True; answer_revealing_support = True

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = NumberWorldFlow._summary(state); attempts = state.get("attempts")
        latest = attempts[-1] if isinstance(attempts, list) and attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            normalized = latest.get("constructed_response"); score = response.get("server_score")
            if isinstance(normalized, Mapping) and isinstance(score, dict) and isinstance(normalized.get("_feedback_column"), str):
                score["feedback_column"] = normalized["_feedback_column"]
        return response

    @staticmethod
    def _public_game_data(item: DistanceItem) -> dict[str, object]:
        allowed = {"chapter": item.chapter, **item.game_data}
        return allowed

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {}); allowed = {"move_count", "correction_count", "first_action_ms", "active_time_ms", "attempt_count", "working_cell_count", "exchange_count"}
        if not set(result).issubset(allowed): raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        if any(type(value) is not int or not 0 <= value <= 86_400_000 for value in result.values()): raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(response_time_ms: int | None, summary: Mapping[str, object] | None) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "first_action_ms", "active_time_ms", "working_cell_count"):
            if key not in (summary or {}): missing.append(key)
        return missing

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        exposure = state["scaffold_exposure"]; assert isinstance(exposure, dict)
        kind = str(exposure["scaffold_type"]); failed = self._stored_item(state, "unsupported_before")
        worked = self._worked_example(failed, scaffold_type=kind)
        latest = state["attempts"][-1]; normalized = latest.get("constructed_response", {})
        focus = normalized.get("_feedback_column") if isinstance(normalized, Mapping) else "metres"
        return {"scaffold_id": f"{state['skill_id']}:{kind}", "revision_id": exposure["revision_id"], "scaffold_type": kind,
            "title_si": {"visual_guidance": "ඊළඟ ඒකකය බලමු", "worked_parallel_example": "ඔබේ දුර ගණනය බලමු", "step_by_step_guidance": "වගුව එක්ව පුරවමු"}[kind],
            "body_si": worked["steps_si"], "visual_alt_text_si": "කිලෝමීටර් සහ මීටර් වගුවේ වත්මන් තීරුව පෙන්වයි", "maximum_steps": 8,
            "game_manifest": {"schema_version": self.support_schema_version, "activity_id": state["chapter"], "revision_id": exposure["manifest_revision_id"],
                "deterministic_seed": state["seed"], "skill_id": state["skill_id"], "scaffold_type": kind, "renderer_id": f"{state['chapter']}:{kind}",
                "parallel_example_id": f"{state['skill_id']}:parallel-support-v1", "parallel_example_version": "v1", "parallel_values": [], "required_actions": 3,
                "focus_column": focus if focus in {"conversion", "kilometres", "metres"} else "metres", "worked_example": worked}}

    @staticmethod
    def _worked_example(item: dict[str, object], *, scaffold_type: str = "worked_parallel_example") -> dict[str, object]:
        game = dict(item["game_data"])
        public = DistanceItem(str(item["item_id"]), str(item["revision_id"]), str(item["parallel_family_id"]), str(item["skill_id"]), item["chapter"], item["role"], str(item["prompt_si"]), (), "constructed-response", {}, game)
        return {"mode": "exact_failed_activity", "prompt_si": item["prompt_si"], "game": {"schema_version": "distance-adventure-item-v1", **DistanceAdventureFlow._public_game_data(public)},
                "correct_response": correct_response(game), "steps_si": worked_steps(game, scaffold_type)}
