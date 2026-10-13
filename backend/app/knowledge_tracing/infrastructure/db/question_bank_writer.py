from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.knowledge_tracing.application.question_import import ImportPlan
from app.knowledge_tracing.infrastructure.db.models import (
    QuestionModel,
    QuestionPartModel,
    QuestionVariantModel,
    SkillModel,
)


class SkillOrderConflict(Exception):
    """A skill already in the database would get a different model index."""


def write_plan(session: Session, plan: ImportPlan) -> dict[str, int]:
    """Apply a valid plan. Re-running it updates rows in place; nothing is deleted except
    the parts of re-imported variants. The caller commits (or rolls back)."""
    if not plan.ok:
        raise ValueError("refusing to write a plan that has errors")

    counts = {"skills": 0, "questions": 0, "variants": 0, "parts": 0}

    existing = {s.code: s for s in session.scalars(select(SkillModel))}
    for skill in plan.skills:
        row = existing.get(skill.code)
        if row is not None and row.sort_index != skill.sort_index:
            raise SkillOrderConflict(
                f"{skill.code} is stored with index {row.sort_index} but the plan gives "
                f"{skill.sort_index}. Changing a skill index would corrupt the model."
            )
        session.merge(
            SkillModel(
                code=skill.code,
                sort_index=skill.sort_index,
                area=skill.area,
                name_en=skill.name_en,
                name_si=skill.name_si,
                description=skill.description,
            )
        )
        counts["skills"] += 1
    session.flush()

    known = {q.id: q for q in session.scalars(select(QuestionModel))}
    for question in plan.questions:
        row = known.get(question.id)
        if row is None:
            row = QuestionModel(id=question.id, skill_code=question.skill_code, difficulty="easy")
            session.add(row)
        # Fields owned by the files are refreshed; verification and notes are left alone.
        row.skill_code = question.skill_code
        row.secondary_skill_codes = list(question.secondary_skill_codes)
        row.difficulty = question.difficulty
        row.est_seconds = question.est_seconds
        counts["questions"] += 1
    session.flush()

    for question in plan.questions:
        for variant in question.variants.values():
            session.execute(
                delete(QuestionPartModel).where(
                    QuestionPartModel.question_id == question.id,
                    QuestionPartModel.language == variant.language,
                )
            )
            session.merge(
                QuestionVariantModel(
                    question_id=question.id,
                    language=variant.language,
                    image_key=variant.image.key,
                    image_width_px=variant.image.width,
                    image_height_px=variant.image.height,
                    content_hash=variant.image.content_hash,
                    answer_key_raw=variant.answer_key_raw,
                )
            )
            session.flush()
            for part in variant.parts:
                session.add(
                    QuestionPartModel(
                        question_id=question.id,
                        language=variant.language,
                        part_no=part.part_no,
                        part_type=part.part_type,
                        answer_kind=part.answer_kind,
                        option_labels=list(part.option_labels) if part.option_labels else None,
                        correct_option=part.correct_option,
                        accepted_answers=list(part.alternatives) if part.alternatives else None,
                        instruction=part.instruction,
                        label_on_image=part.label,
                    )
                )
                counts["parts"] += 1
            counts["variants"] += 1
    session.flush()
    return counts
