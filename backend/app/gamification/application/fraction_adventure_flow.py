"""Durable Fraction Adventure profile on the shared adaptive episode engine."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.engine.area_flow import AreaFlowError, AreaGameFlow
from app.gamification.content.fraction_adventure import (
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
    FractionItem,
    generate_item,
    generate_simpler_item,
    infer_belief,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
    worked_steps,
)

_VISUAL_FIRST = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
_WORKED_FIRST = ("worked_parallel_example", "visual_guidance", "step_by_step_guidance")


class FractionAdventureFlow(AreaGameFlow):
    area_id = AREA_ID
    experience_id = "fraction_adventure"
    universal_skill_id = UNIVERSAL_SKILL_ID
    contract_version = "fraction-adventure-learning-flow-v1"
    context_version = "g5-mat-fraction-context-v1"
    measurement_version = "fraction-independence-measurement-v1"
    item_schema_version = "fraction-adventure-item-v1"
    support_schema_version = "fraction-adventure-support-v1"
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
    missing_skill_error = "FRACTION_SKILL_NOT_FOUND"
    episode_type_error = "FRACTION_EPISODE_REQUIRED"
    operation_prefix = "fraction_adventure"

    @staticmethod
    def _public_game_data(item: FractionItem) -> dict[str, object]:
        game = item.game_data
        public = {
            "chapter": item.chapter,
            "response_kind": game["response_kind"],
            "source_page": game["source_page"],
            "representation": game.get("representation"),
            "denominator": game.get("denominator"),
            "total": game.get("total"),
            "object_kind": game.get("object_kind"),
            "region_count": game.get("region_count"),
            "requested_numerator": game.get("requested_numerator"),
            "stimulus_shaded_indices": game.get("stimulus_shaded_indices", []),
            "columns": game.get("columns", []),
        }
        return {key: value for key, value in public.items() if value is not None}

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        allowed = {
            "move_count",
            "reassignment_count",
            "correction_count",
            "shade_count",
            "unshade_count",
            "numerator_revisions",
            "denominator_revisions",
            "table_cell_revisions",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "evidence_quality",
            "all_objects_placed",
        }
        if not set(result).issubset(allowed) or len(result) > 13:
            raise AreaFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "all_objects_placed":
                if not isinstance(value, bool):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "evidence_quality":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not 0 <= float(value) <= 1
                ):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(
        response_time_ms: int | None, summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "correction_count", "first_action_ms", "active_time_ms"):
            if key not in (summary or {}):
                missing.append(key)
        return missing

    @staticmethod
    def _additional_exclusions(
        state: dict[str, object], after_item: dict[str, object]
    ) -> list[str]:
        before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")  # type: ignore[index]
        before_game, after_game = before["game_data"], after_item["game_data"]
        exclusions = []
        for field in ("response_kind", "denominator", "representation"):
            if before_game.get(field) != after_game.get(field):
                exclusions.append(f"INCOMPATIBLE_{field.upper()}")
        if before["revision_id"] == after_item["revision_id"]:
            exclusions.append("AFTER_ITEM_REEXPOSED")
        return exclusions

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        reveal = scaffold_type != "visual_guidance"
        response: dict[str, object] | None = None
        if reveal:
            kind = str(game["response_kind"])
            denominator = int(game["denominator"])
            if kind == "fraction_shading":
                response = {
                    "kind": kind,
                    "representation": game["representation"],
                    "denominator": denominator,
                    "shaded_indices": list(range(int(game["requested_numerator"]))),
                }
            elif kind == "equal_grouping":
                response = {
                    "kind": kind,
                    "denominator": denominator,
                    "assignments": [i % denominator for i in range(int(game["total"]))],
                }
            elif kind == "fraction_quantity_table":
                total = int(game["total"])
                response = {
                    "kind": kind,
                    "total": total,
                    "quarter_values": [total // 4, total // 2, total * 3 // 4],
                }
            else:
                target = int(
                    game.get("requested_numerator", len(game.get("stimulus_shaded_indices", [])))
                )
                response = {
                    "kind": kind,
                    "representation": game["representation"],
                    "numerator": target,
                    "denominator": 10,
                    # A build item starts unshaded, so its solution shades the first target parts.
                    "shaded_indices": list(game.get("stimulus_shaded_indices") or range(target)),
                }
        public_item = FractionItem(
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
                "schema_version": "fraction-adventure-item-v1",
                **FractionAdventureFlow._public_game_data(public_item),
            },
            "correct_response": response,
            "steps_si": worked_steps(game, scaffold_type),
        }
