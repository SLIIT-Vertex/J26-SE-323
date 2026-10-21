from collections.abc import Collection
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.adaptive_tutor.application.context_assembly import (
    AssessmentEvidenceResult,
    ContextEvidenceRequest,
    EvidenceOrigin,
    EvidenceSource,
    EvidenceStatus,
)
from app.adaptive_tutor.infrastructure.tutor_assessment import (
    AssessmentInteractionStatus,
    AssessmentSnapshot,
    SqlAlchemyTutorAssessmentRepository,
)


class UnresolvedAssessmentEvidenceProvider:
    """Fail closed until interaction scope and error severity are approved."""

    source = EvidenceSource(
        source_id="assessment:authoritative-semantics-unresolved",
        origin=EvidenceOrigin.REAL,
    )

    def get_assessment_evidence(
        self,
        request: ContextEvidenceRequest,
    ) -> AssessmentEvidenceResult:
        if request.session_id is None or request.interaction_id is None:
            return AssessmentEvidenceResult(status=EvidenceStatus.CONTEXT_REQUIRED)
        return AssessmentEvidenceResult(status=EvidenceStatus.POLICY_UNRESOLVED)


class LedgerAssessmentEvidenceProvider:
    """Read persisted Tutor correlations without scoring or severity inference.

    The default configuration cannot produce completed AVAILABLE evidence. A controlled
    research composition must be explicit and is always labelled SYNTHETIC.
    """

    def __init__(
        self,
        repository: SqlAlchemyTutorAssessmentRepository,
        *,
        valid_skill_ids: Collection[str],
        eligible_scorer_sources: Collection[str] = (),
        eligible_severity_policy_versions: Collection[str] = (),
        controlled_research: bool = False,
    ) -> None:
        self._repository = repository
        self._valid_skill_ids = frozenset(valid_skill_ids)
        self._eligible_scorer_sources = frozenset(eligible_scorer_sources)
        self._eligible_severity_policy_versions = frozenset(eligible_severity_policy_versions)
        self._controlled_research = controlled_research
        if not self._valid_skill_ids:
            raise ValueError("valid_skill_ids must not be empty")
        self.source = EvidenceSource(
            source_id=(
                "adaptive-tutor:assessment-ledger-controlled"
                if controlled_research
                else "adaptive-tutor:assessment-ledger"
            ),
            origin=(EvidenceOrigin.SYNTHETIC if controlled_research else EvidenceOrigin.REAL),
        )

    def source_for_result(self, result: AssessmentEvidenceResult) -> EvidenceSource:
        """A committed empty ledger is real; controlled annotations remain synthetic."""

        if self._controlled_research and result.status is EvidenceStatus.NOT_YET_OBSERVED:
            return EvidenceSource(
                source_id="adaptive-tutor:assessment-ledger-empty-snapshot",
                origin=EvidenceOrigin.REAL,
            )
        return self.source

    def get_assessment_evidence(
        self,
        request: ContextEvidenceRequest,
    ) -> AssessmentEvidenceResult:
        if (
            request.session_id is None
            or request.interaction_id is None
            or request.interaction_sequence is None
            or request.as_of is None
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.CONTEXT_REQUIRED)
        if request.skill_id not in self._valid_skill_ids:
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)

        try:
            session_id = UUID(request.session_id)
            interaction_id = UUID(request.interaction_id)
        except ValueError:
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)

        try:
            snapshot = self._repository.snapshot(interaction_id, as_of=request.as_of)
            return self._result(snapshot, request, session_id)
        except (TimeoutError, ConnectionError, OperationalError):
            return AssessmentEvidenceResult(status=EvidenceStatus.PROVIDER_UNAVAILABLE)
        except SQLAlchemyError:
            return AssessmentEvidenceResult(status=EvidenceStatus.PROVIDER_ERROR)
        except (TypeError, ValueError, ValidationError):
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)
        except Exception:  # noqa: BLE001 - trust boundary must fail closed
            return AssessmentEvidenceResult(status=EvidenceStatus.PROVIDER_ERROR)

    def _result(
        self,
        snapshot: AssessmentSnapshot | None,
        request: ContextEvidenceRequest,
        session_id: UUID,
    ) -> AssessmentEvidenceResult:
        if snapshot is None:
            return AssessmentEvidenceResult(status=EvidenceStatus.NOT_FOUND)

        interaction = snapshot.interaction
        if interaction.session_id != session_id:
            return AssessmentEvidenceResult(status=EvidenceStatus.SESSION_MISMATCH)
        if (
            interaction.interaction_id != UUID(request.interaction_id or "")
            or interaction.learner_id != request.learner_id
            or interaction.skill_id != request.skill_id
            or interaction.interaction_sequence != request.interaction_sequence
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)
        assert request.as_of is not None
        if interaction.opened_at > request.as_of:
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)
        if interaction.status is AssessmentInteractionStatus.INVALIDATED:
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)
        if (
            interaction.status is AssessmentInteractionStatus.CLOSED
            or interaction.expires_at is not None
            and request.as_of > interaction.expires_at
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.STALE)
        if snapshot.pending_submission:
            return AssessmentEvidenceResult(status=EvidenceStatus.UNCERTAIN)

        latest = snapshot.latest_accepted
        if latest is None:
            return AssessmentEvidenceResult(
                status=EvidenceStatus.NOT_YET_OBSERVED,
                attempt_count=0,
                assessment_reference=f"interaction:{interaction.interaction_id}",
                observed_at=request.as_of,
            )

        if (
            not latest.scorer_authorized
            or not latest.source_mapping_approved
            or latest.source_component not in self._eligible_scorer_sources
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.POLICY_UNRESOLVED)
        if (
            latest.severity_category is None
            or latest.severity_value is None
            or latest.severity_policy_version is None
            or latest.observed_at is None
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.UNCERTAIN)
        if (
            not latest.severity_reviewed
            or latest.severity_policy_version not in self._eligible_severity_policy_versions
        ):
            return AssessmentEvidenceResult(status=EvidenceStatus.POLICY_UNRESOLVED)
        if latest.is_correct is None:
            return AssessmentEvidenceResult(status=EvidenceStatus.UNCERTAIN)
        if latest.is_correct and latest.severity_value != 0.0:
            return AssessmentEvidenceResult(status=EvidenceStatus.INVALID_EVIDENCE)

        return AssessmentEvidenceResult(
            status=EvidenceStatus.AVAILABLE,
            attempt_count=len(snapshot.accepted_attempts),
            is_correct=latest.is_correct,
            error_severity=latest.severity_value,
            assessment_reference=(f"{latest.source_component}:{latest.source_score_reference}"),
            observed_at=latest.observed_at,
            severity_policy_version=latest.severity_policy_version,
        )
