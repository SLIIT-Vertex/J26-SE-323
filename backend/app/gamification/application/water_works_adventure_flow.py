"""Durable Grade 5 English Water Works Adventure profile."""

from __future__ import annotations

from app.gamification.application.sri_lanka_discovery_flow import SriLankaDiscoveryFlow
from app.gamification.content.water_works_adventure import (
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
    WaterWorksItem,
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


class WaterWorksAdventureFlow(SriLankaDiscoveryFlow):
    area_id = AREA_ID
    experience_id = "water_works_adventure"
    contract_version = "water-works-adventure-learning-flow-v1"
    context_version = "g5-eng-water-context-v1"
    measurement_version = "water-works-adventure-independence-measurement-v1"
    item_schema_version = "water-works-adventure-item-v1"
    support_schema_version = "water-works-adventure-support-v1"
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
    missing_skill_error = "WATER_WORKS_SKILL_NOT_FOUND"
    episode_type_error = "WATER_WORKS_EPISODE_REQUIRED"
    operation_prefix = "water_works_adventure"
    support_sequences = SUPPORT_SEQUENCE

    @staticmethod
    def _public_game_data(item: WaterWorksItem) -> dict[str, object]:
        return public_game_data(item)

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        support = super()._support(state)
        support["title_si"] = {"visual_guidance": "දර්ශන විස්තර මඟ පෙන්වීම", "worked_parallel_example": "නව ජල ක්‍රියාවක උදාහරණයක්", "step_by_step_guidance": "පියවරෙන් පියවර ක්‍රියාව සොයමු"}[str(support["scaffold_type"])]
        support["visual_alt_text_si"] = "ඉංග්‍රීසි ක්‍රියාව සහ ජල දර්ශනය අතර සම්බන්ධය පෙන්වයි"
        return support

    @staticmethod
    def _worked_example(item: dict[str, object], *, scaffold_type: str = "worked_parallel_example") -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = WaterWorksItem(str(item["item_id"]), str(item["revision_id"]), str(item["parallel_family_id"]), str(item["skill_id"]), item["chapter"], item["role"], str(item["prompt_si"]), (), "constructed-response", {}, game)  # type: ignore[arg-type]
        return {"mode": "exact_failed_activity", "prompt_si": item["prompt_si"], "game": {"schema_version": "water-works-adventure-item-v1", "skill_id": item["skill_id"], **public_game_data(public)}, "correct_response": correct_response(game), "steps_si": worked_steps(game, scaffold_type)}
