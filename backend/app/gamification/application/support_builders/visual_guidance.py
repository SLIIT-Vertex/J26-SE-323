"""Visual guidance: the failed game again, with its structure pointed out.

In mathematics it is a demonstration, not a task: the child's own board is shown with its answer
highlighted and every step said beside it, and the child only presses next. Other subjects keep
the playable board with its structure pointed out and no answer.
"""

from __future__ import annotations

import json
from uuid import uuid4

from app.gamification.application.support_builders.context import (
    SupportBuildContext,
    SupportPlan,
    SupportStage,
    answer_reveal,
    answer_tokens,
    target_stage,
    without_answer,
)
from app.gamification.application.support_builders.cues import cues_for
from app.gamification.application.support_builders.teaching import item_lesson, lesson_block

TITLE = "දෘශ්‍ය මඟ පෙන්වීම"


class VisualGuidanceBuilder:
    scaffold_type = "visual_guidance"

    def build(self, context: SupportBuildContext) -> SupportPlan:
        lesson = item_lesson(context, context.failed_record)
        if lesson is not None:
            return SupportPlan(
                scaffold_type="visual_guidance",
                title_si=TITLE,
                stages=(_demonstration(context, lesson),),
            )
        # The game's own visual cues, minus any line that would carry the scored answer.
        cues = context.source.support_solution(
            context.failed_record, scaffold_type="visual_guidance"
        ).get("steps_si", ())
        safe = without_answer(tuple(str(line) for line in cues), answer_tokens(context))
        return SupportPlan(
            scaffold_type="visual_guidance",
            title_si=TITLE,
            stages=(target_stage(context, cues_for(context.subject).visual_opening + safe),),
        )


def _demonstration(context: SupportBuildContext, lesson) -> SupportStage:  # type: ignore[no-untyped-def]
    record = json.loads(json.dumps(context.failed_record))
    record.update(
        presentation_id=str(uuid4()),
        role="supported_practice",
        assistance_state="active",
        created_at=context.at.isoformat(),
    )
    return SupportStage(
        kind="view",
        cues_si=("ඔබේ ප්‍රශ්නය විසඳන හැටි බලන්න. ඉස්මතු කළ කොටස් පිළිතුරයි.",),
        item=record,
        # Shown solved: the board is highlighted and cannot be played.
        answer=answer_reveal(context, context.failed_record, "filled"),
    ).with_lesson(
        lesson_block(
            "බලන්න: මෙසේ කරයි",
            steps=lesson.steps,
            answer=lesson.answer,
            another_view=lesson.another_view,
            continue_label_si="ඊළඟ",
        )
    )
