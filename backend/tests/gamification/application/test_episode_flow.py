import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.gamification.application.episode_use_cases import (
    AssessStruggleCommand,
    CalculateIndependenceOutcomeCommand,
    InferMisconceptionBeliefsCommand,
    OpenAdaptiveEpisodeCommand,
    RecordSupportExposureCommand,
    RecordVerificationResponseCommand,
    ScheduleUnsupportedVerificationCommand,
    SelectSupportActionCommand,
    WithdrawSupportCommand,
    wire_episode_use_cases,
)
from app.gamification.application.errors import EpisodeFlowError
from app.gamification.application.records import (
    ConsentDecision,
    GamificationAttempt,
    SkillMasteryEvidence,
)
from app.gamification.application.struggle_trigger import StruggleEvidence
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.loader import load_pilot_content_package
from app.gamification.content.records import ContentAsset
from app.gamification.domain.types import (
    CatalogueVersion,
    ContractVersion,
    DecisionMode,
    EpisodeId,
    EpisodePhase,
    ItemId,
    SkillId,
)
from app.gamification.infrastructure.episode_memory import InMemoryUnitOfWork
from app.gamification.infrastructure.evidence_publisher import InMemoryLearnerEvidencePublisher
from app.gamification.infrastructure.memory import InMemoryConsentStore
from app.gamification.modeling.independence_gain.calculator import RawIndependenceGainCalculator
from app.gamification.modeling.misconception_inference.probabilistic_model import (
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.support_selection.reference_policy import SafeSupportPolicy

AT = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
SKILL = SkillId("G5-MAT-C03-L01-O01")
BASELINE_ITEM = "G5-MAT-FRC-I010"
STEP_BY_STEP = "G5-MAT-FRC-SC2-STP"
WORKED_EXAMPLE = "G5-MAT-FRC-SC2-WEX"
LEARNER = UUID("00000000-0000-4000-8000-000000000201")
SESSION = UUID("00000000-0000-4000-8000-000000000202")


def _package():
    return load_pilot_content_package(allow_draft=True)


def _flow(catalog: PilotContentCatalog | None = None, **integration: object):
    package = _package()
    catalog = catalog or PilotContentCatalog(package)
    uow = InMemoryUnitOfWork()
    cases = wire_episode_use_cases(
        uow=uow,
        episodes=uow.episodes,
        catalog=catalog,
        predictor=ProbabilisticMisconceptionModel(
            catalogue_version=catalog.misconception_catalogue_version(),
            error_likelihoods={"MAT-FRC-M06": {"MAT-FRC-M06": 4.0}},
            class_priors={
                "MAT-FRC-M05": 0.2,
                "MAT-FRC-M06": 0.5,
                "MAT-FRC-M07": 0.2,
                "unknown/other": 0.1,
            },
            abstain_threshold=0.99,
        ),
        selector=SafeSupportPolicy(
            catalogue_version=CatalogueVersion(catalog.support_catalogue_version()),
            reference_table=catalog.reference_policy_table(),
        ),
        calculator=RawIndependenceGainCalculator(),
        allow_draft=True,
        **integration,  # type: ignore[arg-type]
    )
    return uow, cases, catalog


def _open(cases, episode_id: EpisodeId, *, at: datetime = AT):
    return cases.open_episode.execute(
        OpenAdaptiveEpisodeCommand(
            episode_id=episode_id,
            session_id=SESSION,
            learner_id=LEARNER,
            skill_id=SKILL,
            taxonomy_version="grade5-pilot-skills-v1",
            item_id=BASELINE_ITEM,
            selected_option_id="A",
            submitted_at=at,
            device_capabilities=frozenset({"choice_quest", "sort_and_group", "build_manipulate"}),
            variation_seed=7,
            response_time_ms=5_000,
            incorrect_attempt_count=2,
            learner_requested_help=False,
        )
    )


def _evidence(**overrides: object) -> StruggleEvidence:
    values: dict[str, object] = {
        "captured_at": AT + timedelta(seconds=1),
        "incorrect_attempt_count": 2,
        "response_time_ms": 5_000,
        "selected_option_is_misconception_linked": True,
        "learner_requested_help": False,
        "source_as_of": {"baseline_response": AT},
    }
    values.update(overrides)
    return StruggleEvidence(**values)  # type: ignore[arg-type]


def _through_decision(cases, episode_id: EpisodeId):
    _open(cases, episode_id)
    cases.assess_struggle.execute(
        AssessStruggleCommand(
            episode_id=episode_id,
            evidence=_evidence(),
            at=AT + timedelta(seconds=1),
        )
    )
    cases.infer_beliefs.execute(
        InferMisconceptionBeliefsCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=2),
            attempt_count=2,
            recent_correctness=(False,),
            source_as_of={"baseline_response": AT},
        )
    )
    return cases.select_support.execute(
        SelectSupportActionCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=3),
            seed=7,
        )
    )


