"""Mastery adapter over the published Knowledge Tracing contract.

Mastery is one probability per Universal parent, such as ``MAT-FRC``, not per
fine-grained gamification skill. Model 1 and Model 2 therefore share that parent
value. ``MasteryResult`` carries no timestamp, uncertainty, or model version, so
those fields stay empty instead of being invented.
"""

from collections.abc import Collection, Mapping
from uuid import UUID

from app.gamification.application.ports import AuditOutput, Clock
from app.gamification.application.records import AuditEvent, SkillMasteryEvidence
from app.gamification.domain.types import ContractVersion, SkillId
from app.knowledge_tracing.application.mastery import (
    MasteryProvider,
    MasteryRetrievalRequest,
    MasteryStatus,
)

MASTERY_CONTRACT_VERSION = ContractVersion("knowledge-tracing-mastery-v1")
MASTERY_MODEL_VERSION = "knowledge-tracing-mastery-v1"


class NullMasteryEvidenceGateway:
    def get_mastery(self, *, learner_id: UUID, skill_id: SkillId) -> None:
        del learner_id, skill_id


class KnowledgeTracingMasteryGateway:
    def __init__(
        self,
        *,
        provider: MasteryProvider,
        crosswalk: Mapping[str, str],
        allowed_universal_ids: Collection[str],
        audit: AuditOutput,
        clock: Clock,
    ) -> None:
        self._provider = provider
        self._crosswalk = dict(crosswalk)
        self._allowed = set(allowed_universal_ids)
        self._audit = audit
        self._clock = clock
        self.requested_skill_ids: list[str] = []

    def get_mastery(self, *, learner_id: UUID, skill_id: SkillId) -> SkillMasteryEvidence | None:
        universal = self._crosswalk.get(str(skill_id))
        if universal is None:
            self._audit_missing("MASTERY_CROSSWALK_MISSING", skill_id)
            return None
        if universal not in self._allowed:
            self._audit_missing("UNIVERSAL_SKILL_NOT_IN_TAXONOMY", skill_id)
            return None
        self.requested_skill_ids.append(universal)
        try:
            result = self._provider.get_mastery(
                MasteryRetrievalRequest(learner_id=learner_id, skill_id=universal)
            )
        except Exception:  # noqa: BLE001  # a provider failure is a recorded absence
            self._audit_missing("MASTERY_PROVIDER_EXCEPTION", skill_id)
            return None
        if result.status is not MasteryStatus.AVAILABLE or result.mastery is None:
            self._audit_missing(f"MASTERY_{result.status.value}", skill_id)
            return None
        return SkillMasteryEvidence(
            learner_id=result.learner_id,
            skill_id=skill_id,
            universal_skill_id=universal,
            mastery_probability=result.mastery,
            model_version=MASTERY_MODEL_VERSION,
            contract_version=MASTERY_CONTRACT_VERSION,
        )

    def _audit_missing(self, reason: str, skill_id: SkillId) -> None:
        self._audit.write(
            AuditEvent(
                event_type="mastery_missing",
                subject_id=str(skill_id),
                occurred_at=self._clock.now(),
                reason_codes=(reason,),
                metadata={"skill_id": str(skill_id)},
            )
        )
