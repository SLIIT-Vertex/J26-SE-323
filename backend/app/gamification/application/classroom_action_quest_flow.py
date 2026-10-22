"""Durable Grade 5 English classroom-action adventure profile."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow, _attempts
from app.gamification.content.classroom_action_quest import (
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
    ClassroomActionItem,
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


class ClassroomActionQuestFlow(AreaGameFlow):
    area_id = AREA_ID
    experience_id = "classroom_action_quest"
    universal_skill_id = "LAN-BIL"
    # Learner-state behaviour models were trained on mathematics answers only.
    records_learner_state = False
    contract_version = "classroom-action-quest-learning-flow-v1"
    context_version = "g5-eng-action-command-context-v1"
    measurement_version = "classroom-action-independence-measurement-v1"
    item_schema_version = "classroom-action-item-v1"
    support_schema_version = "classroom-action-support-v1"
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
    missing_skill_error = "CLASSROOM_ACTION_SKILL_NOT_FOUND"
    episode_type_error = "CLASSROOM_ACTION_EPISODE_REQUIRED"
    operation_prefix = "classroom_action_quest"

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        response = AreaGameFlow._summary(state)
        attempts = _attempts(state)
        latest = attempts[-1] if attempts else None
        if isinstance(latest, Mapping) and latest.get("correct") is False:
            normalized = latest.get("constructed_response")
            score = response.get("server_score")
            if isinstance(normalized, Mapping) and isinstance(score, dict):
                score["feedback_column"] = str(latest.get("error_code", "command"))
        return response

    @staticmethod
    def _public_game_data(item: ClassroomActionItem) -> dict[str, object]:
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
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "tap_alternative_used":
                if type(value) is not bool:
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
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
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        public = ClassroomActionItem(
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
                "schema_version": "classroom-action-item-v1",
                "skill_id": item["skill_id"],
                **public_game_data(public),
            },
            "correct_response": correct_response(game),
            "steps_si": worked_steps(game, scaffold_type),
        }
