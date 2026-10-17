"""Learner State support need through the published SupportNeedProvider contract.

``UNCERTAIN`` has no numeric value on that contract. The uncertainty flag is the
feature, and it is never a struggle trigger by itself.
"""

from collections.abc import Collection, Mapping
from datetime import datetime
from uuid import UUID

from app.gamification.application.ports import AuditOutput, Clock
from app.gamification.application.records import AuditEvent, LearnerStateEvidence
from app.gamification.domain.types import ContractVersion, SkillId
from app.learner_state.application.support_need import (
    RECOMMENDED_MAX_STATE_AGE_MS,
    SupportNeedProvider,
    SupportNeedRequest,
    SupportNeedStatus,
)

SUPPORT_NEED_CONTRACT = ContractVersion("learner-state-support-need-v1")


class LearnerStateSupportNeedGateway:
    def __init__(
        self,
        *,
        provider: SupportNeedProvider,
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

    def get_support_evidence(
        self,
        *,
        learner_id: UUID,
        skill_id: SkillId,
        observed_no_earlier_than: datetime,
        session_id: UUID | None = None,
    ) -> LearnerStateEvidence | None:
        universal = self._crosswalk.get(str(skill_id))
        if universal is None:
            self._audit_missing("SUPPORT_NEED_CROSSWALK_MISSING", skill_id)
            return None
        if universal not in self._allowed:
            self._audit_missing("UNIVERSAL_SKILL_NOT_IN_TAXONOMY", skill_id)
            return None
        self.requested_skill_ids.append(universal)
        try:
            result = self._provider.get_support_need(
                SupportNeedRequest(
                    learner_id=learner_id,
                    skill_id=universal,
                    session_id=None if session_id is None else str(session_id),
                    max_age_ms=RECOMMENDED_MAX_STATE_AGE_MS,
                )
            )
        except Exception:  # noqa: BLE001  # a provider failure is a recorded absence
            self._audit_missing("SUPPORT_NEED_PROVIDER_EXCEPTION", skill_id)
            return None
        if result.status is SupportNeedStatus.NOT_FOUND:
            self._audit_missing("SUPPORT_NEED_NOT_FOUND", skill_id)
            return None
        if result.observed_at is None or result.observed_at < observed_no_earlier_than:
            self._audit_missing("LEARNER_STATE_STALE", skill_id)
            return None
        if result.status is SupportNeedStatus.UNCERTAIN:
            return LearnerStateEvidence(
                learner_id=learner_id,
                skill_id=skill_id,
                universal_skill_id=universal,
                observed_at=result.observed_at,
                contract_version=SUPPORT_NEED_CONTRACT,
                uncertain=True,
                recommended_action=result.recommended_action,
            )
        if result.status is not SupportNeedStatus.AVAILABLE or result.support_need is None:
            self._audit_missing(f"SUPPORT_NEED_{result.status.value}", skill_id)
            return None
        return LearnerStateEvidence(
            learner_id=learner_id,
            skill_id=skill_id,
            universal_skill_id=universal,
            observed_at=result.observed_at,
            contract_version=SUPPORT_NEED_CONTRACT,
            support_need=result.support_need,
            recommended_action=result.recommended_action,
        )

    def _audit_missing(self, reason: str, skill_id: SkillId) -> None:
        self._audit.write(
            AuditEvent(
                event_type="support_need_missing",
                subject_id=str(skill_id),
                occurred_at=self._clock.now(),
                reason_codes=(reason,),
                metadata={"skill_id": str(skill_id)},
            )
        )
