"""Durable Grade 5 English Bloom Builder Garden profile."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlowError
from app.gamification.application.sri_lanka_discovery_flow import SriLankaDiscoveryFlow
from app.gamification.content.bloom_builder_garden import (
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
    BloomBuilderItem,
    correct_response,
    generate_item,
    infer_belief,
    package_hash,
    public_game_data,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

SUPPORT_SEQUENCE = {skill_id: ("visual_guidance", "worked_parallel_example", "step_by_step_guidance") for skill_id in SKILLS}


class BloomBuilderGardenFlow(SriLankaDiscoveryFlow):
    area_id = AREA_ID
    experience_id = "bloom_builder_garden"
    contract_version = "bloom-builder-garden-learning-flow-v1"
    context_version = "g5-eng-flower-context-v1"
    measurement_version = "bloom-builder-independence-measurement-v1"
    item_schema_version = "bloom-builder-garden-item-v1"
    support_schema_version = "bloom-builder-garden-support-v1"
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
    missing_skill_error = "BLOOM_BUILDER_SKILL_NOT_FOUND"
    episode_type_error = "BLOOM_BUILDER_EPISODE_REQUIRED"
    operation_prefix = "bloom_builder_garden"
    support_sequences = SUPPORT_SEQUENCE

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        allowed = {
            "move_count", "correction_count", "first_action_ms", "active_time_ms",
            "attempt_count", "invalid_drop_count", "tap_alternative_used", "detail_sheet_open_count",
        }
        if not set(result).issubset(allowed):
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "tap_alternative_used":
                if type(value) is not bool:
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _public_game_data(item: BloomBuilderItem) -> dict[str, object]:
        return public_game_data(item)

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        support = super()._support(state)
        support["title_si"] = {
            "visual_guidance": "මලේ ව්‍යුහය බලන මඟ පෙන්වීම",
            "worked_parallel_example": "නව මලක උදාහරණයක්",
            "step_by_step_guidance": "පියවරෙන් පියවර මල සොයමු",
        }[str(support["scaffold_type"])]
        support["visual_alt_text_si"] = "පාට පමණක් නොව මලේ පෙති, මැද කොටස සහ පොකුරු හැඩය සසඳන ආකාරය"
        return support

    @staticmethod
    def _worked_example(item: dict[str, object], *, scaffold_type: str = "worked_parallel_example") -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = BloomBuilderItem(
            str(item["item_id"]), str(item["revision_id"]), str(item["parallel_family_id"]),
            str(item["skill_id"]), item["chapter"], item["role"], str(item["prompt_si"]),
            (), "constructed-response", {}, game,  # type: ignore[arg-type]
        )
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {"schema_version": "bloom-builder-garden-item-v1", "skill_id": item["skill_id"], **public_game_data(public)},
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
