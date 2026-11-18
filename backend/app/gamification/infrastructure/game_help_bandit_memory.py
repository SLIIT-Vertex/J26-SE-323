"""The games' help-order bandit store without a database, for flow tests and local runs.

It keeps the same rules as the database store: one approved artifact per subject, one snapshot
per episode, each episode applied once, and a learned state that is always the artifact with the
ledger applied in order.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from app.gamification.application.game_help_order import (
    ApprovedGameHelpBandit,
    StoredDecisionSnapshot,
)
from app.gamification.modeling.support_selection.game_bandit import (
    GameHelpBandit,
    load_game_help_bandit,
)
from app.gamification.modeling.support_selection.game_bandit_ledger import (
    DecisionSnapshot,
    LedgerEntry,
    apply_entry,
    canonical_sha256,
    replay,
)


class InMemoryGameHelpBanditStore:
    def __init__(self) -> None:
        self._artifacts: dict[UUID, dict[str, object]] = {}
        self._approved: dict[str, UUID] = {}
        self._states: dict[UUID, dict[str, object]] = {}
        self._snapshots: dict[UUID, StoredDecisionSnapshot] = {}
        self._snapshot_episodes: dict[UUID, UUID] = {}
        self._ledger: dict[UUID, list[tuple[LedgerEntry, UUID]]] = {}

    @classmethod
    def with_expert_start(cls, *subjects: str) -> InMemoryGameHelpBanditStore:
        """A store whose subjects each have their expert-initialised artifact approved."""

        store = cls()
        for subject in subjects:
            store.approve(load_game_help_bandit(subject), approved_by="test")
        return store

    def approve(self, bandit: GameHelpBandit, *, approved_by: str) -> UUID:
        if not approved_by.strip():
            raise ValueError("APPROVER_REQUIRED")
        parameters = bandit.parameters()
        model_version_id = uuid4()
        self._artifacts[model_version_id] = {
            "subject": bandit.subject,
            "parameters": parameters,
            "artifact_sha256": canonical_sha256(parameters),
            "approved_by": approved_by,
        }
        self._approved[bandit.subject] = model_version_id
        self._states[model_version_id] = {"ledger_position": 0, "parameters": parameters}
        self._ledger[model_version_id] = []
        return model_version_id

    def approved(self, subject: str) -> ApprovedGameHelpBandit | None:
        model_version_id = self._approved.get(subject)
        if model_version_id is None:
            return None
        state = self._states[model_version_id]
        return ApprovedGameHelpBandit(
            model_version_id=model_version_id,
            artifact_sha256=str(self._artifacts[model_version_id]["artifact_sha256"]),
            ledger_position=int(state["ledger_position"]),  # type: ignore[call-overload]
            bandit=GameHelpBandit.from_parameters(state["parameters"]),  # type: ignore[arg-type]
        )

    def save_snapshot(
        self,
        *,
        episode_id: UUID,
        model_version_id: UUID,
        snapshot: DecisionSnapshot,
        now: datetime,
    ) -> UUID:
        del now
        existing = self.snapshot_for(episode_id)
        if existing is not None:
            if canonical_sha256(existing.snapshot.as_record()) != canonical_sha256(
                snapshot.as_record()
            ):
                raise ValueError("SNAPSHOT_CONFLICT")
            return existing.snapshot_id
        snapshot_id = uuid4()
        self._snapshots[snapshot_id] = StoredDecisionSnapshot(
            snapshot_id=snapshot_id, model_version_id=model_version_id, snapshot=snapshot
        )
        self._snapshot_episodes[episode_id] = snapshot_id
        return snapshot_id

    def snapshot_for(self, episode_id: UUID) -> StoredDecisionSnapshot | None:
        snapshot_id = self._snapshot_episodes.get(episode_id)
        return None if snapshot_id is None else self._snapshots[snapshot_id]

    def apply(
        self,
        *,
        model_version_id: UUID,
        snapshot_id: UUID,
        entries: Sequence[LedgerEntry],
        now: datetime,
    ) -> int:
        del now
        if not entries:
            return 0
        ledger = self._ledger[model_version_id]
        episode = entries[0].episode_id
        if any(entry.episode_id == episode for entry, _ in ledger):
            return 0
        stored = self._snapshots[snapshot_id]
        if stored.model_version_id != model_version_id:
            raise ValueError("SNAPSHOT_FROM_ANOTHER_ARTIFACT")
        state = self._states[model_version_id]
        bandit = GameHelpBandit.from_parameters(state["parameters"])  # type: ignore[arg-type]
        for entry in entries:
            apply_entry(bandit, entry, stored.snapshot)
            ledger.append((entry, snapshot_id))
        state["parameters"] = bandit.parameters()
        state["ledger_position"] = len(ledger)
        return len(entries)

    def ledger(self, model_version_id: UUID) -> tuple[tuple[int, LedgerEntry, UUID], ...]:
        return tuple(
            (position, entry, snapshot_id)
            for position, (entry, snapshot_id) in enumerate(self._ledger[model_version_id], 1)
        )

    def replay_matches(self, model_version_id: UUID) -> bool:
        rebuilt = replay(
            self._artifacts[model_version_id]["parameters"],  # type: ignore[arg-type]
            (
                (entry, self._snapshots[snapshot_id].snapshot)
                for entry, snapshot_id in self._ledger[model_version_id]
            ),
        )
        return canonical_sha256(rebuilt.parameters()) == canonical_sha256(
            self._states[model_version_id]["parameters"]
        )