def test_happy_path_reaches_a_valid_outcome_with_one_template() -> None:
    uow, cases, catalog = _flow()
    episode_id = EpisodeId(uuid4())
    opened = _open(cases, episode_id)
    assert opened.episode.phase is EpisodePhase.BASELINE_RECORDED
    assert opened.baseline_response is not None
    assert opened.baseline_response.phase == "baseline"
    assert opened.baseline_response.support_state == "unsupported"
    assert opened.baseline_template == "choice_quest"
    assert opened.decision_mode is DecisionMode.DETERMINISTIC_REFERENCE

    assessed = cases.assess_struggle.execute(
        AssessStruggleCommand(
            episode_id=episode_id, evidence=_evidence(), at=AT + timedelta(seconds=1)
        )
    )
    assert assessed.episode.phase is EpisodePhase.STRUGGLE_ASSESSED
    assert assessed.trigger_type == "TWO_INCORRECT_ATTEMPTS"
    assert "MISCONCEPTION_LINKED_OPTION_SELECTED" in assessed.trigger_reasons

    cases.infer_beliefs.execute(
        InferMisconceptionBeliefsCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=2),
            attempt_count=2,
            recent_correctness=(False,),
            source_as_of={"baseline_response": AT},
        )
    )
    decided = cases.select_support.execute(
        SelectSupportActionCommand(episode_id=episode_id, at=AT + timedelta(seconds=3), seed=7)
    )
    assert decided.decision is not None
    assert decided.decision.mode is DecisionMode.DETERMINISTIC_REFERENCE
    assert decided.decision.selected_action_id == STEP_BY_STEP
    assert "AUTHORED_REFERENCE_TABLE" in decided.decision.reason_codes
    assert decided.policy_context_snapshot is not None
    assert decided.policy_context_snapshot.purpose == "policy_context"

    delivered = cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=1_000,
            step_count=1,
            supported_item_id=BASELINE_ITEM,
            supported_option_id="A",
        )
    )
    assert delivered.supported_responses[0].phase == "supported"
    assert delivered.supported_responses[0].support_state == "supported"
    assert delivered.exposures[0].evidence.delivery_status == "completed"
    assert delivered.exposures[0].maximum_duration_ms > 0

    cases.withdraw_support.execute(
        WithdrawSupportCommand(episode_id=episode_id, at=AT + timedelta(seconds=5))
    )
    scheduled = cases.schedule_verification.execute(
        ScheduleUnsupportedVerificationCommand(episode_id=episode_id, at=AT + timedelta(seconds=6))
    )
    assert scheduled.verification_pair is not None
    assert scheduled.verification_pair.unseen_verification_item is True
    assert scheduled.verification_pair.answer_overlap == 0.0
    assert str(scheduled.verification_pair.verification_item_id) != BASELINE_ITEM
    verification = catalog.item(str(scheduled.verification_pair.verification_item_id))
    assert verification.default_template == opened.baseline_template

    cases.record_verification.execute(
        RecordVerificationResponseCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=7),
            selected_option_id=verification.correct_option_id or "",
        )
    )
    finished = cases.calculate_outcome.execute(
        CalculateIndependenceOutcomeCommand(episode_id=episode_id, at=AT + timedelta(seconds=8))
    )

    assert finished.episode.phase is EpisodePhase.COMPLETED
    assert finished.outcome is not None
    assert finished.outcome.validity == "valid"
    assert finished.outcome.raw_independence_gain == 1.0
    assert finished.verification_response is not None
    assert finished.verification_response.support_state == "unsupported"
    templates = [
        event.metadata.get("template")
        for event in uow.audit.events
        if event.metadata.get("template") is not None
    ]
    assert templates
    assert set(templates) == {"choice_quest"}


