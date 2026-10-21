"""Simpler versions of the English matching games: the same game with fewer pairs.

Most Grade 5 English games ask the child to link words to pictures, places, headings or other
words. Their answer is a map of tokens kept server-side in ``game_data``. A simpler version keeps
the same game, the same skill and the same kind of link, with fewer pairs: the tokens of the
dropped pairs are removed from every list the phone shows, and the answer map shrinks with them,
so scoring and the public game stay consistent.

The item is made from a fresh seed by the content module, so its words are not the failed item's.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Iterable, Mapping

# The answer maps the English games keep server-side, in the order a game is searched for one.
ANSWER_MAP_KEYS = ("target_mapping", "target_pairs", "target_links", "target_groups")
# The smallest matching game: one link, with one other target left on screen so the child
# still chooses between two.
MINIMUM_PAIRS = 1


def pair_count(game: Mapping[str, object]) -> int | None:
    """How many links or group members the child must place, or ``None`` for a non-matching game."""

    key = _answer_key(game)
    if key is None:
        return None
    answer = game[key]
    assert isinstance(answer, Mapping)
    if key == "target_groups":
        return sum(len(_listed(members)) for members in answer.values())
    return len(answer)


def fewer_pairs(game: Mapping[str, object], *, below: int) -> dict[str, object] | None:
    """The game with fewer than ``below`` pairs, or ``None`` when it cannot get that small."""

    key = _answer_key(game)
    if key is None:
        return None
    answer = game[key]
    assert isinstance(answer, Mapping)
    if key == "target_groups":
        kept_answer, removed = _fewer_members(answer, below=below)
    else:
        kept_answer, removed = _fewer_links(answer, below=below)
    if kept_answer is None:
        return None
    simpler = {
        name: _without(value, removed) if isinstance(value, list | tuple) else copy.deepcopy(value)
        for name, value in game.items()
    }
    simpler[key] = kept_answer
    return simpler


def simpler_matching_item[Item](item: Item, *, than: Mapping[str, object]) -> Item | None:
    """A copy of a fresh English item with fewer pairs than the failed game ``than``.

    ``None`` for a game that is not a matching game, or when the failed game already had the
    fewest pairs a matching game can usefully have.
    """

    failed_pairs = pair_count(than)
    if failed_pairs is None:
        return None
    game = fewer_pairs(item.game_data, below=failed_pairs)  # type: ignore[attr-defined]
    if game is None:
        return None
    revision = str(item.revision_id)  # type: ignore[attr-defined]
    stem, _, version = revision.rpartition("@")
    return dataclasses.replace(
        item,  # type: ignore[type-var]
        game_data=game,
        revision_id=f"{stem}:simpler@{version}" if stem else f"{revision}:simpler",
    )


def shown_tokens(game: Mapping[str, object], field: str) -> set[str]:
    """Every ``field`` token in the rows the phone shows, including a simpler version's distractor.

    A validator accepts a link to any shown target, so linking to the distractor scores as wrong
    instead of being rejected as a forged token.
    """

    return {
        str(row[field])
        for rows in game.values()
        if isinstance(rows, list | tuple)
        for row in rows
        if isinstance(row, Mapping) and field in row
    }


def _answer_key(game: Mapping[str, object]) -> str | None:
    return next((name for name in ANSWER_MAP_KEYS if isinstance(game.get(name), Mapping)), None)


def _listed(members: object) -> list[object]:
    return list(members) if isinstance(members, list | tuple) else [members]


def _fewer_links(
    answer: Mapping[str, object], *, below: int
) -> tuple[dict[str, object] | None, set[str]]:
    # About half of the failed game's pairs.
    keep = max(MINIMUM_PAIRS, below // 2)
    if keep >= below:
        return None, set()
    if keep >= len(answer):
        # The fresh item is already small enough.
        return dict(answer), set()
    kept = dict(_spread_over_targets(answer)[:keep])
    kept_targets = set(_tokens(kept.values()))
    dropped = {name: value for name, value in answer.items() if name not in kept}
    # A target shared with a kept pair (a heading in a sorting game) stays on screen.
    dropped_targets = [token for token in _tokens(dropped.values()) if token not in kept_targets]
    if len(kept_targets) == 1:
        # A single link keeps one other target, so it is still a choice and not a gift.
        dropped_targets = dropped_targets[1:]
    return kept, set(dropped) | set(dropped_targets)


def _spread_over_targets(answer: Mapping[str, object]) -> list[tuple[str, object]]:
    """The pairs in round-robin order over their targets, so a sorting game keeps every heading."""

    by_target: dict[str, list[tuple[str, object]]] = {}
    for name, value in answer.items():
        by_target.setdefault(repr(value), []).append((name, value))
    columns = list(by_target.values())
    return [
        column[row]
        for row in range(max(len(column) for column in columns))
        for column in columns
        if row < len(column)
    ]


def _fewer_members(
    answer: Mapping[str, object], *, below: int
) -> tuple[dict[str, object] | None, set[str]]:
    # Each group keeps at least one member, so every group still has something to sort.
    groups = len(answer)
    keep = max(groups, below // 2)
    if keep >= below:
        return None, set()
    per_group = max(1, keep // groups)
    kept: dict[str, object] = {}
    removed: set[str] = set()
    for group, members in answer.items():
        listed = _listed(members)
        kept[group] = listed[:per_group]
        removed |= set(_tokens(listed[per_group:]))
    return kept, removed


def _without(rows: Iterable[object], removed: set[str]) -> list[object]:
    """The rows of a shown list, minus any row that carries a removed token."""

    return [copy.deepcopy(row) for row in rows if not (set(_tokens([row])) & removed)]


def _tokens(values: Iterable[object]) -> Iterable[str]:
    for value in values:
        if isinstance(value, str):
            yield value
        elif isinstance(value, Mapping):
            yield from _tokens(value.values())
        elif isinstance(value, list | tuple):
            yield from _tokens(value)
