"""Makes this week's paper for many learners at once (the Saturday run).

Each learner is handled on their own: a failure for one child is recorded and the rest carry on.
Running it twice in the same week is harmless, because a learner who already has this week's
paper is left alone.
"""

import logging
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from uuid import UUID

from app.knowledge_tracing.application.paper_generation import (
    NotEligibleYetError,
    PaperRequest,
    PaperService,
)

logger = logging.getLogger("mindbridge.weekly_batch")


@dataclass(slots=True)
class BatchResult:
    created: list[UUID] = field(default_factory=list)
    already_had: list[UUID] = field(default_factory=list)
    not_eligible: list[UUID] = field(default_factory=list)  # joined too recently
    failed: list[tuple[UUID, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.created) + len(self.already_had) + len(self.not_eligible) + len(self.failed)
        )

    @property
    def ok(self) -> bool:
        return not self.failed


# One service per learner, in its own database session, so one failure cannot spoil another.
ServiceScope = Callable[[], AbstractContextManager[PaperService]]


def generate_weekly_batch(
    learner_ids: Iterable[UUID],
    service_scope: ServiceScope,
    request: PaperRequest = PaperRequest(),  # noqa: B008
) -> BatchResult:
    result = BatchResult()
    for learner_id in learner_ids:
        try:
            with service_scope() as service:
                generated = service.generate_weekly(learner_id, request)
        except NotEligibleYetError:
            result.not_eligible.append(learner_id)
            continue
        except Exception as error:  # noqa: BLE001  (one child's failure must not stop the others)
            logger.warning("weekly paper failed for %s: %s", learner_id, error)
            result.failed.append((learner_id, f"{type(error).__name__}: {error}"))
            continue
        (result.created if generated.created else result.already_had).append(learner_id)
    return result
