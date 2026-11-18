"""Model 2 for the games: a LinUCB help-order bandit per subject, started from the expert gains.

The bandit runs greedily (``alpha = 0``, ``epsilon_min = 0``): it always offers the help with the
highest predicted valid Independence Gain first, and no child is given a help only so the model can
learn. Each help type is a ridge regression over ``area-bandit-context-v1``:

- which cell of the expert table the episode is in (reason family × Model 1 uncertain × Learning
  State), plus the matching reason, certainty and Learning State indicators, so evidence in one cell
  partly carries to related cells;
- this child's own record with that help on this skill, whether the child's previous episode on the
  skill moved on from that help, and how often the child needed help on the skill.

The expert gains are the prior mean and ``prior_strength`` its weight, so with no data the order is
today's. The child's own features are 0 until the child has a record, so they leave that start
untouched. Every learned value comes from valid Independence Gain through ``episode_observations``;
supported success is never a reward. All gains and weights are provisional expert assumptions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from app.gamification.content.support_types import SUPPORT_TYPES
from app.gamification.modeling.shared.expert_data import (
    EXPERT_MODEL_DATA_DIRECTORY,
    read_expert_manifest,
    read_verified_expert_file,
)
from app.gamification.modeling.support_selection.context import (
    GAME_CONTEXT_VERSION,
    BanditContext,
)
from app.gamification.modeling.support_selection.learned_policy import LinUCBPolicy

GAME_POLICY_VERSION = "area-help-order-bandit-v1"
CREDIT_RULE_VERSION = "weighted-round-credit-v1"
# A help that failed while shown is weaker evidence than an unsupported measurement.
PROVISIONAL_FAILED_ROUND_WEIGHT = 0.5
# Features the expert data says nothing about start at 0, with this many times prior_strength as
# their precision, so they move only once there is plenty of evidence.
PROVISIONAL_UNINFORMED_PRECISION = 100.0
REASON_FAMILIES = ("representation", "procedure", "relation", "prerequisite", "unclear")
LEARNING_STATES = ("not_available", "calm", "confused", "disengaged")
MODEL1_STATES: tuple[tuple[str, bool], ...] = (
    *((family, False) for family in REASON_FAMILIES),
    ("unclear", True),
)
# Counts in the child's own record are capped, so one busy child cannot dominate the vector.
OWN_COUNT_CAP = 5
SUCCESS_OUTCOMES = frozenset({"succeeded", "supported_success"})

Role = Literal["credited", "failed_round"]


def _certainty(uncertain: bool) -> str:
    return "uncertain" if uncertain else "certain"


def cell_feature(family: str, uncertain: bool, learning_state: str) -> str:
    return f"cell:{family}:{_certainty(uncertain)}:{learning_state}"


CELL_FEATURES = tuple(
    cell_feature(family, uncertain, state)
    for family, uncertain in MODEL1_STATES
    for state in LEARNING_STATES
)
MAIN_EFFECT_FEATURES = (
    *(f"family:{family}" for family in REASON_FAMILIES),
    "model1:certain",
    "model1:uncertain",
    *(f"learning_state:{state}" for state in LEARNING_STATES),
)
OWN_SUCCESS_RATE = "own:independent_success_rate"
PREVIOUS_FIRST_NOT_TRANSFERRED = "previous_first_help_not_transferred"
CHILD_FEATURES = (
    "own:record_present",
    OWN_SUCCESS_RATE,
    "own:credited_episodes",
    "own:mean_gain",
    "own:did_not_help",
    PREVIOUS_FIRST_NOT_TRANSFERRED,
    "support_dependency:present",
    "support_dependency",
)
FEATURE_NAMES = (*CELL_FEATURES, *MAIN_EFFECT_FEATURES, *CHILD_FEATURES)


# --- Credit rule ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CreditObservation:
    """What the bandit learns about one help type from one finished episode."""

    support: str
    role: Role
    score: float
    weight: float
    independent: bool


def episode_observations(
    state: Mapping[str, object], *, failed_round_weight: float
) -> tuple[CreditObservation, ...]:
    """One finished episode's observations, at most one per help type.

    Only a valid proposed episode with a measured Independence Gain teaches the bandit. The help
    the loop ended on is scored with that gain at full weight; each help that failed while shown is
    scored 0 at ``failed_round_weight``. When every shown help failed and the child still answered
    right alone, no help can be credited and nothing is learned. Follow-up help after a wrong
    after-answer lives outside ``support_loop`` and is never read.
    """

    if state.get("condition") != "proposed" or state.get("validity") != "valid":
        return ()
    measurement = state.get("measurement")
    if not isinstance(measurement, Mapping):
        return ()
    gain = measurement.get("raw_independence_gain", state.get("raw_independence_gain"))
    maximum = Decimal(str(measurement.get("after_maximum", 0)))
    if gain is None or maximum <= 0:
        return ()
    independent = Decimal(str(measurement.get("after_earned", 0))) == maximum
    score = float(Decimal(str(gain)))
    loop = state.get("support_loop")
    if not isinstance(loop, Mapping) or "rounds" not in loop:
        # Episodes from before the multi-help loop showed one help.
        model2 = state.get("model2")
        support = model2.get("selected_action") if isinstance(model2, Mapping) else None
        if support not in SUPPORT_TYPES:
            return ()
        return (CreditObservation(str(support), "credited", score, 1.0, independent),)
    rounds = [
        row
        for row in loop.get("rounds") or []  # type: ignore[union-attr]
        if isinstance(row, Mapping) and row.get("scaffold_type") in SUPPORT_TYPES
    ]
    stop = loop.get("stop_reason")
    credited: str | None = None
    if stop == "support_viewed" and rounds:
        credited = str(rounds[-1]["scaffold_type"])
    elif stop != "order_exhausted":
        credited = next(
            (str(row["scaffold_type"]) for row in rounds if row.get("outcome") in SUCCESS_OUTCOMES),
            None,
        )
    if credited is None and independent:
        return ()
    observations = []
    if credited is not None:
        observations.append(CreditObservation(credited, "credited", score, 1.0, independent))
    if failed_round_weight > 0:
        failed = dict.fromkeys(
            str(row["scaffold_type"])
            for row in rounds
            if row.get("outcome") == "failed" and row["scaffold_type"] != credited
        )
        observations.extend(
            CreditObservation(support, "failed_round", 0.0, failed_round_weight, False)
            for support in failed
        )
    return tuple(observations)


# --- This child's own record ----------------------------------------------------------------


@dataclass(frozen=True)
class OwnRecord:
    credited_episodes: int = 0
    independent_successes: int = 0
    total_gain: float = 0.0
    did_not_help: int = 0


def own_records(history: Iterable[Mapping[str, object]]) -> dict[str, OwnRecord]:
    """This child's record per help type on this skill, from the same credit rule."""

    records: dict[str, OwnRecord] = {}
    for episode in history:
        for observation in episode_observations(episode, failed_round_weight=1.0):
            row = records.get(observation.support, OwnRecord())
            if observation.role == "credited":
                row = OwnRecord(
                    row.credited_episodes + 1,
                    row.independent_successes + int(observation.independent),
                    row.total_gain + observation.score,
                    row.did_not_help,
                )
            else:
                row = OwnRecord(
                    row.credited_episodes,
                    row.independent_successes,
                    row.total_gain,
                    row.did_not_help + 1,
                )
            records[observation.support] = row
    return records


