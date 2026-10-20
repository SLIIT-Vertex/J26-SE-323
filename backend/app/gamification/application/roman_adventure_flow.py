"""Durable Roman-numeral adventure profile."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.content.roman_adventure import (
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
    RomanItem,
    correct_response,
    generate_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

ROMAN_SUPPORT_SEQUENCE = {
    skill_id: ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
    for skill_id in SKILLS
}


class RomanAdventureFlow(NumberWorldFlow):
    area_id = AREA_ID
    experience_id = "roman_adventure"
    universal_skill_id = "MAT-ROM"
    contract_version = "roman-adventure-learning-flow-v1"
    context_version = "g5-mat-roman-context-v1"
    measurement_version = "roman-independence-measurement-v1"
    item_schema_version = "roman-adventure-item-v1"
    support_schema_version = "roman-adventure-support-v1"
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
    missing_skill_error = "ROMAN_SKILL_NOT_FOUND"
    episode_type_error = "ROMAN_EPISODE_REQUIRED"
    operation_prefix = "roman_adventure"
    support_sequences = ROMAN_SUPPORT_SEQUENCE
    activity_support_memory = True
    answer_revealing_support = True

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = NumberWorldFlow._summary(state)
        attempts = state.get("attempts")
        latest = attempts[-1] if isinstance(attempts, list) and attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            normalized, score = latest.get("constructed_response"), response.get("server_score")
            if (
                isinstance(normalized, Mapping)
                and isinstance(score, dict)
                and isinstance(normalized.get("_feedback_column"), str)
            ):
                score["feedback_column"] = normalized["_feedback_column"]
        return response

    @staticmethod
    def _public_game_data(item: RomanItem) -> dict[str, object]:
        return {"chapter": item.chapter, **dict(item.game_data)}

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
        }
        if not set(result).issubset(allowed):
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        if any(type(v) is not int or not 0 <= v <= 86_400_000 for v in result.values()):
            raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
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

    @staticmethod
    def _required_support_actions(scaffold_type: str) -> int:
        return 1 if scaffold_type == "visual_guidance" else 3

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        exposure = state["scaffold_exposure"]
        assert isinstance(exposure, dict)
        kind = str(exposure["scaffold_type"])
        worked = self._worked_example(
            self._stored_item(state, "unsupported_before"), scaffold_type=kind
        )
        latest = state["attempts"][-1]  # type: ignore[index]
        normalized = latest.get("constructed_response", {})
        focus = normalized.get("_feedback_column") if isinstance(normalized, Mapping) else "roman"
        return {
            "scaffold_id": f"{state['skill_id']}:{kind}",
            "revision_id": exposure["revision_id"],
            "scaffold_type": kind,
            "title_si": {
                "visual_guidance": "බලන්න ඕන තැන",
                "worked_parallel_example": "ඔබේ ප්‍රශ්නය විසඳන හැටි",
                "step_by_step_guidance": "පියවරෙන් පියවර එක්ව කරමු",
            }[kind],
            "body_si": worked["steps_si"],
            "visual_alt_text_si": "රෝම සංකේත, ඉමෝජි ගණන සහ ගණිත පියවර දෘශ්‍යව පෙන්වයි",
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
                "required_actions": min(6, len(worked["steps_si"])),
                "focus_column": str(focus),
                "worked_example": worked,
            },
        }

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = RomanItem(
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
                "schema_version": "roman-adventure-item-v1",
                "skill_id": item["skill_id"],
                **RomanAdventureFlow._public_game_data(public),
            },
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
