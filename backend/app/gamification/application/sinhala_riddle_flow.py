"""Durable G5-AREA-SIN-03 Riddle Journey profile on the shared Sinhala package flow.

The riddle pool is small and its answers repeat (riddles 1 and 17 are both කොකා), so freshness
is decided per learner: before an episode is opened, every answer family this learner has had
revealed in any earlier SIN-03 episode (probe, support, demonstration; any status) is excluded
from its probes. When no fresh pair remains the episode runs as practice and its measurement is
recorded as unavailable.
"""

from __future__ import annotations

from uuid import UUID

from app.gamification.application.number_world_flow import NumberWorldFlowError
from app.gamification.application.sinhala_package_flow import SinhalaPackageFlow
from app.gamification.content import sinhala_riddles

EXPOSURE_RULE_VERSION = "g5-sin-riddles-exposure-v1"


class SinhalaRiddleFlow(SinhalaPackageFlow):
    experience_id = "sinhala_riddle_journey"
    contract_version = "sinhala-riddle-learning-flow-v1"
    context_version = "g5-sin-riddles-context-v1"
    measurement_version = "sinhala-riddle-independence-measurement-v1"
    missing_skill_error = "SINHALA_RIDDLE_SKILL_NOT_FOUND"
    episode_type_error = "SINHALA_RIDDLE_EPISODE_REQUIRED"
    operation_prefix = "sinhala_riddle"

    def _history(self, learner_id: UUID) -> tuple[dict[str, object], ...]:
        query = getattr(self._store, "exposure_history", None)
        if query is not None:
            rows = query(learner_id=learner_id, skill_ids=tuple(self.skills))
        else:
            rows = tuple(
                row for skill in self.skills for row in self._store.support_history(learner_id=learner_id, skill_id=skill)
            )
        return tuple(row for row in rows if row.get("experience_id") == self.experience_id)

    def _exposure(self, learner_id: UUID) -> tuple[set[str], set[str]]:
        revealed: set[str] = set()
        distractor_only: set[str] = set()
        for row in self._history(learner_id):
            skill, seed = str(row["skill_id"]), int(row["seed"])  # type: ignore[call-overload]
            revealed |= sinhala_riddles.revealed_families(skill, seed)
            distractor_only |= sinhala_riddles.episode_families(skill, seed)
        return revealed, distractor_only - revealed

    def _episode_seed(self, *, learner_id: UUID, session_id: UUID, atomic_skill_id: str) -> int:
        base = super()._episode_seed(learner_id=learner_id, session_id=session_id, atomic_skill_id=atomic_skill_id)
        revealed, _ = self._exposure(learner_id)
        # An earlier after probe is never reserved again, fresh pool or not.
        reserved_after = {
            sinhala_riddles.probe_riddles(str(row["skill_id"]), int(row["seed"]))[2]  # type: ignore[call-overload]
            for row in self._history(learner_id)
            if row["skill_id"] == atomic_skill_id
        }
        try:
            seed, _fresh = sinhala_riddles.fresh_seed(
                atomic_skill_id, base, revealed, reserved_after=reserved_after
            )
        except ValueError as error:
            raise NumberWorldFlowError(str(error)) from error
        return seed

    def _response(self, state: dict[str, object], item) -> dict[str, object]:  # type: ignore[no-untyped-def,override]
        if item.measurement_role == "unsupported_before" and "exposure_check" not in state:
            learner = UUID(str(state["learner_id"]))
            revealed, distractor_only = self._exposure(learner)
            # The episode being opened is not in the history yet, so this is prior exposure only.
            _, before, after = sinhala_riddles.probe_riddles(str(state["skill_id"]), int(state["seed"]))  # type: ignore[call-overload]
            probes = {sinhala_riddles.family_of(before), sinhala_riddles.family_of(after)}
            state["exposure_check"] = {
                "rule_version": EXPOSURE_RULE_VERSION,
                "probe_answer_families": sorted(probes),
                "previously_revealed_families": sorted(revealed),
                "previously_seen_as_distractor_only": sorted(distractor_only),
                "fresh": not probes & revealed,
                # Seeing an answer only as a distractor is recorded, not treated as a reveal.
                "distractor_exposure_of_probes": sorted(probes & distractor_only),
            }
        return super()._response(state, item)

    @staticmethod
    def _additional_exclusions(state: dict[str, object], after_item: dict[str, object]) -> list[str]:
        exclusions = SinhalaPackageFlow._additional_exclusions(state, after_item)
        check = state.get("exposure_check")
        if not isinstance(check, dict) or check.get("fresh") is not True:
            exclusions.append("PROBE_POOL_EXHAUSTED_OR_PREVIOUSLY_REVEALED")
        return exclusions


SinhalaRiddleFlow.bind(sinhala_riddles)
