"""Durable Time Adventure profile on the shared adaptive episode engine."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.content.time_adventure import (
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
    TimeItem,
    correct_response,
    generate_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

_VISUAL_FIRST = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
_WORKED_FIRST = ("worked_parallel_example", "visual_guidance", "step_by_step_guidance")
TIME_SUPPORT_SEQUENCE = {
    skill_id: (_WORKED_FIRST if skill_id == "G5-MAT-TIME-ARITHMETIC-01" else _VISUAL_FIRST)
    for skill_id in SKILLS
}


class TimeAdventureFlow(NumberWorldFlow):
    area_id = AREA_ID
    experience_id = "time_adventure"
    universal_skill_id = "MAT-TIME"
    contract_version = "time-adventure-learning-flow-v1"
    context_version = "g5-mat-time-context-v1"
    measurement_version = "time-independence-measurement-v1"
    item_schema_version = "time-adventure-item-v1"
    support_schema_version = "time-adventure-support-v1"
    package_version = PACKAGE_VERSION
    catalogue_version = CATALOGUE_VERSION
    feature_version = FEATURE_VERSION
    mapping_version = MAPPING_VERSION
    model_version = MODEL_VERSION
    policy_version = POLICY_VERSION
    scoring_version = SCORING_VERSION
    equivalence_version = EQUIVALENCE_VERSION
    skills = SKILLS
    generate_item = staticmethod(generate_item)
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "TIME_SKILL_NOT_FOUND"
    episode_type_error = "TIME_EPISODE_REQUIRED"
    operation_prefix = "time_adventure"
    support_sequences = TIME_SUPPORT_SEQUENCE
    activity_support_memory = True
    answer_revealing_support = True

    @staticmethod
    def _public_game_data(item: TimeItem) -> dict[str, object]:
        game = item.game_data
        public = {
            "chapter": item.chapter,
            "response_kind": game["response_kind"],
            "source_page": game["source_page"],
            "left_options": game.get("left_options"),
            "right_options": game.get("right_options"),
            "target_hour": game.get("target_hour"),
            "target_minute": game.get("target_minute"),
            "source_hour": game.get("source_hour"),
            "source_minute": game.get("source_minute"),
            "period": game.get("period"),
            "start_hour": game.get("start_hour"),
            "start_minute": game.get("start_minute"),
            "end_hour": game.get("end_hour"),
            "end_minute": game.get("end_minute"),
            "operation": game.get("operation"),
            "left_hours": game.get("left_hours"),
            "left_minutes": game.get("left_minutes"),
            "right_hours": game.get("right_hours"),
            "right_minutes": game.get("right_minutes"),
        }
        return {key: value for key, value in public.items() if value is not None}

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        allowed = {"move_count", "correction_count", "first_action_ms", "active_time_ms", "attempt_count", "evidence_quality", "all_objects_placed"}
        if not set(result).issubset(allowed):
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "all_objects_placed":
                if not isinstance(value, bool):
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "evidence_quality":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(response_time_ms: int | None, summary: Mapping[str, object] | None) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "correction_count", "first_action_ms", "active_time_ms"):
            if key not in (summary or {}):
                missing.append(key)
        return missing

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        exposure = state["scaffold_exposure"]
        kind = str(exposure["scaffold_type"])
        failed_item = self._stored_item(state, "unsupported_before")
        titles = {
            "visual_guidance": "දෘශ්‍ය මඟ පෙන්වීම",
            "worked_parallel_example": "පියවරෙන් පියවර දෘශ්‍ය උදාහරණය",
            "step_by_step_guidance": "පියවරෙන් පියවර මඟ පෙන්වීම",
        }
        worked = self._worked_example(failed_item, scaffold_type=kind)
        return {
            "scaffold_id": f"{state['skill_id']}:{kind}",
            "revision_id": exposure["revision_id"],
            "scaffold_type": kind,
            "title_si": titles[kind],
            "body_si": worked["steps_si"],
            "visual_alt_text_si": "එම කාල ක්‍රියාකාරකම පියවරෙන් පියවර පෙන්වන සහාය",
            "maximum_steps": 6,
            "game_manifest": {
                "schema_version": self.support_schema_version,
                "activity_id": state["chapter"],
                "revision_id": exposure["manifest_revision_id"],
                "deterministic_seed": state["seed"],
                "skill_id": state["skill_id"],
                "scaffold_type": kind,
                "renderer_id": f"{state['chapter']}:{kind}",
                "parallel_example_id": f"{state['skill_id']}:parallel-support-v1",
                "parallel_example_version": "v1",
                "parallel_values": [],
                "required_actions": 3,
                "worked_example": worked,
            },
        }

    @staticmethod
    def _worked_example(item: dict[str, object], *, scaffold_type: str = "worked_parallel_example") -> dict[str, object]:
        game = dict(item["game_data"])
        public_item = TimeItem(str(item["item_id"]), str(item["revision_id"]), str(item["parallel_family_id"]), str(item["skill_id"]), item["chapter"], item["role"], str(item["prompt_si"]), (), "constructed-response", {}, game)
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {"schema_version": "time-adventure-item-v1", **TimeAdventureFlow._public_game_data(public_item)},
            "correct_response": correct_response(game) if scaffold_type != "visual_guidance" else None,
            "steps_si": worked_steps(game, scaffold_type),
        }
