"""Development session orchestrator. The server owns every research transition.

Authentication and the in-memory stores are ``NOT_FOR_PRODUCTION`` (UD-007).
Child-facing delivery stays blocked: ``allow_draft`` is only for adult testers.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.gamification.application.episode_use_cases import (
    AssessStruggleCommand,
    CalculateIndependenceOutcomeCommand,
    EpisodeUseCases,
    InferMisconceptionBeliefsCommand,
    OpenAdaptiveEpisodeCommand,
    RecordSupportExposureCommand,
    RecordVerificationResponseCommand,
    ScheduleUnsupportedVerificationCommand,
    SelectSupportActionCommand,
    WithdrawSupportCommand,
)
from app.gamification.application.errors import EpisodeFlowError, PlayError
from app.gamification.application.struggle_trigger import StruggleEvidence
from app.gamification.application.template_selection import TemplateCompatibilityTable
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.records import (
    ContentAsset,
    ItemDefinition,
    ResponseFormat,
    ScaffoldDefinition,
)
from app.gamification.domain.types import DecisionMode, EpisodeId, EpisodePhase, SkillId

MAX_EVENTS = 50
_ALLOWED_MODES = {
    DecisionMode.PERFORMANCE_TRIGGERED_FIXED,
    DecisionMode.SHADOW,
}
_FORBIDDEN_EVENT_KEYS = frozenset(
    {"x", "y", "pointer", "pointers", "coordinates", "answer", "correct_option_id"}
)


@dataclass
class PlaySession:
    session_id: UUID
    learner_id: UUID
    client_session_id: UUID
    language: str
    status: str
    next_sequence: int = 1
    seen_event_ids: set[str] = field(default_factory=set)
    episode_id: UUID | None = None
    awaiting: str = "none"
    item_id: str | None = None
    template_key: str | None = None
    decision_mode: DecisionMode = DecisionMode.PERFORMANCE_TRIGGERED_FIXED
    variation_seed: int = 7
    device_capabilities: tuple[str, ...] = ("choice_quest", "build_manipulate")


class SessionPlay:
    def __init__(
        self,
        *,
        cases: EpisodeUseCases,
        episodes: object,
        catalog: PilotContentCatalog,
        taxonomy_version: str,
        clock: object | None = None,
    ) -> None:
        self._cases = cases
        self._episodes = episodes
        self._catalog = catalog
        self._taxonomy_version = taxonomy_version
        self._clock = clock
        self.sessions: dict[UUID, PlaySession] = {}
        self.idempotency: dict[str, tuple[str, dict[str, object]]] = {}

    def now(self) -> datetime:
        if self._clock is None:
            return datetime.now(UTC)
        return self._clock.now()  # type: ignore[no-any-return]

    def create_session(
        self,
        *,
        learner_id: UUID,
        client_session_id: UUID,
        language: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = _fingerprint(
            {
                "learner_id": str(learner_id),
                "client_session_id": str(client_session_id),
                "language": language,
            }
        )
        return self._once(
            idempotency_key,
            fingerprint,
            lambda: self._create(learner_id, client_session_id, language),
        )

    def complete_session(
        self, session_id: UUID, *, learner_id: UUID, idempotency_key: str
    ) -> dict[str, object]:
        return self._once(
            idempotency_key,
            _fingerprint({"session_id": str(session_id), "op": "complete"}),
            lambda: self._complete(session_id, learner_id),
        )

    def next_activity(
        self,
        session_id: UUID,
        *,
        learner_id: UUID,
        skill_id: str,
        device_capabilities: tuple[str, ...],
        decision_mode: DecisionMode,
        idempotency_key: str,
    ) -> dict[str, object]:
        if decision_mode is DecisionMode.LEARNED:
            raise PlayError("MODEL_NOT_READY", 409)
        if decision_mode not in _ALLOWED_MODES:
            raise PlayError("MODEL_NOT_READY", 409)
        fingerprint = _fingerprint(
            {
                "session_id": str(session_id),
                "skill_id": skill_id,
                "capabilities": list(device_capabilities),
                "mode": decision_mode.value,
            }
        )
        return self._once(
            idempotency_key,
            fingerprint,
            lambda: self._present(
                session_id, learner_id, skill_id, device_capabilities, decision_mode
            ),
        )

    def submit_response(
        self,
        session_id: UUID,
        *,
        learner_id: UUID,
        episode_id: UUID,
        selected_option_id: str,
        response_time_ms: int | None,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = _fingerprint(
            {
                "session_id": str(session_id),
                "episode_id": str(episode_id),
                "selected_option_id": selected_option_id,
                "response_time_ms": response_time_ms,
            }
        )
        return self._once(
            idempotency_key,
            fingerprint,
            lambda: self._respond(
                session_id, learner_id, episode_id, selected_option_id, response_time_ms
            ),
        )

    def complete_support(
        self,
        episode_id: UUID,
        *,
        learner_id: UUID,
        duration_ms: int,
        step_count: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = _fingerprint(
            {
                "episode_id": str(episode_id),
                "op": "support-complete",
                "duration_ms": duration_ms,
                "step_count": step_count,
            }
        )
        return self._once(
            idempotency_key,
            fingerprint,
            lambda: self._complete_support(episode_id, learner_id, duration_ms, step_count),
        )

    def withdraw_support(
        self, episode_id: UUID, *, learner_id: UUID, idempotency_key: str
    ) -> dict[str, object]:
        return self._once(
            idempotency_key,
            _fingerprint({"episode_id": str(episode_id), "op": "withdraw"}),
            lambda: self._withdraw(episode_id, learner_id),
        )

    def ingest_events(
        self,
        session_id: UUID,
        *,
        learner_id: UUID,
        first_sequence_no: int,
        events: tuple[dict[str, object], ...],
        idempotency_key: str,
    ) -> dict[str, object]:
        fingerprint = _fingerprint(
            {
                "session_id": str(session_id),
                "first_sequence_no": first_sequence_no,
                "events": list(events),
            }
        )
        return self._once(
            idempotency_key,
            fingerprint,
            lambda: self._ingest(session_id, learner_id, first_sequence_no, events),
        )

    def _ingest(
        self,
        session_id: UUID,
        learner_id: UUID,
        first_sequence_no: int,
        events: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        session = self._owned_session(session_id, learner_id)
        if len(events) > MAX_EVENTS:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
        if first_sequence_no != session.next_sequence:
            raise PlayError("SESSION_SEQUENCE_CONFLICT", 409)
        for offset, event in enumerate(events):
            if event.get("sequence_no") != first_sequence_no + offset:
                raise PlayError("SESSION_SEQUENCE_CONFLICT", 409)
        accepted = 0
        duplicate = 0
        quarantined = 0
        for event in events:
            payload = event.get("payload")
            if not isinstance(payload, dict) or _FORBIDDEN_EVENT_KEYS.intersection(payload):
                quarantined += 1
                continue
            event_id = str(event["event_id"])
            if event_id in session.seen_event_ids:
                duplicate += 1
                continue
            session.seen_event_ids.add(event_id)
            accepted += 1
        session.next_sequence = first_sequence_no + len(events)
        return {
            "accepted": accepted,
            "duplicate": duplicate,
            "quarantined": quarantined,
            "expected_next_sequence": session.next_sequence,
        }

    def reconstruct(self, episode_id: UUID) -> dict[str, object]:
        try:
            state = self._episodes.get(EpisodeId(episode_id))
        except LookupError as error:
            raise PlayError("EPISODE_NOT_FOUND", 404) from error
        decision = state.decision
        candidates = []
        if decision is not None:
            candidates = [
                {
                    "action_id": str(candidate.action_id),
                    "action_type": candidate.action_type.value,
                    "propensity": candidate.propensity,
                    "predicted_reward": candidate.predicted_reward,
                    "eligible": candidate.eligible,
                }
                for candidate in decision.candidates
            ]
        beliefs = []
        if state.belief is not None:
            beliefs = [
                {"code": code, "probability": probability}
                for code, probability in sorted(state.belief.probabilities.items())
            ]
        outcome = state.outcome
        return {
            "episode_id": str(episode_id),
            "phase": state.episode.phase.value,
            "beliefs": beliefs,
            "candidates": candidates,
            "delivered_scaffold_id": (
                None if decision is None else str(decision.selected_action_id)
            ),
            "baseline_score": None
            if state.baseline_response is None
            else state.baseline_response.score,
            "verification_score": (
                None if state.verification_response is None else state.verification_response.score
            ),
            "independence_gain": None if outcome is None else outcome.raw_independence_gain,
            "validity": None if outcome is None else outcome.validity,
        }

    def _create(
        self, learner_id: UUID, client_session_id: UUID, language: str
    ) -> dict[str, object]:
        session = PlaySession(
            session_id=uuid4(),
            learner_id=learner_id,
            client_session_id=client_session_id,
            language=language,
            status="active",
        )
        self.sessions[session.session_id] = session
        return _session_body(session)

    def _complete(self, session_id: UUID, learner_id: UUID) -> dict[str, object]:
        session = self._owned_session(session_id, learner_id)
        session.status = "completed"
        return _session_body(session)

    def _present(
        self,
        session_id: UUID,
        learner_id: UUID,
        skill_id: str,
        device_capabilities: tuple[str, ...],
        decision_mode: DecisionMode,
    ) -> dict[str, object]:
        session = self._active(session_id, learner_id)
        if session.awaiting not in {"none", "done"}:
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        item = _baseline_item(self._catalog, skill_id)
        table = TemplateCompatibilityTable(
            self._catalog.template_rules(),
            table_version=self._catalog.template_table_version(),
        )
        selection = table.select_template(item, device_capabilities, session.variation_seed)
        session.episode_id = uuid4()
        session.item_id = item.item_id
        session.template_key = selection.template_key
        session.device_capabilities = device_capabilities
        session.decision_mode = decision_mode
        session.awaiting = "baseline"
        return {
            "episode_id": str(session.episode_id),
            "template_key": selection.template_key,
            "next_step": "continue",
            "manifest": _manifest(item, selection.template_key, session.language),
            "support": None,
        }

    def _respond(
        self,
        session_id: UUID,
        learner_id: UUID,
        episode_id: UUID,
        selected_option_id: str,
        response_time_ms: int | None,
    ) -> dict[str, object]:
        session = self._active(session_id, learner_id)
        if session.episode_id != episode_id:
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        if session.awaiting == "baseline":
            return self._baseline(session, selected_option_id, response_time_ms)
        if session.awaiting == "verification":
            return self._verification(session, selected_option_id, response_time_ms)
        raise PlayError("EPISODE_STATE_CONFLICT", 409)

    def _baseline(
        self, session: PlaySession, selected_option_id: str, response_time_ms: int | None
    ) -> dict[str, object]:
        assert session.episode_id is not None and session.item_id is not None
        item = self._catalog.item(session.item_id)
        at = self.now()
        try:
            option = item.option(selected_option_id)
        except LookupError as error:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422) from error
        correct = option.option_id == item.correct_option_id
        linked = option.misconception_code is not None and not correct
        self._cases.open_episode.execute(
            OpenAdaptiveEpisodeCommand(
                episode_id=EpisodeId(session.episode_id),
                session_id=session.session_id,
                learner_id=session.learner_id,
                skill_id=SkillId(item.skill_id),
                taxonomy_version=self._taxonomy_version,
                item_id=item.item_id,
                selected_option_id=selected_option_id,
                submitted_at=at,
                device_capabilities=frozenset(session.device_capabilities),
                variation_seed=session.variation_seed,
                response_time_ms=response_time_ms,
                incorrect_attempt_count=0 if correct else 1,
                learner_requested_help=False,
                language=session.language,
                decision_mode=session.decision_mode,
            )
        )
        assessed = self._cases.assess_struggle.execute(
            AssessStruggleCommand(
                episode_id=EpisodeId(session.episode_id),
                evidence=StruggleEvidence(
                    captured_at=at + timedelta(milliseconds=1),
                    incorrect_attempt_count=0 if correct else 1,
                    response_time_ms=response_time_ms,
                    selected_option_is_misconception_linked=linked,
                    learner_requested_help=False,
                    source_as_of={"baseline_response": at},
                ),
                at=at + timedelta(milliseconds=1),
            )
        )
        if assessed.episode.phase is EpisodePhase.ABANDONED:
            session.awaiting = "done"
            return _step("finish", session, item, support=None)
        self._cases.infer_beliefs.execute(
            InferMisconceptionBeliefsCommand(
                episode_id=EpisodeId(session.episode_id),
                at=at + timedelta(milliseconds=2),
                attempt_count=1,
                recent_correctness=(correct,),
                source_as_of={"baseline_response": at},
            )
        )
        try:
            decided = self._cases.select_support.execute(
                SelectSupportActionCommand(
                    episode_id=EpisodeId(session.episode_id),
                    at=at + timedelta(milliseconds=3),
                    seed=session.variation_seed,
                    mode=session.decision_mode,
                )
            )
        except ValueError as error:
            raise PlayError("NO_ELIGIBLE_SUPPORT", 409) from error
        session.awaiting = "support"
        assert decided.decision is not None
        scaffold = self._catalog.scaffold(str(decided.decision.selected_action_id))
        asset = self._catalog.asset(scaffold.content_asset_id)
        return _step(
            "present_support", session, item, support=_support(scaffold, asset, session.language)
        )

    def _complete_support(
        self, episode_id: UUID, learner_id: UUID, duration_ms: int, step_count: int
    ) -> dict[str, object]:
        session = self._session_for_episode(episode_id, learner_id)
        if session.awaiting != "support":
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        self._guard(
            lambda: self._cases.record_exposure.execute(
                RecordSupportExposureCommand(
                    episode_id=EpisodeId(episode_id),
                    at=self.now(),
                    duration_ms=duration_ms,
                    step_count=step_count,
                )
            )
        )
        return {"episode_id": str(episode_id), "next_step": "continue"}

    def _withdraw(self, episode_id: UUID, learner_id: UUID) -> dict[str, object]:
        session = self._session_for_episode(episode_id, learner_id)
        if session.awaiting != "support":
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        at = self.now()
        self._guard(
            lambda: self._cases.withdraw_support.execute(
                WithdrawSupportCommand(episode_id=EpisodeId(episode_id), at=at)
            )
        )
        scheduled = self._guard(
            lambda: self._cases.schedule_verification.execute(
                ScheduleUnsupportedVerificationCommand(
                    episode_id=EpisodeId(episode_id), at=at + timedelta(milliseconds=1)
                )
            )
        )
        if (
            scheduled.episode.phase is EpisodePhase.INVALIDATED
            or scheduled.verification_pair is None
        ):
            session.awaiting = "done"
            return {
                "episode_id": str(episode_id),
                "next_step": "safe_fallback",
                "template_key": session.template_key,
                "manifest": None,
                "support": None,
            }
        item = self._catalog.item(str(scheduled.verification_pair.verification_item_id))
        session.awaiting = "verification"
        session.item_id = item.item_id
        return _step("present_verification", session, item, support=None)

    def _verification(
        self, session: PlaySession, selected_option_id: str, response_time_ms: int | None
    ) -> dict[str, object]:
        assert session.episode_id is not None and session.item_id is not None
        item = self._catalog.item(session.item_id)
        at = self.now()
        self._guard(
            lambda: self._cases.record_verification.execute(
                RecordVerificationResponseCommand(
                    episode_id=EpisodeId(session.episode_id),
                    at=at,
                    selected_option_id=selected_option_id,
                    response_time_ms=response_time_ms,
                )
            )
        )
        self._guard(
            lambda: self._cases.calculate_outcome.execute(
                CalculateIndependenceOutcomeCommand(
                    episode_id=EpisodeId(session.episode_id), at=at + timedelta(milliseconds=1)
                )
            )
        )
        session.awaiting = "done"
        return _step("finish", session, item, support=None)

    def _owned_session(self, session_id: UUID, learner_id: UUID) -> PlaySession:
        session = self._session(session_id)
        if session.learner_id != learner_id:
            raise PlayError("LEARNER_ACCESS_DENIED", 403)
        return session

    def _session_for_episode(self, episode_id: UUID, learner_id: UUID) -> PlaySession:
        for session in self.sessions.values():
            if session.episode_id == episode_id:
                if session.learner_id != learner_id:
                    raise PlayError("LEARNER_ACCESS_DENIED", 403)
                return session
        raise PlayError("EPISODE_NOT_FOUND", 404)

    def _session(self, session_id: UUID) -> PlaySession:
        try:
            return self.sessions[session_id]
        except KeyError as error:
            raise PlayError("SESSION_NOT_FOUND", 404) from error

    def _active(self, session_id: UUID, learner_id: UUID) -> PlaySession:
        session = self._owned_session(session_id, learner_id)
        if session.status != "active":
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        return session

    def _once(self, key: str, fingerprint: str, produce) -> dict[str, object]:
        if not key or len(key) > 128:
            raise PlayError("IDEMPOTENCY_KEY_REQUIRED", 400)
        found = self.idempotency.get(key)
        if found is not None:
            if found[0] != fingerprint:
                raise PlayError("DUPLICATE_IDEMPOTENCY_KEY", 409)
            return found[1]
        try:
            body = produce()
        except EpisodeFlowError as error:
            raise PlayError(
                "EPISODE_STATE_CONFLICT" if error.code == "EPISODE_STATE_CONFLICT" else error.code,
                409,
            ) from error
        self.idempotency[key] = (fingerprint, body)
        return body

    def _guard(self, produce):
        try:
            return produce()
        except EpisodeFlowError as error:
            raise PlayError(error.code, 409) from error


def _baseline_item(catalog: PilotContentCatalog, skill_id: str) -> ItemDefinition:
    items = [
        catalog.item(item_id)
        for item_id in catalog.item_ids()
        if catalog.item(item_id).skill_id == skill_id
        and catalog.item(item_id).response_format is ResponseFormat.SINGLE_CHOICE
    ]
    if not items:
        raise PlayError("CONTENT_NOT_APPROVED", 404)
    for item in sorted(items, key=lambda candidate: candidate.item_id):
        try:
            catalog.parallel_group(item.parallel_group_id)
        except LookupError:
            continue
        return item
    raise PlayError("VERIFICATION_PAIR_UNAVAILABLE", 409)


def _manifest(item: ItemDefinition, template_key: str, language: str) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "question_text": item.question_text,
        "language": language,
        "template_key": template_key,
        "options": [
            {"option_id": option.option_id, "text": option.text} for option in item.answer_options
        ],
    }


def _support(scaffold: ScaffoldDefinition, asset: ContentAsset, language: str) -> dict[str, object]:
    steps = asset.body_si if language == "si" else asset.body_en
    title = asset.title_si if language == "si" else asset.title_en
    return {
        "scaffold_type": scaffold.scaffold_type.value,
        "title": title,
        "steps": list(steps),
        "maximum_duration_ms": scaffold.maximum_duration_ms,
        "maximum_number_of_steps": scaffold.maximum_number_of_steps,
        "diagram": None if asset.diagram is None else dict(asset.diagram),
    }


def _step(
    next_step: str, session: PlaySession, item: ItemDefinition, support: dict[str, object] | None
) -> dict[str, object]:
    return {
        "episode_id": str(session.episode_id),
        "template_key": session.template_key,
        "next_step": next_step,
        "manifest": _manifest(item, session.template_key or "choice_quest", session.language),
        "support": support,
    }


def _session_body(session: PlaySession) -> dict[str, object]:
    return {
        "session_id": str(session.session_id),
        "learner_id": str(session.learner_id),
        "status": session.status,
    }


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
