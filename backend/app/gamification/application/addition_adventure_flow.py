"""Durable Addition Adventure profile for the reusable adaptive-game flow."""

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
    infer_belief,
    package_hash,
    scaffold_decision,
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
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
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
        elif skill_id == "G5-MAT-ADD-RUNNING-TOTAL-01":
            public.update(start=game["start"], stops=game["stops"])
        elif skill_id == "G5-MAT-ADD-CONTEXT-01":
            public.update(
                addends=game["addends"], addend_count=game["addend_count"], context=game["context"]
            )
        else:
            public.update(
                table=game["table"],
                row_labels=game["row_labels"],
                column_labels=game["column_labels"],
                target_type=game["target_type"],
                table_context=game["table_context"],
                selection_count=len(game["selected_cells"]),
            )
            if "comparison_rows" in game:
                public["comparison_rows"] = game["comparison_rows"]
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
            "selected_table_cells",
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
            if key == "selected_table_cells":
                if (
                    not isinstance(value, list)
                    or len(value) > 9
                    or any(
                        not isinstance(cell, str) or len(cell) > 8 or not cell.startswith("r")
                        for cell in value
                    )
                ):
                    raise AreaFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key in {"alignment_valid"}:
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
            "column_actions",
            "carry_actions",
            "alignment_valid",
            "selected_table_cells",
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
        if before_game.get("target_type") != after_game.get("target_type") and (
            "target_type" in before_game or "target_type" in after_game
        ):
            exclusions.append("INCOMPATIBLE_TABLE_OPERATION")
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
        elif skill_id == "G5-MAT-ADD-RUNNING-TOTAL-01":
            start = int(game["start"])
            stops = [int(value) for value in game["stops"]]  # type: ignore[union-attr]
            totals = []
            running = start
            for value in stops:
                running += value
                totals.append(running)
            public_game.update(start=start, stops=stops)
            response = {"kind": "route_progression", "totals": totals}
            steps = (
                "ආරම්භක සංඛ්‍යාව තබා ගනිමු.",
                "ඊළඟ අගය එකතු කර නව එකතුව ලියමු.",
                "එම එකතුවෙන් මාර්ගය දිගටම ගොඩනඟමු.",
            )
        elif skill_id == "G5-MAT-ADD-CONTEXT-01":
            addends = [int(value) for value in game["addends"]]  # type: ignore[union-attr]
            public_game.update(addends=addends, context=game["context"])
            response = {
                "kind": "cargo_loading",
                "selected_indices": list(range(len(addends))),
                "total": sum(addends),
            }
            steps = (
                "අදාළ කාණ්ඩ තුන හඳුනා ගනිමු.",
                "කාණ්ඩ තුනම එකතු තැටියට ගෙන එමු.",
                "තීරු අනුව එකතු කර මුළු ගණන සොයමු.",
            )
        else:
            table = [[int(value) for value in row] for row in game["table"]]  # type: ignore[union-attr]
            cells = [tuple(int(part) for part in cell) for cell in game["selected_cells"]]  # type: ignore[union-attr]
            public_game.update(
                table=table,
                row_labels=game["row_labels"],
                column_labels=game["column_labels"],
                target_type=game["target_type"],
                table_context=game["table_context"],
                selection_count=len(cells),
            )
            if game["target_type"] == "difference":
                left, right = (int(value) for value in game["comparison_rows"])  # type: ignore[union-attr]
                public_game["comparison_rows"] = [left, right]
                total = abs(sum(table[left]) - sum(table[right]))
            elif game["target_type"] == "maximum_row":
                total = max(sum(row) for row in table)
            else:
                total = sum(table[row][column] for row, column in cells)
            response = {
                "kind": "data_cell_selection",
                "selected_cells": [f"r{row}c{column}" for row, column in cells],
                "total": total,
            }
            steps = (
                "ප්‍රශ්නයේ පේළිය හෝ තීරුව හඳුනා ගනිමු.",
                "අදාළ කොටු පමණක් තෝරමු.",
                "තෝරාගත් අගයන් එකතු කර ප්‍රතිඵලය සොයමු.",
            )

        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": public_game,
            "correct_response": None if scaffold_type == "visual_guidance" else response,
            "steps_si": list(steps),
        }
