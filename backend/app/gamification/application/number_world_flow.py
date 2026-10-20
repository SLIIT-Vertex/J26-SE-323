"""Durable Number World strategy used by :class:`LearningFlowOrchestrator`.

The strategy shares the existing hash-bound store, probe gateway, evidence outbox, idempotency
rules, and research route.  It is not reachable through the lightweight fixture-round service.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.gamification.application.consent_gate import research_consent_granted
from app.gamification.application.learner_state_answers import record_scored_answer
from app.gamification.application.ports import ConsentStore
from app.gamification.application.session_play import LearnerStateAnswerGateway
from app.gamification.content.number_world import (
    AREA_ID,
    CATALOGUE_VERSION,
    EQUIVALENCE_VERSION,
    FEATURE_VERSION,
    MAPPING_VERSION,
    MODEL_VERSION,
    PACKAGE_VERSION,
    POLICY_VERSION,
    SCORING_VERSION,
    SKILLS,
    NumberWorldItem,
    construct_extreme,
    expanded_form,
    generate_item,
    infer_belief,
    order_numbers,
    package_hash,
    scaffold_decision,
    validate_constructed_response,
)

CONTRACT_VERSION = "number-world-learning-flow-v1"
PROTOCOL_VERSION = "adaptive-episode-v1"
_SUPPORT_ORDER = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
_NUMBER_WORLD_SUPPORT_SEQUENCE = {
    "G5-MAT-NUM-POSITION-01": _SUPPORT_ORDER,
    "G5-MAT-NUM-REPRESENTED-01": (
        "worked_parallel_example",
        "visual_guidance",
        "step_by_step_guidance",
    ),
    "G5-MAT-NUM-100000-01": _SUPPORT_ORDER,
    "G5-MAT-NUM-ABACUS-01": (
        "worked_parallel_example",
        "visual_guidance",
        "step_by_step_guidance",
    ),
    "G5-MAT-NUM-EXPAND-01": (
        "worked_parallel_example",
        "visual_guidance",
        "step_by_step_guidance",
    ),
    "G5-MAT-NUM-EXTREME-01": _SUPPORT_ORDER,
    "G5-MAT-NUM-LEADING-ZERO-01": _SUPPORT_ORDER,
    "G5-MAT-NUM-ORDER-01": _SUPPORT_ORDER,
}


# The knowledge-tracing component learns from each scored answer. It needs a difficulty (easy, medium or
# hard); the game's own skills carry a finer level, so this says how the finer level is read.
EVIDENCE_LEVEL_MAPPING_VERSION = "gamification-skill-level-v1"
_LEVEL_BANDS = {
    "easy": "easy",
    "easy_medium": "medium",  # between two bands: the middle one, so neither extreme is over-stated
    "medium": "medium",
    "medium_hard": "medium",
    "hard": "hard",
    "easy_to_hard": "medium",  # items that run across the whole range: the middle band
}

# Environments the flow may run in. Only "pilot" can mark an answer as usable by a model, and only for
# a learner who has given research consent. Content is still draft, so every environment needs the
# explicit allow_draft opt-in.
OPEN_ENVIRONMENTS = frozenset({"development", "test", "pilot"})
PILOT_ENVIRONMENT = "pilot"


def evidence_difficulty(skill: object) -> tuple[str, str]:
    """(band, source) for one scored answer: easy, medium or hard, and whether the skill declared it.

    A skill with no level of its own gets the neutral band "medium", marked "default_unlabelled" so the
    research can leave those answers out later.
    """
    level = getattr(skill, "difficulty", None)
    if isinstance(level, str):
        band = _LEVEL_BANDS.get(level.strip().lower().replace("-", "_"))
        if band is not None:
            return band, "declared"
    return "medium", "default_unlabelled"


class NumberWorldFlowError(ValueError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code)
        self.code = code
        self.context = context


class StoredRun(Protocol):
    revision: int
    state: Mapping[str, object]


class Store(Protocol):
    def get(self, episode_id: UUID, *, for_update: bool = False) -> StoredRun: ...
    def receipt(self, key: str, request_sha256: str) -> dict[str, object] | None: ...
    def create(self, **values: object) -> None: ...
    def replace(self, **values: object) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    def support_history(
        self, *, learner_id: UUID, skill_id: str
    ) -> tuple[Mapping[str, object], ...]: ...


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


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _event(state: dict[str, object], event_type: str, at: datetime, **details: object) -> None:
    events = state["events"]
    assert isinstance(events, list)
    events.append(
        {
            "event_id": str(uuid4()),
            "sequence": len(events) + 1,
            "event_type": event_type,
            "presentation_id": details.pop("presentation_id", None),
            "occurred_at": at.isoformat(),
            "details": details,
        }
    )


def _escalate_scaffold(
    selected: str,
    *,
    condition: str,
    attempt_count: int,
    skill_id: str | None = None,
    preferred_support: str | None = None,
    support_sequences: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, str]:
    """Keep baseline fixed; use a remembered, deterministic activity sequence."""
    if condition != "proposed":
        return selected, "baseline_fixed"
    sequence = (support_sequences or _NUMBER_WORLD_SUPPORT_SEQUENCE).get(skill_id or "")
    if sequence:
        if preferred_support in sequence:
            preferred_index = sequence.index(preferred_support)
            sequence = sequence[preferred_index:] + sequence[:preferred_index]
        support_index = min(max(1, attempt_count) - 1, len(sequence) - 1)
        if support_index == 0:
            mode = "learned_activity_preference" if preferred_support else "activity_default"
        else:
            mode = "activity_support_escalation"
        return sequence[support_index], mode
    minimum_index = 0 if attempt_count <= 1 else (1 if attempt_count == 2 else 2)
    selected_index = _SUPPORT_ORDER.index(selected)
    escalated = _SUPPORT_ORDER[max(selected_index, minimum_index)]
    return escalated, "model_with_attempt_escalation"


def _preferred_support_from_history(
    history: tuple[Mapping[str, object], ...],
) -> tuple[str | None, dict[str, object]]:
    """Rank support only by valid post-withdrawal independent outcomes."""
    stats: dict[str, dict[str, Decimal | int]] = {}
    for state in history:
        if state.get("condition") != "proposed" or state.get("validity") != "valid":
            continue
        model2 = state.get("model2")
        measurement = state.get("measurement")
        if not isinstance(model2, Mapping) or not isinstance(measurement, Mapping):
            continue
        support = str(model2.get("selected_action", ""))
        if support not in _SUPPORT_ORDER:
            continue
        after_earned = Decimal(str(measurement.get("after_earned", 0)))
        after_maximum = Decimal(str(measurement.get("after_maximum", 0)))
        raw_ig = measurement.get("raw_independence_gain")
        if after_maximum <= 0 or raw_ig is None:
            continue
        row = stats.setdefault(
            support,
            {"episodes": 0, "independent_successes": 0, "total_ig": Decimal(0)},
        )
        row["episodes"] = int(row["episodes"]) + 1
        if after_earned == after_maximum:
            row["independent_successes"] = int(row["independent_successes"]) + 1
        row["total_ig"] = Decimal(str(row["total_ig"])) + Decimal(str(raw_ig))

    successful = {
        support: row for support, row in stats.items() if int(row["independent_successes"]) > 0
    }
    preferred = None
    if successful:
        preferred = max(
            successful,
            key=lambda support: (
                int(successful[support]["independent_successes"])
                / int(successful[support]["episodes"]),
                Decimal(str(successful[support]["total_ig"]))
                / int(successful[support]["episodes"]),
                int(successful[support]["episodes"]),
                -_SUPPORT_ORDER.index(support),
            ),
        )
    serializable = {
        support: {
            "episodes": int(row["episodes"]),
            "independent_successes": int(row["independent_successes"]),
            "mean_independence_gain": str(
                Decimal(str(row["total_ig"])) / int(row["episodes"])
            ),
        }
        for support, row in stats.items()
    }
    return preferred, {
        "basis": "valid_unsupported_after_outcomes",
        "supported_correctness_used": False,
        "preferred_support": preferred,
        "by_support": serializable,
    }


def _next_support_attempt_from_history(history: tuple[Mapping[str, object], ...]) -> int:
    """Resume after consecutive valid independent failures; success resets the retry cursor."""
    consecutive_failures = 0
    for state in reversed(history):
        if state.get("condition") != "proposed" or state.get("validity") != "valid":
            continue
        measurement = state.get("measurement")
        if not isinstance(measurement, Mapping):
            continue
        earned = Decimal(str(measurement.get("after_earned", 0)))
        maximum = Decimal(str(measurement.get("after_maximum", 0)))
        if maximum > 0 and earned == maximum:
            break
        consecutive_failures += 1
    return consecutive_failures + 1


class NumberWorldFlow:
    """Reusable durable adaptive-game flow with Number World as the default profile."""

    area_id = AREA_ID
    experience_id = "number_world"
    universal_skill_id = "MAT-NUM"
    contract_version = CONTRACT_VERSION
    context_version = "g5-mat-number-world-context-v1"
    measurement_version = "number-world-independence-measurement-v1"
    item_schema_version = "number-world-item-v1"
    support_schema_version = "number-world-support-v1"
    package_version = PACKAGE_VERSION
    catalogue_version = CATALOGUE_VERSION
    feature_version = FEATURE_VERSION
    mapping_version = MAPPING_VERSION
    model_version = MODEL_VERSION
    policy_version = POLICY_VERSION
    scoring_version = SCORING_VERSION
    equivalence_version = EQUIVALENCE_VERSION
    skills = SKILLS
    generate_item = staticmethod(generate_item)
    infer_belief = staticmethod(infer_belief)
    scaffold_decision = staticmethod(scaffold_decision)
    package_hash = staticmethod(package_hash)
    validate_constructed_response = staticmethod(validate_constructed_response)
    missing_skill_error = "NUMBER_WORLD_SKILL_NOT_FOUND"
    episode_type_error = "NUMBER_WORLD_EPISODE_REQUIRED"
    operation_prefix = "number_world"
    support_sequences: Mapping[str, tuple[str, ...]] = _NUMBER_WORLD_SUPPORT_SEQUENCE
    activity_support_memory = True
    answer_revealing_support = True
    # The learner-state behaviour models were trained on mathematics answers (ASSISTments).
    records_learner_state = True

    def __init__(
        self,
        store: Store,
        probe: ProbeGateway,
        publisher: EvidencePublisher,
        *,
        now: Callable[[], datetime] | None = None,
        learner_state: LearnerStateAnswerGateway | None = None,
        camera_consent: ConsentStore | None = None,
    ) -> None:
        self._store = store
        self._probe = probe
        self._publisher = publisher
        self._now = now or (lambda: datetime.now(UTC))
        self._learner_state = learner_state
        self._camera_consent = camera_consent

    def open(
        self,
        *,
        learner_id: UUID,
        session_id: UUID,
        condition: str,
        environment: str,
        allow_draft: bool,
        atomic_skill_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        request = {
            "op": f"{self.operation_prefix}_open",
            "learner_id": str(learner_id),
            "session_id": str(session_id),
            "condition": condition,
            "environment": environment,
            "allow_draft": allow_draft,
            "atomic_skill_id": atomic_skill_id,
        }
        prior = self._receipt(idempotency_key, request)
        if prior is not None:
            return prior
        if environment not in OPEN_ENVIRONMENTS or not allow_draft:
            raise NumberWorldFlowError("HUMAN_APPROVAL_REQUIRED")
        if atomic_skill_id not in self.skills:
            raise NumberWorldFlowError(self.missing_skill_error)
        episode_id = uuid4()
        seed = int.from_bytes(
            hashlib.sha256(f"{session_id}:{atomic_skill_id}".encode()).digest()[:4], "big"
        )
        before = self.generate_item(atomic_skill_id, role="unsupported_before", seed=seed)
        after = self.generate_item(atomic_skill_id, role="unsupported_after", seed=seed)
        if (
            before.parallel_family_id != after.parallel_family_id
            or before.revision_id == after.revision_id
        ):
            raise NumberWorldFlowError("PARALLEL_FAMILY_INVALID")
        at = self._now()
        reservation_id = self._probe.reserve(
            learner_id=learner_id, episode_id=episode_id, item_revision_id=after.revision_id, at=at
        )
        presentation_id = uuid4()
        state: dict[str, object] = {
            "contract_version": self.contract_version,
            "experience_id": self.experience_id,
            "episode_id": str(episode_id),
            "session_id": str(session_id),
            "learner_id": str(learner_id),
            "area_id": self.area_id,
            "skill_id": atomic_skill_id,
            "skill_version": "v1",
            "universal_skill_id": self.universal_skill_id,
            "chapter": self.skills[atomic_skill_id].chapter,
            "content_package_version": self.package_version,
            "content_artifact_sha256": self.package_hash(),
            "protocol_version": PROTOCOL_VERSION,
            "environment": environment,
            "condition": condition,
            "status": "before_presented",
            "revision": 1,
            "seed": seed,
            "probe_gateway_version": self._probe.version,
            "probe_reservation_id": reservation_id,
            "probe_reservation_uuid": str(uuid5(NAMESPACE_URL, reservation_id)),
            "presentations": [self._item_record(before, presentation_id, 1, at)],
            "attempts": [],
            "model1": None,
            "model2": None,
            "scaffold_exposure": None,
            "withdrawal": None,
            "measurement": None,
            "raw_independence_gain": None,
            "validity": None,
            "exclusion_reasons": [],
            "policy_update_status": "not_authorized_incomplete",
            "policy_updates": [],
            "reward": None,
            "supported_correctness": None,
            "telemetry": [],
            "next_client_sequence": 1,
            "events": [],
        }
        _event(state, "unsupported_before_presented", at, presentation_id=str(presentation_id))
        response = self._response(state, before)
        self._atomic(
            lambda: self._store.create(
                state=state,
                idempotency_key=idempotency_key,
                request_sha256=_digest(request),
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
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None = None,
        idempotency_key: str,
        visual: Mapping[str, float] | None = None,
        learner_state_session_id: UUID | None = None,
    ) -> dict[str, object]:
        interaction_summary = self._validate_interaction_summary(interaction_summary)
        scored: dict[str, object] = {}

        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            item = self._stored_item(state, "unsupported_before")
            score = self._score(
                state, item, option_id, constructed_response, response_time_ms, at
            )
            state["attempts"].append(score)  # type: ignore[union-attr]
            _event(state, "unsupported_before_scored", at, presentation_id=score["presentation_id"])
            self._publish(state, score, at)
            scored.update(state=state, score=score, at=at)
            if score["correct"]:
                state.update(
                    status="completed",
                    validity="not_applicable_no_support",
                    policy_update_status="not_authorized_no_support",
                    reward={"points": 1, "reason": "independent_correct"},
                )
                _event(state, "episode_completed_no_support", at)
                return self._summary(state)
            error_code = str(score["structured_error_code"])
            belief = self._infer_belief(
                error_code,
                response_time_ms=response_time_ms,
                interaction_summary=interaction_summary,
            )
            evidence_id = uuid4()
            state["model1"] = {
                "belief_snapshot_id": str(uuid4()),
                "feature_snapshot_id": str(uuid4()),
                "feature_schema_version": self.feature_version,
                "catalogue_version": self.catalogue_version,
                "mapping_version": self.mapping_version,
                "model_version": self.model_version,
                "artifact_sha256": self.package_hash(),
                "created_at": at.isoformat(),
                "evidence_ids": [str(evidence_id)],
                "learner_id": state["learner_id"],
                "pseudonymous": True,
                "skill_id": state["skill_id"],
                "item_revision_id": item["revision_id"],
                "parallel_family_id": item["parallel_family_id"],
                "presentation_id": item["presentation_id"],
                "pre_decision_only": True,
                "assistance_state": "none",
                "measurement_role": "unsupported_before",
                "structured_response": dict(interaction_summary or {}),
                "constructed_response": score["constructed_response"],
                "structured_error_code": error_code,
                "server_score": {
                    "earned_score": score["earned_score"],
                    "maximum_score": score["maximum_score"],
                    "scoring_version": score["scoring_version"],
                },
                "response_time_ms": response_time_ms,
                "missingness": self._missingness(response_time_ms, interaction_summary),
                "immutable_provenance": True,
                **belief,
            }
            decision = self.scaffold_decision(
                str(state["skill_id"]), str(state["condition"]), belief, seed=int(state["seed"])
            )
            client_attempt_count = max(1, int(interaction_summary.get("attempt_count", 1)))
            attempt_count = client_attempt_count
            model_selected = str(decision["selected_action"])
            preferred_support = None
            preference_analysis: dict[str, object] = {
                "basis": "not_applicable",
                "supported_correctness_used": False,
                "preferred_support": None,
                "by_support": {},
            }
            if self.activity_support_memory and state.get("condition") == "proposed":
                history = self._store.support_history(
                    learner_id=UUID(str(state["learner_id"])),
                    skill_id=str(state["skill_id"]),
                )
                preferred_support, preference_analysis = _preferred_support_from_history(history)
                attempt_count = max(
                    client_attempt_count,
                    _next_support_attempt_from_history(history),
                )
            selected, selection_mode = _escalate_scaffold(
                model_selected,
                condition=str(state["condition"]),
                attempt_count=attempt_count,
                skill_id=(
                    str(state["skill_id"])
                    if self.activity_support_memory
                    else None
                ),
                preferred_support=preferred_support,
                support_sequences=self.support_sequences,
            )
            decision.update(
                model_selected_action=model_selected,
                selected_action=selected,
                attempt_count=attempt_count,
                client_attempt_count=client_attempt_count,
                support_selection_mode=selection_mode,
                learner_activity_support_preference=preference_analysis,
            )
            state["model2"] = {
                "decision_id": str(uuid4()),
                "context_snapshot_id": str(uuid4()),
                "context_version": self.context_version,
                "artifact_sha256": self.package_hash(),
                "created_at": at.isoformat(),
                "complete_model1_probabilities": belief["probabilities"],
                "missingness": self._missingness(response_time_ms, interaction_summary),
                **decision,
            }
            scaffold_type = selected
            state["scaffold_exposure"] = {
                "exposure_id": str(uuid4()),
                "revision_id": f"{state['skill_id']}:{scaffold_type}@v1",
                "scaffold_type": scaffold_type,
                "presented_at": at.isoformat(),
                "completed_at": None,
                "displayed": True,
                "fully_withdrawn": False,
                # Number World support deliberately demonstrates the solution to the
                # exact failed presentation. The answer-bearing UI must be removed
                # before the fresh unsupported-after probe is presented.
                "answer_revealing": self.answer_revealing_support,
                "manifest_revision_id": f"{state['skill_id']}:{state['chapter']}:support@v1",
            }
            state["status"] = "support_active"
            _event(state, "difficulty_detected", at, evidence_id=str(evidence_id))
            _event(state, "misconception_distribution_created", at)
            _event(state, "scaffold_decision_created", at)
            _event(state, "support_exposed", at)
            response = self._summary(state)
            response["support"] = self._support(state)
            return response

        response = self._mutate(
            episode_id,
            idempotency_key,
            self._with_learner_state_request(
                {
                    "op": f"{self.operation_prefix}_before",
                    "option_id": option_id,
                    "constructed_response": dict(constructed_response or {}),
                    "response_time_ms": response_time_ms,
                    "interaction_summary": dict(interaction_summary or {}),
                },
                visual,
                learner_state_session_id,
            ),
            "before_presented",
            transition,
        )
        self._record_learner_state(scored, visual, learner_state_session_id)
        return response

    def complete_support(
        self,
        episode_id: UUID,
        *,
        duration_ms: int,
        steps_viewed: int,
        manifest_revision_id: str,
        interaction_summary: Mapping[str, object],
        idempotency_key: str,
    ) -> dict[str, object]:
        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            exposure = state["scaffold_exposure"]
            assert isinstance(exposure, dict)
            expected_renderer = f"{state['chapter']}:{exposure['scaffold_type']}"
            expected_example = f"{state['skill_id']}:parallel-support-v1"
            required_actions = self._required_support_actions(str(exposure["scaffold_type"]))
            if (
                manifest_revision_id != exposure["manifest_revision_id"]
                or interaction_summary.get("completed") is not True
                or interaction_summary.get("renderer_id") != expected_renderer
                or interaction_summary.get("parallel_example_id") != expected_example
                or type(interaction_summary.get("support_actions")) is not int
                or int(interaction_summary["support_actions"]) < required_actions
            ):
                raise NumberWorldFlowError("INVALID_SUPPORT_COMPLETION")
            exposure.update(
                completed_at=at.isoformat(),
                duration_ms=duration_ms,
                steps_viewed=steps_viewed,
                interaction_summary=dict(interaction_summary),
            )
            # Supported-practice completion is process evidence, never a client score.
            state["supported_correctness"] = None
            state["status"] = "support_complete"
            _event(state, "supported_practice_complete", at)
            return self._summary(state)

        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": f"{self.operation_prefix}_support",
                "duration_ms": duration_ms,
                "steps_viewed": steps_viewed,
                "manifest_revision_id": manifest_revision_id,
                "interaction_summary": dict(interaction_summary),
            },
            "support_active",
            transition,
        )

    def withdraw(
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
        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            exposure = state["scaffold_exposure"]
            assert isinstance(exposure, dict)
            valid = (
                support_revision_id == exposure["revision_id"]
                and manifest_revision_id == exposure["manifest_revision_id"]
                and all_support_removed
                and answer_revealing_state_cleared
                and input_handlers_cleared
            )
            if not valid:
                raise NumberWorldFlowError("INVALID_WITHDRAWAL_ACKNOWLEDGEMENT")
            exposure["fully_withdrawn"] = True
            state["withdrawal"] = {
                "acknowledgement_id": str(uuid4()),
                "request_id": str(request_id),
                "support_revision_id": support_revision_id,
                "manifest_revision_id": manifest_revision_id,
                "all_support_removed": True,
                "answer_revealing_state_cleared": True,
                "input_handlers_cleared": True,
                "server_verified_at": at.isoformat(),
            }
            state["status"] = "support_withdrawn"
            _event(state, "support_withdrawn", at)
            return self._summary(state)

        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": f"{self.operation_prefix}_withdraw",
                "request_id": str(request_id),
                "support_revision_id": support_revision_id,
                "manifest_revision_id": manifest_revision_id,
                "all_support_removed": all_support_removed,
                "answer_revealing_state_cleared": answer_revealing_state_cleared,
                "input_handlers_cleared": input_handlers_cleared,
            },
            "support_complete",
            transition,
        )

    def present_after(self, episode_id: UUID, *, idempotency_key: str) -> dict[str, object]:
        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            reservation = str(state["probe_reservation_id"])
            if not self._probe.confirm_unexposed(reservation):
                state.update(
                    status="invalidated",
                    validity="invalid",
                    exclusion_reasons=["PRIOR_PROBE_EXPOSURE"],
                    policy_update_status="not_authorized_invalid",
                )
                _event(state, "episode_invalidated", at, reason="PRIOR_PROBE_EXPOSURE")
                return self._summary(state)
            item = self.generate_item(
                str(state["skill_id"]), role="unsupported_after", seed=int(state["seed"])
            )
            self._probe.mark_used(reservation, at=at)
            presentation_id = uuid4()
            state["presentations"].append(self._item_record(item, presentation_id, 2, at))  # type: ignore[union-attr]
            state["status"] = "after_presented"
            _event(state, "unsupported_after_presented", at, presentation_id=str(presentation_id))
            return self._response(state, item)

        return self._mutate(
            episode_id,
            idempotency_key,
            {"op": f"{self.operation_prefix}_after_present"},
            "support_withdrawn",
            transition,
        )

    def submit_after(
        self,
        episode_id: UUID,
        *,
        option_id: str | None,
        constructed_response: Mapping[str, object] | None = None,
        response_time_ms: int | None,
        idempotency_key: str,
        visual: Mapping[str, float] | None = None,
        learner_state_session_id: UUID | None = None,
    ) -> dict[str, object]:
        scored: dict[str, object] = {}

        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            item = self._stored_item(state, "unsupported_after")
            score = self._score(
                state, item, option_id, constructed_response, response_time_ms, at
            )
            state["attempts"].append(score)  # type: ignore[union-attr]
            _event(state, "unsupported_after_scored", at, presentation_id=score["presentation_id"])
            self._publish(state, score, at)
            scored.update(state=state, score=score, at=at)
            before = next(row for row in state["attempts"] if row["role"] == "unsupported_before")  # type: ignore[index]
            exclusions = []
            exposure = state.get("scaffold_exposure")
            if not isinstance(exposure, dict) or not exposure.get("fully_withdrawn"):
                exclusions.append("SUPPORT_NOT_WITHDRAWN")
            withdrawal = state.get("withdrawal")
            if not isinstance(withdrawal, dict) or not all(
                withdrawal.get(field) is True
                for field in (
                    "all_support_removed",
                    "answer_revealing_state_cleared",
                    "input_handlers_cleared",
                )
            ):
                exclusions.append("WITHDRAWAL_NOT_VERIFIED")
            elif (
                exposure.get("answer_revealing") is True
                and withdrawal.get("answer_revealing_state_cleared") is not True
            ):
                exclusions.append("ANSWER_REVEALING_STATE_NOT_CLEARED")
            if before.get("scoring_version") != self.scoring_version or score.get(
                "scoring_version"
            ) != self.scoring_version:
                exclusions.append("SCORING_VERSION_MISMATCH")
            if before.get("assistance_state") != "none" or score.get(
                "assistance_state"
            ) != "none":
                exclusions.append("ASSISTANCE_CONTAMINATION")
            if item.get("skill_id") != state.get("skill_id"):
                exclusions.append("SKILL_MISMATCH")
            if (
                item["parallel_family_id"]
                != next(
                    row for row in state["presentations"] if row["role"] == "unsupported_before"
                )["parallel_family_id"]
            ):  # type: ignore[index]
                exclusions.append("INCOMPATIBLE_PARALLEL_FAMILY")
            if (
                item["revision_id"]
                == next(
                    row for row in state["presentations"] if row["role"] == "unsupported_before"
                )["revision_id"]
            ):  # type: ignore[index]
                exclusions.append("AFTER_ITEM_NOT_FRESH")
            exclusions.extend(self._additional_exclusions(state, item))
            valid = not exclusions
            baseline = Decimal(str(before["earned_score"])) / Decimal(str(before["maximum_score"]))
            after = Decimal(str(score["earned_score"])) / Decimal(str(score["maximum_score"]))
            raw_ig = after - baseline if valid else None
            decision = state["model2"]
            assert isinstance(decision, dict)
            update_authorized = valid and state["condition"] == "proposed"
            state["measurement"] = {
                "measurement_id": str(uuid4()),
                "formula_version": "raw-independence-gain-v1",
                "measurement_version": self.measurement_version,
                "equivalence_version": self.equivalence_version,
                "scoring_version": self.scoring_version,
                "before_earned": before["earned_score"],
                "before_maximum": before["maximum_score"],
                "after_earned": score["earned_score"],
                "after_maximum": score["maximum_score"],
                "baseline": str(baseline),
                "after": str(after),
                "raw_independence_gain": None if raw_ig is None else str(raw_ig),
                "valid": valid,
                "exclusion_reasons": exclusions,
                "supported_correctness_used_as_reward": False,
            }
            state["raw_independence_gain"] = None if raw_ig is None else str(raw_ig)
            state["validity"] = "valid" if valid else "invalid"
            state["exclusion_reasons"] = exclusions
            state["policy_update_status"] = (
                "authorized_delayed"
                if update_authorized
                else ("not_authorized_baseline" if valid else "not_authorized_invalid")
            )
            if update_authorized:
                state["policy_updates"].append(
                    {  # type: ignore[union-attr]
                        "update_id": str(uuid5(NAMESPACE_URL, f"{decision['decision_id']}:raw-ig")),
                        "decision_id": decision["decision_id"],
                        "reward": str(raw_ig),
                        "reward_source": "valid_raw_independence_gain",
                        "policy_version": self.policy_version,
                        "applied_once": True,
                        "created_at": at.isoformat(),
                    }
                )
            state["reward"] = {
                "points": 2 if valid else 0,
                "reason": "participation" if valid else "invalid_episode",
            }
            state["status"] = "completed" if valid else "invalidated"
            _event(state, "independence_gain_recorded", at, valid=valid)
            if update_authorized:
                _event(state, "policy_reward_linked", at, decision_id=decision["decision_id"])
            _event(state, "episode_completed" if valid else "episode_invalidated", at)
            return self._summary(state)

        response = self._mutate(
            episode_id,
            idempotency_key,
            self._with_learner_state_request(
                {
                    "op": f"{self.operation_prefix}_after",
                    "option_id": option_id,
                    "constructed_response": dict(constructed_response or {}),
                    "response_time_ms": response_time_ms,
                },
                visual,
                learner_state_session_id,
            ),
            "after_presented",
            transition,
        )
        self._record_learner_state(scored, visual, learner_state_session_id)
        return response

    @staticmethod
    def _with_learner_state_request(
        request: dict[str, object],
        visual: Mapping[str, float] | None,
        learner_state_session_id: UUID | None,
    ) -> dict[str, object]:
        # Part of the idempotency fingerprint, but only when sent, so requests without them keep
        # their earlier fingerprint.
        if visual is not None:
            request["visual"] = dict(visual)
        if learner_state_session_id is not None:
            request["learner_state_session_id"] = str(learner_state_session_id)
        return request

    def _record_learner_state(
        self,
        scored: Mapping[str, object],
        visual: Mapping[str, float] | None,
        learner_state_session_id: UUID | None,
    ) -> None:
        # Nothing was scored when the request replayed a stored receipt.
        if not scored or not self.records_learner_state:
            return
        state, score, at = scored["state"], scored["score"], scored["at"]
        assert isinstance(state, dict) and isinstance(score, dict) and isinstance(at, datetime)
        record_scored_answer(
            self._learner_state,
            self._camera_consent,
            # One learner-state session spans the episodes of one app session; each episode has
            # its own game session id.
            session_id=learner_state_session_id or UUID(str(state["session_id"])),
            learner_id=UUID(str(state["learner_id"])),
            skill_id=self.universal_skill_id,
            at=at,
            correct=bool(score["correct"]),
            response_time_ms=score["response_time_ms"],  # type: ignore[arg-type]
            visual=visual,
        )

    def _score(
        self,
        state: dict[str, object],
        item: dict[str, object],
        option_id: str | None,
        constructed_response: Mapping[str, object] | None,
        response_time_ms: int | None,
        at: datetime,
    ) -> dict[str, object]:
        normalized_response: dict[str, object] | None = None
        if constructed_response is not None:
            if (
                constructed_response.get("presentation_id") != item["presentation_id"]
                or constructed_response.get("item_revision_id") != item["revision_id"]
                or constructed_response.get("interaction_version") != "constructed-response-v1"
            ):
                raise NumberWorldFlowError("STALE_OR_INCOMPATIBLE_MANIFEST")
            response_payload = {
                key: value
                for key, value in constructed_response.items()
                if key not in {"presentation_id", "item_revision_id", "interaction_version"}
            }
            try:
                correct, error_code, normalized_response = self.validate_constructed_response(
                    item, response_payload
                )
            except (TypeError, ValueError) as error:
                raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS") from error
            selected_response = "constructed-response"
        else:
            options = {row[0] for row in item["options"]}  # type: ignore[index]
            if option_id not in options:
                raise NumberWorldFlowError("UNKNOWN_OPTION")
            correct = option_id == item["correct_option_id"]
            error_code = item["error_codes"].get(option_id, "unknown_or_other")  # type: ignore[union-attr]
            selected_response = str(option_id)
        return {
            "attempt_id": str(uuid4()),
            "presentation_id": item["presentation_id"],
            "revision_id": item["revision_id"],
            "role": item["role"],
            "assistance_state": "none",
            "selected_option_id": selected_response,
            "constructed_response": normalized_response,
            "structured_error_code": error_code,
            "earned_score": "1" if correct else "0",
            "maximum_score": "1",
            "rubric_version": f"{item['skill_id']}:rubric-v1",
            "scoring_version": self.scoring_version,
            "server_authoritative": True,
            "correct": correct,
            "response_time_ms": response_time_ms,
            "scored_at": at.isoformat(),
        }

    def _model_eligible(self, state: dict[str, object], at: datetime) -> bool:
        """True only in the pilot environment, for a learner whose research consent is on record.

        Development and test answers, and answers of a learner with no (or withdrawn, or expired)
        research consent, are never released to a model.
        """
        if state["environment"] != PILOT_ENVIRONMENT or self._camera_consent is None:
            return False
        return research_consent_granted(self._camera_consent, UUID(str(state["learner_id"])), at)

    def _publish(self, state: dict[str, object], attempt: dict[str, object], at: datetime) -> None:
        difficulty, difficulty_source = evidence_difficulty(self.skills.get(str(state["skill_id"])))
        presentation = next(
            row
            for row in state["presentations"]  # type: ignore[union-attr]
            if row["presentation_id"] == attempt["presentation_id"]
        )
        self._publisher.publish(
            {
                "contract_version": self._publisher.version,
                "learner_id": state["learner_id"],
                "skill_id": state["skill_id"],
                "universal_skill_id": self.universal_skill_id,
                "episode_id": state["episode_id"],
                "presentation_id": attempt["presentation_id"],
                "item_revision_id": attempt["revision_id"],
                "parallel_family_id": presentation["parallel_family_id"],
                "attempt_id": attempt["attempt_id"],
                "measurement_role": attempt["role"],
                "assistance_state": "none",
                "earned_score": attempt["earned_score"],
                "maximum_score": attempt["maximum_score"],
                "scoring_version": self.scoring_version,
                "correct": attempt["correct"],
                "response_time_ms": attempt["response_time_ms"],
                "supported": False,
                "hint_count": 0,
                "difficulty": difficulty,
                "difficulty_source": difficulty_source,
                "difficulty_mapping_version": EVIDENCE_LEVEL_MAPPING_VERSION,
                "environment": state["environment"],
                "model_ingestion_eligible": self._model_eligible(state, at),
                "session_id": state["session_id"],
            }
        )

    @staticmethod
    def _stored_item(state: dict[str, object], role: str) -> dict[str, object]:
        return next(row for row in state["presentations"] if row["role"] == role)  # type: ignore[index]

    def _mutate(
        self,
        episode_id: UUID,
        key: str,
        request: dict[str, object],
        expected: str,
        transition: Callable[[dict[str, object], datetime], dict[str, object]],
    ) -> dict[str, object]:
        prior = self._receipt(key, request)
        if prior is not None:
            return prior
        at = self._now()
        try:
            row = self._store.get(episode_id, for_update=True)
            state = json.loads(json.dumps(row.state))
            if state.get("experience_id") != self.experience_id:
                raise NumberWorldFlowError(self.episode_type_error)
            if state["status"] != expected:
                raise NumberWorldFlowError("EPISODE_STATE_CONFLICT")
            old_count = len(state["events"])
            response = transition(state, at)
            state["revision"] = int(row.revision) + 1
            self._store.replace(
                episode_id=episode_id,
                expected_revision=row.revision,
                state=state,
                new_events=tuple(state["events"][old_count:]),
                audit_type=str(state["status"]),
                audit_reasons=("DEVELOPMENT_ONLY",),
                idempotency_key=key,
                request_sha256=_digest(request),
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
            return self._store.receipt(key, _digest(request))
        except ValueError as error:
            raise NumberWorldFlowError(str(error)) from error

    def _atomic(self, operation: Callable[[], None]) -> None:
        try:
            operation()
            self._store.commit()
        except Exception:
            self._store.rollback()
            raise

    def _response(self, state: dict[str, object], item: NumberWorldItem) -> dict[str, object]:
        return {
            "episode_id": state["episode_id"],
            "status": state["status"],
            "manifest": self._public_item(item, str(state["presentations"][-1]["presentation_id"])),
            "support": None,
            "reward": state.get("reward"),
        }

    def _public_item(self, item: NumberWorldItem, presentation_id: str) -> dict[str, object]:
        return {
            "presentation_id": presentation_id,
            "revision_id": item.revision_id,
            "measurement_role": item.measurement_role,
            "assistance_state": "none",
            "prompt_si": item.prompt_si,
            "accessibility_label_si": item.prompt_si,
            "options": [],
            "content_version": self.package_version,
            "game": {
                "schema_version": self.item_schema_version,
                "skill_id": item.skill_id,
                **self._public_game_data(item),
            },
        }

    @staticmethod
    def _public_game_data(item: NumberWorldItem) -> dict[str, object]:
        """Expose only task givens; scoring targets remain server-side."""

        game = item.game_data
        public: dict[str, object] = {"chapter": item.chapter}
        if item.skill_id.endswith(("POSITION-01", "REPRESENTED-01")):
            public.update(number=game["number"], digit=game["digit"])
        elif item.skill_id.endswith("100000-01"):
            public["milestone"] = True
        elif item.skill_id.endswith(("ABACUS-01", "EXPAND-01")):
            public["number"] = game["number"]
        elif item.skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
            public.update(digits=game["digits"], greatest=game["greatest"])
        else:
            public.update(values=game["values"], ascending=game["ascending"])
        return public

    @staticmethod
    def _item_record(
        item: NumberWorldItem, presentation_id: UUID, sequence: int, at: datetime
    ) -> dict[str, object]:
        return {
            "presentation_id": str(presentation_id),
            "revision_id": item.revision_id,
            "item_id": item.item_id,
            "role": item.measurement_role,
            "assistance_state": "none",
            "parallel_family_id": item.parallel_family_id,
            "skill_id": item.skill_id,
            "chapter": item.chapter,
            "prompt_si": item.prompt_si,
            "options": [list(value) for value in item.options],
            "correct_option_id": item.correct_option_id,
            "error_codes": item.error_codes,
            "game_data": item.game_data,
            "sequence": sequence,
            "created_at": at.isoformat(),
        }

    def _infer_belief(
        self,
        error_code: str,
        *,
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None,
    ) -> dict[str, object]:
        del interaction_summary
        return self.infer_belief(error_code, sparse=response_time_ms is None)

    @staticmethod
    def _required_support_actions(scaffold_type: str) -> int:
        del scaffold_type
        return 3

    @staticmethod
    def _validate_interaction_summary(
        interaction_summary: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        summary = dict(interaction_summary or {})
        allowed = {
            "move_count",
            "correction_count",
            "first_action_ms",
            "active_time_ms",
            "leading_zero_attempts",
            "attempt_count",
        }
        if not set(summary).issubset(allowed):
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 86_400_000
            for value in summary.values()
        ):
            raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return summary

    @staticmethod
    def _missingness(
        response_time_ms: int | None, interaction_summary: Mapping[str, object] | None
    ) -> list[str]:
        del interaction_summary
        return ["response_time_ms"] if response_time_ms is None else []

    @staticmethod
    def _additional_exclusions(
        state: dict[str, object], after_item: dict[str, object]
    ) -> list[str]:
        del state, after_item
        return []

    def _support(self, state: dict[str, object]) -> dict[str, object]:
        exposure = state["scaffold_exposure"]
        assert isinstance(exposure, dict)
        kind = str(exposure["scaffold_type"])
        copy = {
            "visual_guidance": ("වර්ණ සහ ඉස්මතු කිරීම් සමඟ මේ ප්‍රශ්නය බලමු.",),
            "worked_parallel_example": ("පද්ධතිය මේ ප්‍රශ්නය විසඳන ආකාරය බලමු.",),
            "step_by_step_guidance": ("එක් එක් පියවර පැහැදිලිව පරීක්ෂා කරමු.",),
        }[kind]
        renderer_id = f"{state['chapter']}:{kind}"
        failed_item = self._stored_item(state, "unsupported_before")
        worked_example = self._worked_example(failed_item, scaffold_type=kind)
        parallel_values = {
            "place_value_harbour": [5, 2, 0, 1, 4],
            "firefly_abacus": [5, 2, 0, 1, 4],
            "kite_workshop": [0, 3, 6, 8],
            "river_route_rally": [12_305, 12_350, 13_205],
        }[str(state["chapter"])]
        return {
            "scaffold_id": f"{state['skill_id']}:{kind}",
            "revision_id": exposure["revision_id"],
            "scaffold_type": kind,
            "title_si": {
                "visual_guidance": "දෘශ්‍ය මඟ පෙන්වීමෙන් බලමු",
                "worked_parallel_example": "විසඳන ආකාරය බලමු",
                "step_by_step_guidance": "පියවරෙන් පියවර බලමු",
            }[kind],
            "body_si": list(copy),
            "visual_alt_text_si": "ස්ථානීය අගය සොයා බැලීමට සහාය වන අන්තර්ක්‍රියාකාරී මඟ පෙන්වීම",
            "maximum_steps": 4,
            "game_manifest": {
                "schema_version": self.support_schema_version,
                "activity_id": state["chapter"],
                "revision_id": exposure["manifest_revision_id"],
                "deterministic_seed": state["seed"],
                "skill_id": state["skill_id"],
                "scaffold_type": kind,
                "renderer_id": renderer_id,
                "parallel_example_id": f"{state['skill_id']}:parallel-support-v1",
                "parallel_example_version": "v1",
                "parallel_values": parallel_values,
                "required_actions": 3,
                "worked_example": worked_example,
            },
        }

    @staticmethod
    def _worked_example(
        item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        """Build an answer-bearing demonstration for the exact failed item."""

        skill_id = str(item["skill_id"])
        game = dict(item["game_data"])  # type: ignore[arg-type]
        if skill_id.endswith("POSITION-01"):
            response: dict[str, object] = {
                "kind": "drag_to_slot",
                "selected_place": int(game["place"]),
            }
            steps = (
                "අසන ඉලක්කම සංඛ්‍යාවේ සොයා ගනිමු.",
                "දකුණෙන් එකක තැන සිට එහි ස්ථානය ගණන් කරමු.",
                "ඉලක්කම තිබෙන නිවැරදි ස්ථානය පෙන්වමු.",
            )
        elif skill_id.endswith("REPRESENTED-01"):
            represented = int(game["digit"]) * 10 ** int(game["place"])
            response = {"kind": "drag_to_slot", "represented_value": represented}
            steps = (
                "අසන ඉලක්කම සංඛ්‍යාවේ සොයා ගනිමු.",
                "එය තිබෙන ස්ථානයේ අගය බලමු.",
                "ඉලක්කම × ස්ථානීය අගය ගණනය කරමු.",
            )
        elif skill_id.endswith("100000-01"):
            response = {"kind": "constructed_number", "constructed_number": int(game["number"])}
            steps = (
                "99 999 හි එකක තැනට එකක් එකතු කරමු.",
                "සෑම 9ක්ම 0 වී ඉදිරි තැනට එකක් ගෙන යමු.",
                "නව ලක්ෂ තැනේ 1 සමඟ 100 000 ලැබේ.",
            )
        elif skill_id.endswith("ABACUS-01"):
            rods = [int(value) for value in game["rods"]]  # type: ignore[union-attr]
            response = {"kind": "bead_placement", "rods": rods}
            steps = (
                "දඬු හයේ ස්ථාන වම් සිට දකුණට හඳුනා ගනිමු.",
                "සෑම ඉලක්කමකටම එම දඬුවේ පබළු තබමු.",
                "පබළු ගණන් කර සම්පූර්ණ සංඛ්‍යාව නැවත බලමු.",
            )
        elif skill_id.endswith("EXPAND-01"):
            terms = [int(part) for part in expanded_form(int(game["number"])).split(" + ")]
            response = {"kind": "expanded_form", "terms": terms}
            steps = (
                "සංඛ්‍යාවේ ඉලක්කම් ස්ථාන වගුවේ තබමු.",
                "සෑම ඉලක්කමක්ම එහි ස්ථානීය අගයෙන් විහිදුවමු.",
                "ශූන්‍ය ස්ථාන හැර විහිදුණු එකතුව පරීක්ෂා කරමු.",
            )
        elif skill_id.endswith(("EXTREME-01", "LEADING-ZERO-01")):
            supplied = tuple(int(value) for value in game["digits"])  # type: ignore[union-attr]
            result = construct_extreme(supplied, greatest=bool(game["greatest"]))
            digits = [int(value) for value in str(result)]
            response = {"kind": "digit_order", "digits": digits}
            steps = (
                "දී ඇති ඉලක්කම් සියල්ල හඳුනා ගනිමු.",
                "අවශ්‍ය දිශාවට ඉලක්කම් එකින් එක සකස් කරමු.",
                "මුලට 0 නොතබා සම්පූර්ණ සංඛ්‍යාව පරීක්ෂා කරමු.",
            )
        else:
            supplied_values = tuple(int(value) for value in game["values"])  # type: ignore[union-attr]
            ordered = list(order_numbers(supplied_values, ascending=bool(game["ascending"])))
            response = {"kind": "number_order", "order": ordered}
            steps = (
                "සංඛ්‍යාවල වම්පස ඉලක්කම් මුලින් සසඳමු.",
                "අවශ්‍ය දිශාවට ඊළඟ සංඛ්‍යාව තෝරමු.",
                "සියලු සංඛ්‍යා යොදා ඇතිදැයි මාර්ගය පරීක්ෂා කරමු.",
            )
        if scaffold_type == "visual_guidance":
            steps = (
                "අදාළ නිරූපණය හොඳින් බලමු.",
                "වෙනස් වන ස්ථානය හෝ ඉලක්කම ඉස්මතු කර බලමු.",
                "උදව් නැතිව එම ක්‍රියාව ඔබම කරන්න.",
            )
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {
                "schema_version": "number-world-item-v1",
                "skill_id": skill_id,
                **game,
            },
            "correct_response": response,
            "steps_si": list(steps),
        }

    @staticmethod
    def _summary(state: dict[str, object]) -> dict[str, object]:
        attempts = state.get("attempts")
        latest = attempts[-1] if isinstance(attempts, list) and attempts else None
        score = (
            None
            if latest is None
            else {
                "earned_score": latest["earned_score"],
                "maximum_score": latest["maximum_score"],
                "scoring_version": latest["scoring_version"],
                "server_authoritative": True,
                "measurement_role": latest["role"],
                "correct": latest["correct"],
                "attempt_id": latest["attempt_id"],
                "presentation_id": latest["presentation_id"],
                "item_revision_id": latest["revision_id"],
            }
        )
        return {
            "episode_id": state["episode_id"],
            "status": state["status"],
            "manifest": None,
            "support": None,
            "reward": state.get("reward"),
            "server_score": score,
        }


def is_number_world_state(state: Mapping[str, object]) -> bool:
    return state.get("experience_id") == "number_world"
