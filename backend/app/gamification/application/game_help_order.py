"""The games' help order in the proposed condition, and what each episode teaches the bandit.

The bandit chooses only when its subject has an approved artifact. Without one, the episode gets
the subject's fixed order, exactly as the baseline condition does, and records why. Every valid
proposed episode that the bandit ordered teaches the subject's shared bandit once, whichever child
played it. Baseline and invalid episodes teach it nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.gamification.modeling.support_selection.game_bandit import (
    CREDIT_RULE_VERSION,
    GAME_POLICY_VERSION,
    GameHelpBandit,
    learning_state_of,
)
from app.gamification.modeling.support_selection.game_bandit_ledger import (
    DecisionSnapshot,
    LedgerEntry,
    ledger_entries,
    snapshot_of,
)
from app.gamification.modeling.support_selection.support_order import SUBJECT_ORDERS

BANDIT_GREEDY = "bandit_greedy"
NO_APPROVED_POLICY = "no_approved_policy"


@dataclass(frozen=True)
class ApprovedGameHelpBandit:
    model_version_id: UUID
    artifact_sha256: str
    ledger_position: int
    bandit: GameHelpBandit


@dataclass(frozen=True)
class StoredDecisionSnapshot:
    snapshot_id: UUID
    model_version_id: UUID
    snapshot: DecisionSnapshot


class GameHelpBanditStore(Protocol):
    def approved(self, subject: str) -> ApprovedGameHelpBandit | None: ...

    def save_snapshot(
        self,
        *,
        episode_id: UUID,
        model_version_id: UUID,
        snapshot: DecisionSnapshot,
        now: datetime,
    ) -> UUID: ...

    def snapshot_for(self, episode_id: UUID) -> StoredDecisionSnapshot | None: ...

    def apply(
        self,
        *,
        model_version_id: UUID,
        snapshot_id: UUID,
        entries: Sequence[LedgerEntry],
        now: datetime,
    ) -> int: ...


@dataclass(frozen=True)
class GameHelpOrderChoice:
    order: tuple[str, ...]
    selection_mode: str
    reason_family: str | None = None
    predicted_gain: Mapping[str, float] = field(default_factory=dict)
    model_version_id: UUID | None = None
    artifact_sha256: str | None = None
    ledger_position: int | None = None
    snapshot_id: UUID | None = None

    @property
    def first(self) -> str:
        return self.order[0]

    def as_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "support_order": list(self.order),
            "selected_action": self.first,
            "support_selection_mode": self.selection_mode,
            "reason_family": self.reason_family,
        }
        if self.selection_mode == BANDIT_GREEDY:
            record.update(
                order_policy_version=GAME_POLICY_VERSION,
                credit_rule_version=CREDIT_RULE_VERSION,
                predicted_gain=dict(self.predicted_gain),
                model_version_id=str(self.model_version_id),
                artifact_sha256=self.artifact_sha256,
                ledger_position=self.ledger_position,
                snapshot_id=str(self.snapshot_id),
            )
        return record


def fixed_order(
    subject: str, eligible: Iterable[str], renderable: Iterable[str]
) -> tuple[str, ...]:
    """The subject's fixed order restricted to the helps this area offers and can draw."""

    offered, drawable = set(eligible), set(renderable)
    order = tuple(
        support for support in SUBJECT_ORDERS[subject] if support in offered and support in drawable
    )
    if not order:
        raise ValueError("NO_RENDERABLE_SUPPORT")
    return order


def choose_game_help_order(
    store: GameHelpBanditStore,
    *,
    subject: str,
    episode_id: UUID,
    model1_label: str | None,
    model1_uncertain: bool,
    learning_state_input: Mapping[str, object] | None,
    history: Sequence[Mapping[str, object]],
    eligible: Sequence[str],
    renderable: Sequence[str],
    now: datetime,
) -> GameHelpOrderChoice:
    """The proposed condition's order: the approved bandit's, or the fixed order without one."""

    approved = store.approved(subject)
    if approved is None:
        return GameHelpOrderChoice(
            order=fixed_order(subject, eligible, renderable),
            selection_mode=NO_APPROVED_POLICY,
        )
    chosen = approved.bandit.order(
        model1_label=model1_label,
        model1_uncertain=model1_uncertain,
        learning_state_input=learning_state_input,
        history=history,
        eligible=eligible,
        renderable=renderable,
    )
    snapshot = snapshot_of(
        chosen,
        subject=subject,
        inputs={
            "model1_label": model1_label,
            "model1_uncertain": model1_uncertain,
            "reason_family": chosen.reason_family,
            "learning_state_input": dict(learning_state_input or {}),
            "learning_state": learning_state_of(learning_state_input),
            "eligible": list(eligible),
            "renderable": list(renderable),
            "history_episode_ids": [str(episode["episode_id"]) for episode in history],
        },
    )
    snapshot_id = store.save_snapshot(
        episode_id=episode_id,
        model_version_id=approved.model_version_id,
        snapshot=snapshot,
        now=now,
    )
    return GameHelpOrderChoice(
        order=chosen.order,
        selection_mode=BANDIT_GREEDY,
        reason_family=chosen.reason_family,
        predicted_gain=chosen.predicted_gain,
        model_version_id=approved.model_version_id,
        artifact_sha256=approved.artifact_sha256,
        ledger_position=approved.ledger_position,
        snapshot_id=snapshot_id,
    )


def learn_from_episode(
    store: GameHelpBanditStore, state: Mapping[str, object], *, now: datetime
) -> str:
    """Teach the subject's bandit one finished episode, once. Returns what happened."""

    if state.get("condition") != "proposed":
        return "baseline_condition"
    if state.get("validity") != "valid":
        return "not_valid"
    stored = store.snapshot_for(UUID(str(state["episode_id"])))
    if stored is None:
        return "no_bandit_decision"
    approved = store.approved(stored.snapshot.subject)
    if approved is None or approved.model_version_id != stored.model_version_id:
        return "artifact_replaced"
    entries = ledger_entries(state, snapshot=stored.snapshot, settings=approved.bandit.settings)
    if not entries:
        return "nothing_to_credit"
    applied = store.apply(
        model_version_id=stored.model_version_id,
        snapshot_id=stored.snapshot_id,
        entries=entries,
        now=now,
    )
    return "applied" if applied else "already_applied"
