from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Thread
from uuid import UUID, uuid4

import pytest

from app.gamification.domain.types import AssistanceState, ExperimentMode, MeasurementRole
from app.gamification.modeling.independence_gain.measurement import (
    AttemptSubmission,
    IndependenceGainError,
    ItemRubric,
    MeasurementInput,
    NormalizedEvent,
    PolicyUpdateStatus,
    Presentation,
    ProbeReservation,
    ProbeReservationLedger,
    ProbeUnavailableError,
    ScaffoldExposure,
    ScoredAttempt,
    ServerAuthoritativeScorer,
    SupportWithdrawal,
    assert_unsupported_after_may_begin,
    calculate_measurement,
    development_curriculum_scorer,
    replay_measurement,
    support_dependency_rate,
)

AT = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
LEARNER = UUID("00000000-0000-4000-8000-000000000101")
EPISODE = UUID("00000000-0000-4000-8000-000000000201")
DECISION = UUID("00000000-0000-4000-8000-000000000301")
FAMILY = "G5-MAT-HALF-F01"
EQUIVALENCE = "half-family-equivalence-v1"


def presentation(
    role: MeasurementRole,
    item: str,
    sequence: int,
    *,
    reservation_id: UUID | None = None,
    assistance: AssistanceState = AssistanceState.NONE,
) -> Presentation:
    return Presentation(
        presentation_id=uuid4(),
        episode_id=EPISODE,
        learner_id=LEARNER,
        item_revision_id=item,
        skill_id="G5-MAT-C03-L01-O01",
        parallel_family_id=FAMILY,
        equivalence_version=EQUIVALENCE,
        role=role,
        assistance_state=assistance,
        sequence=sequence,
        created_at=AT + timedelta(minutes=sequence),
        reservation_id=reservation_id,
    )


def scored(
    row: Presentation,
    earned: str,
    maximum: str = "1",
    *,
    assistance: AssistanceState | None = None,
    scoring_version: str = "half-single-choice-scoring-v1",
) -> ScoredAttempt:
    return ScoredAttempt(
        attempt_id=uuid4(),
        presentation_id=row.presentation_id,
        item_revision_id=row.item_revision_id,
        role=row.role,
        assistance_state=assistance or row.assistance_state,
        earned_score=Decimal(earned),
        maximum_score=Decimal(maximum),
        rubric_version="rubric-v1",
        scoring_version=scoring_version,
        server_authoritative=True,
        idempotency_key=str(uuid4()),
        scored_at=row.created_at + timedelta(seconds=30),
    )


