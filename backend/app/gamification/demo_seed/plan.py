"""The seed plan: which scripted episodes each skill gets.

A pattern scripts only the child: whether each answer was right. The help types, their order, the
misconception estimate and the gain all come from the real models when the plan is played.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

Before = Literal["wrong", "wrong_sparse", "correct"]
After = Literal["correct", "wrong", "exit"]
REASON_FAMILIES = ("representation", "procedure", "relation", "prerequisite", "unclear")


@dataclass(frozen=True)
class EpisodeScript:
    before: Before
    # One entry per help round: whether the child's supported answers in that round are right.
    rounds: tuple[bool, ...] = ()
    after: After | None = None
    condition: Literal["baseline", "proposed"] = "proposed"


def _rounds(failures: int) -> tuple[bool, ...]:
    return (*([False] * failures), True)


def _learned(failures: int) -> tuple[EpisodeScript, EpisodeScript]:
    """Help works on round ``failures + 1``, then a second episode where Model 2 can use that."""

    return (
        EpisodeScript("wrong", _rounds(failures), "correct"),
        EpisodeScript("wrong", (True,), "correct"),
    )


PATTERNS: dict[str, tuple[EpisodeScript, ...]] = {
    "responds_to_round_1": _learned(0),
    "responds_to_round_2": _learned(1),
    "responds_to_round_3": _learned(2),
    "needs_two_tries": (
        EpisodeScript("wrong", _rounds(1), "wrong"),
        EpisodeScript("wrong", _rounds(1), "correct"),
        EpisodeScript("wrong", (True,), "correct"),
    ),
    # Right while helped, wrong alone: must not become a preference.
    "helped_but_not_independent": (
        EpisodeScript("wrong", (True,), "wrong"),
        *_learned(1),
    ),
    # Every type tried and missed, then withdrawn by rule W.
    "all_rounds_fail": (
        EpisodeScript("wrong", (False,) * 6, "correct"),
        EpisodeScript("wrong", (True,), "correct"),
    ),
    # No timing and no interaction summary: Model 1 falls back to a flat estimate.
    "low_evidence": (
        EpisodeScript("wrong_sparse", (True,), "correct"),
        EpisodeScript("wrong", (True,), "correct"),
    ),
    # Help delivered, then the child leaves: an invalid episode Model 2 must ignore.
    "exits_after_help": (
        EpisodeScript("wrong", (True,), "exit"),
        *_learned(1),
    ),
    # Right first time: no difficulty, no help, no update. Then a learned episode pair.
    "already_secure": (
        EpisodeScript("correct"),
        *_learned(1),
    ),
}
BASELINE_EPISODE = EpisodeScript("wrong", _rounds(1), "correct", condition="baseline")
# Each area's skills take patterns in this order, so every area shows several of them.
ROTATION = (
    "responds_to_round_1",
    "responds_to_round_2",
    "needs_two_tries",
    "responds_to_round_3",
    "helped_but_not_independent",
    "low_evidence",
    "all_rounds_fail",
    "exits_after_help",
    "already_secure",
)


@dataclass(frozen=True)
class SkillPlan:
    area_id: str
    skill_id: str
    pattern: str
    # The Model 1 reason family the wrong answers aim for, when the game's scorer can produce it.
    target_family: str
    episodes: tuple[EpisodeScript, ...]


@dataclass(frozen=True)
class SeedPlan:
    version: str
    learner_id: str
    skills: tuple[SkillPlan, ...] = field(default_factory=tuple)

    @property
    def episode_count(self) -> int:
        return sum(len(skill.episodes) for skill in self.skills)


def load_config(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict) or config.get("version") is None:
        raise ValueError("SEED_FILE_INVALID")
    for name in (
        *dict(config.get("overrides") or {}).values(),
        *dict(config.get("areas") or {}).values(),
    ):
        if name not in PATTERNS:
            raise ValueError(f"UNKNOWN_PATTERN:{name}")
    return config


def build_plan(config: Mapping[str, object], areas: Mapping[str, Sequence[str]]) -> SeedPlan:
    """Assign a pattern to every skill of every area given.

    ``areas`` maps each multi-help area to its skills in teaching order. An area's skills follow
    ``ROTATION`` from the area's start pattern, unless the file overrides a skill. The first skill of
    each area also gets one baseline episode, for the proposed-against-baseline comparison.
    """

    starts = dict(config.get("areas") or {})
    overrides = dict(config.get("overrides") or {})
    skills: list[SkillPlan] = []
    for area_index, (area_id, area_skills) in enumerate(sorted(areas.items())):
        start = ROTATION.index(starts.get(area_id, ROTATION[area_index % len(ROTATION)]))
        if config.get("small_rehearsal"):
            area_skills = area_skills[:1]
        for index, skill_id in enumerate(area_skills):
            pattern = overrides.get(skill_id, ROTATION[(start + index) % len(ROTATION)])
            episodes = PATTERNS[pattern]
            if config.get("small_rehearsal"):
                episodes = PATTERNS["responds_to_round_2"][: 1 + area_index % 2]
            elif index == 0:
                episodes = (BASELINE_EPISODE, *episodes)
            skills.append(
                SkillPlan(
                    area_id=area_id,
                    skill_id=skill_id,
                    pattern=pattern,
                    target_family=REASON_FAMILIES[(area_index + index) % len(REASON_FAMILIES)],
                    episodes=episodes,
                )
            )
    return SeedPlan(
        version=str(config["version"]), learner_id=str(config["learner_id"]), skills=tuple(skills)
    )
