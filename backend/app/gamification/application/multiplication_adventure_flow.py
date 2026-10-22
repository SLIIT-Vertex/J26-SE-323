"""Durable Multiplication Adventure profile on the shared adaptive episode engine."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow
from app.gamification.content.multiplication_adventure import (
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
    MultiplicationItem,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

_SEQUENCE = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


class MultiplicationAdventureFlow(AreaGameFlow):
    area_id = AREA_ID
    experience_id = "multiplication_adventure"
    universal_skill_id = "MAT-OPS"
    contract_version = "multiplication-adventure-learning-flow-v1"
    context_version = "g5-mat-multiplication-context-v1"
    measurement_version = "multiplication-independence-measurement-v1"
    item_schema_version = "multiplication-adventure-item-v1"
    support_schema_version = "multiplication-adventure-support-v1"
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
    missing_skill_error = "MULTIPLICATION_SKILL_NOT_FOUND"
    episode_type_error = "MULTIPLICATION_EPISODE_REQUIRED"
    operation_prefix = "multiplication_adventure"

    @staticmethod
    def _public_game_data(item: MultiplicationItem) -> dict[str, object]:
        game = item.game_data
        public: dict[str, object] = {
            "chapter": item.chapter,
            "response_kind": game["response_kind"],
            "difficulty": SKILLS[item.skill_id].difficulty,
        }
        if game["response_kind"] == "multiplication_fact":
            public.update(
                multiplicand=game["multiplicand"],
                multiplier=game["multiplier"],
                grid_max=12,
            )
        elif game["response_kind"] == "written_multiplication":
            public.update(
                multiplicand=game["multiplicand"],
                multiplier=game["multiplier"],
                places=list(game["places"]),  # type: ignore[arg-type]
                place_labels_si=list(game["place_labels_si"]),  # type: ignore[arg-type]
                blank_count=len(game["result_digits"]),  # type: ignore[arg-type]
                place_shift=game["place_shift"],
            )
        else:
            public.update(
                context_id=game["context_id"],
                label_si=game["label_si"],
                asset=game["asset"],
                group_size=game["group_size"],
                group_count=game["group_count"],
            )
        return public

    def _validate_interaction_summary(
        self, interaction_summary: Mapping[str, object] | None
    ) -> None:
        summary = dict(interaction_summary or {})
        if len(summary) > 12:
            raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
        allowed = {
            "attempt_count",
            "digit_entry_count",
            "first_action_ms",
            "active_time_ms",
            "incorrect_place",
            "evidence_quality",
        }
        if not set(summary).issubset(allowed):
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        return summary

    def _worked_example(self, item: dict[str, object], *, scaffold_type: str) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        reveal = scaffold_type != "visual_guidance"
        public = {
            "schema_version": self.item_schema_version,
            **self._public_game_data_from_mapping(item),
        }
        if reveal and game["response_kind"] == "written_multiplication":
            public["staged_digits"] = list(game["result_digits"])
        response = None
        if reveal:
            if game["response_kind"] == "multiplication_fact":
                response = {
                    "kind": "multiplication_fact",
                    "multiplicand": game["multiplicand"],
                    "multiplier": game["multiplier"],
                    "product": game["product"],
                }
            elif game["response_kind"] == "written_multiplication":
                response = {
                    "kind": "written_multiplication",
                    "multiplicand": game["multiplicand"],
                    "multiplier": game["multiplier"],
                    "result_digits": list(game["result_digits"]),
                    "product": game["product"],
                }
            else:
                response = {
                    "kind": "multiplication_story",
                    "group_size": game["group_size"],
                    "group_count": game["group_count"],
                    "product": game["product"],
                }
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": public,
            "correct_response": response,
            "steps_si": worked_steps(game, scaffold_type),
        }

    def _public_game_data_from_mapping(self, item: dict[str, object]) -> dict[str, object]:
        skill = SKILLS[str(item["skill_id"])]
        stored = MultiplicationItem(
            item_id=str(item.get("item_id") or skill.skill_id),
            revision_id=str(item.get("revision_id") or ""),
            parallel_family_id=f"{skill.skill_id}:{EQUIVALENCE_VERSION}",
            skill_id=skill.skill_id,
            chapter=skill.chapter,
            measurement_role="unsupported_before",
            prompt_si=str(item["prompt_si"]),
            options=(),
            correct_option_id="",
            error_codes={},
            game_data=dict(item["game_data"]),  # type: ignore[arg-type]
        )
        return self._public_game_data(stored)