def test_no_struggle_abandons_the_episode() -> None:
    _uow, cases, _catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _open(cases, episode_id)
    finished = cases.assess_struggle.execute(
        AssessStruggleCommand(
            episode_id=episode_id,
            evidence=_evidence(
                incorrect_attempt_count=1,
                selected_option_is_misconception_linked=False,
            ),
            at=AT + timedelta(seconds=1),
        )
    )

    assert finished.episode.phase is EpisodePhase.ABANDONED
    assert finished.episode.terminal_reason == "NO_STRUGGLE_DETECTED"
    assert finished.trigger_type == "no_struggle"


def test_second_scaffold_and_early_verification_are_rejected() -> None:
    _uow, cases, _catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)
    cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=1_000,
            step_count=1,
        )
    )

    with pytest.raises(EpisodeFlowError, match="SCAFFOLD_ALREADY_ACTIVE"):
        cases.record_exposure.execute(
            RecordSupportExposureCommand(
                episode_id=episode_id,
                at=AT + timedelta(seconds=5),
                duration_ms=1_000,
                step_count=1,
            )
        )
    with pytest.raises(EpisodeFlowError, match="SUPPORT_NOT_WITHDRAWN"):
        cases.schedule_verification.execute(
            ScheduleUnsupportedVerificationCommand(
                episode_id=episode_id, at=AT + timedelta(seconds=5)
            )
        )
    stored = _uow.episodes.get(episode_id)
    assert stored.episode.phase is EpisodePhase.SUPPORT_DELIVERED
    assert len(stored.exposures) == 1


def test_no_unseen_parallel_item_invalidates_the_episode() -> None:
    uow, cases, catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)
    cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=1_000,
            step_count=1,
        )
    )
    cases.withdraw_support.execute(
        WithdrawSupportCommand(episode_id=episode_id, at=AT + timedelta(seconds=5))
    )
    baseline = catalog.item(BASELINE_ITEM)
    for item_id in catalog.parallel_group(baseline.parallel_group_id).item_ids:
        if item_id == BASELINE_ITEM:
            continue
        uow.learning_records.record_attempt(
            GamificationAttempt(
                attempt_id=uuid4(),
                learner_id=LEARNER,
                item_id=ItemId(item_id),
                skill_ids=(SKILL,),
                language="si",
                correct=False,
                score=0.0,
                response_time_ms=None,
                support_exposure="none",
                attempted_at=AT,
                contract_version=ContractVersion("gamification-attempt-v1"),
            )
        )

    finished = cases.schedule_verification.execute(
        ScheduleUnsupportedVerificationCommand(episode_id=episode_id, at=AT + timedelta(seconds=6))
    )

    assert finished.episode.phase is EpisodePhase.INVALIDATED
    assert finished.episode.terminal_reason == "VERIFICATION_PAIR_UNAVAILABLE"


def test_leakage_rejects_the_reference_scaffold_and_falls_back_to_the_worked_example() -> None:
    catalog = PilotContentCatalog(_package())

    class LeakingAssets:
        def asset(self, asset_id: str) -> ContentAsset:
            asset = catalog.asset(asset_id)
            if asset_id == "G5-MAT-FRC-CA2-STP":
                return replace(asset, body_si=("8",), body_en=("8",))
            return asset

        def __getattr__(self, name: str):
            return getattr(catalog, name)

    uow, cases, _catalog = _flow(LeakingAssets())  # type: ignore[arg-type]
    episode_id = EpisodeId(uuid4())
    decided = _through_decision(cases, episode_id)

    assert decided.decision is not None
    assert decided.decision.selected_action_id == WORKED_EXAMPLE
    assert "LEAKAGE_FALLBACK" in decided.decision.reason_codes
    assert any(event.event_type == "scaffold_rejected" for event in uow.audit.events)


def test_over_budget_exposure_is_marked_and_still_delivered() -> None:
    uow, cases, _catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)
    delivered = cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=200_000,
            step_count=1,
        )
    )

    assert delivered.episode.phase is EpisodePhase.SUPPORT_DELIVERED
    assert delivered.exposures[0].evidence.delivery_status == "completed_over_budget"
    assert any(event.metadata.get("maximum_duration_ms") for event in uow.audit.events)


