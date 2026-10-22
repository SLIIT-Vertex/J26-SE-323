"""Worked example: a different problem with the same pattern, solved start to finish, answer
included; then the child solves their own."""

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
from app.gamification.application.support_builders.teaching import item_lesson, lesson_block
from app.gamification.application.support_builders.theory import rule_for


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
            return _plan(context, record, activity)
        return None


def _plan(context: SupportBuildContext, record: dict, activity: dict) -> SupportPlan:  # type: ignore[type-arg]
    solution = context.source.support_solution(record)
    lesson = item_lesson(context, record)
    steps = list(lesson.steps) if lesson else [str(step) for step in solution.get("steps_si", ())]
    demonstration = {
        "presentation_id": record["presentation_id"],
        "revision_id": record["revision_id"],
        "skill_id": record["skill_id"],
        "prompt_si": activity["prompt_si"],
        "game": activity["game"],
        "steps_si": list(dict.fromkeys(steps)),
        "solution": solution.get("correct_response"),
        # Shown already solved: the child only watches.
        "answer": answer_reveal(context, record, "filled"),
    }
    cues = cues_for(context.subject)
    view = SupportStage(kind="view", cues_si=cues.worked_view, worked_example=demonstration)
    target = target_stage(context, cues.worked_then_you)
    if lesson is not None:
        view = view.with_lesson(
            lesson_block(
                "විසඳූ උදාහරණය",
                answer=lesson.answer,
                continue_label_si="දැන් මම කරමි",
            )
        )
        own = item_lesson(context, context.failed_record)
        target = target_stage(
            context, ("උදාහරණයේ පියවරම ඔබේ අගයන් සමඟ කරන්න.", *cues.worked_then_you)
        ).with_lesson(
            lesson_block(
                "ඔබේ වාරය",
                notes=rule_for(context.area_id),
                hints=own.hints[:1] if own else (),
            )
        )
    return SupportPlan(
        scaffold_type="worked_parallel_example",
        title_si="විසඳූ උදාහරණයක්",
        stages=(view, target),
    )
