"""Simpler version: the same game and skill with easier quantities, then the failed difficulty."""

from __future__ import annotations

from collections.abc import Mapping

from app.gamification.application.support_builders.context import (
    SUPPORT_SEED_ATTEMPTS,
    SUPPORT_SEED_OFFSET,
    SupportBuildContext,
    SupportPlan,
    practice_record,
    practice_stage,
    solution_matches_failed,
    target_stage,
)
from app.gamification.application.support_builders.cues import cues_for

# Fields that describe the item rather than its difficulty.
_IGNORED = frozenset({"source_page", "seed", "round_id", "schema_version", "grid_max"})


def difficulty(game: object) -> tuple[int, int, int]:
    """Objects to handle, then the largest number, then the sum: fewer and smaller is easier."""

    numbers: list[int] = []
    objects = 0

    def walk(value: object) -> None:
        nonlocal objects
        if isinstance(value, bool):
            return
        if isinstance(value, int | float):
            numbers.append(abs(int(value)))
        elif isinstance(value, Mapping):
            for key, item in value.items():
                if key not in _IGNORED:
                    walk(item)
        elif isinstance(value, list | tuple):
            objects += len(value)
            for item in value:
                walk(item)

    walk(game)
    return objects, max(numbers, default=0), sum(numbers)


class SimplerSameGameBuilder:
    scaffold_type = "simpler_same_game"

    def build(self, context: SupportBuildContext) -> SupportPlan | None:
        ceiling = difficulty(context.source.support_activity(context.failed_record)["game"])
        record = self._designed(context) or self._searched(context, ceiling)
        if record is None:
            return None
        cues = cues_for(context.subject)
        return SupportPlan(
            scaffold_type="simpler_same_game",
            title_si="පහසු අනුවාදය",
            stages=(
                practice_stage(context, record, cues.simpler_start, gate_on_success=True),
                target_stage(context, cues.simpler_return),
            ),
        )

    @staticmethod
    def _designed(context: SupportBuildContext) -> dict[str, object] | None:
        """The content module's own easier item of this skill, from a fresh seed.

        The module makes it easier by construction along the dimension that makes this skill
        hard (fewer carries, fewer pairs, a shorter pattern), which an object-and-number count
        cannot always see, so it is not re-checked against that count.
        """

        for attempt in range(SUPPORT_SEED_ATTEMPTS):
            item = context.source.simpler_support_item(
                context.skill_id,
                context.seed + SUPPORT_SEED_OFFSET * 2 + attempt,
                context.failed_record,
            )
            # Whether a fresh item can be made smaller can depend on its seed.
            if item is None:
                continue
            record = practice_record(context, item)
            if _usable(context, record):
                return record
        return None

    @staticmethod
    def _searched(
        context: SupportBuildContext, ceiling: tuple[int, int, int]
    ) -> dict[str, object] | None:
        """Otherwise the easiest ordinary item of this skill that is easier than the failed one."""

        best: tuple[tuple[int, int, int], dict[str, object]] | None = None
        for attempt in range(SUPPORT_SEED_ATTEMPTS):
            item = context.source.support_item(
                context.skill_id, context.seed + SUPPORT_SEED_OFFSET * 2 + attempt
            )
            record = practice_record(context, item)
            if not _usable(context, record):
                continue
            level = _level(context, record)
            if level < ceiling and (best is None or level < best[0]):
                best = (level, record)
        return None if best is None else best[1]


def _level(context: SupportBuildContext, record: dict[str, object]) -> tuple[int, int, int]:
    return difficulty(context.source.support_activity(record)["game"])


def _usable(context: SupportBuildContext, record: dict[str, object]) -> bool:
    return (
        record["skill_id"] == context.skill_id
        and record["revision_id"] not in context.reserved_revisions
        and not solution_matches_failed(context, record)
    )
