"""Durable Grade 5 English Family Word Constellation profile."""

from __future__ import annotations

from app.gamification.application.engine.english_area_flow import EnglishAreaFlow
from app.gamification.content.family_word_constellation import (
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
    FamilyConstellationItem,
    correct_response,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    public_game_data,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)


class FamilyWordConstellationFlow(EnglishAreaFlow):
    area_id = AREA_ID
    experience_id = "family_word_constellation"
    contract_version = "family-word-constellation-learning-flow-v1"
    context_version = "g5-eng-family-context-v1"
    measurement_version = "family-word-constellation-independence-measurement-v1"
    item_schema_version = "family-word-constellation-item-v1"
    support_schema_version = "family-word-constellation-support-v1"
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
    missing_skill_error = "FAMILY_CONSTELLATION_SKILL_NOT_FOUND"
    episode_type_error = "FAMILY_CONSTELLATION_EPISODE_REQUIRED"
    operation_prefix = "family_word_constellation"

    @staticmethod
    def _public_game_data(item: FamilyConstellationItem) -> dict[str, object]:
        return public_game_data(item)

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = FamilyConstellationItem(
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
        )  # type: ignore[arg-type]
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {
                "schema_version": "family-word-constellation-item-v1",
                "skill_id": item["skill_id"],
                **public_game_data(public),
            },
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
