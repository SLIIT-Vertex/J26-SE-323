"""In-process adapter from real Knowledge Tracing snapshots to the Tutor contract."""

import logging
import math
from collections.abc import Collection

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.adaptive_tutor.application.context_assembly import (
    EvidenceOrigin,
    EvidenceSource,
)
from app.knowledge_tracing.application.mastery import (
    MasteryResult,
    MasteryRetrievalRequest,
    MasteryStatus,
    validate_mastery_request_against_taxonomy,
)
from app.knowledge_tracing.application.mastery_service import (
    LearnerNotFoundError,
    MasteryService,
    ModelUnavailableError,
)
from app.knowledge_tracing.domain.mastery import MasterySnapshot

logger = logging.getLogger("mindbridge.adaptive_tutor.kt_mastery")


class KnowledgeTracingMasteryProvider:
    """Select one validated skill from the real KT all-skill snapshot."""

    source = EvidenceSource(
        source_id="knowledge-tracing:mastery-service",
        origin=EvidenceOrigin.REAL,
    )

    def __init__(
        self,
        service: MasteryService,
        valid_skill_ids: Collection[str],
        *,
        cold_start_default: float | None = None,
    ) -> None:
        self._service = service
        self._valid_skill_ids = frozenset(valid_skill_ids)
        if cold_start_default is not None and (
            not math.isfinite(cold_start_default) or not 0.0 <= cold_start_default <= 1.0
        ):
            raise ValueError("cold_start_default must be within [0, 1]")
        self._cold_start_default = cold_start_default
        if cold_start_default is not None:
            self.source = EvidenceSource(
                source_id="adaptive-tutor:experimental-cold-start-mastery-default",
                origin=EvidenceOrigin.SYNTHETIC,
            )
        if not self._valid_skill_ids:
            raise ValueError("valid_skill_ids must not be empty")

    def get_mastery(self, request: MasteryRetrievalRequest) -> MasteryResult:
        try:
            validate_mastery_request_against_taxonomy(request, self._valid_skill_ids)
        except ValueError:
            return self._result(request, MasteryStatus.NOT_FOUND)

        try:
            snapshot = self._service.current(request.learner_id)
        except LearnerNotFoundError:
            return self._result(request, MasteryStatus.NOT_FOUND)
        except (ModelUnavailableError, OSError) as error:
            logger.warning(
                "KT mastery model is unavailable: %s",
                type(error).__name__,
            )
            return self._result(request, MasteryStatus.PROVIDER_UNAVAILABLE)
        except SQLAlchemyError as error:
            logger.error(
                "KT mastery repository failed: %s",
                type(error).__name__,
            )
            return self._result(request, MasteryStatus.PROVIDER_ERROR)
        except Exception as error:
            logger.exception(
                "KT mastery service failed unexpectedly: %s",
                type(error).__name__,
            )
            return self._result(request, MasteryStatus.PROVIDER_ERROR)

        return self._from_snapshot(request, snapshot)

    def _from_snapshot(
        self,
        request: MasteryRetrievalRequest,
        snapshot: MasterySnapshot,
    ) -> MasteryResult:
        try:
            if snapshot.learner_id != request.learner_id:
                raise ValueError("snapshot learner mismatch")
            matches = [skill for skill in snapshot.skills if skill.code == request.skill_id]
            if len(matches) != 1:
                raise ValueError("snapshot must contain the requested skill exactly once")
            mastery = matches[0].mastery
            if mastery is None:
                if self._cold_start_default is not None:
                    return MasteryResult(
                        learner_id=request.learner_id,
                        skill_id=request.skill_id,
                        status=MasteryStatus.AVAILABLE,
                        mastery=self._cold_start_default,
                    )
                return self._result(request, MasteryStatus.NOT_FOUND)
            return MasteryResult(
                learner_id=request.learner_id,
                skill_id=request.skill_id,
                status=MasteryStatus.AVAILABLE,
                mastery=mastery,
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as error:
            logger.error(
                "KT mastery snapshot is invalid: %s",
                type(error).__name__,
            )
            return self._result(request, MasteryStatus.PROVIDER_ERROR)

    @staticmethod
    def _result(
        request: MasteryRetrievalRequest,
        status: MasteryStatus,
    ) -> MasteryResult:
        return MasteryResult(
            learner_id=request.learner_id,
            skill_id=request.skill_id,
            status=status,
        )