def valid_input(
    *,
    before_scores: tuple[tuple[str, str], ...] = (("0", "1"),),
    after_scores: tuple[tuple[str, str], ...] = (("1", "1"),),
    mode: ExperimentMode = ExperimentMode.PROPOSED,
) -> MeasurementInput:
    before_presentations = tuple(
        presentation(MeasurementRole.UNSUPPORTED_BEFORE, f"before-{i}@v1", i)
        for i in range(1, len(before_scores) + 1)
    )
    reservation_ids = tuple(uuid4() for _ in after_scores)
    after_presentations = tuple(
        presentation(
            MeasurementRole.UNSUPPORTED_AFTER,
            f"after-{i}@v1",
            10 + i,
            reservation_id=reservation_ids[i - 1],
        )
        for i in range(1, len(after_scores) + 1)
    )
    attempts = tuple(
        scored(row, earned, maximum)
        for row, (earned, maximum) in zip(before_presentations, before_scores, strict=True)
    ) + tuple(
        scored(row, earned, maximum)
        for row, (earned, maximum) in zip(after_presentations, after_scores, strict=True)
    )
    reservations = tuple(
        ProbeReservation(
            reservation_id=reservation_id,
            episode_id=EPISODE,
            learner_id=LEARNER,
            item_revision_id=row.item_revision_id,
            parallel_family_id=FAMILY,
            role=MeasurementRole.UNSUPPORTED_AFTER,
            reserved_at=AT,
            expires_at=AT + timedelta(days=1),
            used_at=row.created_at,
        )
        for reservation_id, row in zip(reservation_ids, after_presentations, strict=True)
    )
    exposure = ScaffoldExposure(
        exposure_id=uuid4(),
        episode_id=EPISODE,
        scaffold_revision_id="SCAFFOLD-VISUAL@v1",
        rendered_step_ids=("step-1",),
        answer_revealing=False,
        started_at=AT + timedelta(minutes=3),
        completed_at=AT + timedelta(minutes=4),
    )
    withdrawal = SupportWithdrawal(
        confirmation_id=uuid4(),
        episode_id=EPISODE,
        exposure_id=exposure.exposure_id,
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        client_confirmed_at=AT + timedelta(minutes=5),
        server_verified_at=AT + timedelta(minutes=5, seconds=1),
    )
    events = (
        NormalizedEvent(uuid4(), 1, "unsupported_before_scored", before_presentations[0].presentation_id),
        NormalizedEvent(uuid4(), 2, "support_exposed", None),
        NormalizedEvent(uuid4(), 3, "support_withdrawn", None),
        NormalizedEvent(uuid4(), 4, "unsupported_after_scored", after_presentations[0].presentation_id),
    )
    return MeasurementInput(
        measurement_id=uuid4(),
        episode_id=EPISODE,
        decision_id=DECISION,
        experiment_mode=mode,
        presentations=(*before_presentations, *after_presentations),
        attempts=attempts,
        reservations=reservations,
        scaffold_exposures=(exposure,),
        withdrawal=withdrawal,
        events=events,
        expected_event_sequence_end=4,
    )


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ((("0", "1"),), (("1", "1"),), Decimal(1)),
        ((("1", "2"),), (("1", "2"),), Decimal(0)),
        ((("1", "1"),), (("0", "1"),), Decimal(-1)),
        (
            (("0.5", "1"), ("1", "2")),
            (("1", "1"), ("1.5", "2")),
            Decimal("0.3333333333333333333333333333"),
        ),
        ((("1", "2"),), (("1", "1"), ("1", "2")), Decimal("0.1666666666666666666666666667")),
    ],
)
def test_exact_raw_ig_fixtures(before, after, expected) -> None:
    result = calculate_measurement(valid_input(before_scores=before, after_scores=after), calculated_at=AT)
    assert result.valid
    assert result.raw_independence_gain == expected
    assert result.percentage_point_value == expected * 100
    assert result.policy_update_status is PolicyUpdateStatus.AUTHORIZED_DELAYED


def test_server_scoring_rejects_client_forgery_and_changed_retry() -> None:
    row = presentation(MeasurementRole.UNSUPPORTED_BEFORE, "before@v1", 1)
    scorer = ServerAuthoritativeScorer(
        {
            "before@v1": ItemRubric(
                "before@v1", "rubric-v1", "scoring-v1", Decimal(1), "B"
            )
        }
    )
    request = AttemptSubmission(
        uuid4(), row.presentation_id, "A", AssistanceState.NONE, AT, "retry-1", Decimal(1)
    )
    first = scorer.score(row, request)
    assert first.earned_score == 0
    assert first.server_authoritative
    assert scorer.score(row, request) is first
    with pytest.raises(IndependenceGainError, match="IDEMPOTENCY_CONFLICT"):
        scorer.score(row, replace(request, response="B"))


def test_nonauthoritative_score_is_excluded_from_policy_feedback() -> None:
    data = valid_input()
    forged = replace(data.attempts[-1], server_authoritative=False)
    result = calculate_measurement(
        replace(data, attempts=(*data.attempts[:-1], forged)), calculated_at=AT
    )
    assert "NONAUTHORITATIVE_SCORE" in result.exclusion_reasons
    assert result.policy_update_status is PolicyUpdateStatus.NOT_AUTHORIZED_INVALID


def test_curriculum_draft_scoring_requires_explicit_development_composition() -> None:
    with pytest.raises(PermissionError, match="allow_draft"):
        development_curriculum_scorer()
    scorer = development_curriculum_scorer(allow_draft=True)
    row = presentation(
        MeasurementRole.UNSUPPORTED_BEFORE, "G5-MAT-HALF-I01@v1", 1
    )
    attempt = AttemptSubmission(
        uuid4(), row.presentation_id, "B", AssistanceState.NONE, AT, "curriculum-dev"
    )
    assert scorer.score(row, attempt).earned_score == 1


