"""Worked example: a different problem with the same pattern, solved start to finish."""

from __future__ import annotations

from app.gamification.application.support_builders.context import (
    SUPPORT_SEED_ATTEMPTS,
    SUPPORT_SEED_OFFSET,
    SupportBuildContext,
    SupportPlan,
    SupportStage,
    answer_reveal,
    practice_record,
    solution_matches_failed,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for


class WorkedParallelExampleBuilder:
    scaffold_type = "worked_parallel_example"

    def build(self, context: SupportBuildContext) -> SupportPlan | None:
        for attempt in range(SUPPORT_SEED_ATTEMPTS):
            item = context.source.support_item(
                context.skill_id, context.seed + SUPPORT_SEED_OFFSET + attempt
            )
            record = practice_record(context, item)
            if record["revision_id"] in context.reserved_revisions:
                continue
            activity = context.source.support_activity(record)
            if activity["game"] == context.source.support_activity(context.failed_record)["game"]:
                continue
            # The parallel problem must never show the child's own answer.
            if solution_matches_failed(context, record):
                continue
            solution = context.source.support_solution(record)
            demonstration = {
                "presentation_id": record["presentation_id"],
                "revision_id": record["revision_id"],
                "skill_id": record["skill_id"],
                "prompt_si": activity["prompt_si"],
                "game": activity["game"],
                "steps_si": list(solution.get("steps_si", ())),
                "solution": solution.get("correct_response"),
                # Shown already solved: the child only watches.
                "answer": answer_reveal(context, record, "filled"),
            }
            return SupportPlan(
                scaffold_type="worked_parallel_example",
                title_si="විසඳූ උදාහරණයක්",
                stages=(
                    SupportStage(
                        kind="view",
                        cues_si=cues_for(context.subject).worked_view,
                        worked_example=demonstration,
                    ),
                    target_stage(context, cues_for(context.subject).worked_then_you),
                ),
            )
        return None
