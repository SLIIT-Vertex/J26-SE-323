"""Durable adaptive-game profile for the Number Pattern Adventure."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow
from app.gamification.content.number_patterns import (
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
    NumberPatternItem,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
)

_VISUAL_FIRST = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
_WORKED_FIRST = ("worked_parallel_example", "visual_guidance", "step_by_step_guidance")


class NumberPatternsFlow(AreaGameFlow):
    area_id = AREA_ID
    experience_id = "number_pattern_adventure"
    universal_skill_id = "APT-PAT"
    contract_version = "number-pattern-adventure-learning-flow-v1"
    context_version = "g5-mat-number-patterns-context-v1"
    measurement_version = "number-patterns-independence-measurement-v1"
    item_schema_version = "number-pattern-item-v1"
    support_schema_version = "number-pattern-support-v1"
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
    missing_skill_error = "NUMBER_PATTERN_SKILL_NOT_FOUND"
    episode_type_error = "NUMBER_PATTERN_EPISODE_REQUIRED"
    operation_prefix = "number_patterns"

    @staticmethod
    def _public_game_data(item: NumberPatternItem) -> dict[str, object]:
        game = item.game_data
        return {
            "chapter": item.chapter,
            "operation": game["operation"],
            "visible_terms": game["visible_terms"],
            "missing_indices": game["missing_indices"],
            "term_count": game["term_count"],
        }

    @staticmethod
    def _validate_interaction_summary(
        interaction_summary: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        summary = dict(interaction_summary or {})
        allowed = {
            "move_count",
            "correction_count",
            "rule_changes",
            "operation_changes",
            "multiplier_changes",
            "invalid_placements",
            "cleared_values",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "completion_order_valid",
            "evidence_quality",
        }
        if not set(summary).issubset(allowed) or len(summary) > 12:
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in summary.items():
            if key == "completion_order_valid":
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

    def _infer_belief(
        self,
        error_code: str,
        *,
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None,
    ) -> dict[str, object]:
        summary = interaction_summary or {}
        quality = float(summary.get("evidence_quality", 0.35 if not summary else 0.8))
        return self.infer_belief(
            error_code,
            sparse=response_time_ms is None and not summary,
            evidence_quality=max(0.0, min(1.0, quality)),
        )

    @staticmethod
    def _missingness(
        response_time_ms: int | None, interaction_summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = []
        if response_time_ms is None:
            missing.append("response_time_ms")
        summary = interaction_summary or {}
        for field in (
            "move_count",
            "correction_count",
            "rule_changes",
            "operation_changes",
            "active_time_ms",
        ):
            if field not in summary:
                missing.append(field)
        return missing

    @staticmethod
    def _additional_exclusions(
        state: dict[str, object], after_item: dict[str, object]
    ) -> list[str]:
        before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")  # type: ignore[index]
        before_game = before["game_data"]
        after_game = after_item["game_data"]
        assert isinstance(before_game, dict) and isinstance(after_game, dict)
        exclusions = []
        for field, code in (
            ("operation", "INCOMPATIBLE_PATTERN_OPERATION"),
            ("rule", "INCOMPATIBLE_PATTERN_RULE"),
            ("term_count", "INCOMPATIBLE_TERM_COUNT"),
            ("missing_indices", "INCOMPATIBLE_MISSING_POSITIONS"),
        ):
            if before_game.get(field) != after_game.get(field):
                exclusions.append(code)
        return exclusions

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        operation = str(game["operation"])
        rule = int(game["rule"])
        sequence = [int(value) for value in game["sequence"]]  # type: ignore[union-attr]
        missing_indices = [int(value) for value in game["missing_indices"]]  # type: ignore[union-attr]
        symbol = {"add": "+", "subtract": "−", "multiply": "×"}[operation]
        equations = [
            f"{sequence[index - 1]} {symbol} {rule} = {sequence[index]}"
            for index in range(1, len(sequence))
        ]
        public_game = {
            "schema_version": "number-pattern-item-v1",
            "chapter": item["chapter"],
            "skill_id": item["skill_id"],
            "operation": operation,
            "visible_terms": game["visible_terms"],
            "missing_indices": missing_indices,
            "term_count": game["term_count"],
            "equations": [] if scaffold_type == "visual_guidance" else equations,
        }
        if operation == "multiply":
            response: dict[str, object] = {
                "kind": "constant_ratio_pattern",
                "multiplier": rule,
                "completed_terms": [sequence[index] for index in missing_indices],
            }
        else:
            response = {
                "kind": "constant_difference_pattern",
                "operation": operation,
                "difference": rule,
                "completed_terms": [sequence[index] for index in missing_indices],
            }
        steps = (
            "පළමු අසල්වැසි සංඛ්‍යා දෙක සසඳමු.",
            f"{symbol} {rule} යන එකම රීතිය හඳුනා ගනිමු.",
            "පෙර සංඛ්‍යාවට එම රීතිය යොදා ඊළඟ සංඛ්‍යාව තබමු.",
        )
        if scaffold_type == "visual_guidance":
            steps = (
                "අසල්වැසි සංඛ්‍යා දෙක ඉස්මතු කර බලමු.",
                "ඒ අතර වෙනස හෝ ගුණනය සොයමු.",
                "පිළිතුර නොබලා එම රීතිය ඔබම යොදන්න.",
            )
        elif scaffold_type == "step_by_step_guidance":
            steps = (
                "සසඳන අසල්වැසි සංඛ්‍යා දෙක තෝරන්න.",
                "එකතු කිරීම, අඩු කිරීම හෝ ගුණ කිරීම හඳුනා ගන්න.",
                "නැවත නැවත යොදන රීති අගය සකස් කරන්න.",
                "පෙර සංඛ්‍යාවෙන් ඊළඟ අගය ගණනය කරන්න.",
                "ගණනය කළ අගය ඊළඟ හිස් ස්ථානයට තබන්න.",
                "අලුතින් තැබූ අගයෙන් එම රීතිය නැවත යොදන්න.",
            )
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": public_game,
            "correct_response": None if scaffold_type == "visual_guidance" else response,
            "steps_si": list(steps),
        }
