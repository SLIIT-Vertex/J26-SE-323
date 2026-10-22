"""Durable G5-AREA-SIN-02 Punctuation Journey profile on the shared Sinhala package flow."""

from __future__ import annotations

from app.gamification.application.number_world_flow import NumberWorldFlowError
from app.gamification.application.sinhala_package_flow import SinhalaPackageFlow
from app.gamification.content import sinhala_punctuation


class SinhalaPunctuationFlow(SinhalaPackageFlow):
    experience_id = "sinhala_punctuation_journey"
    contract_version = "sinhala-punctuation-learning-flow-v1"
    context_version = "g5-sin-punctuation-context-v1"
    measurement_version = "sinhala-punctuation-independence-measurement-v1"
    missing_skill_error = "SINHALA_PUNCTUATION_SKILL_NOT_FOUND"
    episode_type_error = "SINHALA_PUNCTUATION_EPISODE_REQUIRED"
    operation_prefix = "sinhala_punctuation"

    def open(self, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def,override]
        # The line-break activity has no approved rule or example: it fails closed before
        # anything is reserved or presented.
        skill = self.skills.get(str(kwargs.get("atomic_skill_id")))
        if skill is not None and skill.review_blocked:
            raise NumberWorldFlowError("SINHALA_LINEBREAK_CONTENT_REVIEW_BLOCKED")
        return super().open(**kwargs)


SinhalaPunctuationFlow.bind(sinhala_punctuation)
