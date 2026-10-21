"""Validate the three models against simulated learners whose true answers are known.

A real child's true misconception and best help are never known, so accuracy can only be
estimated indirectly from their games. Here each simulated learner is given hidden truths: the
kind of mistake it makes on a skill and the help type that really works for it. It then plays the
real games through the real models. Because the truths are known, each model's accuracy can be
measured directly.

Every simulated learner has its own account named "Simulated test learner NN" and every session is
tagged ``validation-sim-v1``, so none of this ever mixes with a real child's record.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
)
from app.gamification.application.research_accuracy import present_simulation, wilson
from app.gamification.content.support_types import SUPPORT_TYPES
from app.gamification.demo_seed.answers import correct_answer, wrong_answers
from app.gamification.demo_seed.runner import multi_help_areas
from app.gamification.modeling.support_selection.support_order import (
    LEAD_BY_REASON,
    reason_family,
    subject_of,
)
from app.shared.learner.model import LearnerModel

TAG = "validation-sim-v1"
REPORT = Path(__file__).resolve().parents[3] / "reports" / "simulated-validation.json"
FAMILIES = ("representation", "procedure", "relation", "prerequisite", "unclear")


@dataclass(frozen=True)
class Assumptions:
    """The simulated world. Each value is shown on the dashboard next to the results."""

    learners: int = 20
    sessions_per_skill: int = 3
    # How often a learner makes its own kind of mistake rather than a random one.
    consistent_mistake: float = 0.8
    # How often the help that really works is the one matched to the kind of mistake.
    best_help_matches_reason: float = 0.6
    help_works_if_best: float = 0.85
    help_works_otherwise: float = 0.3
    learns_after_best_help: float = 0.85
    learns_after_other_help: float = 0.45
    learns_without_help_success: float = 0.15
    lucky_guess: float = 0.1
    seed: int = 20261021


@dataclass
class Observation:
    learner: int
    condition: str
    area_id: str
    skill_id: str
    session: int
    true_family: str
    testable_family: bool
    predicted_family: str | None = None
    confidence: float | None = None
    true_best: str = ""
    first_help: str | None = None
    preferred_after: str | None = None
    helped_success: bool = False
    truly_learned: bool = False
    measured_gain: str | None = None
    valid: bool = False
    selection_mode: str | None = None


@dataclass
class CohortResult:
    observations: list[Observation] = field(default_factory=list)
    skipped: int = 0
    # Sessions that could not be played to the end, with where they stopped.
    problems: list[str] = field(default_factory=list)


def learner_id(index: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"{TAG}:learner:{index}")


def ensure_learners(session: Session, assumptions: Assumptions) -> list[UUID]:
    ids = []
    now = datetime.now(UTC)
    for index in range(assumptions.learners):
        identifier = learner_id(index)
        if session.get(LearnerModel, identifier) is None:
            session.add(
                LearnerModel(
                    id=identifier,
                    grade=5,
                    preferred_language="si",
                    display_name=f"Simulated test learner {index + 1:02d}",
                    created_at=now,
                    updated_at=now,
                )
            )
        ids.append(identifier)
    session.commit()
    return ids


def run_cohort(
    session: Session,
    orchestrator: LearningFlowOrchestrator,
    assumptions: Assumptions | None = None,
) -> CohortResult:
    assumptions = assumptions or Assumptions()
    learners = ensure_learners(session, assumptions)
    areas = multi_help_areas(orchestrator)
    result = CohortResult()
    for index, learner in enumerate(learners):
        condition = "proposed" if index % 2 == 0 else "baseline"
        for area_id, skills in sorted(areas.items()):
            skill = skills[0]
            rng = random.Random(f"{assumptions.seed}:{index}:{skill}")
            family = rng.choice(FAMILIES)
            lead = LEAD_BY_REASON[family]
            best = (
                lead
                if rng.random() < assumptions.best_help_matches_reason
                else rng.choice([value for value in SUPPORT_TYPES if value != lead])
            )
            for number in range(assumptions.sessions_per_skill):
                observation = Observation(
                    learner=index,
                    condition=condition,
                    area_id=area_id,
                    skill_id=skill,
                    session=number + 1,
                    true_family=family,
                    testable_family=False,
                    true_best=best,
                )
                try:
                    if _play(orchestrator, learner, observation, rng, assumptions):
                        result.observations.append(observation)
                    else:
                        result.skipped += 1
                except (LearningFlowOrchestrationError, ValueError) as error:
                    result.skipped += 1
                    result.problems.append(f"{skill} session {number + 1}: {error}")
    return result


def _play(orchestrator, learner, obs: Observation, rng, a: Assumptions) -> bool:
    base = f"{TAG}:{learner}:{obs.skill_id}:{obs.session}"
    opened, prefix = None, base
    for salt in range(60):
        prefix = base if salt == 0 else f"{base}:salt-{salt}"
        try:
            opened = orchestrator.open_episode(
                learner_id=learner,
                session_id=uuid5(NAMESPACE_URL, prefix),
                grade=5,
                medium="si",
                condition=obs.condition,
                environment="development",
                allow_draft=True,
                area_id=obs.area_id,
                atomic_skill_id=obs.skill_id,
                idempotency_key=f"{prefix}:open",
                seed_source=TAG,
            )
            break
        except LearningFlowOrchestrationError as error:
            if error.code != "PROBE_ALREADY_RESERVED_OR_EXPOSED":
                raise
    if opened is None:
        return False
    episode = UUID(str(opened["episode_id"]))
    state = orchestrator.reconstruct(episode)["state"]
    if state["status"] in {"completed", "invalidated"}:
        _read_back(obs, state)
        return True
    flow = orchestrator._adaptive_flow(episode)
    before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
    subject = subject_of(obs.area_id)
    candidates = list(wrong_answers(flow, before))
    if not candidates:
        return False
    own = [
        pair for pair in candidates if reason_family(pair[1], subject=subject) == obs.true_family
    ]
    obs.testable_family = bool(own)
    if own and rng.random() < a.consistent_mistake:
        payload = rng.choice(own)[0]
    else:
        payload = rng.choice(candidates)[0]
    response = orchestrator.submit_before(
        episode,
        option_id=None,
        constructed_response=payload,
        response_time_ms=rng.randint(6_000, 30_000),
        interaction_summary=_summary(flow, rng),
        idempotency_key=f"{prefix}:before",
    )
    for step in range(24):
        status = response["support_round"]
        if status["withdrawal_allowed"]:
            break
        if status["stage_kind"] == "view":
            response = orchestrator.complete_support(
                episode,
                duration_ms=rng.randint(8_000, 20_000),
                steps_viewed=3,
                manifest_revision_id=status["manifest_revision_id"],
                grouped_count=0,
                group_sizes=(0, 0),
                interaction_summary={"completed": True},
                idempotency_key=f"{prefix}:help:{step}:view",
            )
            continue
        works = (
            a.help_works_if_best
            if status["scaffold_type"] == obs.true_best
            else a.help_works_otherwise
        )
        item = flow._support_rounds.current_item(orchestrator.reconstruct(episode)["state"])
        right = rng.random() < works
        try:
            answer = correct_answer(flow, item) if right else _any_wrong(flow, item)
        except ValueError as error:
            raise ValueError(
                f"{status['scaffold_type']} round {status['round_number']}, "
                f"{status['stage_kind']} item {item.get('skill_id')}: {error}"
            ) from error
        response = orchestrator.submit_supported(
            episode,
            constructed_response=answer,
            response_time_ms=rng.randint(5_000, 20_000),
            interaction_summary={},
            idempotency_key=f"{prefix}:help:{step}",
        )
    status = response["support_round"]
    state = orchestrator.reconstruct(episode)["state"]
    rounds = state["support_loop"]["rounds"]
    winner = next((r["scaffold_type"] for r in rounds if r.get("outcome") == "succeeded"), None)
    obs.helped_success = winner is not None
    chance = (
        a.learns_after_best_help
        if winner == obs.true_best
        else a.learns_after_other_help
        if winner
        else a.learns_without_help_success
    )
    obs.truly_learned = rng.random() < chance
    orchestrator.withdraw_support(
        episode,
        request_id=uuid5(NAMESPACE_URL, f"{prefix}:withdraw"),
        support_revision_id=status["support_revision_id"],
        manifest_revision_id=status["manifest_revision_id"],
        all_support_removed=True,
        answer_revealing_state_cleared=True,
        input_handlers_cleared=True,
        idempotency_key=f"{prefix}:withdraw",
    )
    orchestrator.present_after(episode, idempotency_key=f"{prefix}:present-after")
    after = orchestrator.reconstruct(episode)["state"]["presentations"][-1]
    right_alone = obs.truly_learned or rng.random() < a.lucky_guess
    orchestrator.submit_after(
        episode,
        option_id=None,
        constructed_response=correct_answer(flow, after)
        if right_alone
        else _any_wrong(flow, after),
        response_time_ms=rng.randint(5_000, 25_000),
        idempotency_key=f"{prefix}:after",
    )
    _read_back(obs, orchestrator.reconstruct(episode)["state"])
    return True


def _read_back(obs: Observation, state) -> None:
    model1 = state.get("model1") or {}
    model2 = state.get("model2") or {}
    subject = subject_of(obs.area_id)
    label = model1.get("top_hypothesis") or model1.get("predicted_label")
    uncertain = any(model1.get(flag) for flag in ("low_confidence", "fallback_used", "abstained"))
    obs.predicted_family = "unclear" if uncertain else reason_family(label, subject=subject)
    obs.confidence = float(model1.get("confidence") or 0) or None
    obs.first_help = (model2.get("support_order") or [None])[0]
    obs.selection_mode = model2.get("support_selection_mode")
    preference = (model2.get("learner_activity_support_preference") or {}).get("preferred_support")
    obs.preferred_after = preference
    measurement = state.get("measurement") or {}
    gain = measurement.get("raw_independence_gain")
    obs.measured_gain = None if gain is None else str(gain)
    obs.valid = state.get("validity") == "valid"


def _any_wrong(flow, record):
    for payload, _code in wrong_answers(flow, record):
        return payload
    return correct_answer(flow, record)


def _summary(flow, rng) -> dict[str, object]:
    values = {
        "attempt_count": 1,
        "move_count": rng.randint(2, 9),
        "correction_count": rng.randint(0, 3),
        "first_action_ms": rng.randint(800, 6_000),
        "active_time_ms": rng.randint(5_000, 28_000),
        "evidence_quality": round(rng.uniform(0.45, 0.95), 2),
    }
    accepted = {}
    for key, value in values.items():
        try:
            flow._validate_interaction_summary({key: value})
        except (TypeError, ValueError):
            continue
        accepted[key] = value
    return accepted


# Report -------------------------------------------------------------------------------------------


def _rate(name, good, how, hits: list[int]) -> dict[str, object]:
    n = len(hits)
    return {
        "title": name,
        "good": good,
        "method": how,
        "count": n,
        "value": sum(hits) / n if n else None,
        "interval": wilson(sum(hits), n) if n else None,
    }


def report(result: CohortResult, assumptions: Assumptions) -> dict[str, object]:
    obs = result.observations
    testable = [o for o in obs if o.testable_family and o.predicted_family]
    family_hits = [int(o.predicted_family == o.true_family) for o in testable]
    first = [o for o in testable if o.session == 1]
    later = [o for o in testable if o.session > 1]
    confident = [o for o in testable if o.confidence is not None]
    mean_conf = sum(o.confidence for o in confident) / len(confident) if confident else None
    proposed = [o for o in obs if o.condition == "proposed"]
    baseline = [o for o in obs if o.condition == "baseline"]
    final = {}
    for o in proposed:
        final[(o.learner, o.skill_id)] = o
    preference_hits = [
        int(o.preferred_after == o.true_best) for o in final.values() if o.preferred_after
    ]
    measured = [o for o in obs if o.measured_gain is not None and o.valid]
    agree = [int((o.measured_gain == "1") == o.truly_learned) for o in measured]
    sensitivity = [int(o.measured_gain == "1") for o in measured if o.truly_learned]
    specificity = [int(o.measured_gain != "1") for o in measured if not o.truly_learned]
    learners_by_condition = defaultdict(set)
    for o in obs:
        learners_by_condition[o.condition].add(o.learner)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "title": "Check against simulated test learners",
        "what": (
            "A real child's true reason for a mistake, and the help that truly works for them, can "
            "never be known for certain. So we also test the models on simulated learners whose "
            "true answers are set in advance. They play the real games through the real models; "
            "only their answers are simulated."
        ),
        "cohort": {
            "learners": assumptions.learners,
            "proposed": len(learners_by_condition["proposed"]),
            "comparison": len(learners_by_condition["baseline"]),
            "games": 34,
            "sessions": len(obs),
            "not_playable": result.skipped,
        },
        "assumptions": [
            f"Each simulated learner makes its own kind of mistake {assumptions.consistent_mistake:.0%} of the time.",
            f"The help that really works matches the kind of mistake {assumptions.best_help_matches_reason:.0%} of the time; otherwise it is another help.",
            f"With the help that really works, the learner succeeds while helped {assumptions.help_works_if_best:.0%} of the time; with other help {assumptions.help_works_otherwise:.0%}.",
            f"After succeeding with the right help, it has truly learned {assumptions.learns_after_best_help:.0%} of the time; with other help {assumptions.learns_after_other_help:.0%}; without success {assumptions.learns_without_help_success:.0%}.",
            f"A learner who has not learned still guesses right {assumptions.lucky_guess:.0%} of the time.",
        ],
        "models": [
            {
                "name": "Probabilistic Misconception",
                "metrics": [
                    _rate(
                        "Found the true kind of mistake",
                        "Higher is better. Picking at random among 5 kinds would score about 20%.",
                        "Compare the most likely reason with the learner's hidden kind of mistake.",
                        family_hits,
                    ),
                    _rate(
                        "First game on a skill",
                        "Shows accuracy from one answer alone.",
                        "Same comparison, first game only.",
                        [int(o.predicted_family == o.true_family) for o in first],
                    ),
                    _rate(
                        "Later games on a skill",
                        "Should be at least as high, because earlier answers are remembered.",
                        "Same comparison, second and third games.",
                        [int(o.predicted_family == o.true_family) for o in later],
                    ),
                ],
                "note": (
                    f"Average stated confidence: {mean_conf:.0%}. Compare it with how often it was right, "
                    "above: if they are close, its confidence can be trusted."
                    if mean_conf is not None
                    else ""
                ),
            },
            {
                "name": "Contextual Support Selection",
                "metrics": [
                    _rate(
                        "First help was the one that really works (proposed)",
                        "Higher is better than the comparison group below.",
                        "Compare the first help chosen with the learner's hidden best help.",
                        [int(o.first_help == o.true_best) for o in proposed if o.first_help],
                    ),
                    _rate(
                        "First help was the one that really works (comparison group)",
                        "The fixed order, for comparison.",
                        "Same comparison for the fixed order.",
                        [int(o.first_help == o.true_best) for o in baseline if o.first_help],
                    ),
                    _rate(
                        "Could do it alone after help (proposed)",
                        "Higher is better.",
                        "Right on the fresh question after help was removed.",
                        [
                            int(o.measured_gain == "1")
                            for o in proposed
                            if o.measured_gain is not None
                        ],
                    ),
                    _rate(
                        "Could do it alone after help (comparison group)",
                        "The fixed order, for comparison.",
                        "Same, for the fixed order.",
                        [
                            int(o.measured_gain == "1")
                            for o in baseline
                            if o.measured_gain is not None
                        ],
                    ),
                    _rate(
                        "Learned the help that really works",
                        "Higher is better.",
                        "After three games, is the child's preferred help the hidden best one?",
                        preference_hits,
                    ),
                ],
            },
            {
                "name": "Independence Gain",
                "metrics": [
                    _rate(
                        "Measured gain agrees with real learning",
                        "Higher is better.",
                        "A gain of +1 should mean the learner truly learned; 0 that it did not.",
                        agree,
                    ),
                    _rate(
                        "Caught real learning",
                        "How often real learning showed as +1.",
                        "Among learners who truly learned.",
                        sensitivity,
                    ),
                    _rate(
                        "Avoided false gains",
                        "How often no learning showed as 0 (lucky guesses lower this).",
                        "Among learners who did not learn.",
                        specificity,
                    ),
                    _rate(
                        "Fair tests",
                        "Every measured game should pass the fairness checks.",
                        "Share of measured games that were valid.",
                        [int(o.valid) for o in obs if o.measured_gain is not None],
                    ),
                ],
            },
        ],
    }
    return present_simulation(payload)


def write_report(data: dict[str, object]) -> Path:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return REPORT