class _FixedMastery:
    def __init__(
        self, evidence: SkillMasteryEvidence | None = None, error: Exception | None = None
    ):
        self.evidence = evidence
        self.error = error
        self.calls: list[str] = []

    def get_mastery(self, *, learner_id: UUID, skill_id: SkillId) -> SkillMasteryEvidence | None:
        del learner_id
        self.calls.append(str(skill_id))
        if self.error is not None:
            raise self.error
        return self.evidence


class _RecordingLearnerState:
    def __init__(self, evidence: object | None = None, error: Exception | None = None) -> None:
        self.evidence = evidence
        self.error = error
        self.calls: list[tuple[str, datetime]] = []

    def get_support_evidence(
        self, *, learner_id: UUID, skill_id: SkillId, observed_no_earlier_than
    ):
        del learner_id
        self.calls.append((str(skill_id), observed_no_earlier_than))
        if self.error is not None:
            raise self.error
        return self.evidence


def _research_consent() -> InMemoryConsentStore:
    return InMemoryConsentStore(
        [
            ConsentDecision(
                learner_id=LEARNER,
                purpose="research",
                granted=True,
                consent_version="consent-v1",
                decided_at=AT - timedelta(days=1),
                expires_at=None,
                contract_version=ContractVersion("gamification-consent-v1"),
            )
        ]
    )


def test_episode_publishes_consented_evidence_and_keeps_attempt_counts_separate() -> None:
    publisher = InMemoryLearnerEvidencePublisher()
    uow, cases, catalog = _flow(publisher=publisher, consent=_research_consent(), summaries=None)
    summaries = uow.learning_records
    for command in (
        cases.open_episode,
        cases.assess_struggle,
        cases.infer_beliefs,
        cases.select_support,
    ):
        command._summaries = summaries
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)

    event_types = [event.event_type for event in publisher.events]
    assert event_types == [
        "attempt_summary",
        "detected_difficulty",
        "misconception_probabilities",
        "selected_scaffold",
    ]
    universal = catalog.universal_skill_id(str(SKILL))
    assert universal == "MAT-FRC"
    for event in publisher.events:
        body = publisher.payload(event.idempotency_key)
        assert body["skill_id"] == str(SKILL)
        assert body["universal_skill_id"] == universal
        assert body["source_component"] == "gamification"
        assert "answer" not in body["payload"]
        assert "A" not in body["payload"].values()
    publisher.publish(publisher.events[0])
    assert len(publisher.events) == 4
    summary = summaries.get_skill_summary(learner_id=LEARNER, skill_id=SKILL)
    assert summary is not None
    assert summary.unsupported_attempts == 1
    assert summary.supported_attempts == 0
    assert summary.independent_accuracy == 0.0


def test_missing_consent_withholds_evidence_without_failing_the_episode() -> None:
    publisher = InMemoryLearnerEvidencePublisher()
    uow, cases, _catalog = _flow(publisher=publisher, consent=InMemoryConsentStore([]))
    opened = _open(cases, EpisodeId(uuid4()))

    assert opened.episode.phase is EpisodePhase.BASELINE_RECORDED
    assert publisher.events == []
    assert any(event.reason_codes == ("CONSENT_SCOPE_MISSING",) for event in uow.audit.events)


def test_mastery_and_learner_state_failures_do_not_fail_the_episode() -> None:
    mastery = _FixedMastery(error=RuntimeError("provider down"))
    learner_state = _RecordingLearnerState(error=RuntimeError("provider down"))
    _uow, cases, _catalog = _flow(mastery=mastery, learner_state=learner_state)
    episode_id = EpisodeId(uuid4())
    _open(cases, episode_id)
    assessed = cases.assess_struggle.execute(
        AssessStruggleCommand(
            episode_id=episode_id,
            evidence=_evidence(),
            at=AT + timedelta(seconds=1),
        )
    )
    inferred = cases.infer_beliefs.execute(
        InferMisconceptionBeliefsCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=2),
            attempt_count=2,
            recent_correctness=(False,),
            source_as_of={"baseline_response": AT},
        )
    )

    assert assessed.episode.phase is EpisodePhase.STRUGGLE_ASSESSED
    assert inferred.feature_snapshot is not None
    assert inferred.feature_snapshot.missingness["mastery_probability"] is True
    assert learner_state.calls[0][0] == str(SKILL)
    assert learner_state.calls[0][1] == AT + timedelta(seconds=1) - timedelta(days=7)
    assert mastery.calls == [str(SKILL)]


