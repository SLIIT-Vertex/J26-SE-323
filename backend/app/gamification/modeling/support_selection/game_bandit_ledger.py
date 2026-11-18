"""What the games' help-order bandit keeps, and how its learned state is rebuilt from it.

A decision snapshot keeps the context vector of every help the bandit scored (non-zero features
only) together with the inputs they came from. A ledger entry is one credit-rule observation,
applied in its snapshot's context. The learned state is always the approved artifact with the
ledger applied in order, so it can be rebuilt and audited at any time.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.gamification.modeling.support_selection.context import (
    GAME_CONTEXT_VERSION,
    BanditContext,
)
from app.gamification.modeling.support_selection.game_bandit import (
    FEATURE_NAMES,
    GameHelpBandit,
    HelpOrder,
    episode_observations,
)

ROLES = ("credited", "failed_round")


def canonical_sha256(value: object) -> str:
    """SHA-256 of the value as stored, whatever the database does to its numbers.

    PostgreSQL's JSONB keeps numbers as decimals: it returns ``-0.0`` as ``0`` and a large float
    as an integer. Every number is hashed as a float, with ``-0.0`` as ``0.0``, so a stored state
    keeps its hash.
    """

    text = json.dumps(
        _numbers_as_floats(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _numbers_as_floats(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int | float):
        number = float(value)
        return 0.0 if number == 0 else number
    if isinstance(value, Mapping):
        return {str(key): _numbers_as_floats(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_numbers_as_floats(item) for item in value]
    raise TypeError(f"cannot hash {type(value).__name__}")


@dataclass(frozen=True)
class DecisionSnapshot:
    subject: str
    context_version: str
    inputs: Mapping[str, object]
    vectors: Mapping[str, Mapping[str, float]]
    predicted_gain: Mapping[str, float]

    def context(self, support: str) -> BanditContext:
        """The full context vector this help was scored with."""

        if self.context_version != GAME_CONTEXT_VERSION:
            raise ValueError(f"snapshot uses another context: {self.context_version}")
        if support not in self.vectors:
            raise ValueError(f"{support} was not scored in this decision")
        values = self.vectors[support]
        unknown = set(values) - set(FEATURE_NAMES)
        if unknown:
            raise ValueError(f"snapshot has unknown features {sorted(unknown)}")
        return BanditContext(
            self.context_version,
            FEATURE_NAMES,
            tuple(float(values.get(name, 0.0)) for name in FEATURE_NAMES),
            {},
        )

    def as_record(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "context_version": self.context_version,
            "inputs": dict(self.inputs),
            "vectors": {support: dict(values) for support, values in self.vectors.items()},
            "predicted_gain": dict(self.predicted_gain),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> DecisionSnapshot:
        vectors = record["vectors"]
        assert isinstance(vectors, Mapping)
        return cls(
            subject=str(record["subject"]),
            context_version=str(record["context_version"]),
            inputs=dict(record["inputs"]),  # type: ignore[call-overload]
            vectors={
                str(support): {str(name): float(value) for name, value in values.items()}
                for support, values in vectors.items()
            },
            predicted_gain={
                str(support): float(value)
                for support, value in record["predicted_gain"].items()  # type: ignore[union-attr]
            },
        )


def snapshot_of(
    order: HelpOrder, *, subject: str, inputs: Mapping[str, object]
) -> DecisionSnapshot:
    return DecisionSnapshot(
        subject=subject,
        context_version=GAME_CONTEXT_VERSION,
        inputs=dict(inputs),
        vectors={
            support: {
                name: value
                for name, value in zip(context.names, context.values, strict=True)
                if value != 0.0
            }
            for support, context in order.contexts.items()
        },
        predicted_gain=dict(order.predicted_gain),
    )


@dataclass(frozen=True)
class LedgerEntry:
    episode_id: str
    support: str
    role: str
    score: float
    weight: float
    credit_rule_version: str

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"unknown observation role {self.role}")


def ledger_entries(
    state: Mapping[str, object],
    *,
    snapshot: DecisionSnapshot,
    settings: Mapping[str, object],
) -> tuple[LedgerEntry, ...]:
    """The episode's credit-rule observations, in the artifact's settings.

    Every shown help was scored in the decision, so one that was not is a defect, not something
    to skip.
    """

    observations = episode_observations(
        state,
        failed_round_weight=float(settings["failed_round_weight"]),  # type: ignore[arg-type]
    )
    entries = []
    for observation in observations:
        if observation.support not in snapshot.vectors:
            raise ValueError(f"{observation.support} was shown but not scored in the decision")
        entries.append(
            LedgerEntry(
                episode_id=str(state["episode_id"]),
                support=observation.support,
                role=observation.role,
                score=observation.score,
                weight=observation.weight,
                credit_rule_version=str(settings["credit_rule_version"]),
            )
        )
    return tuple(entries)


def apply_entry(bandit: GameHelpBandit, entry: LedgerEntry, snapshot: DecisionSnapshot) -> None:
    """The one update both live learning and replay use."""

    if entry.credit_rule_version != bandit.settings["credit_rule_version"]:
        raise ValueError("the ledger entry follows another credit rule")
    bandit.policy.update(snapshot.context(entry.support), entry.support, entry.score, entry.weight)


def replay(
    parameters: Mapping[str, object],
    entries: Iterable[tuple[LedgerEntry, DecisionSnapshot]],
) -> GameHelpBandit:
    """The approved artifact with the ledger applied in order."""

    bandit = GameHelpBandit.from_parameters(parameters)
    for entry, snapshot in entries:
        apply_entry(bandit, entry, snapshot)
    return bandit
