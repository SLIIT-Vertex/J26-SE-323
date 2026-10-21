"""Answers built from the server's own solution: one right answer, and wrong answers by error code.

A wrong answer is the solution with one value changed (a digit, a link, a swapped token), kept only
when the game's real scorer marks it wrong. The scorer also names the error, so a caller can pick a
wrong answer by the misconception it shows rather than assuming one.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping


def envelope(record: Mapping[str, object], payload: Mapping[str, object]) -> dict[str, object]:
    return {
        **payload,
        "presentation_id": record["presentation_id"],
        "item_revision_id": record["revision_id"],
        "interaction_version": "constructed-response-v1",
    }


def correct_answer(flow, record: Mapping[str, object]) -> dict[str, object]:
    solution = flow.support_solution(record)["correct_response"]
    if flow.validate_constructed_response(dict(record), dict(solution))[0] is not True:
        raise ValueError(f"SOLUTION_NOT_CORRECT:{record['skill_id']}")
    return envelope(record, solution)


def wrong_answers(flow, record: Mapping[str, object]) -> Iterator[tuple[dict[str, object], str]]:
    """Every distinct wrong answer found, with the error code the real scorer gave it."""

    solution = flow.support_solution(record)["correct_response"]
    seen: set[str] = set()
    for candidate in (*_perturbations(solution), *_swaps(solution, record.get("game_data", {}))):
        try:
            correct, error_code, _ = flow.validate_constructed_response(dict(record), candidate)
        except (TypeError, ValueError, KeyError, IndexError):
            continue
        key = repr(candidate)
        if correct is False and key not in seen:
            seen.add(key)
            yield envelope(record, candidate), str(error_code)


def wrong_answer(flow, record: Mapping[str, object]) -> dict[str, object]:
    for payload, _code in wrong_answers(flow, record):
        return payload
    raise ValueError(f"NO_WRONG_ANSWER:{record['skill_id']}")


def _swaps(solution: Mapping[str, object], game: object):
    """Replace one answer token everywhere with another token from the same on-screen list."""

    lists = [row for row in _walk(game) if isinstance(row, list | tuple)]
    # A list of rows is also a list of options per column (every word token, every picture token).
    lists += [
        [row.get(key) for row in rows if isinstance(row, Mapping)]
        for rows in list(lists)
        for key in {key for row in rows if isinstance(row, Mapping) for key in row}
    ]
    seen: set[tuple[str, str]] = set()
    for token in {value for value in _walk(solution) if isinstance(value, str)}:
        for options in lists:
            if token not in options:
                continue
            for other in options:
                if isinstance(other, str) and other != token and (token, other) not in seen:
                    seen.add((token, other))
                    yield _replace(solution, token, other)
                    # The same swap, but leaving the fields that restate the board (an origin
                    # that equals the board's origin) as they are.
                    fixed = {
                        key
                        for key, value in solution.items()
                        if isinstance(game, Mapping) and game.get(key) == value
                    }
                    if fixed:
                        yield {
                            key: value if key in fixed else _replace(value, token, other)
                            for key, value in solution.items()
                        }


def _walk(value: object):
    yield value
    if isinstance(value, Mapping):
        for inner in value.values():
            yield from _walk(inner)
    elif isinstance(value, list | tuple):
        for inner in value:
            yield from _walk(inner)


def _replace(value: object, old: str, new: str):
    if value == old:
        return new
    if isinstance(value, Mapping):
        return {key: _replace(inner, old, new) for key, inner in value.items()}
    if isinstance(value, list | tuple):
        return [_replace(inner, old, new) for inner in value]
    return value


def _perturbations(solution: Mapping[str, object]):
    for key, value in solution.items():
        if key == "kind":
            continue
        if isinstance(value, bool):
            candidate = copy.deepcopy(dict(solution))
            candidate[key] = not value
            yield candidate
        elif isinstance(value, int):
            for delta in (1, -1, 10, 2):
                candidate = copy.deepcopy(dict(solution))
                candidate[key] = value + delta
                yield candidate
        elif isinstance(value, list) and value:
            candidate = copy.deepcopy(dict(solution))
            candidate[key] = list(reversed(value))
            yield candidate
            candidate = copy.deepcopy(dict(solution))
            candidate[key] = value[:-1]
            yield candidate
            if isinstance(value[0], int) and not isinstance(value[0], bool):
                candidate = copy.deepcopy(dict(solution))
                candidate[key] = [value[0] + 1, *value[1:]]
                yield candidate
        elif isinstance(value, str):
            candidate = copy.deepcopy(dict(solution))
            candidate[key] = value + "x"
            yield candidate
        elif isinstance(value, dict) and value:
            first = next(iter(value))
            candidate = copy.deepcopy(dict(solution))
            inner = candidate[key][first]
            candidate[key][first] = (inner + 1) if isinstance(inner, int) else None
            yield candidate
    # Answers that carry their own evidence (indices, counts, traces): drop the last entry
    # everywhere at once so the answer stays internally consistent.
    lengths = {len(value) for value in solution.values() if isinstance(value, list) and value}
    if len(lengths) == 1:
        (length,) = lengths
        candidate = copy.deepcopy(dict(solution))
        for key, value in solution.items():
            if isinstance(value, list) and value:
                candidate[key] = value[:-1]
            elif type(value) is int and value == length and "count" in key:
                candidate[key] = value - 1
        yield candidate
    # Matching and linking games: pair one entry with another entry's target.
    for key, value in solution.items():
        if not (isinstance(value, list) and len(value) > 1 and isinstance(value[0], dict)):
            continue
        for field in value[0]:
            if field == "sequence" or value[0].get(field) == value[1].get(field):
                continue
            candidate = copy.deepcopy(dict(solution))
            rows = candidate[key]
            rows[0][field], rows[1][field] = rows[1][field], rows[0][field]
            yield candidate
    for key, value in solution.items():
        if isinstance(value, dict) and value:
            for inner in _perturbations(value):
                candidate = copy.deepcopy(dict(solution))
                candidate[key] = inner
                yield candidate
