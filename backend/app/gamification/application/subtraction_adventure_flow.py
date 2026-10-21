"""Durable Subtraction Adventure profile for the reusable adaptive-game flow."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.content.subtraction_adventure import (
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
    SubtractionItem,
    analyze_subtraction,
    apply_interaction_evidence,
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


class SubtractionAdventureFlow(NumberWorldFlow):
    area_id = AREA_ID
    experience_id = "subtraction_adventure"
    universal_skill_id = "MAT-OPS"
    contract_version = "subtraction-adventure-learning-flow-v1"
    context_version = "g5-mat-subtraction-context-v1"
    measurement_version = "subtraction-independence-measurement-v1"
    item_schema_version = "subtraction-adventure-item-v1"
    support_schema_version = "subtraction-adventure-support-v1"
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
    missing_skill_error = "SUBTRACTION_SKILL_NOT_FOUND"
    episode_type_error = "SUBTRACTION_EPISODE_REQUIRED"
    operation_prefix = "subtraction_adventure"

    @staticmethod
    def _public_game_data(item: SubtractionItem) -> dict[str, object]:
        game = item.game_data
        public: dict[str, object] = {
            "chapter": item.chapter,
            "places": list(game["places"]),
            "place_labels_si": list(game["place_labels_si"]),
            "width": game["width"],
            "blank_count": game["blank_count"],
        }
        if game.get("relationship"):
            public.update(
                relationship=game["relationship"],
                context_id=game["context_id"],
                scene=game["scene"],
                asset=game["asset"],
                quantities=[
                    {
                        "source": "first",
                        "label_si": game["first_label_si"],
                        "value": game["first_value"],
                    },
                    {
                        "source": "second",
                        "label_si": game["second_label_si"],
                        "value": game["second_value"],
                    },
                ],
            )
        else:
            public.update(minuend=game["minuend"], subtrahend=game["subtrahend"])
        if item.skill_id == "G5-MAT-SUB-EXPANDED-01":
            public["representation"] = "expanded"
        return public

    @staticmethod
    def _validate_interaction_summary(
        interaction_summary: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        summary = dict(interaction_summary or {})
        allowed = {
            "digit_entry_count",
            "exchange_count",
            "invalid_exchange_count",
            "column_corrections",
            "cleared_digits",
            "operation_changes",
            "story_reorder_count",
            "alignment_corrections",
            "started_from_ones",
            "alignment_valid",
            "completion_order_consistent",
            "first_action_ms",
            "active_time_ms",
            "attempt_count",
            "evidence_quality",
        }
        if not set(summary).issubset(allowed) or len(summary) > 15:
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in summary.items():
            if key in {"started_from_ones", "alignment_valid", "completion_order_consistent"}:
                if not isinstance(value, bool):
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "evidence_quality":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not 0 <= float(value) <= 1
                ):
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= 86_400_000
            ):
                raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
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
        refined = apply_interaction_evidence(error_code, summary)
        return self.infer_belief(
            refined,
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
            "digit_entry_count",
            "exchange_count",
            "invalid_exchange_count",
            "column_corrections",
            "first_action_ms",
            "active_time_ms",
            "completion_order_consistent",
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
            ("width", "INCOMPATIBLE_DIGIT_COUNT"),
            ("regroup_count", "INCOMPATIBLE_REGROUP_COUNT"),
            ("regroup_positions", "INCOMPATIBLE_REGROUP_POSITIONS"),
            ("sequential", "INCOMPATIBLE_EXCHANGE_SEQUENCE"),
            ("zero_mask", "INCOMPATIBLE_ZERO_STRUCTURE"),
            ("relationship", "INCOMPATIBLE_STORY_RELATIONSHIP"),
            ("response_kind", "INCOMPATIBLE_RESPONSE_KIND"),
        ):
            if before_game.get(field) != after_game.get(field) and (
                field in before_game or field in after_game
            ):
                exclusions.append(code)
        if before_game.get("context_id") and before_game.get("context_id") == after_game.get(
            "context_id"
        ):
            exclusions.append("STORY_CONTEXT_REEXPOSED")
        if before_game.get("minuend") == after_game.get("minuend") and before_game.get(
            "subtrahend"
        ) == after_game.get("subtrahend"):
            exclusions.append("AFTER_OPERANDS_REEXPOSED")
        return exclusions

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        reveal = scaffold_type != "visual_guidance"
        analysed = analyze_subtraction(int(game["minuend"]), int(game["subtrahend"]))
        public_game: dict[str, object] = {
            "schema_version": "subtraction-adventure-item-v1",
            "chapter": item["chapter"],
            "skill_id": item["skill_id"],
            "places": list(game["places"]),
            "place_labels_si": list(game["place_labels_si"]),
            "width": game["width"],
            "minuend": game["minuend"],
            "subtrahend": game["subtrahend"],
            "highlight_place": "ones",
        }
        if game.get("relationship"):
            public_game.update(
                relationship=game["relationship"],
                quantities=[
                    {
                        "source": "first",
                        "label_si": game["first_label_si"],
                        "value": game["first_value"],
                    },
                    {
                        "source": "second",
                        "label_si": game["second_label_si"],
                        "value": game["second_value"],
                    },
                ],
            )
        response: dict[str, object] | None
        kind = str(game["response_kind"])
        if kind == "expanded_subtraction":
            response = {
                "kind": "expanded_subtraction",
                "minuend_terms": list(analysed["minuend_terms"]),  # type: ignore[arg-type]
                "subtrahend_terms": list(analysed["subtrahend_terms"]),  # type: ignore[arg-type]
                "adjusted_minuend_terms": list(analysed["adjusted_terms"]),  # type: ignore[arg-type]
                "result_terms": list(analysed["result_terms"]),  # type: ignore[arg-type]
                "result": analysed["result"],
            }
        elif kind == "difference_story":
            response = {
                "kind": "difference_story",
                "relationship": game["relationship"],
                "minuend_source": game["minuend_source"],
                "subtrahend_source": game["subtrahend_source"],
                "result_digits": list(analysed["result_digits"]),  # type: ignore[arg-type]
                "result": analysed["result"],
            }
        else:
            response = {
                "kind": "column_subtraction",
                "result_digits": list(analysed["result_digits"]),  # type: ignore[arg-type]
                "exchanges": [dict(row) for row in analysed["exchanges"]],  # type: ignore[union-attr]
            }
        if reveal:
            public_game["staged_columns"] = _staged_columns(analysed)
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": public_game,
            "correct_response": response if reveal else None,
            "steps_si": worked_steps(game, scaffold_type),
        }


def _staged_columns(analysed: Mapping[str, object]) -> list[dict[str, object]]:
    places = list(analysed["places"])  # type: ignore[arg-type]
    adjusted = list(analysed["adjusted_digits"])  # type: ignore[arg-type]
    subtrahend = list(analysed["subtrahend_digits"])  # type: ignore[arg-type]
    result = list(analysed["result_digits"])  # type: ignore[arg-type]
    exchange_to = {row["to_place"]: row["from_place"] for row in analysed["exchanges"]}  # type: ignore[union-attr]
    staged = []
    for index, place in enumerate(places):
        staged.append(
            {
                "place": place,
                "top": adjusted[index],
                "bottom": subtrahend[index],
                "result": result[index],
                "exchange_from": exchange_to.get(place),
            }
        )
    return list(reversed(staged))
