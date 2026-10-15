"""Authoring retrieval over the shared curriculum contract.

Gamification skill IDs are translated to Universal IDs before the request leaves
this component. The request purpose is CONTENT_AUTHORING. A missing crosswalk
raises because this path is authoring, not an adaptive episode.
"""

from collections.abc import Mapping

from app.curriculum.application.retrieval import (
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetriever,
)


class SharedCurriculumAdapter:
    def __init__(self, retriever: CurriculumRetriever, crosswalk: Mapping[str, str]) -> None:
        self._retriever = retriever
        self._crosswalk = dict(crosswalk)
        self.requested_skill_ids: list[str] = []

    def retrieve(
        self,
        *,
        learner_question: str,
        skill_id: str,
        grade: int,
        requested_language: str | None = None,
        limit: int = 5,
    ) -> CurriculumRetrievalResult:
        universal = self._crosswalk.get(skill_id)
        if universal is None:
            raise ValueError(f"no universal skill id for {skill_id}")
        self.requested_skill_ids.append(universal)
        return self._retriever.retrieve(
            CurriculumRetrievalRequest(
                learner_question=learner_question,
                skill_id=universal,
                grade=grade,  # type: ignore[arg-type]
                requested_language=requested_language,
                purpose="CONTENT_AUTHORING",
                limit=limit,  # type: ignore[arg-type]
            )
        )
