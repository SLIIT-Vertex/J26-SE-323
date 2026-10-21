"""Durable division profile on the shared adaptive episode engine."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.content.division_adventure import (
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
    DivisionItem,
    correct_response,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)


class DivisionAdventureFlow(NumberWorldFlow):
    area_id = AREA_ID
    experience_id = "division_adventure"
    universal_skill_id = "MAT-DIV"
    contract_version = "division-adventure-learning-flow-v1"
    context_version = "g5-mat-division-context-v1"
    measurement_version = "division-independence-measurement-v1"
    item_schema_version = "division-adventure-item-v1"
    support_schema_version = "division-adventure-support-v1"
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
    missing_skill_error = "DIVISION_SKILL_NOT_FOUND"
    episode_type_error = "DIVISION_EPISODE_REQUIRED"
    operation_prefix = "division_adventure"

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = NumberWorldFlow._summary(state)
        attempts = state.get("attempts")
        latest = attempts[-1] if isinstance(attempts, list) and attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            normalized = latest.get("constructed_response")
            feedback_step = None
            if isinstance(normalized, Mapping):
                feedback_step = normalized.get("_feedback_step_index")
                if feedback_step is None and isinstance(normalized.get("written_working"), Mapping):
                    feedback_step = normalized["written_working"].get("_feedback_step_index")
            score = response.get("server_score")
            if isinstance(score, dict) and type(feedback_step) is int:
                score["feedback_step_index"] = feedback_step
        return response

    @staticmethod
    def _public_game_data(item: DivisionItem) -> dict[str, object]:
        game = item.game_data
        public = {
            "chapter": item.chapter,
            "response_kind": game["response_kind"],
            "dividend": game["dividend"],
            "divisor": game["divisor"],
            "has_remainder": game["has_remainder"],
            "dividend_digit_count": game["dividend_digit_count"],
            "step_count": game["step_count"],
            "trace_limit": game.get("trace_limit"),
            "story_id": game.get("story_id"),
            "context_mode": game.get("context_mode"),
            "object_label_si": game.get("object_label_si"),
            "group_label_si": game.get("group_label_si"),
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
            "working_cell_count",
            "bring_down_count",
        }
        if not set(result).issubset(allowed):
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        if any(type(value) is not int or not 0 <= value <= 86_400_000 for value in result.values()):
            raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(
        response_time_ms: int | None, summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "first_action_ms", "active_time_ms", "working_cell_count"):
            if key not in (summary or {}):
                missing.append(key)
        return missing

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])
        public_item = DivisionItem(
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
                "schema_version": "division-adventure-item-v1",
                **DivisionAdventureFlow._public_game_data(public_item),
            },
            # Support is already earned after a failed attempt. The renderer first
            # shows the focused cue, then progressively reveals this exact trace.
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
