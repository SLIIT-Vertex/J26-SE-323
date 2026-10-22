"""Prove from the stored episodes that each model did what its documented logic says.

Read-only. Model 1 and Model 2 are checked by recomputing their output with the same code from
the inputs stored with the decision; Model 3 by recomputing the gain from the stored scores. Every
check reports the episodes it looked at, so a failure points at the evidence.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Uuid, bindparam, select, text
from sqlalchemy.orm import Session

from app.gamification.application.engine.area_flow import _model1_label, _model1_uncertain
from app.gamification.application.learning_flow_orchestration import LearningFlowOrchestrator
from app.gamification.content.support_types import SUPPORT_TYPES
from app.gamification.infrastructure.db.models import (
    LearningFlowEpisodeRunModel,
    LearningFlowSupportRoundModel,
)
from app.gamification.modeling.misconception_inference.learner_prior import (
    apply_learner_prior,
    prior_errors,
)
from app.gamification.modeling.support_selection.support_order import (
    LEAD_BY_REASON,
    SUBJECT_ORDERS,
    choose_support_order,
    credited_support,
    rank_support_history,
    subject_of,
)

_TOLERANCE = 1e-6


@dataclass
class Check:
    model: str
    name: str
    passed: bool
    checked: int = 0
    detail: str = ""
    failures: list[str] = field(default_factory=list)

    def as_record(self) -> dict[str, object]:
        return {
            "model": self.model,
            "name": self.name,
            "passed": self.passed,
            "checked": self.checked,
            "detail": self.detail,
            "failures": self.failures[:20],
        }


@dataclass
class Episode:
    state: dict[str, object]
    status: str
    updated_at: datetime
    rounds_in_table: int

    @property
    def seeded(self) -> bool:
        return self.state.get("seed_source") is not None


def load_episodes(session: Session, learner_id: UUID) -> list[Episode]:
    rows = session.scalars(
        select(LearningFlowEpisodeRunModel)
        .where(LearningFlowEpisodeRunModel.learner_id == learner_id)
        .order_by(LearningFlowEpisodeRunModel.updated_at, LearningFlowEpisodeRunModel.episode_id)
    ).all()
    counts = Counter(
        session.scalars(
            select(LearningFlowSupportRoundModel.episode_id).where(
                LearningFlowSupportRoundModel.episode_id.in_([row.episode_id for row in rows])
            )
        ).all()
    )
    return [
        Episode(
            state=dict(row.state_json),
            status=row.status,
            updated_at=_utc(row.updated_at),
            rounds_in_table=counts.get(row.episode_id, 0),
        )
        for row in rows
    ]


def verify(
    session: Session,
    orchestrator: LearningFlowOrchestrator,
    learner_id: UUID,
    *,
    expected_skills: Iterable[str] = (),
    seed_version: str | None = None,
) -> list[Check]:
    episodes = load_episodes(session, learner_id)
    seeded = [
        episode
        for episode in episodes
        if episode.seeded and (seed_version is None or episode.state["seed_source"] == seed_version)
    ]
    flows = orchestrator._area_flows
    checks = [
        *_model1_checks(seeded, flows, episodes),
        *_model2_checks(seeded, episodes),
        *_loop_checks(seeded),
        *_model3_checks(seeded, episodes),
        *_learner_state_checks(session, learner_id, seeded, flows),
        *_coverage_checks(seeded, expected_skills),
    ]
    return checks


# Model 1 ----------------------------------------------------------------------------------------


def _model1_checks(
    seeded: Sequence[Episode], flows: Mapping[str, object], everything: Sequence[Episode]
) -> list[Check]:
    beliefs = [episode for episode in seeded if isinstance(episode.state.get("model1"), Mapping)]
    distribution = Check("model1", "Probabilities are a full distribution (≥ 0, sum to 1)", True)
    recompute = Check(
        "model1",
        "Recomputing the area's Model 1 from the stored inputs gives the stored estimate",
        True,
    )
    label = Check("model1", "Predicted label is the most probable misconception", True)
    fallback = Check(
        "model1",
        "Fallback (flat estimate) appears only when timing and interaction evidence are missing",
        True,
    )
    provenance = Check("model1", "Model, catalogue and mapping versions are recorded", True)
    families: dict[str, set[str]] = defaultdict(set)
    for episode in beliefs:
        state = episode.state
        model1 = state["model1"]
        assert isinstance(model1, Mapping)
        episode_id = str(state["episode_id"])
        probabilities = {key: float(value) for key, value in dict(model1["probabilities"]).items()}
        for check in (distribution, recompute, label, fallback, provenance):
            check.checked += 1
        if (
            any(value < 0 or not math.isfinite(value) for value in probabilities.values())
            or abs(sum(probabilities.values()) - 1) > _TOLERANCE
        ):
            _fail(distribution, episode_id, f"sum={sum(probabilities.values())}")
        flow = flows[str(state["area_id"])]
        summary = model1.get("structured_response") or None
        expected = flow._infer_belief(  # type: ignore[attr-defined]
            str(model1["structured_error_code"]),
            response_time_ms=model1.get("response_time_ms"),
            interaction_summary=summary,
        )
        if model1.get("prior_version"):
            expected = apply_learner_prior(
                expected, prior_errors(_prior_history(episode, everything))
            )
        stored_fields = {
            "probabilities": probabilities,
            "predicted_label": model1.get("predicted_label"),
            "fallback_used": bool(model1.get("fallback_used")),
        }
        expected_fields = {
            "probabilities": {
                key: float(value) for key, value in dict(expected["probabilities"]).items()
            },
            "predicted_label": expected.get("predicted_label"),
            "fallback_used": bool(expected.get("fallback_used")),
        }
        if not _same_distribution(
            stored_fields["probabilities"], expected_fields["probabilities"]
        ) or any(
            stored_fields[key] != expected_fields[key]
            for key in ("predicted_label", "fallback_used")
        ):
            _fail(recompute, episode_id, f"stored {stored_fields} != recomputed {expected_fields}")
        top = max(probabilities.values())
        predicted = model1.get("predicted_label")
        if predicted is not None and abs(probabilities.get(str(predicted), -1) - top) > _TOLERANCE:
            _fail(label, episode_id, f"{predicted} is not the most probable")
        sparse = model1.get("response_time_ms") is None and not summary
        if bool(model1.get("fallback_used")) and not sparse:
            _fail(fallback, episode_id, "fallback used although evidence was present")
        for key in ("model_version", "catalogue_version", "mapping_version"):
            if not model1.get(key):
                _fail(provenance, episode_id, f"missing {key}")
        model2 = state.get("model2")
        if isinstance(model2, Mapping) and model2.get("reason_family"):
            families[subject_of(str(state["area_id"]))].add(str(model2["reason_family"]))
    coverage = Check(
        "model1",
        "Reason families reached by the seeded wrong answers",
        True,
        checked=len(beliefs),
        detail="; ".join(
            f"{subject}: {', '.join(sorted(found))}" for subject, found in sorted(families.items())
        ),
    )
    return [distribution, recompute, label, fallback, provenance, coverage]


def _same_distribution(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return set(left) == set(right) and all(
        abs(left[key] - right[key]) <= _TOLERANCE for key in left
    )


# Model 2 ----------------------------------------------------------------------------------------


def _prior_history(
    episode: Episode, everything: Sequence[Episode]
) -> tuple[dict[str, object], ...]:
    """The completed episodes of this learner and skill that existed when the decision was made."""

    model2 = episode.state["model2"]
    assert isinstance(model2, Mapping)
    decided_at = _parse(str(model2["created_at"]))
    return tuple(
        other.state
        for other in everything
        if other.status == "completed"
        and other.state.get("skill_id") == episode.state.get("skill_id")
        and other.state.get("episode_id") != episode.state.get("episode_id")
        and other.updated_at < decided_at
    )


def _model2_checks(seeded: Sequence[Episode], everything: Sequence[Episode]) -> list[Check]:
    decisions = [
        episode
        for episode in seeded
        if isinstance(episode.state.get("model2"), Mapping)
        and "support_order" in episode.state["model2"]  # type: ignore[operator]
    ]
    recompute = Check(
        "model2",
        "Recomputing the help order from the stored inputs and the history at that moment gives "
        "the stored order, mode and reason family",
        True,
    )
    baseline = Check("model2", "Baseline uses the subject's fixed order and no history", True)
    lead = Check("model2", "Reason lead puts the type matched to Model 1's reason first", True)
    learned = Check(
        "model2",
        "Learned preference puts first the type with the best valid independent record",
        True,
    )
    no_supported_reward = Check(
        "model2", "Success only while helped never creates a preference", True
    )
    first_types: Counter[str] = Counter()
    used_types: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    preferred_by_skill: dict[str, str] = {}
    for episode in decisions:
        state = episode.state
        model2 = state["model2"]
        assert isinstance(model2, Mapping)
        episode_id = str(state["episode_id"])
        subject = subject_of(str(state["area_id"]))
        model1 = state.get("model1") if isinstance(state.get("model1"), Mapping) else {}
        history = _prior_history(episode, everything)
        recompute.checked += 1
        try:
            expected = choose_support_order(
                subject=subject,
                condition=str(state["condition"]),
                model1_label=_model1_label(model1),  # type: ignore[arg-type]
                model1_uncertain=_model1_uncertain(model1),  # type: ignore[arg-type]
                eligible=list(model2["eligible_actions"]),
                renderable=list(model2.get("renderable_actions") or model2["eligible_actions"]),
                history=history,
                policy_version=str(model2.get("order_policy_version", "support-order-v2")),
                learning_state_input=model2.get("learning_state_input"),
            ).as_record()
        except ValueError as error:
            _fail(recompute, episode_id, f"recompute raised {error}")
            continue
        for key in ("support_order", "support_selection_mode", "reason_family"):
            if expected[key] != model2.get(key):
                _fail(recompute, episode_id, f"{key}: stored {model2.get(key)} != {expected[key]}")
        mode = str(model2["support_selection_mode"])
        modes[mode] += 1
        order = list(model2["support_order"])
        first_types[order[0]] += 1
        loop = state.get("support_loop")
        if isinstance(loop, Mapping):
            used_types.update(loop.get("types_used") or [])
        if mode == "baseline_fixed_order":
            baseline.checked += 1
            allowed = [
                support
                for support in SUBJECT_ORDERS[subject]
                if support in model2["eligible_actions"]
                and support in (model2.get("renderable_actions") or model2["eligible_actions"])
            ]
            preference = dict(model2.get("learner_activity_support_preference") or {})
            if order != allowed or preference.get("by_support"):
                _fail(baseline, episode_id, f"order {order} != {allowed} or history used")
        elif mode == "model1_reason_lead":
            lead.checked += 1
            if order[0] != LEAD_BY_REASON[str(model2["reason_family"])]:
                _fail(lead, episode_id, f"{order[0]} for {model2['reason_family']}")
        elif mode == "learned_post_withdrawal_preference":
            learned.checked += 1
            ranking = rank_support_history(
                history,
                order=SUBJECT_ORDERS[subject],
                legacy=model2.get("order_policy_version") == "support-order-v2",
            )
            if ranking.preferred != order[0]:
                _fail(
                    learned, episode_id, f"first {order[0]} but ranking prefers {ranking.preferred}"
                )
            preferred_by_skill[str(state["skill_id"])] = order[0]
        # No preference may rest on an episode whose after-question was missed.
        preference = dict(model2.get("learner_activity_support_preference") or {})
        for support, row in dict(preference.get("by_support") or {}).items():
            no_supported_reward.checked += 1
            successes = sum(
                1
                for prior in history
                if (
                    support in _types(prior)
                    if model2.get("order_policy_version") == "support-order-v2"
                    else credited_support(prior)[0] == support
                )
                and _independent(prior)
            )
            if int(row["independent_successes"]) != successes:
                _fail(
                    no_supported_reward,
                    episode_id,
                    f"{support}: {row} vs {successes} valid successes",
                )
    reachable = Check(
        "model2",
        "Every help type is delivered in some round",
        set(used_types) == set(SUPPORT_TYPES),
        checked=len(decisions),
        # The worked example is last in both subject orders and leads no reason family, so it is
        # first only when it alone holds the best valid record: by design that is rare.
        detail=f"chosen first: {dict(first_types)}; delivered: {dict(used_types)}",
    )
    if not reachable.passed:
        reachable.failures.append(
            f"never delivered: {sorted(set(SUPPORT_TYPES) - set(used_types))}"
        )
    isolation = Check(
        "model2",
        "Preferences are per skill: different skills learned different types",
        len(set(preferred_by_skill.values())) > 1,
        checked=len(preferred_by_skill),
        detail=f"preferred types across skills: {dict(Counter(preferred_by_skill.values()))}",
    )
    paths = Check(
        "model2",
        "Decision paths taken",
        {"baseline_fixed_order", "model1_reason_lead", "learned_post_withdrawal_preference"}
        <= set(modes),
        checked=len(decisions),
        detail=str(dict(modes)),
    )
    return [recompute, baseline, lead, learned, no_supported_reward, reachable, isolation, paths]


def _types(state: Mapping[str, object]) -> list[str]:
    loop = state.get("support_loop")
    if isinstance(loop, Mapping):
        return list(loop.get("types_used") or [])
    model2 = state.get("model2")
    return [str(model2.get("selected_action"))] if isinstance(model2, Mapping) else []


def _independent(state: Mapping[str, object]) -> bool:
    measurement = state.get("measurement")
    if state.get("condition") != "proposed" or state.get("validity") != "valid":
        return False
    if not isinstance(measurement, Mapping):
        return False
    maximum = Decimal(str(measurement.get("after_maximum", 0)))
    return maximum > 0 and Decimal(str(measurement.get("after_earned", 0))) == maximum


# Help loop --------------------------------------------------------------------------------------


def _loop_checks(seeded: Sequence[Episode]) -> list[Check]:
    order_check = Check("loop", "Rounds follow Model 2's order, each type at most once", True)
    switch = Check("loop", "A failed round opens the next type (rule S)", True)
    withdrawal = Check(
        "loop",
        "Help stops only after a supported success or when the order runs out (rule W)",
        True,
    )
    stored = Check("loop", "One support-round row per delivered type", True)
    gate = Check(
        "loop", "A simpler version returns to the failed item only after success on it", True
    )
    for episode in seeded:
        loop = episode.state.get("support_loop")
        if not isinstance(loop, Mapping):
            continue
        episode_id = str(episode.state["episode_id"])
        rounds = list(loop["rounds"])
        types = [str(row["scaffold_type"]) for row in rounds]
        for check in (order_check, switch, withdrawal, stored):
            check.checked += 1
        expected = [
            support
            for support in loop["order"]
            if support not in loop.get("skipped_unrenderable", [])
        ][: len(types)]
        if types != expected or len(set(types)) != len(types):
            _fail(order_check, episode_id, f"{types} vs {expected}")
        for index, row in enumerate(rounds[:-1]):
            if row.get("outcome") not in {"failed", "viewed"}:
                _fail(
                    switch, episode_id, f"round {index + 1} {row.get('outcome')} but another opened"
                )
        stop = loop.get("stop_reason")
        last = rounds[-1] if rounds else {}
        if stop == "supported_success" and last.get("outcome") != "succeeded":
            _fail(withdrawal, episode_id, "success stop without a successful round")
        if stop == "order_exhausted" and (
            last.get("outcome") != "failed" or len(types) != len(expected)
        ):
            _fail(withdrawal, episode_id, "exhausted stop before the order ran out")
        if stop is None and episode.status == "completed":
            _fail(withdrawal, episode_id, "completed without a stop reason")
        if episode.rounds_in_table != len(rounds):
            _fail(stored, episode_id, f"{episode.rounds_in_table} rows for {len(rounds)} rounds")
        for row in rounds:
            if row["scaffold_type"] != "simpler_same_game":
                continue
            gate.checked += 1
            attempts = list(row.get("attempts") or [])
            practice_failed = bool(attempts) and not attempts[0].get("correct")
            if practice_failed and row.get("outcome") != "failed":
                _fail(gate, episode_id, "returned to the failed item after a missed simpler item")
    return [order_check, switch, withdrawal, stored, gate]


# Model 3 ----------------------------------------------------------------------------------------


def _model3_checks(seeded: Sequence[Episode], everything: Sequence[Episode]) -> list[Check]:
    formula = Check(
        "model3",
        "Gain = after earned/maximum − before earned/maximum, recomputed from the stored scores",
        True,
    )
    values = Check("model3", "Gain is 0 or +1 (help only follows a wrong first answer)", True)
    validity = Check(
        "model3", "Valid episodes passed every check: help withdrawn, fresh after item", True
    )
    authority = Check(
        "model3", "Only valid proposed episodes update the policy, exactly once", True
    )
    never_supported = Check("model3", "Supported correctness is never the reward", True)
    closed = Check(
        "model3",
        "Every valid +1 is counted for its help types in the next decision on that skill",
        True,
    )
    gains: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    by_skill: dict[str, list[Episode]] = defaultdict(list)
    for episode in everything:
        by_skill[str(episode.state.get("skill_id"))].append(episode)
    for episode in seeded:
        state = episode.state
        episode_id = str(state["episode_id"])
        statuses[str(state.get("policy_update_status"))] += 1
        updates = list(state.get("policy_updates") or [])
        measurement = state.get("measurement")
        authority.checked += 1
        status = state.get("policy_update_status")
        if episode.status == "invalidated":
            if updates or status != "not_authorized_invalid":
                _fail(
                    authority, episode_id, f"invalid episode has {status} / {len(updates)} updates"
                )
            continue
        if state.get("support_loop") is None:
            if updates or status != "not_authorized_no_support":
                _fail(authority, episode_id, f"no-help episode has {status}")
            continue
        if not isinstance(measurement, Mapping):
            _fail(authority, episode_id, "help episode without a measurement")
            continue
        attempts = {str(row["role"]): row for row in state.get("attempts") or []}
        before, after = attempts.get("unsupported_before"), attempts.get("unsupported_after")
        formula.checked += 1
        values.checked += 1
        never_supported.checked += 1
        if before is None or after is None:
            _fail(formula, episode_id, "before or after score missing")
            continue
        expected = Decimal(str(after["earned_score"])) / Decimal(str(after["maximum_score"])) - (
            Decimal(str(before["earned_score"])) / Decimal(str(before["maximum_score"]))
        )
        stored_gain = Decimal(str(measurement["raw_independence_gain"]))
        if stored_gain != expected:
            _fail(formula, episode_id, f"stored {stored_gain} != {expected}")
        gains[str(stored_gain)] += 1
        if stored_gain not in (Decimal(0), Decimal(1)):
            _fail(values, episode_id, f"gain {stored_gain}")
        if measurement.get("supported_correctness_used_as_reward") is not False:
            _fail(never_supported, episode_id, "supported correctness used")
        if state.get("validity") == "valid":
            validity.checked += 1
            withdrawal = state.get("withdrawal") or {}
            if measurement.get("exclusion_reasons") or not (
                isinstance(withdrawal, Mapping)
                and withdrawal.get("all_support_removed") is True
                and withdrawal.get("answer_revealing_state_cleared") is True
            ):
                _fail(validity, episode_id, "valid without a confirmed withdrawal")
        if state["condition"] == "baseline":
            if updates or status != "not_authorized_baseline":
                _fail(authority, episode_id, f"baseline has {status} / {len(updates)} updates")
        elif state.get("validity") == "valid" and (
            len(updates) != 1
            or Decimal(str(updates[0]["reward"])) != stored_gain
            or updates[0].get("reward_source") != "valid_raw_independence_gain"
        ):
            _fail(authority, episode_id, f"update {updates} for gain {stored_gain}")
        if _independent(state):
            later = [
                other
                for other in by_skill[str(state["skill_id"])]
                if isinstance(other.state.get("model2"), Mapping)
                and other.state["condition"] == "proposed"
                and _parse(str(other.state["model2"]["created_at"]))  # type: ignore[index]
                > episode.updated_at
            ]
            if later:
                closed.checked += 1
                nxt = min(
                    later,
                    key=lambda other: str(other.state["model2"]["created_at"]),  # type: ignore[index]
                )
                counted = (
                    dict(
                        dict(nxt.state["model2"]).get("learner_activity_support_preference") or {}
                    ).get("by_support")
                    or {}
                )
                for support in (
                    _types(state)
                    if dict(nxt.state["model2"]).get("order_policy_version") == "support-order-v2"
                    else tuple(filter(None, [credited_support(state)[0]]))
                ):
                    if int(dict(counted.get(support) or {}).get("independent_successes", 0)) < 1:
                        _fail(closed, episode_id, f"{support} not counted in the next decision")
    summary = Check(
        "model3",
        "Outcomes produced",
        True,
        checked=len(seeded),
        detail=f"gains {dict(gains)}; policy status {dict(statuses)}",
    )
    return [formula, values, validity, authority, never_supported, closed, summary]


# Learner State ----------------------------------------------------------------------------------


def _learner_state_checks(
    session: Session, learner_id: UUID, seeded: Sequence[Episode], flows: Mapping[str, object]
) -> list[Check]:
    rows = (
        session.execute(
            text(
                "select skill_id, confusion_state, disengagement_state, recommended_action, "
                "support_need, observed_at from learner_skill_states where learner_id = :learner"
            ).bindparams(bindparam("learner", type_=Uuid)),
            {"learner": learner_id},
        )
        .mappings()
        .all()
    )
    expected = {
        str(getattr(flows[str(episode.state["area_id"])], "universal_skill_id", ""))
        for episode in seeded
        if getattr(flows[str(episode.state["area_id"])], "records_learner_state", False)
    }
    found = {str(row["skill_id"]) for row in rows}
    present = Check(
        "learner_state",
        "Every broad skill the seed answered has a learner-state row",
        expected <= found,
        checked=len(expected),
        detail=f"{len(found)} rows: {', '.join(sorted(found))}",
    )
    if not present.passed:
        present.failures.append(f"missing: {sorted(expected - found)}")
    populated = Check("learner_state", "Rows are complete and support need is within 0–1", True)
    for row in rows:
        populated.checked += 1
        if not all(
            row[key] for key in ("confusion_state", "disengagement_state", "recommended_action")
        ):
            _fail(populated, str(row["skill_id"]), "empty state field")
        need = row["support_need"]
        if need is not None and not 0 <= float(need) <= 1:
            _fail(populated, str(row["skill_id"]), f"support need {need}")
    return [present, populated]


# Whole seed -------------------------------------------------------------------------------------


def _coverage_checks(seeded: Sequence[Episode], expected_skills: Iterable[str]) -> list[Check]:
    wanted = set(expected_skills)
    found = {str(episode.state["skill_id"]) for episode in seeded}
    check = Check(
        "seed",
        "Every planned skill has seeded episodes",
        wanted <= found,
        checked=len(wanted),
        detail=f"{len(found)} skills, {len(seeded)} episodes",
    )
    if not check.passed:
        check.failures.append(f"missing: {sorted(wanted - found)}")
    return [check]


def _utc(value: datetime) -> datetime:
    # SQLite returns naive timestamps; the store always writes UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _parse(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value))


def _fail(check: Check, episode_id: str, message: str) -> None:
    check.passed = False
    check.failures.append(f"{episode_id}: {message}")