def previous_first_not_transferred(history: Sequence[Mapping[str, object]]) -> str | None:
    """The first help of the child's last measured episode, if the after-answer was wrong."""

    for episode in reversed(history):
        loop = episode.get("support_loop")
        measurement = episode.get("measurement")
        if not isinstance(loop, Mapping) or not isinstance(measurement, Mapping):
            continue
        rounds = loop.get("rounds") or []
        if not rounds:
            continue
        if str(measurement.get("after_earned")) != "0":
            return None
        return str(rounds[0].get("scaffold_type"))  # type: ignore[union-attr]
    return None


def support_dependency(history: Iterable[Mapping[str, object]]) -> float | None:
    """Share of the child's measured episodes on this skill in which help had to be shown."""

    eligible = helped = 0
    for episode in history:
        attempts = episode.get("attempts") or []
        if not any(a.get("role") == "unsupported_before" for a in attempts):  # type: ignore[union-attr]
            continue
        eligible += 1
        loop = episode.get("support_loop")
        model2 = episode.get("model2")
        if isinstance(loop, Mapping) and "rounds" in loop:
            helped += int(bool(loop.get("rounds")))
        else:
            helped += int(isinstance(model2, Mapping) and bool(model2.get("selected_action")))
    return helped / eligible if eligible else None