def test_available_mastery_reaches_the_decision_snapshot() -> None:
    evidence = SkillMasteryEvidence(
        learner_id=LEARNER,
        skill_id=SKILL,
        universal_skill_id="MAT-FRC",
        mastery_probability=0.42,
        model_version="knowledge-tracing-mastery-v1",
        contract_version=ContractVersion("knowledge-tracing-mastery-v1"),
    )
    _uow, cases, _catalog = _flow(mastery=_FixedMastery(evidence))
    episode_id = EpisodeId(uuid4())
    _open(cases, episode_id)
    cases.assess_struggle.execute(
        AssessStruggleCommand(
            episode_id=episode_id, evidence=_evidence(), at=AT + timedelta(seconds=1)
        )
    )
    inferred = cases.infer_beliefs.execute(
        InferMisconceptionBeliefsCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=2),
            attempt_count=2,
            recent_correctness=(False,),
            source_as_of={"baseline_response": AT},
        )
    )

    assert inferred.feature_snapshot is not None
    assert inferred.feature_snapshot.values["mastery_probability"] == 0.42
    assert inferred.feature_snapshot.missingness["mastery_probability"] is False


def test_episode_completes_without_a_curriculum_retriever() -> None:
    assert "curriculum" not in inspect.signature(wire_episode_use_cases).parameters
    assert "retriever" not in inspect.signature(wire_episode_use_cases).parameters
    uow, cases, catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)
    cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=1_000,
            step_count=1,
        )
    )
    cases.withdraw_support.execute(
        WithdrawSupportCommand(episode_id=episode_id, at=AT + timedelta(seconds=5))
    )
    scheduled = cases.schedule_verification.execute(
        ScheduleUnsupportedVerificationCommand(episode_id=episode_id, at=AT + timedelta(seconds=6))
    )
    assert scheduled.verification_pair is not None
    verification = catalog.item(str(scheduled.verification_pair.verification_item_id))
    cases.record_verification.execute(
        RecordVerificationResponseCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=7),
            selected_option_id=verification.correct_option_id or "",
        )
    )
    finished = cases.calculate_outcome.execute(
        CalculateIndependenceOutcomeCommand(episode_id=episode_id, at=AT + timedelta(seconds=8))
    )
    assert finished.outcome is not None
    assert finished.outcome.validity == "valid"
    assert uow.episodes.get(episode_id).outcome is not None


def test_misconception_resolution_stays_out_of_decision_features() -> None:
    _uow, cases, catalog = _flow()
    episode_id = EpisodeId(uuid4())
    _through_decision(cases, episode_id)
    cases.record_exposure.execute(
        RecordSupportExposureCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=4),
            duration_ms=1_000,
            step_count=1,
        )
    )
    cases.withdraw_support.execute(
        WithdrawSupportCommand(episode_id=episode_id, at=AT + timedelta(seconds=5))
    )
    scheduled = cases.schedule_verification.execute(
        ScheduleUnsupportedVerificationCommand(episode_id=episode_id, at=AT + timedelta(seconds=6))
    )
    assert scheduled.verification_pair is not None
    verification = catalog.item(str(scheduled.verification_pair.verification_item_id))
    cases.record_verification.execute(
        RecordVerificationResponseCommand(
            episode_id=episode_id,
            at=AT + timedelta(seconds=7),
            selected_option_id=verification.correct_option_id or "",
        )
    )
    finished = cases.calculate_outcome.execute(
        CalculateIndependenceOutcomeCommand(episode_id=episode_id, at=AT + timedelta(seconds=8))
    )
    assert finished.outcome is not None
    assert finished.outcome.misconception_resolution is not None
    assert finished.feature_snapshot is not None
    assert finished.feature_snapshot.purpose == "model_decision"
    assert "misconception_resolution" not in finished.feature_snapshot.values
    assert finished.policy_context_snapshot is not None
    assert finished.policy_context_snapshot.purpose == "policy_context"
    assert "misconception_resolution" not in finished.policy_context_snapshot.values