@pytest.mark.parametrize(
    ("assistance", "reason"),
    [
        (AssistanceState.SCAFFOLD_ACTIVE, "ACTIVE_ASSISTANCE"),
        (AssistanceState.ADULT_REPORTED, "ADULT_ASSISTANCE"),
        (AssistanceState.TUTOR_ACTIVE, "TUTOR_ASSISTANCE"),
        (AssistanceState.UNKNOWN, "UNKNOWN_ASSISTANCE"),
    ],
)
def test_assistance_invalidates_measurement(assistance, reason) -> None:
    data = valid_input()
    attempts = (*data.attempts[:-1], replace(data.attempts[-1], assistance_state=assistance))
    result = calculate_measurement(replace(data, attempts=attempts), calculated_at=AT)
    assert not result.valid
    assert reason in result.exclusion_reasons
    assert result.policy_update_status is PolicyUpdateStatus.NOT_AUTHORIZED_INVALID


def test_roles_are_explicit_and_unsupported_after_requires_withdrawal() -> None:
    with pytest.raises(IndependenceGainError, match="assistance_state=none"):
        presentation(
            MeasurementRole.UNSUPPORTED_AFTER,
            "after@v1",
            5,
            assistance=AssistanceState.SCAFFOLD_ACTIVE,
        )
    data = valid_input()
    after = next(row for row in data.presentations if row.role is MeasurementRole.UNSUPPORTED_AFTER)
    assert_unsupported_after_may_begin(after, data.withdrawal)
    with pytest.raises(IndependenceGainError, match="withdrawal"):
        assert_unsupported_after_may_begin(after, replace(data.withdrawal, all_support_removed=False))


def test_probe_reservation_concurrency_expiry_reuse_and_cross_component_contamination() -> None:
    ledger = ProbeReservationLedger()
    barrier = Barrier(2)
    successes: list[ProbeReservation] = []
    failures: list[Exception] = []

    def reserve_one() -> None:
        candidate = ProbeReservation(
            uuid4(), EPISODE, LEARNER, "after@v1", FAMILY,
            MeasurementRole.UNSUPPORTED_AFTER, AT, AT + timedelta(hours=1)
        )
        barrier.wait()
        try:
            successes.append(ledger.reserve(candidate))
        except Exception as error:  # noqa: BLE001 - thread result is asserted below
            failures.append(error)

    threads = [Thread(target=reserve_one), Thread(target=reserve_one)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(successes) == 1
    assert len(failures) == 1 and isinstance(failures[0], ProbeUnavailableError)

    ledger.expose(
        learner_id=LEARNER,
        item_revision_id="after@v1",
        component="paper_generator",
        at=AT + timedelta(minutes=2),
    )
    assert ledger.get(successes[0].reservation_id).contamination_sources == ("paper_generator",)
    with pytest.raises(ProbeUnavailableError, match="previously exposed"):
        ledger.reserve(replace(successes[0], reservation_id=uuid4(), reserved_at=AT + timedelta(hours=2), expires_at=AT + timedelta(hours=3)))

    expired = ProbeReservation(
        uuid4(), EPISODE, LEARNER, "fresh@v1", FAMILY,
        MeasurementRole.UNSUPPORTED_AFTER, AT, AT + timedelta(minutes=1)
    )
    ledger.reserve(expired)
    ledger.reserve(replace(expired, reservation_id=uuid4(), reserved_at=AT + timedelta(minutes=2), expires_at=AT + timedelta(minutes=3)))


@pytest.mark.parametrize("component", ["game", "paper_generator", "tutor", "worked_example"])
def test_every_external_component_contaminates_a_reserved_probe(component: str) -> None:
    ledger = ProbeReservationLedger()
    reservation = ProbeReservation(
        uuid4(), EPISODE, LEARNER, f"{component}@v1", FAMILY,
        MeasurementRole.UNSUPPORTED_AFTER, AT, AT + timedelta(hours=1)
    )
    ledger.reserve(reservation)
    ledger.expose(
        learner_id=LEARNER,
        item_revision_id=reservation.item_revision_id,
        component=component,
        at=AT + timedelta(minutes=1),
    )
    assert ledger.get(reservation.reservation_id).contamination_sources == (component,)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"withdrawal": None}, "SUPPORT_NOT_WITHDRAWN"),
        ({"scaffold_leak": True}, "SCAFFOLD_ANSWER_LEAKAGE"),
        ({"external_contamination": True}, "EXTERNAL_PROBE_CONTAMINATION"),
        ({"prior_exposure": True}, "PRIOR_PROBE_EXPOSURE"),
        ({"missing_sequence": True}, "MISSING_OR_CONFLICTING_EVENT_SEQUENCE"),
        ({"invalid_order": True}, "INVALID_EPISODE_ORDER"),
        ({"interrupted": True}, "EPISODE_INTERRUPTED"),
        ({"episode_complete": False}, "INCOMPLETE_EVIDENCE"),
        ({"duplicate_conflict": True}, "DUPLICATE_SUBMISSION_CONFLICT"),
        ({"family_compatible": False}, "INCOMPATIBLE_PARALLEL_FAMILY"),
        ({"content_versions_compatible": False}, "INCOMPATIBLE_CONTENT_VERSION"),
        ({"scoring_versions_compatible": False}, "INCOMPATIBLE_SCORING_VERSION"),
        ({"later_invalidated_content": True}, "DEFECTIVE_OR_INVALIDATED_CONTENT"),
    ],
)
def test_contamination_and_exclusion_reasons(change, reason) -> None:
    data = valid_input()
    if change.pop("scaffold_leak", False):
        change["scaffold_exposures"] = (replace(data.scaffold_exposures[0], answer_revealing=True),)
    if change.pop("external_contamination", False):
        change["reservations"] = (replace(data.reservations[0], contamination_sources=("tutor",)),)
    if change.pop("prior_exposure", False):
        change["reservations"] = (replace(data.reservations[0], used_at=AT),)
    if change.pop("missing_sequence", False):
        change["events"] = data.events[:-1]
    if change.pop("invalid_order", False):
        change["events"] = (
            data.events[0],
            replace(data.events[2], sequence=2),
            replace(data.events[1], sequence=3),
            data.events[3],
        )
    result = calculate_measurement(replace(data, **change), calculated_at=AT)
    assert not result.valid
    assert reason in result.exclusion_reasons
    assert result.raw_independence_gain is None


