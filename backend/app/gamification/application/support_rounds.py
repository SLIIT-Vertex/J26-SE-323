"""The multi-help loop inside one episode.

After a detected difficulty, Model 2 fixes the help order. Each round delivers one type. A wrong
supported attempt opens the next type in that order that has not been used; a correct one, a
watched demonstration (which already showed the answer), or the end of the order stops the loop
and allows withdrawal. A type is never repeated in an episode.

If the child then fails the fresh after item, that first after item stays the Model 3
measurement and a follow-up loop opens with the next unused type of the same order. It lives in
``state["follow_up"]`` (see :func:`scope`), so the measured loop, exposure and withdrawal are never
overwritten. Each follow-up help ends in another withdrawal and another fresh practice item, until
the child succeeds alone or the order runs out.

This service advances, scores and stops the loop. It does not render (the builders do), does not
choose the order (Model 2 does), and does not calculate Model 3 (the measurement module does).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from uuid import uuid4

from app.gamification.application.support_builders import (
    SUPPORT_BUILDERS,
    SupportBuildContext,
    SupportBuilder,
    SupportPlan,
)
from app.gamification.content.support_types import ENGLISH_TAG_KEYS
from app.gamification.modeling.support_selection.support_order import SupportOrderDecision

SUPPORT_ROUND_SCHEMA_VERSION = "support-round-v1"


class SupportRoundError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


ContextFactory = Callable[[], SupportBuildContext]


def scope(state: Mapping[str, object]) -> dict[str, object]:
    """Where the current help loop, exposure, withdrawal and phase live: the episode itself, or
    its follow-up after a failed after item."""

    follow_up = state.get("follow_up")
    if isinstance(follow_up, dict) and follow_up["status"] != "finished":
        return follow_up
    return state  # type: ignore[return-value]


def phase(state: Mapping[str, object]) -> str:
    """The step the phone is on. The episode's own status stays terminal during a follow-up."""

    return str(scope(state)["status"])


