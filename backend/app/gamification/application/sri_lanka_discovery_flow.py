"""Durable Grade 5 English Sri Lanka Discovery profile."""

from __future__ import annotations

from app.gamification.application.engine.english_area_flow import EnglishAreaFlow
from app.gamification.content.sri_lanka_discovery import (
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
    SriLankaDiscoveryItem,
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


class SriLankaDiscoveryFlow(EnglishAreaFlow):
    area_id = AREA_ID
    experience_id = "sri_lanka_discovery"
    universal_skill_id = "LAN-BIL"
    contract_version = "sri-lanka-discovery-learning-flow-v1"
    context_version = "g5-eng-sri-lanka-context-v1"
    measurement_version = "sri-lanka-discovery-independence-measurement-v1"
    item_schema_version = "sri-lanka-discovery-item-v1"
    support_schema_version = "sri-lanka-discovery-support-v1"
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
    missing_skill_error = "SRI_LANKA_DISCOVERY_SKILL_NOT_FOUND"
    episode_type_error = "SRI_LANKA_DISCOVERY_EPISODE_REQUIRED"
    operation_prefix = "sri_lanka_discovery"

    @staticmethod
    def _public_game_data(item: SriLankaDiscoveryItem) -> dict[str, object]:
        return public_game_data(item)

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = SriLankaDiscoveryItem(
            str(item["item_id"]),
            str(item["revision_id"]),
            str(item["parallel_family_id"]),
            str(item["skill_id"]),
            item["chapter"],  # type: ignore[arg-type]
            item["role"],  # type: ignore[arg-type]
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
                "schema_version": "sri-lanka-discovery-item-v1",
                "skill_id": item["skill_id"],
                **public_game_data(public),
            },
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