def test_reused_revision_and_zero_maximum_are_invalid() -> None:
    data = valid_input()
    duplicate = replace(data.presentations[-1], item_revision_id=data.presentations[0].item_revision_id)
    duplicate_attempt = replace(data.attempts[-1], item_revision_id=duplicate.item_revision_id)
    result = calculate_measurement(
        replace(data, presentations=(data.presentations[0], duplicate), attempts=(data.attempts[0], duplicate_attempt)),
        calculated_at=AT,
    )
    assert "REUSED_ITEM_OR_REVISION" in result.exclusion_reasons
    zero = replace(data.attempts[-1], maximum_score=Decimal(0))
    result = calculate_measurement(replace(data, attempts=(*data.attempts[:-1], zero)), calculated_at=AT)
    assert "INVALID_MAXIMUM_SCORE" in result.exclusion_reasons


def test_valid_baseline_never_authorizes_policy_learning() -> None:
    result = calculate_measurement(valid_input(mode=ExperimentMode.BASELINE), calculated_at=AT)
    assert result.valid
    assert result.policy_update_status is PolicyUpdateStatus.NOT_AUTHORIZED_BASELINE


def test_secondary_measurement_has_distinct_name_and_does_not_change_raw_ig() -> None:
    raw = calculate_measurement(valid_input(), calculated_at=AT)
    secondary = support_dependency_rate(helped_attempts=1, eligible_attempts=4)
    assert secondary.name == "support_dependency_rate"
    assert secondary.value == Decimal("0.25")
    assert raw.raw_independence_gain == 1


def test_replay_is_byte_for_byte_equivalent_except_object_identity() -> None:
    data = valid_input(before_scores=(("1", "2"),), after_scores=(("1", "1"),))
    original = calculate_measurement(data, calculated_at=AT)
    replayed = replay_measurement(data, calculated_at=AT)
    assert replayed == original
    assert replayed.formula_version == "raw-independence-gain-v1"
    assert replayed.scoring_versions == original.scoring_versions
    assert replayed.equivalence_version == EQUIVALENCE
