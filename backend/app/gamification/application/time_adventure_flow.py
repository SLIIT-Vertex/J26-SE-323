"""Durable Time Adventure profile on the shared adaptive episode engine."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow
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
    UNIVERSAL_SKILL_ID,
    TimeItem,
    correct_response,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

_VISUAL_FIRST = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
_WORKED_FIRST = ("worked_parallel_example", "visual_guidance", "step_by_step_guidance")


class TimeAdventureFlow(AreaGameFlow):
    area_id = AREA_ID
    experience_id = "time_adventure"
    universal_skill_id = UNIVERSAL_SKILL_ID
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
    generate_simpler_item = staticmethod(generate_simpler_item)
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "TIME_SKILL_NOT_FOUND"
    episode_type_error = "TIME_EPISODE_REQUIRED"
    operation_prefix = "time_adventure"

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
        allowed = {
            "move_count",
            "correction_count",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "evidence_quality",
            "all_objects_placed",
        }
        if not set(result).issubset(allowed):
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "all_objects_placed":
                if not isinstance(value, bool):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "evidence_quality":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not 0 <= float(value) <= 1
                ):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(
        response_time_ms: int | None, summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "correction_count", "first_action_ms", "active_time_ms"):
            if key not in (summary or {}):
                missing.append(key)
        return missing

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])
        public_item = TimeItem(
            str(item["item_id"]),
            str(item["revision_id"]),
            str(item["parallel_family_id"]),
            str(item["skill_id"]),
            item["chapter"],
            item["role"],
            str(item["prompt_si"]),
            (),
            "constructed-response",
            {},
            game,
        )
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {
                "schema_version": "time-adventure-item-v1",
                **TimeAdventureFlow._public_game_data(public_item),
            },
            "correct_response": correct_response(game)
            if scaffold_type != "visual_guidance"
            else None,
            "steps_si": worked_steps(game, scaffold_type),
        }
