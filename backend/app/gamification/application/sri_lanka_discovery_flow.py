"""Durable Grade 5 English Sri Lanka Discovery profile."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
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
    infer_belief,
    package_hash,
    public_game_data,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

SUPPORT_SEQUENCE = {
    skill_id: ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
    for skill_id in SKILLS
}


class SriLankaDiscoveryFlow(NumberWorldFlow):
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
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "SRI_LANKA_DISCOVERY_SKILL_NOT_FOUND"
    episode_type_error = "SRI_LANKA_DISCOVERY_EPISODE_REQUIRED"
    operation_prefix = "sri_lanka_discovery"
    support_sequences = SUPPORT_SEQUENCE
    activity_support_memory = True
    answer_revealing_support = True

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = NumberWorldFlow._summary(state)
        attempts = state.get("attempts")
        latest = attempts[-1] if isinstance(attempts, list) and attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            score = response.get("server_score")
            if isinstance(score, dict):
                score["feedback_column"] = str(latest.get("error_code", "mapping"))
        return response

    @staticmethod
    def _public_game_data(item: SriLankaDiscoveryItem) -> dict[str, object]:
        return public_game_data(item)

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        allowed = {
            "move_count",
            "correction_count",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "invalid_drop_count",
            "tap_alternative_used",
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
        return {
            "scaffold_id": f"{state['skill_id']}:{kind}",
            "revision_id": exposure["revision_id"],
            "scaffold_type": kind,
            "title_si": {
                "visual_guidance": "අර්ථ මඟ පෙන්වීම",
                "worked_parallel_example": "නව උදාහරණයක් බලමු",
                "step_by_step_guidance": "පියවරෙන් පියවර වර්ග කරමු",
            }[kind],
            "body_si": worked["steps_si"],
            "visual_alt_text_si": "ඉංග්‍රීසි වචන, අර්ථ සහ ප්‍රවර්ග අතර සම්බන්ධය පෙන්වයි",
            "maximum_steps": 4,
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
                "required_actions": min(4, len(worked["steps_si"])),
                "worked_example": worked,
            },
        }

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
