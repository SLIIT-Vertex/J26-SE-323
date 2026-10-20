"""In-process adapter from Shared Learner to the Tutor learner contract."""

import logging
from collections.abc import Collection
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.adaptive_tutor.application.context_assembly import (
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
    LearnerLookupResult,
)
from app.adaptive_tutor.application.generation import SUPPORTED_RESPONSE_LANGUAGES
from app.shared.learner.domain import Learner
from app.shared.learner.service import LearnerNotFoundError, LearnerService

logger = logging.getLogger("mindbridge.adaptive_tutor.shared_learner")


class SharedLearnerProvider:
    """Validate a learner returned by the existing Shared Learner service."""

    source = EvidenceSource(
        source_id="shared-learner:learner-service",
        origin=EvidenceOrigin.REAL,
    )

    def __init__(
        self,
        service: LearnerService,
        *,
        supported_grades: Collection[int] = (4, 5),
        supported_languages: Collection[str] = SUPPORTED_RESPONSE_LANGUAGES,
    ) -> None:
        self._service = service
        self._supported_grades = frozenset(supported_grades)
        self._supported_languages = frozenset(supported_languages)
        if not self._supported_grades:
            raise ValueError("supported_grades must not be empty")
        if not self._supported_languages:
            raise ValueError("supported_languages must not be empty")

    def get_learner(self, learner_id: UUID) -> LearnerLookupResult:
        try:
            learner = self._service.get(learner_id)
        except LearnerNotFoundError:
            return LearnerLookupResult(status=EvidenceStatus.NOT_FOUND)
        except SQLAlchemyError as error:
            logger.error(
                "Shared Learner repository failed: %s",
                type(error).__name__,
            )
            return LearnerLookupResult(status=EvidenceStatus.PROVIDER_ERROR)
        except Exception as error:
            logger.exception(
                "Shared Learner service failed unexpectedly: %s",
                type(error).__name__,
            )
            return LearnerLookupResult(status=EvidenceStatus.PROVIDER_ERROR)

        if not self._is_valid(learner, learner_id):
            logger.error("Shared Learner returned invalid Tutor evidence")
            return LearnerLookupResult(status=EvidenceStatus.INVALID_EVIDENCE)
        return LearnerLookupResult(status=EvidenceStatus.AVAILABLE, learner=learner)

    def _is_valid(self, learner: object, learner_id: UUID) -> bool:
        return (
            isinstance(learner, Learner)
            and learner.id == learner_id
            and learner.grade in self._supported_grades
            and learner.preferred_language in self._supported_languages
        )
