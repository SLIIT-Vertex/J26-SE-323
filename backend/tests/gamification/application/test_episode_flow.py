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
from app.gamification.application.records import GamificationAttempt
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


def _flow(catalog: PilotContentCatalog | None = None):
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
            catalogue_version=CatalogueVersion(catalog.support_catalogue_version())
        ),
        calculator=RawIndependenceGainCalculator(),
        allow_draft=True,
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
