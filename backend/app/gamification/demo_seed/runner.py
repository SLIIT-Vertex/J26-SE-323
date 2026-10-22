"""Play a seed plan through the real learning-flow orchestrator.

Every call is one the phone makes: open, answer before, answer or view each help round, withdraw,
answer after. The models therefore produce every estimate, order and gain the seed leaves behind.
Keys and session ids are derived from the plan, so running the seed again changes nothing.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, UUID, uuid5

from app.gamification.application.learning_flow_orchestration import (
    LearningFlowOrchestrationError,
    LearningFlowOrchestrator,
)
from app.gamification.application.teardown_receipt import (
    shown_steps,
    simulated_receipt,
    supported_summary,
)
from app.gamification.demo_seed.answers import correct_answer, wrong_answers
from app.gamification.demo_seed.plan import EpisodeScript, SeedPlan, SkillPlan
from app.gamification.modeling.support_selection.support_order import reason_family, subject_of

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "invalidated"}
# Interaction fields a game may accept; each game's own validator decides which it keeps.
_SUMMARY_FIELDS = (
    "attempt_count",
    "move_count",
    "correction_count",
    "first_action_ms",
    "active_time_ms",
    "evidence_quality",
)
_MAX_HELP_STEPS = 24
_OPEN_ATTEMPTS = 160


def multi_help_areas(orchestrator: LearningFlowOrchestrator) -> dict[str, list[str]]:
    """Every area that runs the multi-help loop, with its skills in teaching order."""

    return {
        area_id: list(flow.skills)
        for area_id, flow in orchestrator._area_flows.items()
        if getattr(flow, "runs_support_loop", False)
    }


class ItemPoolExhaustedError(RuntimeError):
    pass


@dataclass
class SeedReport:
    played: int = 0
    already_seeded: int = 0
    failed: list[str] = field(default_factory=list)
    # Episodes left out because the skill has no unused after-item left for this learner: Model 3
    # never reuses one, and some skills have very small item pools.
    pool_exhausted: list[str] = field(default_factory=list)
    # (skill, episode) -> the Model 1 family the before answer aimed for and what the scorer gave.
    families: dict[str, tuple[str, str]] = field(default_factory=dict)


class SeedRunner:
    def __init__(self, orchestrator: LearningFlowOrchestrator, plan: SeedPlan) -> None:
        self._orchestrator = orchestrator
        self._plan = plan
        self._learner = UUID(plan.learner_id)

    def run(self) -> SeedReport:
        report = SeedReport()
        for skill in self._plan.skills:
            for index, script in enumerate(skill.episodes):
                label = f"{skill.skill_id}#{index}"
                try:
                    if self._episode(skill, index, script, report):
                        report.played += 1
                    else:
                        report.already_seeded += 1
                except ItemPoolExhaustedError:
                    report.pool_exhausted.append(label)
                except Exception as error:  # one bad episode must not stop the seed
                    logger.exception("seed episode failed: %s", label)
                    report.failed.append(f"{label}: {type(error).__name__}: {error}")
        return report

    def _episode(
        self, skill: SkillPlan, index: int, script: EpisodeScript, report: SeedReport
    ) -> bool:
        base = f"{self._plan.version}:{self._plan.learner_id}:{skill.skill_id}:{index}"
        orchestrator = self._orchestrator
        prefix, opened = self._open(skill, script, base)
        rng = random.Random(prefix)
        episode_id = UUID(str(opened["episode_id"]))
        state = orchestrator.reconstruct(episode_id)["state"]
        if state["status"] in TERMINAL:
            return False
        flow = orchestrator._adaptive_flow(episode_id)
        before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")
        sparse = script.before == "wrong_sparse"
        if script.before == "correct":
            payload = correct_answer(flow, before)
        else:
            payload, code = self._targeted_wrong(flow, before, skill)
            report.families[f"{skill.skill_id}#{index}"] = (
                skill.target_family,
                reason_family(code, subject=subject_of(skill.area_id)),
            )
        response = orchestrator.submit_before(
            episode_id,
            option_id=None,
            constructed_response=payload,
            response_time_ms=None if sparse else rng.randint(6_000, 30_000),
            interaction_summary=None if sparse else self._summary(flow, rng),
            idempotency_key=f"{prefix}:before",
        )
        if script.before == "correct":
            return True
        response = self._help(flow, episode_id, script, response, prefix, rng)
        if script.after == "exit":
            orchestrator.invalidate(
                episode_id, reason="learner_exited", idempotency_key=f"{prefix}:exit"
            )
            return True
        status = response["support_round"]
        orchestrator.withdraw_support(
            episode_id,
            request_id=uuid5(NAMESPACE_URL, f"{prefix}:withdraw"),
            support_revision_id=status["support_revision_id"],
            manifest_revision_id=status["manifest_revision_id"],
            all_support_removed=True,
            answer_revealing_state_cleared=True,
            input_handlers_cleared=True,
            idempotency_key=f"{prefix}:withdraw",
            teardown_receipt=simulated_receipt(
                status["support_revision_id"], status["manifest_revision_id"]
            ),
        )
        orchestrator.present_after(episode_id, idempotency_key=f"{prefix}:present-after")
        after = orchestrator.reconstruct(episode_id)["state"]["presentations"][-1]
        orchestrator.submit_after(
            episode_id,
            option_id=None,
            constructed_response=(
                correct_answer(flow, after)
                if script.after == "correct"
                else self._any_wrong(flow, after)
            ),
            response_time_ms=rng.randint(5_000, 25_000),
            idempotency_key=f"{prefix}:after",
        )
        return True

    def _open(
        self, skill: SkillPlan, script: EpisodeScript, base: str
    ) -> tuple[str, Mapping[str, object]]:
        """Open the episode. Small item pools can give an after-item this learner already holds
        reserved; the next salt gives other items. The salts are tried in the same order on every
        run, so a rerun reaches the same episode."""

        for salt in range(_OPEN_ATTEMPTS):
            prefix = base if salt == 0 else f"{base}:salt-{salt}"
            try:
                return prefix, self._orchestrator.open_episode(
                    learner_id=self._learner,
                    session_id=uuid5(NAMESPACE_URL, prefix),
                    grade=5,
                    medium="si",
                    condition=script.condition,
                    environment="development",
                    allow_draft=True,
                    area_id=skill.area_id,
                    atomic_skill_id=skill.skill_id,
                    idempotency_key=f"{prefix}:open",
                    seed_source=self._plan.version,
                )
            except LearningFlowOrchestrationError as error:
                if error.code != "PROBE_ALREADY_RESERVED_OR_EXPOSED":
                    raise
        raise ItemPoolExhaustedError(skill.skill_id)

    def _help(
        self,
        flow,
        episode_id: UUID,
        script: EpisodeScript,
        response: Mapping[str, object],
        prefix: str,
        rng: random.Random,
    ) -> Mapping[str, object]:
        orchestrator = self._orchestrator
        for step in range(_MAX_HELP_STEPS):
            status = response["support_round"]
            if status["withdrawal_allowed"]:
                return response
            if status["stage_kind"] == "view":
                response = orchestrator.complete_support(
                    episode_id,
                    duration_ms=rng.randint(8_000, 20_000),
                    steps_viewed=shown_steps(response),
                    manifest_revision_id=status["manifest_revision_id"],
                    grouped_count=0,
                    group_sizes=(0, 0),
                    interaction_summary={"completed": True, "next_presses": shown_steps(response)},
                    idempotency_key=f"{prefix}:help:{step}:view",
                )
                continue
            round_number = int(status["round_number"])
            # Rounds past the script are answered correctly, so the loop always ends.
            right = script.rounds[round_number - 1] if round_number <= len(script.rounds) else True
            item = flow._support_rounds.current_item(orchestrator.reconstruct(episode_id)["state"])
            answer = correct_answer(flow, item) if right else self._any_wrong(flow, item)
            response = orchestrator.submit_supported(
                episode_id,
                constructed_response=answer,
                response_time_ms=rng.randint(5_000, 20_000),
                interaction_summary=supported_summary(flow),
                idempotency_key=f"{prefix}:help:{step}",
            )
        raise RuntimeError("HELP_LOOP_DID_NOT_END")

    @staticmethod
    def _targeted_wrong(
        flow, record: Mapping[str, object], skill: SkillPlan
    ) -> tuple[dict[str, object], str]:
        """A wrong answer whose error falls in the skill's target family, when the game has one."""

        subject = subject_of(skill.area_id)
        candidates = list(wrong_answers(flow, record))
        if not candidates:
            raise ValueError(f"NO_WRONG_ANSWER:{skill.skill_id}")
        for payload, code in candidates:
            if reason_family(code, subject=subject) == skill.target_family:
                return payload, code
        return candidates[0]

    @staticmethod
    def _any_wrong(flow, record: Mapping[str, object]) -> dict[str, object]:
        for payload, _code in wrong_answers(flow, record):
            return payload
        # A help item with no wrong answer the scorer accepts is answered right instead.
        return correct_answer(flow, record)

    @staticmethod
    def _summary(flow, rng: random.Random) -> dict[str, object]:
        values = {
            "attempt_count": 1,
            "move_count": rng.randint(2, 9),
            "correction_count": rng.randint(0, 3),
            "first_action_ms": rng.randint(800, 6_000),
            "active_time_ms": rng.randint(5_000, 28_000),
            "evidence_quality": round(rng.uniform(0.45, 0.95), 2),
        }
        accepted: dict[str, object] = {}
        for name in _SUMMARY_FIELDS:
            try:
                flow._validate_interaction_summary({name: values[name]})
            except (TypeError, ValueError):
                # This game does not take that field.
                continue
            accepted[name] = values[name]
        return accepted