class SupportRoundService:
    def __init__(self, builders: Mapping[str, SupportBuilder] = SUPPORT_BUILDERS) -> None:
        self._builders = builders

    def renderable_plans(
        self, context: SupportBuildContext, eligible: tuple[str, ...]
    ) -> dict[str, SupportPlan]:
        """Plans for every eligible type this game can render for this failed item."""

        plans: dict[str, SupportPlan] = {}
        for support in eligible:
            builder = self._builders.get(support)
            plan = builder.build(context) if builder is not None else None
            if plan is not None:
                plans[support] = plan
        return plans

    def start(
        self,
        state: dict[str, object],
        decision: SupportOrderDecision,
        first_plan: SupportPlan,
        at: datetime,
    ) -> None:
        if first_plan.scaffold_type != decision.first:
            raise SupportRoundError("SUPPORT_ORDER_MISMATCH")
        state["support_loop"] = {
            "order": list(decision.order),
            "types_used": [],
            "rounds": [],
            "skipped_unrenderable": [],
            "stop_reason": None,
        }
        self._open(state, first_plan, at)

    def record_attempt(
        self,
        state: dict[str, object],
        score: Mapping[str, object],
        next_context: ContextFactory,
        at: datetime,
    ) -> dict[str, object]:
        """Apply one scored supported attempt. Returns the round status for the response."""

        current = self._current_round(state)
        stage = current["stages"][current["stage_index"]]
        if stage["kind"] == "view":
            raise SupportRoundError("SUPPORT_STAGE_REQUIRES_PROGRESS")
        correct = bool(score["correct"])
        current["attempts"].append(dict(score))
        last_stage = current["stage_index"] == len(current["stages"]) - 1
        if not last_stage and (correct or not stage["gate_on_success"]):
            current["stage_index"] += 1
            self._event(state, "support_stage_advanced", at, current)
            return self.status(state, previous_attempt_correct=correct)
        if correct and last_stage:
            self._close(state, current, "succeeded", at)
            self._stop(state, "supported_success", at)
            return self.status(state, previous_attempt_correct=True)
        self._close(state, current, "failed", at)
        opened = self._open_next(state, next_context, at)
        if not opened:
            self._stop(state, "order_exhausted", at)
        return self.status(state, previous_attempt_correct=False, another_round=opened)

    def open_follow_up(
        self,
        state: dict[str, object],
        failed: Mapping[str, object],
        next_context: ContextFactory,
        at: datetime,
    ) -> bool:
        """Open the next unused type after a failed unsupported item. False when none is left.

        ``failed`` names the item the child just failed; the next help is built on it.
        """

        follow_up = state.get("follow_up")
        if not isinstance(follow_up, dict):
            measured = state.get("support_loop")
            if not isinstance(measured, dict):
                return False
            used = {*measured["types_used"], *measured["skipped_unrenderable"]}
            follow_up = {
                "status": "finished",
                "support_loop": {
                    "order": [support for support in measured["order"] if support not in used],
                    "types_used": [],
                    "rounds": [],
                    "skipped_unrenderable": [],
                    "stop_reason": None,
                },
                "scaffold_exposure": None,
                "withdrawal": None,
                "supported_correctness": None,
                "presentations": [],
                "attempts": [],
                "failed": None,
            }
            state["follow_up"] = follow_up
        follow_up["failed"] = dict(failed)
        follow_up["status"] = "support_pending"
        follow_up["support_loop"]["stop_reason"] = None
        if self._open_next(state, next_context, at):
            return True
        follow_up["support_loop"]["stop_reason"] = "order_exhausted"
        self.finish_follow_up(state, "order_exhausted", at)
        return False

    def finish_follow_up(self, state: dict[str, object], reason: str, at: datetime) -> None:
        follow_up = state["follow_up"]
        assert isinstance(follow_up, dict)
        follow_up["status"] = "finished"
        follow_up["finish_reason"] = reason
        self._event(state, "follow_up_finished", at, None, reason=reason)

    def record_view_complete(
        self,
        state: dict[str, object],
        manifest_revision_id: str,
        at: datetime,
    ) -> dict[str, object]:
        current = self._current_round(state)
        stage = current["stages"][current["stage_index"]]
        if stage["kind"] != "view" or manifest_revision_id != current["manifest_revision_id"]:
            raise SupportRoundError("INVALID_SUPPORT_COMPLETION")
        if current["stage_index"] == len(current["stages"]) - 1:
            # A demonstration-only round (mathematics visual guidance) has nothing to answer:
            # it already showed the answer. Watching it ends the loop and allows withdrawal,
            # so the after item measures what the demonstration taught.
            self._close(state, current, "viewed", at)
            self._stop(state, "support_viewed", at)
            return self.status(state, previous_attempt_correct=None)
        current["stage_index"] += 1
        self._event(state, "support_stage_advanced", at, current)
        return self.status(state, previous_attempt_correct=None)

    def current_item(self, state: Mapping[str, object]) -> dict[str, object]:
        current = self._current_round(state)
        item = current["stages"][current["stage_index"]]["item"]
        if not isinstance(item, dict):
            raise SupportRoundError("SUPPORT_STAGE_REQUIRES_PROGRESS")
        return item

    def status(
        self,
        state: Mapping[str, object],
        *,
        previous_attempt_correct: bool | None,
        another_round: bool = False,
    ) -> dict[str, object]:
        loop = scope(state)["support_loop"]
        assert isinstance(loop, dict)
        latest = loop["rounds"][-1]
        stopped = loop["stop_reason"] is not None
        return {
            "round_number": latest["round_number"],
            "scaffold_type": latest["scaffold_type"],
            "english_tag_key": latest["english_tag_key"],
            "stage_kind": None if stopped else latest["stages"][latest["stage_index"]]["kind"],
            "previous_attempt_correct": previous_attempt_correct,
            "another_round_required": another_round,
            "withdrawal_allowed": stopped,
            # What the phone acknowledges when it removes this help.
            "support_revision_id": latest["revision_id"],
            "manifest_revision_id": latest["manifest_revision_id"],
        }

    def public_view(
        self, state: Mapping[str, object], *, activity: Callable[[Mapping[str, object]], dict]
    ) -> dict[str, object] | None:
        """The phone's view of the current round: no later type and no order.

        A help stage carries its item's answer for the board to tint (or, in a worked example,
        to show filled); the scored before and after items never do.
        """

        loop = scope(state).get("support_loop")
        if not isinstance(loop, dict) or loop["stop_reason"] is not None:
            return None
        current = loop["rounds"][-1]
        stage = current["stages"][current["stage_index"]]
        item = stage["item"]
        worked = stage["worked_example"]
        public_activity = None
        if isinstance(item, dict):
            public_activity = {
                **activity(item),
                "returns_to_failed_item": stage["kind"] == "target" and current["stage_index"] > 0,
                "answer": stage.get("answer"),
            }
        return {
            "scaffold_id": f"{state['skill_id']}:{current['scaffold_type']}",
            "revision_id": current["revision_id"],
            "scaffold_type": current["scaffold_type"],
            "english_tag_key": current["english_tag_key"],
            "title_si": current["title_si"],
            "body_si": list(stage["cues_si"]),
            "visual_alt_text_si": None,
            "maximum_steps": len(current["stages"]),
            "game_manifest": {
                "schema_version": SUPPORT_ROUND_SCHEMA_VERSION,
                "activity_id": state["experience_id"],
                "revision_id": current["manifest_revision_id"],
                "deterministic_seed": state["seed"],
                "skill_id": state["skill_id"],
                "scaffold_type": current["scaffold_type"],
                "english_tag_key": current["english_tag_key"],
                "renderer_id": f"{state['experience_id']}:{current['scaffold_type']}",
                "parallel_example_id": f"{state['skill_id']}:{current['scaffold_type']}",
                "parallel_example_version": "v1",
                "parallel_values": [],
                "required_actions": 1,
                "round_number": current["round_number"],
                "stage_index": current["stage_index"],
                "stage_count": len(current["stages"]),
                "stage_kind": stage["kind"],
                "cues_si": list(stage["cues_si"]),
                "guidance": list(stage.get("guidance") or ()),
                "lesson": stage.get("lesson"),
                "activity": public_activity,
                "worked_example": worked,
            },
        }

    @staticmethod
    def round_rows(state: Mapping[str, object]) -> tuple[dict[str, object], ...]:
        """One durable row per delivered type, for the store's support-round table.

        Only the measured loop: follow-up help comes after Model 3 and is kept in the state.
        """

        loop = state.get("support_loop")
        if not isinstance(loop, dict):
            return ()
        return tuple(
            {
                "round_id": row["round_id"],
                "round_number": row["round_number"],
                "scaffold_type": row["scaffold_type"],
                "english_tag_key": row["english_tag_key"],
                "order_position": loop["order"].index(row["scaffold_type"]),
                "outcome": row["outcome"],
                # A watched demonstration was never answered, so it has no supported result.
                "supported_correct": (
                    None
                    if row["outcome"] in {None, "viewed"}
                    else row["outcome"] == "succeeded"
                ),
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
            }
            for row in loop["rounds"]
        )

    def _open_next(
        self, state: dict[str, object], next_context: ContextFactory, at: datetime
    ) -> bool:
        loop = scope(state)["support_loop"]
        assert isinstance(loop, dict)
        for support in loop["order"]:
            if support in loop["types_used"] or support in loop["skipped_unrenderable"]:
                continue
            plan = self._builders[support].build(next_context())
            if plan is None:
                loop["skipped_unrenderable"].append(support)
                continue
            self._open(state, plan, at)
            return True
        return False

    def _open(self, state: dict[str, object], plan: SupportPlan, at: datetime) -> None:
        holder = scope(state)
        loop = holder["support_loop"]
        assert isinstance(loop, dict)
        if plan.scaffold_type in loop["types_used"]:
            raise SupportRoundError("SUPPORT_TYPE_REPEATED")
        number = len(loop["rounds"]) + 1
        label = "round" if holder is state else "follow-up-round"
        revision = f"{state['skill_id']}:{plan.scaffold_type}:{label}-{number}@v1"
        current = {
            "round_id": str(uuid4()),
            "round_number": number,
            "scaffold_type": plan.scaffold_type,
            "english_tag_key": ENGLISH_TAG_KEYS[plan.scaffold_type],
            "title_si": plan.title_si,
            "revision_id": revision,
            "manifest_revision_id": f"{revision}:manifest",
            "stages": [stage.as_record() for stage in plan.stages],
            "stage_index": 0,
            "attempts": [],
            "outcome": None,
            "opened_at": at.isoformat(),
            "closed_at": None,
        }
        loop["rounds"].append(current)
        loop["types_used"].append(plan.scaffold_type)
        holder["scaffold_exposure"] = {
            "exposure_id": str(uuid4()),
            "revision_id": revision,
            "scaffold_type": plan.scaffold_type,
            "round_number": number,
            "presented_at": at.isoformat(),
            "completed_at": None,
            "displayed": True,
            "fully_withdrawn": False,
            # A worked example shows a full solution; withdrawal must clear it either way.
            "answer_revealing": plan.scaffold_type == "worked_parallel_example"
            or any(stage.kind == "view" and stage.item is not None for stage in plan.stages),
            "manifest_revision_id": current["manifest_revision_id"],
        }
        holder["status"] = "support_active"
        self._event(state, "support_round_opened", at, current)

    @staticmethod
    def _close(
        state: dict[str, object], current: dict[str, object], outcome: str, at: datetime
    ) -> None:
        current.update(outcome=outcome, closed_at=at.isoformat())
        SupportRoundService._event(state, f"support_round_{outcome}", at, current)

    @staticmethod
    def _stop(state: dict[str, object], reason: str, at: datetime) -> None:
        holder = scope(state)
        loop = holder["support_loop"]
        assert isinstance(loop, dict)
        loop["stop_reason"] = reason
        exposure = holder["scaffold_exposure"]
        assert isinstance(exposure, dict)
        exposure["completed_at"] = at.isoformat()
        # The supported result is kept for audit only; it is never a reward.
        holder["supported_correctness"] = (
            None if reason == "support_viewed" else reason == "supported_success"
        )
        holder["status"] = "support_complete"
        SupportRoundService._event(state, "support_loop_stopped", at, None, reason=reason)

    @staticmethod
    def _current_round(state: Mapping[str, object]) -> dict[str, object]:
        loop = scope(state).get("support_loop")
        if not isinstance(loop, dict) or not loop["rounds"] or loop["stop_reason"] is not None:
            raise SupportRoundError("EPISODE_STATE_CONFLICT")
        return loop["rounds"][-1]

    @staticmethod
    def _event(
        state: dict[str, object],
        event_type: str,
        at: datetime,
        current: Mapping[str, object] | None,
        **details: object,
    ) -> None:
        events = state["events"]
        assert isinstance(events, list)
        if current is not None:
            details.update(
                round_number=current["round_number"],
                scaffold_type=current["scaffold_type"],
                stage_index=current["stage_index"],
            )
        events.append(
            {
                "event_id": str(uuid4()),
                "sequence": len(events) + 1,
                "event_type": event_type,
                "presentation_id": None,
                "occurred_at": at.isoformat(),
                "details": details,
            }
        )
