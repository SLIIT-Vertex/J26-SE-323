"""Durable development orchestration for the single draft Sinhala skill.

The service is intentionally unavailable to production/child composition. It persists a
hash-bound projection plus append-only events for every accepted command. Public manifests never
contain answer keys; scoring uses the server-authoritative Independence Gain scorer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.gamification.application.adaptive_game_flow import AdaptiveGameFlow
from app.gamification.application.addition_adventure_flow import AdditionAdventureFlow
from app.gamification.application.capacity_adventure_flow import CapacityAdventureFlow
from app.gamification.application.decimal_adventure_flow import DecimalAdventureFlow
from app.gamification.application.direction_adventure_flow import DirectionAdventureFlow
from app.gamification.application.distance_adventure_flow import DistanceAdventureFlow
from app.gamification.application.division_adventure_flow import DivisionAdventureFlow
from app.gamification.application.fraction_adventure_flow import FractionAdventureFlow
from app.gamification.application.mass_adventure_flow import MassAdventureFlow
from app.gamification.application.money_adventure_flow import MoneyAdventureFlow
from app.gamification.application.multiplication_adventure_flow import MultiplicationAdventureFlow
from app.gamification.application.number_patterns_flow import NumberPatternsFlow
from app.gamification.application.number_world_flow import NumberWorldFlow, NumberWorldFlowError
from app.gamification.application.roman_adventure_flow import RomanAdventureFlow
from app.gamification.application.shape_adventure_flow import ShapeAdventureFlow
from app.gamification.application.subtraction_adventure_flow import SubtractionAdventureFlow
from app.gamification.application.time_adventure_flow import TimeAdventureFlow
from app.gamification.content.curriculum_registry import (
    ItemRevision,
    PublicCurriculumPackage,
    load_curriculum_public_package,
    load_curriculum_server_answer_keys,
)
from app.gamification.domain.types import AssistanceState, ExperimentMode, MeasurementRole
from app.gamification.modeling.independence_gain.measurement import (
    AttemptSubmission,
    MeasurementInput,
    NormalizedEvent,
    Presentation,
    ProbeReservation,
    ScaffoldExposure,
    SupportWithdrawal,
    assert_unsupported_after_may_begin,
    calculate_measurement,
    development_curriculum_scorer,
)
from app.gamification.modeling.misconception_inference.inference import (
    CATALOGUE_VERSION as MODEL1_MAPPING_VERSION,
)
from app.gamification.modeling.misconception_inference.inference import (
    MODEL_VERSION as MODEL1_VERSION,
)
from app.gamification.modeling.misconception_inference.inference import (
    InferenceEvidence,
    InteractionSummary,
    Model1FeatureBuilder,
    Model1InferenceInput,
    development_curriculum_candidate,
)
from app.gamification.modeling.support_selection.selection import (
    ContextualScaffoldPolicy,
    DifficultyEvidence,
    EligibilityInput,
    EpisodeMetadata,
    ItemMetadata,
    Model2ContextInput,
    PolicyMode,
    UnsupportedEvidence,
    development_curriculum_scaffolds,
)

PROTOCOL_VERSION = "adaptive-episode-v1"
CONTRACT_VERSION = "learning_flow-orchestration-v1"
FORMULA_VERSION = "raw-independence-gain-v1"
_FORBIDDEN_TELEMETRY_KEYS = frozenset(
    {
        "answer",
        "selected_option_id",
        "correct_option_id",
        "prompt",
        "question_text",
        "name",
        "email",
        "phone",
        "address",
        "coordinates",
        "audio",
        "video",
    }
)


def request_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class LearningFlowOrchestrationError(ValueError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code)
        self.code = code
        self.context = context


class LearningFlowPersistenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredLearningFlowRun:
    episode_id: UUID
    revision: int
    state: Mapping[str, object]


class LearningFlowStore(Protocol):
    def get(self, episode_id: UUID, *, for_update: bool = False) -> StoredLearningFlowRun: ...

    def receipt(self, key: str, request_sha256: str) -> dict[str, object] | None: ...

    def create(self, **values: object) -> None: ...

    def replace(self, **values: object) -> None: ...

    def reconstruct(self, episode_id: UUID) -> dict[str, object]: ...

    def export_manifest(self, episode_id: UUID) -> dict[str, object]: ...

    def support_history(
        self, *, learner_id: UUID, skill_id: str
    ) -> tuple[Mapping[str, object], ...]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class ProbeGateway(Protocol):
    version: str

    def reserve(
        self, *, learner_id: UUID, episode_id: UUID, item_revision_id: str, at: datetime
    ) -> str: ...

    def confirm_unexposed(self, reservation_id: str) -> bool: ...

    def mark_used(self, reservation_id: str, *, at: datetime) -> None: ...


class EvidencePublisher(Protocol):
    version: str

    def publish(self, evidence: Mapping[str, object]) -> None: ...


class LocalProbeGateway:
    """Test/development stand-in for the shared cross-platform reservation service."""

    version = "probe-gateway-development-v1"

    def __init__(self) -> None:
        self._active: dict[tuple[UUID, str], str] = {}
        self._clean: set[str] = set()
        self._used: set[str] = set()

    def reserve(
        self, *, learner_id: UUID, episode_id: UUID, item_revision_id: str, at: datetime
    ) -> str:
        del at
        key = (learner_id, item_revision_id)
        if key in self._active:
            raise LearningFlowOrchestrationError("PROBE_ALREADY_RESERVED_OR_EXPOSED")
        token = f"{self.version}:{episode_id}:{item_revision_id}"
        self._active[key] = token
        self._clean.add(token)
        return token

    def confirm_unexposed(self, reservation_id: str) -> bool:
        return reservation_id in self._clean

    def contaminate(self, reservation_id: str) -> None:
        self._clean.discard(reservation_id)

    def mark_used(self, reservation_id: str, *, at: datetime) -> None:
        del at
        if reservation_id not in self._clean:
            raise LearningFlowOrchestrationError("PROBE_RESERVATION_UNAVAILABLE")
        self._used.add(reservation_id)


class RecordingEvidencePublisher:
    version = "knowledge-tracing-evidence-v1"

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def publish(self, evidence: Mapping[str, object]) -> None:
        self.records.append(dict(evidence))


class LearningFlowOrchestrator:
    """State-transition owner for one durable development/test episode."""

    def __init__(
        self,
        store: LearningFlowStore,
        *,
        probe_gateway: ProbeGateway,
        evidence_publisher: EvidencePublisher,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._probe = probe_gateway
        self._publisher = evidence_publisher
        self._now = now or (lambda: datetime.now(UTC))
        flows: tuple[AdaptiveGameFlow, ...] = (
            NumberWorldFlow(store, probe_gateway, evidence_publisher, now=self._now),
            AdditionAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            NumberPatternsFlow(store, probe_gateway, evidence_publisher, now=self._now),
            SubtractionAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            FractionAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            MultiplicationAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            TimeAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            DivisionAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            DistanceAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            MoneyAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            CapacityAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            MassAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            ShapeAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            DirectionAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            DecimalAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
            RomanAdventureFlow(store, probe_gateway, evidence_publisher, now=self._now),
        )
        self._area_flows = {flow.area_id: flow for flow in flows}
        self._experience_flows = {flow.experience_id: flow for flow in flows}

    def open_episode(
        self,
        *,
        learner_id: UUID,
        session_id: UUID,
        grade: int,
        medium: str,
        condition: Literal["baseline", "proposed"],
        environment: str,
        allow_draft: bool,
        idempotency_key: str,
        area_id: str | None = None,
        atomic_skill_id: str | None = None,
    ) -> dict[str, object]:
        adaptive_flow = self._area_flows.get(area_id or "")
        if adaptive_flow is not None:
            if grade != 5 or medium != "si":
                raise LearningFlowOrchestrationError("GRADE5_SINHALA_REQUIRED")
            if atomic_skill_id is None:
                raise LearningFlowOrchestrationError("ATOMIC_SKILL_REQUIRED")
            try:
                return adaptive_flow.open(
                    learner_id=learner_id,
                    session_id=session_id,
                    condition=condition,
                    environment=environment,
                    allow_draft=allow_draft,
                    atomic_skill_id=atomic_skill_id,
                    idempotency_key=idempotency_key,
                )
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        request: dict[str, object] = {
            "op": "open",
            "learner_id": str(learner_id),
            "session_id": str(session_id),
            "grade": grade,
            "medium": medium,
            "condition": condition,
            "environment": environment,
            "allow_draft": allow_draft,
        }
        prior = self._receipt(idempotency_key, request)
        if prior is not None:
            return prior
        if environment not in {"development", "test"} or not allow_draft:
            raise LearningFlowOrchestrationError("HUMAN_APPROVAL_REQUIRED")
        if grade != 5 or medium != "si":
            raise LearningFlowOrchestrationError("GRADE5_SINHALA_REQUIRED")
        package = load_curriculum_public_package(allow_draft=True)
        before = _item(package, "unsupported_before")
        after = _item(package, "unsupported_after")
        episode_id = uuid4()
        at = self._now()
        reservation_id = self._probe.reserve(
            learner_id=learner_id,
            episode_id=episode_id,
            item_revision_id=after.revision_id,
            at=at,
        )
        reservation_uuid = uuid5(NAMESPACE_URL, reservation_id)
        before_presentation_id = uuid4()
        event = _event(1, "unsupported_before_presented", at, before_presentation_id)
        state: dict[str, object] = {
            "contract_version": CONTRACT_VERSION,
            "episode_id": str(episode_id),
            "session_id": str(session_id),
            "learner_id": str(learner_id),
            "skill_id": package.skill.skill_id,
            "skill_version": package.skill.skill_version,
            "content_package_version": package.package_version,
            "protocol_version": PROTOCOL_VERSION,
            "environment": environment,
            "condition": condition,
            "status": "before_presented",
            "revision": 1,
            "probe_gateway_version": self._probe.version,
            "evidence_gateway_version": self._publisher.version,
            "external_gateways": {
                "authentication": {
                    "version": "development-principal-v1",
                    "status": "development_only",
                },
                "learner_profile": {
                    "version": "shared-learner-profile-v1",
                    "status": "grade5_sinhala_eligible",
                },
                "learner_state": {
                    "version": "learner-state-port-v1",
                    "status": "missing_safe_fallback",
                },
                "verified_tutor": {
                    "version": "verified-sinhala-tutor-port-v1",
                    "status": "unavailable_authored_fallback",
                    "probe_access": False,
                    "research_action_control": False,
                },
                "knowledge_tracing": {
                    "version": self._publisher.version,
                    "status": "durable_outbox",
                    "may_overwrite_independence_gain": False,
                },
            },
            "probe_reservation_id": reservation_id,
            "probe_reservation_uuid": str(reservation_uuid),
            "presentations": [_presentation_record(before, before_presentation_id, "none", 1)],
            "attempts": [],
            "model1": None,
            "model2": None,
            "scaffold_exposure": None,
            "withdrawal": None,
            "raw_independence_gain": None,
            "percentage_point_value": None,
            "validity": None,
            "exclusion_reasons": [],
            "policy_update_status": "not_authorized_incomplete",
            "reward": None,
            "telemetry": [],
            "next_client_sequence": 1,
            "events": [event],
        }
        response = self._child_response(state, before)
        self._atomic(
            lambda: self._store.create(
                state=state,
                idempotency_key=idempotency_key,
                request_sha256=request_digest(request),
                response=response,
                now=at,
            )
        )
        return response

    def submit_before(
        self,
        episode_id: UUID,
        *,
        option_id: str | None,
        constructed_response: Mapping[str, object] | None = None,
        response_time_ms: int | None = None,
        interaction_summary: Mapping[str, object] | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        adaptive_flow = self._adaptive_flow(episode_id)
        if adaptive_flow is not None:
            try:
                return adaptive_flow.submit_before(
                    episode_id,
                    option_id=option_id,
                    constructed_response=constructed_response,
                    response_time_ms=response_time_ms,
                    interaction_summary=interaction_summary,
                    idempotency_key=idempotency_key,
                )
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        if option_id is None:
            raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")
        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": "submit_before",
                "episode_id": str(episode_id),
                "option_id": option_id,
                "response_time_ms": response_time_ms,
            },
            expected="before_presented",
            transition=lambda state, package, at: self._score_before(
                state, package, option_id, response_time_ms, at
            ),
        )

    def complete_support(
        self,
        episode_id: UUID,
        *,
        duration_ms: int,
        steps_viewed: int,
        manifest_revision_id: str,
        grouped_count: int,
        group_sizes: tuple[int, int],
        idempotency_key: str,
        interaction_summary: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        adaptive_flow = self._adaptive_flow(episode_id)
        if adaptive_flow is not None:
            try:
                return adaptive_flow.complete_support(
                    episode_id,
                    duration_ms=duration_ms,
                    steps_viewed=steps_viewed,
                    manifest_revision_id=manifest_revision_id,
                    interaction_summary=interaction_summary or {"completed": False},
                    idempotency_key=idempotency_key,
                )
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        if (
            duration_ms < 0
            or steps_viewed < 1
            or steps_viewed > 8
            or grouped_count < 2
            or len(group_sizes) != 2
        ):
            raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")
        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": "complete_support",
                "episode_id": str(episode_id),
                "duration_ms": duration_ms,
                "steps_viewed": steps_viewed,
                "manifest_revision_id": manifest_revision_id,
                "grouped_count": grouped_count,
                "group_sizes": list(group_sizes),
            },
            expected="support_active",
            transition=lambda state, _package, at: self._support_complete(
                state,
                duration_ms,
                steps_viewed,
                manifest_revision_id,
                grouped_count,
                group_sizes,
                at,
            ),
        )

    def withdraw_support(
        self,
        episode_id: UUID,
        *,
        request_id: UUID,
        support_revision_id: str,
        manifest_revision_id: str,
        all_support_removed: bool,
        answer_revealing_state_cleared: bool,
        input_handlers_cleared: bool,
        idempotency_key: str,
    ) -> dict[str, object]:
        adaptive_flow = self._adaptive_flow(episode_id)
        if adaptive_flow is not None:
            try:
                return adaptive_flow.withdraw(
                    episode_id,
                    request_id=request_id,
                    support_revision_id=support_revision_id,
                    manifest_revision_id=manifest_revision_id,
                    all_support_removed=all_support_removed,
                    answer_revealing_state_cleared=answer_revealing_state_cleared,
                    input_handlers_cleared=input_handlers_cleared,
                    idempotency_key=idempotency_key,
                )
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": "withdraw_support",
                "episode_id": str(episode_id),
                "request_id": str(request_id),
                "support_revision_id": support_revision_id,
                "manifest_revision_id": manifest_revision_id,
                "all_support_removed": all_support_removed,
                "answer_revealing_state_cleared": answer_revealing_state_cleared,
                "input_handlers_cleared": input_handlers_cleared,
            },
            expected="support_complete",
            transition=lambda state, _package, at: self._withdraw(
                state,
                request_id,
                support_revision_id,
                manifest_revision_id,
                all_support_removed,
                answer_revealing_state_cleared,
                input_handlers_cleared,
                at,
            ),
        )

    def present_after(self, episode_id: UUID, *, idempotency_key: str) -> dict[str, object]:
        adaptive_flow = self._adaptive_flow(episode_id)
        if adaptive_flow is not None:
            try:
                return adaptive_flow.present_after(episode_id, idempotency_key=idempotency_key)
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        return self._mutate(
            episode_id,
            idempotency_key,
            {"op": "present_after", "episode_id": str(episode_id)},
            expected="support_withdrawn",
            transition=self._present_after,
        )

    def submit_after(
        self,
        episode_id: UUID,
        *,
        option_id: str | None,
        constructed_response: Mapping[str, object] | None = None,
        response_time_ms: int | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        adaptive_flow = self._adaptive_flow(episode_id)
        if adaptive_flow is not None:
            try:
                return adaptive_flow.submit_after(
                    episode_id,
                    option_id=option_id,
                    constructed_response=constructed_response,
                    response_time_ms=response_time_ms,
                    idempotency_key=idempotency_key,
                )
            except NumberWorldFlowError as error:
                raise LearningFlowOrchestrationError(error.code, **error.context) from error
        if option_id is None:
            raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")
        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": "submit_after",
                "episode_id": str(episode_id),
                "option_id": option_id,
                "response_time_ms": response_time_ms,
            },
            expected="after_presented",
            transition=lambda state, package, at: self._score_after(
                state, package, option_id, response_time_ms, at
            ),
        )

    def ingest_telemetry(
        self,
        episode_id: UUID,
        *,
        batch_id: UUID,
        first_sequence: int,
        events: tuple[Mapping[str, object], ...],
        idempotency_key: str,
    ) -> dict[str, object]:
        if not events or len(events) > 50:
            raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")
        for offset, event in enumerate(events):
            if event.get("sequence") != first_sequence + offset:
                raise LearningFlowOrchestrationError("CLIENT_SEQUENCE_CONFLICT")
            payload = event.get("payload", {})
            if not isinstance(payload, Mapping) or len(payload) > 8:
                raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")
            if _FORBIDDEN_TELEMETRY_KEYS.intersection(payload):
                raise LearningFlowOrchestrationError("PII_OR_ANSWER_DATA_REJECTED")
            if event.get("version") != 1:
                raise LearningFlowOrchestrationError("EVENT_VERSION_UNSUPPORTED")

        def transition(
            state: dict[str, object], _package: PublicCurriculumPackage, at: datetime
        ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
            expected = int(state["next_client_sequence"])
            existing = {str(row["event_id"]): row for row in state["telemetry"]}  # type: ignore[index]
            if first_sequence > expected:
                raise LearningFlowOrchestrationError(
                    "CLIENT_SEQUENCE_GAP", expected_sequence=expected
                )
            accepted = 0
            duplicates = 0
            for event in events:
                event_id = str(event["event_id"])
                if event_id in existing:
                    if request_digest(existing[event_id]) != request_digest(dict(event)):
                        raise LearningFlowOrchestrationError("DUPLICATE_EVENT_CONFLICT")
                    duplicates += 1
                    continue
                if int(event["sequence"]) < expected:
                    raise LearningFlowOrchestrationError(
                        "LATE_EVENT_CONFLICT", expected_sequence=expected
                    )
                state["telemetry"].append(dict(event))  # type: ignore[union-attr]
                accepted += 1
                expected += 1
            state["next_client_sequence"] = expected
            _append_event(
                state,
                "telemetry_batch_ingested",
                at,
                None,
                {"batch_id": str(batch_id), "accepted": accepted, "duplicates": duplicates},
            )
            response = {
                "accepted": accepted,
                "duplicates": duplicates,
                "next_sequence": expected,
            }
            return state, response, "telemetry_ingested", ("PRIVACY_FILTERED",)

        return self._mutate_any(
            episode_id,
            idempotency_key,
            {
                "op": "telemetry",
                "batch_id": str(batch_id),
                "first_sequence": first_sequence,
                "events": [dict(row) for row in events],
            },
            transition,
        )

    def reconstruct(self, episode_id: UUID) -> dict[str, object]:
        try:
            return self._store.reconstruct(episode_id)
        except LearningFlowPersistenceError as error:
            raise LearningFlowOrchestrationError(str(error)) from error

    def export_manifest(self, episode_id: UUID) -> dict[str, object]:
        try:
            return self._store.export_manifest(episode_id)
        except LearningFlowPersistenceError as error:
            raise LearningFlowOrchestrationError(str(error)) from error

    def invalidate(
        self, episode_id: UUID, *, reason: str, idempotency_key: str
    ) -> dict[str, object]:
        if not reason or len(reason) > 64:
            raise LearningFlowOrchestrationError("PAYLOAD_OUT_OF_BOUNDS")

        def transition(
            state: dict[str, object], _package: PublicCurriculumPackage, at: datetime
        ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
            state["status"] = "invalidated"
            state["validity"] = "invalid"
            state["exclusion_reasons"] = sorted({*state.get("exclusion_reasons", []), reason})
            state["policy_update_status"] = "not_authorized_invalid"
            _append_event(state, "episode_invalidated", at, None, {"reason": reason})
            return state, self._summary(state), "episode_invalidated", (reason,)

        return self._mutate_any(
            episode_id,
            idempotency_key,
            {"op": "invalidate", "episode_id": str(episode_id), "reason": reason},
            transition,
        )

    def _score_before(
        self,
        state: dict[str, object],
        package: PublicCurriculumPackage,
        option_id: str,
        response_time_ms: int | None,
        at: datetime,
    ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
        before = _item(package, "unsupported_before")
        scored = self._score(state, before, option_id, AssistanceState.NONE, response_time_ms, at)
        state["attempts"].append(scored)  # type: ignore[union-attr]
        _append_event(state, "unsupported_before_scored", at, UUID(scored["presentation_id"]))
        self._publish_score(state, scored)
        if Decimal(str(scored["earned_score"])) == Decimal(str(scored["maximum_score"])):
            state["status"] = "completed"
            state["validity"] = "not_applicable_no_support"
            state["policy_update_status"] = "not_authorized_no_support"
            state["reward"] = {"points": 1, "reason": "independent_correct"}
            _append_event(state, "episode_completed_no_support", at)
            return state, self._summary(state), "episode_completed", ("NO_SUPPORT_REQUIRED",)
        keys = load_curriculum_server_answer_keys()
        mapping = keys[before.revision_id].distractor_misconception_ids.get(
            option_id, "unknown_or_other"
        )
        evidence_id = uuid4()
        evidence = InferenceEvidence(
            evidence_id=evidence_id,
            event_ids=(UUID(str(state["events"][-1]["event_id"])),),  # type: ignore[index]
            attempt_id=UUID(str(scored["attempt_id"])),
            episode_id=UUID(str(state["episode_id"])),
            presentation_id=UUID(str(scored["presentation_id"])),
            item_revision_id=before.revision_id,
            content_version=before.content_version,
            observed_at=at,
            measurement_role=MeasurementRole.UNSUPPORTED_BEFORE,
            assistance_state=AssistanceState.NONE,
            earned_score=float(scored["earned_score"]),
            maximum_score=float(scored["maximum_score"]),
            selected_response=option_id,
            distractor_misconception_code=mapping,
            structured_error_code=mapping,
            attempt_number=1,
            active_response_ms=None,
            wall_clock_ms=None,
            inactivity_ms=None,
            interactions=InteractionSummary(),
            quality="partial",
            missing_fields=("active_response_ms", "wall_clock_ms", "inactivity_ms"),
        )
        inference_input = Model1InferenceInput(
            learner_id=UUID(str(state["learner_id"])),
            pseudonymous=True,
            grade=5,
            medium="si",
            skill_id=str(state["skill_id"]),
            skill_version=str(state["skill_version"]),
            episode_id=UUID(str(state["episode_id"])),
            presentation_id=UUID(str(scored["presentation_id"])),
            item_revision_id=before.revision_id,
            inference_at=at,
            evidence_window_version="learning_flow-pre-decision-window-v1",
            evidence=(evidence,),
            recent_same_skill_errors=(),
            recent_error_evidence_ids=(),
            recent_errors_as_of=None,
            previous_beliefs={},
            previous_belief_snapshot_id=None,
            previous_belief_at=None,
            optional_evidence=(),
            mapping_version=MODEL1_MAPPING_VERSION,
            model_version=MODEL1_VERSION,
            development_mode=True,
        )
        feature_snapshot = Model1FeatureBuilder().build(inference_input)
        belief = development_curriculum_candidate(
            artifact_sha256="0" * 64, allow_draft=True
        ).predict(feature_snapshot)
        state["model1"] = {
            "interface_version": "model1-inference-interface-v1",
            "feature_snapshot_id": str(feature_snapshot.snapshot_id),
            "belief_snapshot_id": str(belief.belief_snapshot_id),
            "feature_schema_version": belief.feature_schema_version,
            "model_version": belief.model_version,
            "mapping_version": belief.mapping_version,
            "evidence_ids": [str(value) for value in belief.evidence_event_ids],
            "evidence_presentation_id": scored["presentation_id"],
            "top_hypothesis": belief.top_hypothesis,
            "probabilities": dict(belief.probabilities),
            "abstained": belief.abstained,
            "low_confidence": belief.low_confidence,
            "artifact_sha256": belief.artifact_sha256,
            "synthetic_development_only": True,
            "uses_post_decision_evidence": False,
        }
        scaffolds = development_curriculum_scaffolds(allow_draft=True)
        after = _item(package, "unsupported_after")
        experiment_mode = (
            ExperimentMode.BASELINE if state["condition"] == "baseline" else ExperimentMode.PROPOSED
        )
        difficulty_event_id = uuid4()
        context_input = Model2ContextInput(
            learner_id=UUID(str(state["learner_id"])),
            pseudonymous=True,
            grade=5,
            medium="si",
            skill_id=str(state["skill_id"]),
            skill_version=str(state["skill_version"]),
            episode_id=UUID(str(state["episode_id"])),
            presentation_id=UUID(str(scored["presentation_id"])),
            decision_at=at,
            current_unsupported=UnsupportedEvidence(
                evidence_id=evidence_id,
                presentation_id=UUID(str(scored["presentation_id"])),
                episode_id=UUID(str(state["episode_id"])),
                observed_at=at,
                measurement_role=MeasurementRole.UNSUPPORTED_BEFORE,
                assistance_state=AssistanceState.NONE,
                earned_score=Decimal(str(scored["earned_score"])),
                maximum_score=Decimal(str(scored["maximum_score"])),
                attempt_count=1,
                error_persistence=1,
                item_revision_id=before.revision_id,
            ),
            recent_unsupported=(),
            difficulty=DifficultyEvidence(
                difficulty_event_id=difficulty_event_id,
                detected=True,
                severity=1.0,
                trigger_version="learning_flow-incorrect-unsupported-v1",
                contributing_event_ids=(evidence_id,),
                observed_at=at,
            ),
            belief=belief,
            prior_outcomes=(),
            recent_support_count=0,
            support_dependency_rate=None,
            support_dependency_as_of=None,
            item=ItemMetadata(
                item_revision_id=before.revision_id,
                content_version=before.content_version,
                difficulty=0.25,
                response_format=before.response_format,
                template_id="choice_quest-v1",
                parallel_family_id=before.parallel_family_id,
            ),
            episode=EpisodeMetadata(
                protocol_version=PROTOCOL_VERSION,
                experiment_mode=experiment_mode,
                sequence_at_decision=2,
                session_support_count=0,
                session_support_budget=1,
                remaining_support_steps=4,
                reserved_probe_revision_id=after.revision_id,
                reserved_probe_family_id=after.parallel_family_id,
            ),
            optional_evidence=(),
            extra_metadata={"source": "learning_flow_durable_orchestrator"},
            development_mode=True,
        )
        policy_mode = (
            PolicyMode.DETERMINISTIC_BASELINE
            if state["condition"] == "baseline"
            else PolicyMode.PROPOSED_SHADOW
        )
        context_snapshot, decision = ContextualScaffoldPolicy(
            artifact_version="support_selection-synthetic-engineering-v1",
            artifact_sha256="0" * 64,
        ).decide(
            mode=policy_mode,
            context_input=context_input,
            candidates=scaffolds,
            eligibility=EligibilityInput(accommodations=(), allow_draft=True, child_facing=False),
            seed=31,
            assignment_token=f"{state['episode_id']}:{state['condition']}",
        )
        if decision.selected_scaffold_id is None:
            raise LearningFlowOrchestrationError("NO_SAFE_SCAFFOLD")
        selected = next(
            row for row in scaffolds if row.scaffold_id == decision.selected_scaffold_id
        )
        state["model2"] = {
            "interface_version": "model2-scaffold-selection-interface-v1",
            "decision_id": str(decision.decision_id),
            "context_snapshot_id": (
                None if context_snapshot is None else str(context_snapshot.context_snapshot_id)
            ),
            "context_schema_version": decision.context_schema_version,
            "policy_version": decision.policy_version,
            "mode": decision.mode.value,
            "selection_kind": decision.selection_kind.value,
            "delivered_scaffold_id": decision.selected_scaffold_id,
            "delivered_revision_id": selected.revision_id,
            "shadow_scaffold_id": decision.shadow_scaffold_id,
            "candidate_revision_ids": [row.revision_id for row in scaffolds],
            "candidates": [
                {
                    "scaffold_id": row.scaffold_id,
                    "revision_id": row.revision_id,
                    "eligible": row.eligible,
                    "reason_codes": list(row.reason_codes),
                    "predicted_raw_ig": row.predicted_raw_ig,
                    "uncertainty": row.uncertainty,
                    "rank": row.rank,
                    "propensity": row.propensity,
                }
                for row in decision.candidates
            ],
            "artifact_version": decision.artifact_version,
            "artifact_sha256": decision.artifact_sha256,
            "artifact_status": "synthetic_engineering_only",
            "difficulty": {
                "event_id": str(difficulty_event_id),
                "detected": True,
                "severity": 1.0,
                "trigger_version": "learning_flow-incorrect-unsupported-v1",
                "raw_evidence_ids": [str(evidence_id)],
            },
        }
        scaffold = next(row for row in package.scaffolds if row.scaffold_id == selected.scaffold_id)
        visual_reference = next(
            row for row in package.scaffolds if row.scaffold_type == "visual_guidance"
        )
        state["scaffold_exposure"] = {
            "exposure_id": str(uuid4()),
            "scaffold_id": scaffold.scaffold_id,
            "revision_id": scaffold.scaffold_revision_id,
            "scaffold_type": scaffold.scaffold_type,
            "presented_at": at.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "steps_viewed": 0,
            "answer_leakage": False,
            "game_manifest_revision_id": scaffold.scaffold_revision_id,
            "game_total_objects": visual_reference.worked_values[0],
        }
        state["status"] = "support_active"
        _append_event(state, "support_exposed", at)
        response = self._summary(state)
        response["support"] = {
            "scaffold_id": scaffold.scaffold_id,
            "revision_id": scaffold.scaffold_revision_id,
            "scaffold_type": scaffold.scaffold_type,
            "title_si": scaffold.title_si,
            "body_si": list(scaffold.body_si),
            "visual_alt_text_si": scaffold.visual_alt_text_si,
            "maximum_steps": scaffold.maximum_steps,
            "game_manifest": {
                "schema_version": "half-set-manifest-v1",
                "activity_id": "half-even-set-support",
                "revision_id": scaffold.scaffold_revision_id,
                "deterministic_seed": 31,
                "total_objects": visual_reference.worked_values[0],
                "group_count": 2,
                "object_label_si": "ද්‍රව්‍යය",
                "instruction_si": "ද්‍රව්‍ය සමාන කාණ්ඩ දෙකකට බෙදන්න.",
            },
        }
        return state, response, "support_selected", ("DEVELOPMENT_ONLY",)

    def _support_complete(
        self,
        state: dict[str, object],
        duration_ms: int,
        steps: int,
        manifest_revision_id: str,
        grouped_count: int,
        group_sizes: tuple[int, int],
        at: datetime,
    ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
        exposure = state["scaffold_exposure"]
        assert isinstance(exposure, dict)
        expected_total = int(exposure["game_total_objects"])
        if (
            manifest_revision_id != exposure["game_manifest_revision_id"]
            or grouped_count != expected_total
            or sum(group_sizes) != expected_total
            or group_sizes[0] != group_sizes[1]
        ):
            raise LearningFlowOrchestrationError("INVALID_SUPPORT_COMPLETION")
        exposure["completed_at"] = at.isoformat()
        exposure["duration_ms"] = duration_ms
        exposure["steps_viewed"] = steps
        exposure["group_sizes"] = list(group_sizes)
        state["status"] = "support_complete"
        _append_event(state, "supported_practice_complete", at)
        return state, self._summary(state), "support_completed", ("ASSISTED_EVIDENCE",)

    def _withdraw(
        self,
        state: dict[str, object],
        request_id: UUID,
        support_revision_id: str,
        manifest_revision_id: str,
        all_support_removed: bool,
        answer_revealing_state_cleared: bool,
        input_handlers_cleared: bool,
        at: datetime,
    ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
        exposure = state["scaffold_exposure"]
        assert isinstance(exposure, dict)
        if (
            support_revision_id != exposure["revision_id"]
            or manifest_revision_id != exposure["game_manifest_revision_id"]
            or not all_support_removed
            or not answer_revealing_state_cleared
            or not input_handlers_cleared
        ):
            raise LearningFlowOrchestrationError("INVALID_WITHDRAWAL_ACKNOWLEDGEMENT")
        state["withdrawal"] = {
            "withdrawal_id": str(uuid4()),
            "request_id": str(request_id),
            "support_revision_id": support_revision_id,
            "manifest_revision_id": manifest_revision_id,
            "all_support_removed": all_support_removed,
            "answer_revealing_state_cleared": answer_revealing_state_cleared,
            "input_handlers_cleared": input_handlers_cleared,
            "client_confirmed_at": at.isoformat(),
            "server_verified_at": at.isoformat(),
        }
        state["status"] = "support_withdrawn"
        _append_event(state, "support_withdrawn", at)
        return state, self._summary(state), "support_withdrawn", ("SUPPORT_CLEARED",)

    def _present_after(
        self,
        state: dict[str, object],
        package: PublicCurriculumPackage,
        at: datetime,
    ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
        reservation_id = str(state["probe_reservation_id"])
        if not self._probe.confirm_unexposed(reservation_id):
            state["status"] = "invalidated"
            state["validity"] = "invalid"
            state["exclusion_reasons"] = ["PRIOR_PROBE_EXPOSURE"]
            state["policy_update_status"] = "not_authorized_invalid"
            _append_event(
                state, "episode_invalidated", at, None, {"reason": "PRIOR_PROBE_EXPOSURE"}
            )
            return state, self._summary(state), "episode_invalidated", ("PRIOR_PROBE_EXPOSURE",)
        after = _item(package, "unsupported_after")
        presentation_id = uuid4()
        presentation = _independence_gain_presentation(state, after, presentation_id, at)
        withdrawal = _independence_gain_withdrawal(state)
        assert_unsupported_after_may_begin(presentation, withdrawal)
        self._probe.mark_used(reservation_id, at=at)
        state["presentations"].append(  # type: ignore[union-attr]
            _presentation_record(after, presentation_id, "none", 3)
        )
        state["status"] = "after_presented"
        _append_event(state, "unsupported_after_presented", at, presentation_id)
        return state, self._child_response(state, after), "after_presented", ("PROBE_RESERVED",)

    def _score_after(
        self,
        state: dict[str, object],
        package: PublicCurriculumPackage,
        option_id: str,
        response_time_ms: int | None,
        at: datetime,
    ) -> tuple[dict[str, object], dict[str, object], str, tuple[str, ...]]:
        after = _item(package, "unsupported_after")
        scored = self._score(state, after, option_id, AssistanceState.NONE, response_time_ms, at)
        state["attempts"].append(scored)  # type: ignore[union-attr]
        _append_event(state, "unsupported_after_scored", at, UUID(scored["presentation_id"]))
        self._publish_score(state, scored)
        measurement = self._measurement(state, package, at)
        state["raw_independence_gain"] = (
            None
            if measurement.raw_independence_gain is None
            else str(measurement.raw_independence_gain)
        )
        state["percentage_point_value"] = (
            None
            if measurement.percentage_point_value is None
            else str(measurement.percentage_point_value)
        )
        state["validity"] = "valid" if measurement.valid else "invalid"
        state["exclusion_reasons"] = list(measurement.exclusion_reasons)
        state["policy_update_status"] = measurement.policy_update_status.value
        state["measurement"] = {
            "measurement_id": str(measurement.measurement_id),
            "before_presentation_ids": [
                str(value) for value in measurement.before.presentation_ids
            ],
            "after_presentation_ids": [str(value) for value in measurement.after.presentation_ids],
            "before_earned": str(measurement.before.earned),
            "before_maximum": str(measurement.before.maximum),
            "after_earned": str(measurement.after.earned),
            "after_maximum": str(measurement.after.maximum),
            "formula_version": measurement.formula_version,
            "scoring_versions": list(measurement.scoring_versions),
            "rubric_versions": list(measurement.rubric_versions),
            "equivalence_version": measurement.equivalence_version,
            "measurement_version": measurement.measurement_version,
        }
        state["reward"] = {
            "points": 1 if measurement.valid else 0,
            "reason": "episode_complete" if measurement.valid else "invalid_episode",
        }
        state["status"] = "completed" if measurement.valid else "invalidated"
        _append_event(state, "independence_gain_recorded", at)
        _append_event(
            state, "episode_completed" if measurement.valid else "episode_invalidated", at
        )
        return (
            state,
            self._summary(state),
            "episode_completed" if measurement.valid else "episode_invalidated",
            ("VALID_RAW_IG",) if measurement.valid else measurement.exclusion_reasons,
        )

    def _score(
        self,
        state: dict[str, object],
        item: ItemRevision,
        option_id: str,
        assistance: AssistanceState,
        response_time_ms: int | None,
        at: datetime,
    ) -> dict[str, object]:
        if option_id not in {option.option_id for option in item.options}:
            raise LearningFlowOrchestrationError("UNKNOWN_OPTION")
        presentation_row = next(
            row
            for row in state["presentations"]  # type: ignore[union-attr]
            if row["revision_id"] == item.revision_id
        )
        presentation = _independence_gain_presentation(
            state, item, UUID(str(presentation_row["presentation_id"])), at
        )
        attempt = development_curriculum_scorer(allow_draft=True).score(
            presentation,
            AttemptSubmission(
                attempt_id=uuid4(),
                presentation_id=presentation.presentation_id,
                response=option_id,
                assistance_state=assistance,
                submitted_at=at,
                idempotency_key=f"{state['episode_id']}:{item.revision_id}",
                client_claimed_score=None,
            ),
        )
        return {
            "attempt_id": str(attempt.attempt_id),
            "presentation_id": str(attempt.presentation_id),
            "revision_id": attempt.item_revision_id,
            "role": attempt.role.value,
            "assistance_state": attempt.assistance_state.value,
            "selected_option_id": option_id,
            "earned_score": str(attempt.earned_score),
            "maximum_score": str(attempt.maximum_score),
            "rubric_version": attempt.rubric_version,
            "scoring_version": attempt.scoring_version,
            "server_authoritative": True,
            "correct": attempt.earned_score == attempt.maximum_score,
            "response_time_ms": response_time_ms,
            "supported": assistance is not AssistanceState.NONE,
            "hint_count": 0,
            "difficulty": "easy",
            "difficulty_source": item.difficulty_band,
            "difficulty_mapping_version": "learning_flow-introductory-v1",
            "scored_at": at.isoformat(),
        }

    def _measurement(
        self, state: dict[str, object], package: PublicCurriculumPackage, at: datetime
    ):
        presentations = tuple(
            _independence_gain_presentation(
                state,
                next(
                    item
                    for item in package.item_revisions
                    if item.revision_id == row["revision_id"]
                ),
                UUID(str(row["presentation_id"])),
                datetime.fromisoformat(str(row["created_at"])),
            )
            for row in state["presentations"]  # type: ignore[union-attr]
        )
        by_id = {row.presentation_id: row for row in presentations}
        attempts = []
        for row in state["attempts"]:  # type: ignore[union-attr]
            presentation = by_id[UUID(str(row["presentation_id"]))]
            attempts.append(
                development_curriculum_scorer(allow_draft=True).score(
                    presentation,
                    AttemptSubmission(
                        attempt_id=UUID(str(row["attempt_id"])),
                        presentation_id=presentation.presentation_id,
                        response=str(row["selected_option_id"]),
                        assistance_state=AssistanceState(str(row["assistance_state"])),
                        submitted_at=datetime.fromisoformat(str(row["scored_at"])),
                        idempotency_key=f"replay:{row['attempt_id']}",
                    ),
                )
            )
        exposure = state["scaffold_exposure"]
        assert isinstance(exposure, dict)
        exposure_record = ScaffoldExposure(
            exposure_id=UUID(str(exposure["exposure_id"])),
            episode_id=UUID(str(state["episode_id"])),
            scaffold_revision_id=str(exposure["revision_id"]),
            rendered_step_ids=tuple(
                f"step-{index + 1}" for index in range(int(exposure["steps_viewed"]))
            ),
            answer_revealing=bool(exposure["answer_leakage"]),
            started_at=datetime.fromisoformat(str(exposure["presented_at"])),
            completed_at=datetime.fromisoformat(str(exposure["completed_at"])),
        )
        after_row = next(
            row
            for row in state["presentations"]  # type: ignore[union-attr]
            if row["role"] == "unsupported_after"
        )
        after_presented_at = datetime.fromisoformat(str(after_row["created_at"]))
        reservation = ProbeReservation(
            reservation_id=UUID(str(state["probe_reservation_uuid"])),
            episode_id=UUID(str(state["episode_id"])),
            learner_id=UUID(str(state["learner_id"])),
            item_revision_id=_item(package, "unsupported_after").revision_id,
            parallel_family_id=package.parallel_family.family_id,
            role=MeasurementRole.UNSUPPORTED_AFTER,
            reserved_at=datetime.fromisoformat(str(state["events"][0]["occurred_at"])),  # type: ignore[index]
            expires_at=after_presented_at.replace(year=after_presented_at.year + 1),
            used_at=after_presented_at,
        )
        measurement_events = []
        wanted = {
            "unsupported_before_scored",
            "support_exposed",
            "support_withdrawn",
            "unsupported_after_scored",
        }
        for event in state["events"]:  # type: ignore[union-attr]
            if event["event_type"] in wanted:
                measurement_events.append(
                    NormalizedEvent(
                        event_id=UUID(str(event["event_id"])),
                        sequence=len(measurement_events) + 1,
                        event_type=str(event["event_type"]),
                        presentation_id=(
                            UUID(str(event["presentation_id"]))
                            if event.get("presentation_id")
                            else None
                        ),
                    )
                )
        return calculate_measurement(
            MeasurementInput(
                measurement_id=uuid4(),
                episode_id=UUID(str(state["episode_id"])),
                decision_id=uuid4(),
                experiment_mode=(
                    ExperimentMode.BASELINE
                    if state["condition"] == "baseline"
                    else ExperimentMode.PROPOSED
                ),
                presentations=presentations,
                attempts=tuple(attempts),
                reservations=(reservation,),
                scaffold_exposures=(exposure_record,),
                withdrawal=_independence_gain_withdrawal(state),
                events=tuple(measurement_events),
                expected_event_sequence_end=len(measurement_events),
            ),
            calculated_at=at,
        )

    def _publish_score(self, state: dict[str, object], attempt: dict[str, object]) -> None:
        self._publisher.publish(
            {
                "contract_version": self._publisher.version,
                "learner_id": state["learner_id"],
                "skill_id": state["skill_id"],
                "universal_skill_id": "MAT-FRC",
                "episode_id": state["episode_id"],
                "presentation_id": attempt["presentation_id"],
                "attempt_id": attempt["attempt_id"],
                "measurement_role": attempt["role"],
                "assistance_state": attempt["assistance_state"],
                "earned_score": attempt["earned_score"],
                "maximum_score": attempt["maximum_score"],
                "scoring_version": attempt["scoring_version"],
                "correct": attempt["correct"],
                "response_time_ms": attempt["response_time_ms"],
                "supported": attempt["supported"],
                "hint_count": attempt["hint_count"],
                "difficulty": attempt["difficulty"],
                "difficulty_source": attempt["difficulty_source"],
                "difficulty_mapping_version": attempt["difficulty_mapping_version"],
                "environment": state["environment"],
                "model_ingestion_eligible": False,
                "session_id": state["session_id"],
            }
        )

    def _mutate(self, episode_id, key, request, *, expected, transition):
        def checked(state, package, at):
            if state["status"] != expected:
                raise LearningFlowOrchestrationError("EPISODE_STATE_CONFLICT")
            return transition(state, package, at)

        return self._mutate_any(episode_id, key, request, checked)

    def _mutate_any(self, episode_id, key, request, transition):
        prior = self._receipt(key, request)
        if prior is not None:
            return prior
        at = self._now()
        try:
            row = self._store.get(episode_id, for_update=True)
            state = dict(row.state)
            state["presentations"] = [dict(value) for value in state["presentations"]]
            state["attempts"] = [dict(value) for value in state["attempts"]]
            state["events"] = [dict(value) for value in state["events"]]
            state["telemetry"] = [dict(value) for value in state["telemetry"]]
            old_event_count = len(state["events"])
            expected_revision = int(state["revision"])
            package = load_curriculum_public_package(allow_draft=True)
            state, response, audit_type, audit_reasons = transition(state, package, at)
            state["revision"] = expected_revision + 1
            self._store.replace(
                episode_id=row.episode_id,
                expected_revision=expected_revision,
                state=state,
                new_events=tuple(state["events"][old_event_count:]),
                audit_type=audit_type,
                audit_reasons=tuple(audit_reasons),
                idempotency_key=key,
                request_sha256=request_digest(request),
                response=response,
                now=at,
            )
            self._store.commit()
            return response
        except Exception:
            self._store.rollback()
            raise

    def _receipt(self, key: str, request: dict[str, object]) -> dict[str, object] | None:
        try:
            return self._store.receipt(key, request_digest(request))
        except LearningFlowPersistenceError as error:
            raise LearningFlowOrchestrationError(str(error)) from error

    def _adaptive_flow(self, episode_id: UUID) -> AdaptiveGameFlow | None:
        try:
            experience_id = self._store.get(episode_id).state.get("experience_id")
            return self._experience_flows.get(str(experience_id))
        except LearningFlowPersistenceError as error:
            raise LearningFlowOrchestrationError(str(error)) from error

    def _atomic(self, operation: Callable[[], None]) -> None:
        try:
            operation()
            self._store.commit()
        except Exception:
            self._store.rollback()
            raise

    @staticmethod
    def _child_response(state: dict[str, object], item: ItemRevision) -> dict[str, object]:
        return {
            "episode_id": state["episode_id"],
            "status": state["status"],
            "server_score": _server_score(state),
            "manifest": {
                "presentation_id": state["presentations"][-1]["presentation_id"],  # type: ignore[index]
                "revision_id": item.revision_id,
                "measurement_role": item.measurement_role,
                "assistance_state": "none",
                "prompt_si": item.prompt_si,
                "accessibility_label_si": item.accessibility_label_si,
                "options": [option.model_dump() for option in item.options],
                "content_version": item.content_version,
            },
            "support": None,
        }

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        return {
            "episode_id": state["episode_id"],
            "status": state["status"],
            "server_score": _server_score(state),
            "validity": state.get("validity"),
            "raw_independence_gain": state.get("raw_independence_gain"),
            "percentage_point_value": state.get("percentage_point_value"),
            "policy_update_status": state.get("policy_update_status"),
            "exclusion_reasons": state.get("exclusion_reasons", []),
            "reward": state.get("reward"),
            "support": None,
        }


def _server_score(state: dict[str, object]) -> dict[str, object] | None:
    attempts = state.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    latest = attempts[-1]
    if not isinstance(latest, dict):
        return None
    return {
        "earned_score": str(latest["earned_score"]),
        "maximum_score": str(latest["maximum_score"]),
        "scoring_version": str(latest["scoring_version"]),
        "server_authoritative": True,
        "measurement_role": str(latest["role"]),
    }


def _item(package: PublicCurriculumPackage, role: str) -> ItemRevision:
    return next(item for item in package.item_revisions if item.measurement_role == role)


def _presentation_record(
    item: ItemRevision, presentation_id: UUID, assistance: str, sequence: int
) -> dict[str, object]:
    return {
        "presentation_id": str(presentation_id),
        "revision_id": item.revision_id,
        "role": item.measurement_role,
        "assistance_state": assistance,
        "parallel_family_id": item.parallel_family_id,
        "content_version": item.content_version,
        "sequence": sequence,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _independence_gain_presentation(
    state: dict[str, object], item: ItemRevision, presentation_id: UUID, at: datetime
) -> Presentation:
    row = next(
        (
            row
            for row in state["presentations"]  # type: ignore[union-attr]
            if str(row["presentation_id"]) == str(presentation_id)
        ),
        None,
    )
    sequence = 1 if row is None else int(row["sequence"])
    return Presentation(
        presentation_id=presentation_id,
        episode_id=UUID(str(state["episode_id"])),
        learner_id=UUID(str(state["learner_id"])),
        item_revision_id=item.revision_id,
        skill_id=item.skill_id,
        parallel_family_id=item.parallel_family_id,
        equivalence_version="g5-mat-half-parallel-v1",
        role=MeasurementRole(item.measurement_role),
        assistance_state=AssistanceState.NONE,
        sequence=sequence,
        created_at=at,
        reservation_id=(
            UUID(str(state["probe_reservation_uuid"]))
            if item.measurement_role == "unsupported_after"
            else None
        ),
    )


def _independence_gain_withdrawal(state: dict[str, object]) -> SupportWithdrawal:
    row = state["withdrawal"]
    assert isinstance(row, dict)
    exposure = state["scaffold_exposure"]
    assert isinstance(exposure, dict)
    verified = datetime.fromisoformat(str(row["server_verified_at"]))
    return SupportWithdrawal(
        confirmation_id=UUID(str(row["withdrawal_id"])),
        episode_id=UUID(str(state["episode_id"])),
        exposure_id=UUID(str(exposure["exposure_id"])),
        all_support_removed=bool(row["all_support_removed"]),
        answer_revealing_state_cleared=bool(row["answer_revealing_state_cleared"]),
        client_confirmed_at=verified,
        server_verified_at=verified,
    )


def _event(
    sequence: int,
    event_type: str,
    at: datetime,
    presentation_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "event_id": str(uuid4()),
        "sequence": sequence,
        "event_type": event_type,
        "presentation_id": None if presentation_id is None else str(presentation_id),
        "occurred_at": at.isoformat(),
        "details": details or {},
    }


def _append_event(
    state: dict[str, object],
    event_type: str,
    at: datetime,
    presentation_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    events = state["events"]
    assert isinstance(events, list)
    events.append(_event(len(events) + 1, event_type, at, presentation_id, details))


def _belief(top: str) -> dict[str, float]:
    values = {"whole_set_as_half": 0.15, "subtracts_two": 0.15, "unknown_or_other": 0.20}
    values[top] = 0.60
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}