def learning_state_of(reading: Mapping[str, object] | None) -> str:
    state = (reading or {}).get("state")
    available = (reading or {}).get("status") == "available"
    return str(state) if available and state in LEARNING_STATES else "not_available"


# --- The bandit -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HelpOrder:
    order: tuple[str, ...]
    predicted_gain: Mapping[str, float]
    reason_family: str
    model1_uncertain: bool
    learning_state: str
    contexts: Mapping[str, BanditContext]

    @property
    def first(self) -> str:
        return self.order[0]


class GameHelpBandit:
    """One subject's greedy help-order bandit and the expert settings it started from."""

    def __init__(
        self,
        *,
        subject: str,
        supports: Sequence[str],
        cells: Mapping[tuple[str, bool, str], Mapping[str, object]],
        reason_families: Mapping[str, str],
        missing_label_family: str,
        settings: Mapping[str, object],
        policy: LinUCBPolicy,
    ) -> None:
        if policy.alpha != 0 or policy.epsilon_min != 0:
            raise ValueError("the games' bandit never explores")
        self.subject = subject
        self.supports = tuple(supports)
        self.cells = dict(cells)
        self.reason_families = dict(reason_families)
        self.missing_label_family = missing_label_family
        self.settings = dict(settings)
        self.policy = policy

    @classmethod
    def from_expert_data(
        cls,
        subject: str,
        gains: Mapping[str, object],
        families: Mapping[str, object],
        *,
        file_sha256: Mapping[str, str],
        failed_round_weight: float = PROVISIONAL_FAILED_ROUND_WEIGHT,
        uninformed_precision: float = PROVISIONAL_UNINFORMED_PRECISION,
    ) -> GameHelpBandit:
        supports = tuple(gains["help_types"][subject])  # type: ignore[index]
        cells = {
            (
                str(cell["reason_family"]),
                bool(cell["model1_uncertain"]),
                str(cell["learning_state"]),
            ): cell
            for cell in gains["cells"]  # type: ignore[union-attr]
            if cell["subject"] == subject
        }
        missing = [
            key
            for key in ((f, u, s) for f, u in MODEL1_STATES for s in LEARNING_STATES)
            if key not in cells
        ]
        if missing:
            raise ValueError(f"{subject} expert gains miss cells {missing}")
        strength = float(gains["prior_strength"])  # type: ignore[arg-type]
        own_gain = float(gains["own_success_rate_gain"])  # type: ignore[arg-type]
        previous_gain = float(gains["previous_first_not_transferred_gain"][subject])  # type: ignore[index]
        # The four indicators of a cell context share its prior weight, so the context as a whole
        # is worth exactly prior_strength episodes.
        indicators = {*CELL_FEATURES, *MAIN_EFFECT_FEATURES}
        precision = [
            4 * strength
            if name in indicators
            else strength
            if name in (OWN_SUCCESS_RATE, PREVIOUS_FIRST_NOT_TRANSFERRED)
            else uninformed_precision * strength
            for name in FEATURE_NAMES
        ]
        arms = {}
        for support in supports:
            mean = dict.fromkeys(FEATURE_NAMES, 0.0)
            for (family, uncertain, state), cell in cells.items():
                mean[cell_feature(family, uncertain, state)] = float(cell["expected_gain"][support])  # type: ignore[index]
            mean[OWN_SUCCESS_RATE] = own_gain
            mean[PREVIOUS_FIRST_NOT_TRANSFERRED] = previous_gain
            arms[support] = {
                "A": [
                    [
                        precision[row] if row == column else 0.0
                        for column in range(len(FEATURE_NAMES))
                    ]
                    for row in range(len(FEATURE_NAMES))
                ],
                "b": [precision[index] * mean[name] for index, name in enumerate(FEATURE_NAMES)],
            }
        policy = LinUCBPolicy.from_parameters(
            {"alpha": 0.0, "ridge": 1.0, "epsilon_min": 0.0, "arms": arms}
        )
        labels = families["subjects"][subject]  # type: ignore[index]
        return cls(
            subject=subject,
            supports=supports,
            cells=cells,
            reason_families={
                label: str(row["reason_family"]) for label, row in labels["labels"].items()
            },
            missing_label_family=str(labels["missing_label"]["reason_family"]),
            settings={
                "data_version": gains["package_version"],
                "evidence_status": gains["evidence_status"],
                "file_sha256": dict(file_sha256),
                "prior_strength": strength,
                "own_success_rate_gain": own_gain,
                "previous_first_not_transferred_gain": previous_gain,
                "tie_tolerance": float(gains["tie_tolerance"]),  # type: ignore[arg-type]
                "failed_round_weight": failed_round_weight,
                "credit_rule_version": CREDIT_RULE_VERSION,
                "uninformed_precision": uninformed_precision,
            },
            policy=policy,
        )

    def reason_family(self, label: str | None) -> str:
        return self.reason_families.get(label or "", self.missing_label_family)

    def context(
        self,
        support: str,
        *,
        reason_family: str,
        model1_uncertain: bool,
        learning_state: str,
        history: Sequence[Mapping[str, object]],
    ) -> BanditContext:
        """``area-bandit-context-v1`` for one help type in one episode."""

        family = "unclear" if model1_uncertain else reason_family
        values = dict.fromkeys(FEATURE_NAMES, 0.0)
        values[cell_feature(family, model1_uncertain, learning_state)] = 1.0
        values[f"family:{family}"] = 1.0
        values[f"model1:{_certainty(model1_uncertain)}"] = 1.0
        values[f"learning_state:{learning_state}"] = 1.0
        record = own_records(history).get(support)
        if record is not None and record.credited_episodes:
            values["own:record_present"] = 1.0
            values[OWN_SUCCESS_RATE] = record.independent_successes / record.credited_episodes
            values["own:credited_episodes"] = (
                min(record.credited_episodes, OWN_COUNT_CAP) / OWN_COUNT_CAP
            )
            values["own:mean_gain"] = record.total_gain / record.credited_episodes
        if record is not None:
            values["own:did_not_help"] = min(record.did_not_help, OWN_COUNT_CAP) / OWN_COUNT_CAP
        if previous_first_not_transferred(history) == support:
            values[PREVIOUS_FIRST_NOT_TRANSFERRED] = 1.0
        dependency = support_dependency(history)
        if dependency is not None:
            values["support_dependency:present"] = 1.0
            values["support_dependency"] = dependency
        return BanditContext(
            GAME_CONTEXT_VERSION,
            FEATURE_NAMES,
            tuple(values[name] for name in FEATURE_NAMES),
            {
                "learning_state": learning_state == "not_available",
                "own_record": record is None or not record.credited_episodes,
                "support_dependency": dependency is None,
            },
        )

    def order(
        self,
        *,
        model1_label: str | None,
        model1_uncertain: bool,
        learning_state_input: Mapping[str, object] | None,
        history: Sequence[Mapping[str, object]],
        eligible: Iterable[str],
        renderable: Iterable[str],
    ) -> HelpOrder:
        """Every drawable help, highest predicted gain first.

        Gains within ``tie_tolerance`` count as equal and the help earlier in the cell's expert
        order wins. Raises ``ValueError("NO_RENDERABLE_SUPPORT")`` when no help can be drawn.
        """

        family = "unclear" if model1_uncertain else self.reason_family(model1_label)
        state = learning_state_of(learning_state_input)
        cell_order = list(self.cells[(family, model1_uncertain, state)]["order"])  # type: ignore[arg-type]
        offered, drawable = set(eligible), set(renderable)
        available = [
            support for support in cell_order if support in offered and support in drawable
        ]
        if not available:
            raise ValueError("NO_RENDERABLE_SUPPORT")
        contexts = {
            support: self.context(
                support,
                reason_family=family,
                model1_uncertain=model1_uncertain,
                learning_state=state,
                history=history,
            )
            for support in available
        }
        gains = {
            support: self.policy.predict(contexts[support], [support])[support][0]
            for support in available
        }
        tolerance = float(self.settings["tie_tolerance"])  # type: ignore[arg-type]
        remaining, order = list(available), []
        while remaining:
            best = max(gains[support] for support in remaining)
            chosen = next(support for support in remaining if gains[support] >= best - tolerance)
            order.append(chosen)
            remaining.remove(chosen)
        return HelpOrder(tuple(order), gains, family, model1_uncertain, state, contexts)

    def learn(self, observation: CreditObservation, context: BanditContext) -> None:
        """Apply one observation, in the context stored when the episode's order was chosen."""

        self.policy.update(context, observation.support, observation.score, observation.weight)

    def parameters(self) -> dict[str, object]:
        return {
            **self.policy.parameters(),
            "thresholds_status": "provisional_assumption",
            "exploration": {"alpha": 0.0, "epsilon_min": 0.0, "status": "decision"},
            "game": {
                "policy_version": GAME_POLICY_VERSION,
                "context_version": GAME_CONTEXT_VERSION,
                "subject": self.subject,
                "supports": list(self.supports),
                "feature_names": list(FEATURE_NAMES),
                "cells": [dict(cell) for cell in self.cells.values()],
                "reason_families": dict(self.reason_families),
                "missing_label_family": self.missing_label_family,
                **self.settings,
            },
        }

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, object]) -> GameHelpBandit:
        game = parameters["game"]
        assert isinstance(game, Mapping)
        if list(game["feature_names"]) != list(FEATURE_NAMES):  # type: ignore[call-overload]
            raise ValueError("the stored bandit uses another context")
        keep = {
            "policy_version",
            "context_version",
            "subject",
            "supports",
            "feature_names",
            "cells",
            "reason_families",
            "missing_label_family",
        }
        return cls(
            subject=str(game["subject"]),
            supports=list(game["supports"]),  # type: ignore[call-overload]
            cells={
                (str(c["reason_family"]), bool(c["model1_uncertain"]), str(c["learning_state"])): c
                for c in game["cells"]  # type: ignore[union-attr]
            },
            reason_families=dict(game["reason_families"]),  # type: ignore[call-overload]
            missing_label_family=str(game["missing_label_family"]),
            settings={key: value for key, value in game.items() if key not in keep},
            policy=LinUCBPolicy.from_parameters(dict(parameters)),
        )


def load_game_help_bandit(
    subject: str, *, directory: Path = EXPERT_MODEL_DATA_DIRECTORY
) -> GameHelpBandit:
    """One subject's expert-initialised bandit, from the checked expert model data."""

    manifest = read_expert_manifest(directory)
    gains, gains_sha = read_verified_expert_file(directory, manifest, "support_gains.json")
    families, families_sha = read_verified_expert_file(directory, manifest, "reason_families.json")
    assert isinstance(gains, Mapping) and isinstance(families, Mapping)
    return GameHelpBandit.from_expert_data(
        subject,
        gains,
        families,
        file_sha256={"support_gains.json": gains_sha, "reason_families.json": families_sha},
    )
