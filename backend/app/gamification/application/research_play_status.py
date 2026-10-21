"""Whether a stored game is finished, being played, abandoned, or not valid.

Derived on read from the child's own answers. Nothing stored is changed, and a dashboard
read must not keep an idle game looking live.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

IDLE_TIMEOUT = timedelta(minutes=10)

STATUS_LABELS = {
    "live": "Being played now",
    "abandoned": "Stopped partway · not counted",
    "invalid": "Not valid · not counted",
    "finished": "Finished",
}


def play_status(run: Mapping[str, object], now: datetime) -> str:
    stored = str(run.get("status") or "")
    if stored == "completed":
        return "finished"
    if stored == "invalidated":
        return "invalid"
    activity = last_child_activity(run)
    if activity is None:
        return "abandoned"
    now = now if now.tzinfo else now.replace(tzinfo=UTC)
    if now - activity <= IDLE_TIMEOUT:
        return "live"
    return "abandoned"


def last_child_activity(run: Mapping[str, object]) -> datetime | None:
    """Latest answer time. A later row update does not count as the child playing."""

    state = run.get("state")
    latest: datetime | None = None
    events = state.get("events") if isinstance(state, Mapping) else None
    for event in events or []:
        if not isinstance(event, Mapping):
            continue
        parsed = parse_time(event.get("occurred_at"))
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    if latest is not None:
        return latest
    return parse_time(run.get("updated_at"))


def parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
