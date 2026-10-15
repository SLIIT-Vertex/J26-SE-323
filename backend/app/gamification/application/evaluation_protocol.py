"""Frozen evaluation protocol. A changed document must not start an experiment."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.gamification.application.errors import PlayError
from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY
from app.gamification.domain.types import DecisionMode

PROTOCOL_PATH = GAMIFICATION_DATA_DIRECTORY / "evaluation-protocol" / "v1" / "protocol.json"
REQUIRED_KEYS = (
    "protocol_version",
    "primary_outcome",
    "secondary_outcomes",
    "exclusion_rules",
    "formula_version",
    "reward_version",
    "context_version",
    "resolution_formula_version",
    "arms",
    "assignment_unit",
    "allocation_rule",
    "stop_rules",
    "sample_size",
)
ARM_KEYS = ("baseline_performance_triggered", "proposed_misconception_ig_policy")


@dataclass(frozen=True, slots=True)
class FrozenProtocol:
    document: Mapping[str, object]
    digest: str
    path: Path

    def require_hash(self, presented: str) -> None:
        if presented != self.digest:
            raise PlayError("PROTOCOL_HASH_MISMATCH", 409)


def load_frozen_protocol(path: Path = PROTOCOL_PATH) -> FrozenProtocol:
    document = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_KEYS if key not in document]
    if missing:
        raise ValueError(f"protocol is missing {', '.join(missing)}")
    arms = document["arms"]
    if not isinstance(arms, list):
        raise TypeError("protocol arms must be a list")
    keys = tuple(arm["arm_key"] for arm in arms)
    if keys != ARM_KEYS:
        raise ValueError("protocol arms drifted from the pre-registered pair")
    if document["assignment_unit"] != "learner":
        raise ValueError("assignment unit must be the learner")
    if document["sample_size"] != "to be confirmed with supervisor/ethics":
        raise ValueError("sample size must stay an explicit human gate")
    return FrozenProtocol(document=document, digest=protocol_digest(document), path=path)


def protocol_digest(document: Mapping[str, object]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def decision_mode_for_arm(arm_key: str) -> DecisionMode:
    if arm_key == "baseline_performance_triggered":
        return DecisionMode.PERFORMANCE_TRIGGERED_FIXED
    if arm_key == "proposed_misconception_ig_policy":
        return DecisionMode.LEARNED
    raise ValueError(f"unknown arm {arm_key}")
