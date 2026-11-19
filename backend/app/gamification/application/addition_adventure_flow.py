"""Durable profile of Nimo's Sky Adventure (Addition) for the reusable adaptive-game flow."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow
from app.gamification.content.addition_adventure import (
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
    generate_item,
    generate_simpler_item,
    package_hash,
    validate_constructed_response,
)

_VISUAL_FIRST = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
_WORKED_FIRST = (
    "worked_parallel_example",
    "visual_guidance",
    "step_by_step_guidance",
)


class AdditionAdventureFlow(AreaGameFlow):
    """Skill-specific content and validity hooks over shared durable episode mechanics."""

    area_id = AREA_ID
    experience_id = "addition_adventure"
    universal_skill_id = UNIVERSAL_SKILL_ID
    contract_version = "addition-adventure-learning-flow-v1"
    context_version = "g5-mat-addition-context-v1"
    measurement_version = "addition-independence-measurement-v1"
    item_schema_version = "addition-adventure-item-v1"
    support_schema_version = "addition-adventure-support-v1"
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
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "ADDITION_SKILL_NOT_FOUND"
    episode_type_error = "ADDITION_EPISODE_REQUIRED"
    operation_prefix = "addition_adventure"

    @staticmethod
    def _public_game_data(item: object) -> dict[str, object]:
        game = item.game_data  # type: ignore[attr-defined]
        skill_id = item.skill_id  # type: ignore[attr-defined]
        public: dict[str, object] = {"chapter": item.chapter}  # type: ignore[attr-defined]
        if skill_id == "G5-MAT-ADD-MENTAL-01":
            public["addends"] = game["addends"]
        elif skill_id.startswith("G5-MAT-C06-"):
            public.update(
                addends=game["addends"], addend_count=game["addend_count"], columns=game["columns"]
            )
        return public

    @staticmethod
    def _validate_interaction_summary(
        interaction_summary: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        summary = dict(interaction_summary or {})
        allowed = {
            "column_actions",
            "carry_actions",
            "alignment_valid",
            "correction_count",
            "undo_count",
            "active_time_ms",
            "evidence_quality",
            "decomposition_steps",
            "retries",
            "attempt_count",
            "move_count",
            "first_action_ms",
        }
        if not set(summary).issubset(allowed) or len(summary) > 12:
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in summary.items():
            if key == "alignment_valid":
                if not isinstance(value, bool):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "evidence_quality":
                if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= 86_400_000
            ):
                raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return summary

    @staticmethod
    def _missingness(
        response_time_ms: int | None, interaction_summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = []
        if response_time_ms is None:
            missing.append("response_time_ms")
        summary = interaction_summary or {}
        for field in (
            "column_actions",
            "carry_actions",
            "alignment_valid",
            "correction_count",
            "undo_count",
            "active_time_ms",
        ):
            if field not in summary:
                missing.append(field)
        return missing

    @staticmethod
    def _additional_exclusions(
        state: dict[str, object], after_item: dict[str, object]
    ) -> list[str]:
        before = next(
            row
            for row in state["presentations"]
            if row["role"] == "unsupported_before"  # type: ignore[index]
        )
        before_game = before["game_data"]
        after_game = after_item["game_data"]
        assert isinstance(before_game, dict) and isinstance(after_game, dict)
        exclusions = []
        if before_game.get("carrying_count") != after_game.get("carrying_count") and (
            "carrying_count" in before_game or "carrying_count" in after_game
        ):
            exclusions.append("INCOMPATIBLE_CARRYING_COMPLEXITY")
        if before_game.get("addend_count") != after_game.get("addend_count") and (
            "addend_count" in before_game or "addend_count" in after_game
        ):
            exclusions.append("INCOMPATIBLE_ADDEND_COUNT")
        return exclusions

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        """Describe the exact failed task; keep visual cues answer-free."""

        skill_id = str(item["skill_id"])
        game = dict(item["game_data"])  # type: ignore[arg-type]
        chapter = str(item["chapter"])
        public_game: dict[str, object] = {
            "schema_version": "addition-adventure-item-v1",
            "chapter": chapter,
            "skill_id": skill_id,
        }
        response: dict[str, object] | None
        if skill_id == "G5-MAT-ADD-MENTAL-01":
            addends = [int(value) for value in game["addends"]]  # type: ignore[union-attr]
            public_game["addends"] = addends
            response = {"kind": "combine_quantities", "combined": True, "total": sum(addends)}
            steps = ("කාණ්ඩ දෙක වෙන වෙනම බලමු.", "කාණ්ඩ දෙක එකට ගෙන එමු.", "මුළු ගණන ගණන් කරමු.")
        elif skill_id.startswith("G5-MAT-C06-"):
            addends = [int(value) for value in game["addends"]]  # type: ignore[union-attr]
            public_game.update(addends=addends, columns=game["columns"])
            response = {
                "kind": "regroup_carry",
                "total": sum(addends),
                "carry_count": int(game["carrying_count"]),
                "aligned": True,
            }
            steps = (
                "එකක තීරුවෙන් එකතු කරමු.",
                "දහයක් වූ විට ඊළඟ තීරුවට එකක් ගෙන යමු.",
                "තීරු සියල්ල එකතු කර පිළිතුර ගොඩනඟමු.",
            )
        else:
            raise ValueError("ADDITION_SKILL_NOT_FOUND")

        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": public_game,
            "correct_response": None if scaffold_type == "visual_guidance" else response,
            "steps_si": list(steps),
        }
