"""Shared durable flow for the Sinhala game packages, on the shared adaptive episode engine.

A package is one content module (``content``) with the interface documented on
:class:`SinhalaPackageFlow`. What differs from the shared profile:

- Help is built from separate assisted items of the episode's subfamily, never the scored before
  item and never a reserved after item. No help stage carries answer marks; worked examples show
  a solved assisted item only.
- Model 2 follows the authored order visual → worked → guided. A failed independent retry in an
  earlier episode of the same skill advances that cursor; a learned preference applies only in
  the proposed condition and is dropped once it fails.
- Withdrawal requires the phone's revision-bound teardown receipt, not only three booleans.
- Explanatory feedback after the before item is deferred while the after probe is reserved.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from types import ModuleType
from uuid import UUID, uuid4

from app.gamification.application.learning_state_input import read_learning_state
from app.gamification.application.number_world_flow import (
    NumberWorldFlow,
    NumberWorldFlowError,
    _event,
    _model1_label,
    _model1_uncertain,
)
from app.gamification.application.support_builders import (
    SupportBuildContext,
    SupportPlan,
    SupportStage,
)
from app.gamification.application.support_rounds import SupportRoundService
from app.gamification.application.teardown_receipt import (
    TEARDOWN_RECEIPT_VERSION,
)
from app.gamification.application.teardown_receipt import TRUE_FLAGS as _TEARDOWN_TRUE_FLAGS
from app.gamification.application.teardown_receipt import ZERO_COUNTS as _TEARDOWN_ZERO_COUNTS
from app.gamification.content.area_support_catalog import assignment
from app.gamification.modeling.support_selection.support_order import choose_support_order

AUTHORED_SEQUENCE = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
SUPPORT_TITLES_SI = {
    "visual_guidance": "හොඳින් බලමු 🌱",
    "worked_parallel_example": "එකට බලමු 🌱",
    "step_by_step_guidance": "පියවරෙන් පියවර 🌱",
}
DIFFICULTY_RULE_VERSION = "g5-sin-package-difficulty-v1"
CURSOR_VERSION = "g5-sin-package-support-cursor-v1"


def _content(context: SupportBuildContext) -> ModuleType:
    return context.source.content  # type: ignore[attr-defined,no-any-return]


def _support_cues(context: SupportBuildContext, *lines: str) -> tuple[str, ...]:
    content = _content(context)
    recap = str(content.support_copy(context.skill_id, _family(context))["recap"])
    return (*lines, recap, content.DONE_LINE)


def _family(context: SupportBuildContext) -> str:
    return _content(context).episode_subfamily(context.skill_id, context.seed)


class _SinhalaBuilder:
    scaffold_type: str
    # Each help type reads its own slots of the assisted pool, so rounds rarely repeat one.
    first_slot: int

    @staticmethod
    def _record(context: SupportBuildContext, slot: int, *, emphasis: str | None = None) -> dict[str, object]:
        """The first assisted item from ``slot`` on that no earlier stage used.

        An earlier help stage's item may be repeated when the pool is that small; a reserved
        before or after probe never is.
        """

        source = context.source
        content = _content(context)
        probes = {
            str(context.failed_record["revision_id"]),
            content.generate_item(context.skill_id, role="unsupported_after", seed=context.seed).revision_id,
        }
        candidates = [
            content.generate_support_item(context.skill_id, seed=context.seed, index=slot + offset)
            for offset in range(8)
        ]
        item = next((c for c in candidates if c.revision_id not in context.reserved_revisions), None)
        item = item or next((c for c in candidates if c.revision_id not in probes), None)
        if item is None:
            raise NumberWorldFlowError("SUPPORT_REUSED_RESERVED_PROBE")
        record = source.support_record(item, context.at)
        record.update(role="supported_practice", assistance_state="active")
        if emphasis is not None:
            record["public_activity"]["game"]["support_emphasis"] = emphasis  # type: ignore[index]
        return record


class SinhalaVisualBuilder(_SinhalaBuilder):
    scaffold_type = "visual_guidance"
    first_slot = 0

    def build(self, context: SupportBuildContext) -> SupportPlan:
        content = _content(context)
        copy = content.support_copy(context.skill_id, _family(context))
        record = self._record(context, self.first_slot, emphasis=content.VISUAL_EMPHASIS)
        return SupportPlan(
            scaffold_type="visual_guidance",
            title_si=SUPPORT_TITLES_SI["visual_guidance"],
            stages=(
                SupportStage(
                    kind="practice", cues_si=_support_cues(context, str(copy["visual"])), item=record
                ),
            ),
        )


class SinhalaWorkedBuilder(_SinhalaBuilder):
    scaffold_type = "worked_parallel_example"
    first_slot = 1

    def build(self, context: SupportBuildContext) -> SupportPlan:
        source = context.source
        shown = self._record(context, self.first_slot)
        practice = self._record(context, self.first_slot + 1)
        activity = source.support_activity(shown)
        game = shown["game_data"]
        assert isinstance(game, Mapping)
        content = _content(context)
        solution = dict(content.correct_response(game))
        solution.update(content.worked_display(game))
        demonstration_record = {
            "presentation_id": shown["presentation_id"],
            "revision_id": shown["revision_id"],
            "skill_id": shown["skill_id"],
            "prompt_si": activity["prompt_si"],
            "game": activity["game"],
            "steps_si": content.worked_steps(game, "worked_parallel_example", context.skill_id),
            "solution": solution,
            "answer": None,
        }
        return SupportPlan(
            scaffold_type="worked_parallel_example",
            title_si=SUPPORT_TITLES_SI["worked_parallel_example"],
            stages=(
                SupportStage(kind="view", cues_si=(), worked_example=demonstration_record),
                SupportStage(kind="practice", cues_si=_support_cues(context), item=practice),
            ),
        )


class SinhalaGuidedBuilder(_SinhalaBuilder):
    scaffold_type = "step_by_step_guidance"
    first_slot = 3

    def build(self, context: SupportBuildContext) -> SupportPlan:
        record = self._record(context, self.first_slot)
        steps = _content(context).worked_steps(record["game_data"], "step_by_step_guidance", context.skill_id)  # type: ignore[arg-type]
        return SupportPlan(
            scaffold_type="step_by_step_guidance",
            title_si=SUPPORT_TITLES_SI["step_by_step_guidance"],
            stages=(
                SupportStage(
                    kind="practice",
                    cues_si=_support_cues(context),
                    item=record,
                    # Each step names an action the child performs; none names the answer.
                    guidance=tuple((step, "ඔයාගේ වාරය") for step in steps),
                ),
            ),
        )


SINHALA_BUILDERS = {
    builder.scaffold_type: builder
    for builder in (SinhalaVisualBuilder(), SinhalaWorkedBuilder(), SinhalaGuidedBuilder())
}


class SinhalaPackageFlow(NumberWorldFlow):
    """One Sinhala package. Subclasses name the content module and their ids; ``bind`` copies
    the module's versions onto the class.

    The content module provides: AREA_ID, UNIVERSAL_SKILL_ID, the *_VERSION constants,
    ITEM_SCHEMA_VERSION, SKILLS, DONE_LINE, VISUAL_EMPHASIS, ResponseError (with ``code``),
    generate_item, generate_support_item, episode_subfamily, opening_demonstration,
    support_copy, worked_steps, worked_display, correct_response,
    validate_constructed_response, public_game_data, feedback_si, infer_belief,
    scaffold_decision and package_hash.
    """

    content: ModuleType
    generate_simpler_item = None
    support_schema_version = "support-round-v1"
    # The learner-state behaviour models were trained on mathematics answers only.
    records_learner_state = False
    accepts_teardown_receipt = True

    @classmethod
    def bind(cls, content: ModuleType) -> None:
        cls.content = content
        cls.area_id = content.AREA_ID
        cls.universal_skill_id = content.UNIVERSAL_SKILL_ID
        cls.item_schema_version = content.ITEM_SCHEMA_VERSION
        cls.package_version = content.PACKAGE_VERSION
        cls.catalogue_version = content.CATALOGUE_VERSION
        cls.feature_version = content.FEATURE_VERSION
        cls.mapping_version = content.MAPPING_VERSION
        cls.model_version = content.MODEL_VERSION
        cls.policy_version = content.POLICY_VERSION
        cls.scoring_version = content.SCORING_VERSION
        cls.equivalence_version = content.EQUIVALENCE_VERSION
        cls.skills = content.SKILLS
        cls.generate_item = staticmethod(content.generate_item)
        cls.infer_belief = staticmethod(content.infer_belief)
        cls.scaffold_decision = staticmethod(content.scaffold_decision)
        cls.package_hash = staticmethod(content.package_hash)
        cls.validate_constructed_response = staticmethod(content.validate_constructed_response)

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._support_rounds = SupportRoundService(SINHALA_BUILDERS)

    # --- Public material -------------------------------------------------------------------

    def _public_game_data(self, item) -> dict[str, object]:  # type: ignore[no-untyped-def,override]
        public = self.content.public_game_data(item)
        if item.measurement_role == "unsupported_before":
            family = str(item.game_data["subfamily"])
            public["opening_demonstration"] = _opening_demonstration(self.content, item.skill_id, family)
        return public

    def _response(self, state: dict[str, object], item) -> dict[str, object]:  # type: ignore[no-untyped-def,override]
        # The opening demonstration is exposure: it is recorded once, at the before item.
        if item.measurement_role == "unsupported_before" and not state.get("demonstration_ledger"):
            demo = _opening_demonstration(self.content, item.skill_id, str(item.game_data["subfamily"]))
            state["demonstration_ledger"] = [
                {
                    "demonstration_id": demo["demonstration_id"],
                    "source_locators": demo["source_locators"],
                    "excluded_from_probe_pool": True,
                    "exposed_at_presentation_id": state["presentations"][-1]["presentation_id"],  # type: ignore[index]
                }
            ]
            # The store persists one event at open, so the exposure rides on it.
            state["events"][-1]["details"]["demonstration_id"] = demo["demonstration_id"]  # type: ignore[index]
        return super()._response(state, item)

    # --- Scoring ---------------------------------------------------------------------------

    def _score(
        self,
        state: dict[str, object],
        item: dict[str, object],
        option_id: str | None,
        constructed_response: Mapping[str, object] | None,
        response_time_ms: int | None,
        at: datetime,
    ) -> dict[str, object]:
        if constructed_response is None or option_id is not None:
            raise NumberWorldFlowError("MALFORMED_RESPONSE")
        if constructed_response.get("interaction_version") != "constructed-response-v1":
            raise NumberWorldFlowError("SCHEMA_MISMATCH")
        if constructed_response.get("presentation_id") != item["presentation_id"]:
            raise NumberWorldFlowError("STALE_OR_INCOMPATIBLE_MANIFEST")
        if constructed_response.get("item_revision_id") != item["revision_id"]:
            raise NumberWorldFlowError("REVISION_MISMATCH")
        payload = {
            key: value
            for key, value in constructed_response.items()
            if key not in {"presentation_id", "item_revision_id", "interaction_version"}
        }
        try:
            correct, code, normalized = self.content.validate_constructed_response(item, payload)
        except self.content.ResponseError as error:
            raise NumberWorldFlowError(error.code) from error
        except (TypeError, ValueError, KeyError) as error:
            raise NumberWorldFlowError("MALFORMED_RESPONSE") from error
        return {
            "attempt_id": str(uuid4()),
            "presentation_id": item["presentation_id"],
            "revision_id": item["revision_id"],
            "role": item["role"],
            "assistance_state": "none",
            "selected_option_id": "constructed-response",
            "constructed_response": normalized,
            "structured_error_code": code,
            "semantic_error_code": normalized.get("semantic_error"),
            "earned_score": "1" if correct else "0",
            "maximum_score": "1",
            "rubric_version": f"{item['skill_id']}:{item['game_data']['subfamily']}:rubric-v1",  # type: ignore[index]
            "scoring_version": self.scoring_version,
            "server_authoritative": True,
            "correct": correct,
            "response_time_ms": response_time_ms,
            "scored_at": at.isoformat(),
        }

    def _summary(self, state: dict[str, object]) -> dict[str, object]:  # type: ignore[override]
        response = NumberWorldFlow._summary(state)
        score = response.get("server_score")
        attempts = state.get("attempts")
        if isinstance(score, dict) and isinstance(attempts, list) and attempts:
            latest = attempts[-1]
            item = next(
                row for row in state["presentations"]  # type: ignore[union-attr]
                if row["presentation_id"] == latest["presentation_id"]
            )
            score["feedback_si"] = _feedback(self.content, latest, item)
            reveal = _reveal_key(self.content, latest, item)
            if reveal is not None:
                score["reveal_key"] = reveal
        return response

    # --- Interaction evidence --------------------------------------------------------------

    @staticmethod
    def _validate_interaction_summary(summary: Mapping[str, object] | None) -> Mapping[str, object]:
        result = dict(summary or {})
        counts = {
            "move_count", "correction_count", "swap_count", "cancelled_drag_count", "skip_count",
            "replay_count", "first_action_ms", "active_time_ms", "wall_time_ms", "inactive_time_ms",
        }
        allowed = counts | {"input_mode", "rendering_issue_reported"}
        if not set(result) <= allowed or len(result) > 12:
            raise NumberWorldFlowError("PII_OR_ANSWER_DATA_REJECTED")
        for key, value in result.items():
            if key == "input_mode":
                if value not in {"drag", "tap", "keyboard", "mixed"}:
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif key == "rendering_issue_reported":
                if type(value) is not bool:
                    raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
            elif type(value) is not int or not 0 <= value <= 86_400_000:
                raise NumberWorldFlowError("PAYLOAD_OUT_OF_BOUNDS")
        return result

    @staticmethod
    def _missingness(
        response_time_ms: int | None, summary: Mapping[str, object] | None
    ) -> list[str]:
        missing = [] if response_time_ms is not None else ["response_time_ms"]
        for key in ("move_count", "correction_count", "first_action_ms", "active_time_ms"):
            if key not in (summary or {}):
                missing.append(key)
        return missing

    def _infer_belief(
        self,
        error_code: str,
        *,
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None,
    ) -> dict[str, object]:
        # Timing is optional (accommodations): it never makes evidence sparse or penalised.
        del response_time_ms
        return self.content.infer_belief(error_code, interaction_summary=interaction_summary)

    # --- Model 2 ---------------------------------------------------------------------------

    def _start_support_loop(
        self,
        state: dict[str, object],
        belief: Mapping[str, object],
        content_decision: Mapping[str, object],
        at: datetime,
        *,
        evidence_id: UUID,
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object],
    ) -> dict[str, object]:
        learner_id = UUID(str(state["learner_id"]))
        history = self._store.support_history(learner_id=learner_id, skill_id=str(state["skill_id"]))
        own_history = tuple(row for row in history if row.get("experience_id") == self.experience_id)
        state["difficulty_evidence"] = _difficulty_evidence(state, interaction_summary, own_history)
        context = self._support_context(state, at)
        eligible = tuple(s for s in assignment(self.area_id).eligible_support_types if s in AUTHORED_SEQUENCE)
        plans = self._support_rounds.renderable_plans(context, eligible)
        proposed = state["condition"] == "proposed"
        try:
            decision = choose_support_order(
                subject="SIN",
                condition=str(state["condition"]),
                model1_label=_model1_label(belief),
                model1_uncertain=_model1_uncertain(belief),
                eligible=eligible,
                renderable=tuple(plans),
                # Baseline never reads outcomes, so it can never learn from IG.
                history=own_history if proposed else (),
                learning_state_input=read_learning_state(
                    self._support_need_provider, learner_id=learner_id,
                    skill_id=self.universal_skill_id,
                    session_id=str(state.get("learning_state_session_id", state["session_id"])), at=at,
                ),
            )
        except ValueError as error:
            raise NumberWorldFlowError(str(error)) from error
        cursor = _support_cursor(own_history, proposed=proposed)
        authored = tuple(s for s in AUTHORED_SEQUENCE if s in plans)
        start = cursor["next_position"] % len(authored)
        rotated = authored[start:] + authored[:start]
        learned = decision.selection_mode == "learned_post_withdrawal_preference"
        if not proposed:
            order, reason = authored, "activity_default"
        elif learned and not cursor["preference_failed"]:
            order, reason = decision.order, "learned_activity_preference"
        elif cursor["unresolved"]:
            order, reason = rotated, "activity_support_escalation"
        else:
            order, reason = rotated, "activity_default"
        decision = replace(decision, order=tuple(order))
        cursor_record = {
            "cursor_version": CURSOR_VERSION,
            "authored_sequence": list(authored),
            "start_position": authored.index(order[0]),
            **cursor,
        }
        state["support_cursor"] = cursor_record
        state["model2"] = {
            "decision_id": str(uuid4()),
            "context_snapshot_id": str(uuid4()),
            "context_version": self.context_version,
            "artifact_sha256": self.package_hash(),
            "created_at": at.isoformat(),
            "complete_model1_probabilities": belief["probabilities"],
            "model1_unknown_probability": belief.get("unknown_probability"),
            "difficulty_evidence_id": state["difficulty_evidence"]["evidence_id"],  # type: ignore[index]
            "missingness": self._missingness(response_time_ms, interaction_summary),
            "condition": state["condition"],
            "policy_version": self.policy_version,
            "model_selected_action": content_decision.get("selected_action"),
            "reference_decision": dict(content_decision),
            "eligible_actions": list(eligible),
            "excluded_actions": [
                {"scaffold_type": s, "reason": "NOT_IN_AREA_SUPPORT_CATALOGUE"}
                for s in content_decision.get("candidates", ())  # type: ignore[union-attr]
                if isinstance(s, Mapping) and s.get("scaffold_type") not in eligible
            ],
            "renderable_actions": list(plans),
            "support_cursor": cursor_record,
            "selection_reason": reason,
            "selection_reasons_by_position": [
                reason if index == 0 else "activity_support_escalation" for index in range(len(order))
            ],
            **decision.as_record(),
        }
        state["supported_correctness"] = None
        _event(state, "difficulty_detected", at, evidence_id=str(evidence_id))
        _event(state, "misconception_distribution_created", at)
        _event(state, "scaffold_decision_created", at, selection_reason=reason)
        first_plan = self._support_rounds.renderable_plans(
            self._support_context(state, at), (decision.first,)
        ).get(decision.first, plans[decision.first])
        self._support_rounds.start(state, decision, first_plan, at)
        _event(state, "support_exposed", at)
        response = self._summary(state)
        response["support"] = self._support_rounds.public_view(state, activity=self.support_activity)
        response["support_round"] = self._support_rounds.status(state, previous_attempt_correct=None)
        return response

    # --- Support delivery ------------------------------------------------------------------

    def submit_supported(
        self,
        episode_id: UUID,
        *,
        constructed_response: Mapping[str, object],
        response_time_ms: int | None,
        interaction_summary: Mapping[str, object] | None = None,
        idempotency_key: str,
    ) -> dict[str, object]:
        summary = self._validate_interaction_summary(interaction_summary)

        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            loop = state["support_loop"]
            current = loop["rounds"][-1]  # type: ignore[index]
            stage = current["stages"][current["stage_index"]]
            if stage.get("guidance") and int(summary.get("move_count", 0)) < 1:
                # Guided support counts only when the child actually acted.
                raise NumberWorldFlowError("GUIDED_ACTIONS_REQUIRED")
            item = self._support_rounds.current_item(state)
            score = self._score(state, item, None, constructed_response, response_time_ms, at)
            score.update(role="supported_practice", assistance_state="active", interaction_summary=dict(summary))
            status = self._support_rounds.record_attempt(
                state, score, lambda: self._support_context(state, at), at
            )
            response = self._summary(state)
            response.update(
                server_score={
                    "earned_score": score["earned_score"],
                    "maximum_score": score["maximum_score"],
                    "scoring_version": score["scoring_version"],
                    "server_authoritative": True,
                    "measurement_role": "supported_practice",
                    "correct": score["correct"],
                    "attempt_id": score["attempt_id"],
                    "presentation_id": score["presentation_id"],
                    "item_revision_id": score["revision_id"],
                    # Assisted material: immediate gentle correction is allowed here.
                    "feedback_si": self.content.feedback_si(item["game_data"], bool(score["correct"])),
                    **(
                        {"reveal_key": self.content.reveal_key(item["game_data"])}
                        if hasattr(self.content, "reveal_key")
                        else {}
                    ),  # type: ignore[arg-type]
                },
                support=self._support_rounds.public_view(state, activity=self.support_activity),
                support_round=status,
            )
            return response

        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": f"{self.operation_prefix}_supported_answer",
                "constructed_response": dict(constructed_response),
                "response_time_ms": response_time_ms,
                "interaction_summary": dict(summary),
            },
            "support_active",
            transition,
        )

    def _support_progress(
        self,
        episode_id: UUID,
        *,
        duration_ms: int,
        steps_viewed: int,
        manifest_revision_id: str,
        interaction_summary: Mapping[str, object],
        idempotency_key: str,
    ) -> dict[str, object]:
        """A worked demonstration ends only after the child pressed ඊළඟ through every step."""

        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            if interaction_summary.get("completed") is not True:
                raise NumberWorldFlowError("INVALID_SUPPORT_COMPLETION")
            current = state["support_loop"]["rounds"][-1]  # type: ignore[index]
            stage = current["stages"][current["stage_index"]]
            worked = stage.get("worked_example")
            authored = len(worked["steps_si"]) if isinstance(worked, Mapping) else 0
            presses = interaction_summary.get("next_presses")
            if type(presses) is not int or presses < authored or steps_viewed < authored:
                raise NumberWorldFlowError("SUPPORT_STEPS_NOT_OBSERVED")
            status = self._support_rounds.record_view_complete(
                state, manifest_revision_id, at, lambda: self._support_context(state, at)
            )
            current.setdefault("observed_views", []).append(
                {
                    "authored_steps": authored,
                    "steps_displayed": steps_viewed,
                    "next_presses": presses,
                    "duration_ms": duration_ms,
                    "recorded_at": at.isoformat(),
                }
            )
            response = self._summary(state)
            response.update(
                support=self._support_rounds.public_view(state, activity=self.support_activity),
                support_round=status,
            )
            return response

        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": f"{self.operation_prefix}_support_progress",
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
        teardown_receipt: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """The phone's booleans are not enough: its teardown receipt must name the same
        revisions and report nothing of the help left in the scene, the DOM or the listeners."""

        receipt = dict(teardown_receipt or {})
        if not receipt:
            raise NumberWorldFlowError("TEARDOWN_RECEIPT_REQUIRED")
        if (
            receipt.get("receipt_version") != TEARDOWN_RECEIPT_VERSION
            or receipt.get("support_revision_id") != support_revision_id
            or receipt.get("manifest_revision_id") != manifest_revision_id
            or any(receipt.get(key) != 0 for key in _TEARDOWN_ZERO_COUNTS)
            or any(receipt.get(key) is not True for key in _TEARDOWN_TRUE_FLAGS)
        ):
            raise NumberWorldFlowError("INVALID_TEARDOWN_RECEIPT")
        def transition(state: dict[str, object], at: datetime) -> dict[str, object]:
            # A simulated receipt is for synthetic development/test clients only; it never
            # stands in for teardown observed on a phone.
            simulated = receipt.get("source") == "simulated_client"
            if simulated and state["environment"] not in {"development", "test"}:
                raise NumberWorldFlowError("SIMULATED_TEARDOWN_NOT_ACCEPTED")
            exposure = state["scaffold_exposure"]
            assert isinstance(exposure, dict)
            if not (
                support_revision_id == exposure["revision_id"]
                and manifest_revision_id == exposure["manifest_revision_id"]
                and all_support_removed
                and answer_revealing_state_cleared
                and input_handlers_cleared
            ):
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
                "teardown_receipt": receipt,
                "teardown_observed_on_device": not simulated,
                "server_verified_at": at.isoformat(),
            }
            state["status"] = "support_withdrawn"
            _event(state, "support_withdrawn", at, teardown_receipt_version=TEARDOWN_RECEIPT_VERSION)
            return self._summary(state)

        return self._mutate(
            episode_id,
            idempotency_key,
            {
                "op": f"{self.operation_prefix}_withdraw",
                "request_id": str(request_id),
                "support_revision_id": support_revision_id,
                "manifest_revision_id": manifest_revision_id,
                "teardown_receipt": receipt,
            },
            "support_complete",
            transition,
        )

    # --- Model 3 equivalence ---------------------------------------------------------------

    @staticmethod
    def _additional_exclusions(
        state: dict[str, object], after_item: dict[str, object]
    ) -> list[str]:
        before = next(row for row in state["presentations"] if row["role"] == "unsupported_before")  # type: ignore[index]
        before_game, after_game = before["game_data"], after_item["game_data"]
        exclusions: list[str] = []
        if before_game["equivalence"] != {**after_game["equivalence"]}:
            exclusions.append("EQUIVALENCE_DIMENSIONS_MISMATCH")
        if not after_game["equivalence"].get("ig_available", False):
            exclusions.append("IG_UNAVAILABLE_INSUFFICIENT_REVIEWED_POOL")
        if before_game["rubric"] == after_game["rubric"] or before["item_id"] == after_item["item_id"]:
            exclusions.append("AFTER_SURFACE_ANSWER_NOT_FRESH")
        withdrawal = state.get("withdrawal")
        if not isinstance(withdrawal, Mapping) or not isinstance(withdrawal.get("teardown_receipt"), Mapping):
            exclusions.append("TEARDOWN_RECEIPT_MISSING")
        demos = {row["demonstration_id"] for row in state.get("demonstration_ledger") or ()}  # type: ignore[union-attr]
        if any(str(after_item["item_id"]).endswith(demo.split(":demo:")[-1].removesuffix("@v1")) and
               demo.split(":demo:")[0] == f"{after_item['skill_id']}:{after_game['subfamily']}" for demo in demos):
            exclusions.append("AFTER_ITEM_EXPOSED_AS_DEMONSTRATION")
        loop = state.get("support_loop")
        if isinstance(loop, Mapping):
            for round_record in loop.get("rounds", ()):  # type: ignore[union-attr]
                for stage in round_record.get("stages", ()):
                    worked = stage.get("worked_example")
                    if isinstance(worked, Mapping) and worked.get("revision_id") == after_item["revision_id"]:
                        exclusions.append("AFTER_ITEM_SEEN_DURING_SUPPORT")
        return exclusions

    # The shared single-help path is not used by these flows; kept for the source protocol.
    def _worked_example(  # type: ignore[override]
        self, item: dict[str, object], *, scaffold_type: str = "worked_parallel_example"
    ) -> dict[str, object]:
        game = dict(item["game_data"])  # type: ignore[arg-type]
        return {
            "mode": "exact_failed_activity",
            "prompt_si": item["prompt_si"],
            "game": {"schema_version": self.item_schema_version, "skill_id": item["skill_id"]},
            "correct_response": self.content.correct_response(game),
            "steps_si": self.content.worked_steps(game, scaffold_type, str(item["skill_id"])),
        }


def _opening_demonstration(content: ModuleType, skill_id: str, family: str) -> dict[str, object]:
    demo = content.opening_demonstration(skill_id, family)
    if demo is None:
        raise NumberWorldFlowError("SINHALA_UNREVIEWED_DEMONSTRATION")
    return {
        **demo,
        "steps_si": list(content.support_copy(skill_id, family)["worked"]),
        "advance_label_si": "ඊළඟ",
    }


def _feedback(content: ModuleType, attempt: Mapping[str, object], item: Mapping[str, object]) -> str:
    """Before-item explanations stay non-revealing while the after probe is reserved."""

    correct = bool(attempt.get("correct"))
    if attempt.get("role") == "unsupported_before":
        return "හරි! නියමයි 🎉" if correct else "කමක් නැහැ. අපි එකට බලමු 🌱"
    return content.feedback_si(item["game_data"], correct)  # type: ignore[no-any-return]


def _reveal_key(content: ModuleType, attempt: Mapping[str, object], item: Mapping[str, object]) -> str | None:
    """A reveal is allowed once it can no longer teach a reserved probe: never for the before item."""

    if attempt.get("role") == "unsupported_before" or not hasattr(content, "reveal_key"):
        return None
    return str(content.reveal_key(item["game_data"]))


def _difficulty_evidence(
    state: Mapping[str, object],
    summary: Mapping[str, object],
    history: tuple[Mapping[str, object], ...],
) -> dict[str, object]:
    """Raw evidence first, then the derived difficulty, its rule and why help is eligible."""

    before = next(row for row in state["attempts"] if row["role"] == "unsupported_before")  # type: ignore[union-attr]
    recent_failures = sum(
        1
        for episode in history[-5:]
        for attempt in episode.get("attempts") or ()
        if attempt.get("role") in {"unsupported_before", "unsupported_after"} and not attempt.get("correct")
    )
    corrections = int(summary.get("correction_count", 0) or 0)
    severity = "high" if recent_failures >= 2 else "moderate"
    return {
        "evidence_id": str(uuid4()),
        "rule_version": DIFFICULTY_RULE_VERSION,
        "thresholds": {"incorrect_unsupported_before": 1, "high_after_recent_failures": 2},
        "raw": {
            "incorrect_response": before.get("constructed_response"),
            "semantic_error": before.get("semantic_error_code"),
            "interaction_summary": dict(summary),
            "response_time_ms": before.get("response_time_ms"),
            "recent_same_skill_failures": recent_failures,
        },
        "contributing_attempt_ids": [before["attempt_id"]],
        "severity": severity,
        "confidence": 0.6 if corrections < 3 else 0.4,
        "eligibility_reason": "unsupported_before_incorrect",
        # Timing never enters severity: accommodations must not be penalised.
        "timing_used_for_severity": False,
    }


def _support_cursor(history: tuple[Mapping[str, object], ...], *, proposed: bool) -> dict[str, object]:
    """Where the authored help sequence resumes for this learner and skill.

    Only completed episodes with a recorded withdrawn after-score move it; invalidated episodes
    are never in the history and so never move it. Baseline always starts at the beginning.
    """

    if not proposed:
        return {"next_position": 0, "unresolved": False, "preference_failed": False,
                "source_episode_id": None}
    for episode in reversed(history):
        cursor = episode.get("support_cursor")
        measurement = episode.get("measurement")
        if not isinstance(cursor, Mapping) or not isinstance(measurement, Mapping):
            continue
        failed = str(measurement.get("after_earned")) == "0"
        start = int(cursor.get("start_position", 0))
        model2 = episode.get("model2") or {}
        return {
            "next_position": start + 1 if failed else start,
            "unresolved": failed,
            "preference_failed": failed and model2.get("selection_reason") == "learned_activity_preference",
            "source_episode_id": episode.get("episode_id"),
        }
    return {"next_position": 0, "unresolved": False, "preference_failed": False, "source_episode_id": None}


__all__ = ["SINHALA_BUILDERS", "SinhalaPackageFlow"]
