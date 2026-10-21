"""What the research dashboard shows: one learner's episodes, explained model by model.

Read-only. It reads stored episodes and the published Learner State rows and reuses the models'
own pure functions (help ranking, reason grouping), so it shows what the models did and cannot
drift from them.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Protocol
from uuid import UUID

from app.gamification.application.research_accuracy import (
    accuracy_report,
    is_independent,
    present_simulation,
)
from app.gamification.application.research_explain import (
    area_title,
    area_titles,
    english_title,
    episode_summary,
    explain_model1,
    explain_model2,
    explain_model3,
    explain_rounds,
    research_subject,
    resolved_area,
)
from app.gamification.application.research_glossary import reason_name
from app.gamification.application.research_history import model_history, model_series
from app.gamification.application.research_play_status import (
    STATUS_LABELS,
    last_child_activity,
    parse_time,
    play_status,
)
from app.gamification.modeling.offline.research_accuracy_report import replay_report
from app.gamification.modeling.support_selection.support_order import (
    SUBJECT_ORDERS,
    rank_support_history,
    subject_of,
)

_ACCURACY_CACHE = {}
SIMULATION_REPORT = Path(__file__).resolve().parents[3] / "reports/simulated-validation.json"

TERMINAL = {"completed", "invalidated"}
# A just-finished or just-abandoned game stays on the live view this long.
RECENT_WINDOW = timedelta(minutes=3)


class ResearchDashboardReader(Protocol):
    def runs(self, learner_id: UUID) -> list[dict[str, object]]: ...

    def run(self, episode_id: UUID) -> dict[str, object] | None: ...

    def learner_state(self, learner_id: UUID) -> list[dict[str, object]]: ...

    def profile(self, learner_id: UUID) -> dict[str, object] | None: ...

    def all_runs(self) -> list[dict[str, object]]: ...


class ResearchDashboardService:
    def __init__(self, reader: ResearchDashboardReader, *, now=lambda: datetime.now(UTC)) -> None:
        self._reader = reader
        self._now = now

    def overview(self, learner_id: UUID, *, include_invalidated: bool = False) -> dict[str, object]:
        runs = self._real_runs(learner_id)
        completed = [run for run in runs if run["status"] == "completed"]
        helped = [run for run in completed if _state(run).get("measurement")]
        # Seeded answers are scripted, so their gains illustrate the models but are not evidence;
        # live play is kept apart from them.
        gains: dict[str, dict[str, list[Decimal]]] = {
            "live": defaultdict(list),
            "seeded": defaultdict(list),
        }
        for run in helped:
            state = _state(run)
            gain = _gain(state)
            if state.get("validity") == "valid" and gain is not None:
                source = "seeded" if state.get("seed_source") else "live"
                gains[source][str(state["condition"])].append(gain)
        modes = Counter(
            str(_state(run)["model2"].get("support_selection_mode"))  # type: ignore[union-attr]
            for run in runs
            if isinstance(_state(run).get("model2"), Mapping)
            and "support_order" in _state(run)["model2"]  # type: ignore[operator]
        )
        listed = (
            runs if include_invalidated else [run for run in runs if run["status"] != "invalidated"]
        )
        now = self._now()
        return {
            "learner_id": str(learner_id),
            "learner_name": (self._reader.profile(learner_id) or {}).get("display_name")
            or f"Learner {str(learner_id)[:4]}",
            "generated_at": now.isoformat(),
            "counts": {
                "episodes": len(runs),
                "completed": len(completed),
                "invalidated": sum(run["status"] == "invalidated" for run in runs),
                "in_progress": sum(play_status(run, now) == "live" for run in runs),
                "abandoned": sum(play_status(run, now) == "abandoned" for run in runs),
                "seeded": sum(_state(run).get("seed_source") is not None for run in runs),
                "helped_completed": len(helped),
                "policy_updates": sum(len(_state(run).get("policy_updates") or []) for run in runs),
            },
            "weeks": _weeks(completed),
            "board": _board(completed),
            "mean_gain": {
                source: {
                    condition: {"episodes": len(values), "mean": str(sum(values) / len(values))}
                    for condition, values in sorted(by_condition.items())
                    if values
                }
                for source, by_condition in gains.items()
            },
            "selection_modes": dict(modes),
            "skills": self._skill_table(completed),
            "recent": [self._summary(run) for run in reversed(listed[-12:])],
            "independent_after_help": sum(is_independent(_state(run)) for run in helped),
            "independent_after_help_total": sum(
                _state(run).get("validity") == "valid" for run in helped
            ),
        }

    def episodes(
        self,
        learner_id: UUID,
        *,
        skill_id: str | None = None,
        source: str | None = None,
        include_invalidated: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        runs = [
            run
            for run in reversed(self._reader.runs(learner_id))
            if (include_invalidated or run["status"] != "invalidated")
            and (skill_id is None or _state(run).get("skill_id") == skill_id)
            and (
                source is None
                or (source == "seeded") == (_state(run).get("seed_source") is not None)
            )
        ]
        return {
            "total": len(runs),
            "episodes": [self._summary(run) for run in runs[offset : offset + limit]],
        }

    def trace(self, episode_id: UUID) -> dict[str, object] | None:
        run = self._reader.run(episode_id)
        if run is None:
            return None
        state = _state(run)
        return {
            "summary": self._summary(run),
            "pipeline": _pipeline(state),
            "difficulty": {
                "detected": isinstance(state.get("model1"), Mapping),
                "why": "A wrong first answer with no help on screen starts the models."
                if isinstance(state.get("model1"), Mapping)
                else "No wrong first answer yet, so no model has run.",
            },
            "model1": explain_model1(state.get("model1"), research_subject(state)),  # type: ignore[arg-type]
            "model1_record": state.get("model1"),
            "model2": explain_model2(state),
            "model2_record": state.get("model2"),
            "rounds": explain_rounds(state),
            "withdrawal": state.get("withdrawal"),
            "model3": explain_model3(state),
            "measurement_record": state.get("measurement"),
            "events": [
                {"type": event.get("event_type"), "at": event.get("occurred_at")}
                for event in state.get("events") or []
            ],
        }

    def live(self, learner_id: UUID) -> dict[str, object]:
        """The game being played now, or one that just finished or was just abandoned."""

        now = self._now()
        runs = self._reader.runs(learner_id)
        candidates = [run for run in runs if _on_live_view(run, now)]
        if not candidates:
            return {"active": False, "play_status": None, "trace": None}
        latest = max(candidates, key=lambda run: _activity_or_update(run))
        status = play_status(latest, now)
        return {
            "active": status == "live",
            "play_status": status,
            "trace": self.trace(UUID(str(_state(latest)["episode_id"]))),
        }

    def learner_state(self, learner_id: UUID) -> dict[str, object]:
        rows = self._reader.learner_state(learner_id)
        return {
            "rows": [
                {
                    **{key: value for key, value in row.items() if key != "observed_at"},
                    "session_id": str(row["session_id"]),
                    "observed_at": (
                        row["observed_at"].isoformat()
                        if isinstance(row["observed_at"], datetime)
                        else str(row["observed_at"])
                    )
                    if row.get("observed_at")
                    else None,
                }
                for row in rows
            ],
            "used_by_help_choice": True,
            "note": "The Contextual Support Selection and Adaptive Tutor read the same current-session learning state.",
        }

    def model_history(self, learner_id: UUID, model: str) -> dict[str, object]:
        return {
            "model": model,
            "sessions": model_history(self._reader.runs(learner_id), model, now=self._now()),
        }

    def model_series(self, learner_id: UUID, model: str) -> dict[str, object]:
        return {
            "model": model,
            **model_series(self._reader.runs(learner_id), model, now=self._now()),
        }

    def _real_runs(self, learner_id):
        return [run for run in self._reader.runs(learner_id) if not _state(run).get("seed_source")]

    def profile(self, learner_id):
        identity = self._reader.profile(learner_id) or {
            "learner_id": str(learner_id),
            "grade": None,
            "language": None,
        }
        runs = self._real_runs(learner_id)
        completed = [r for r in runs if r["status"] == "completed"]
        mistakes = Counter()
        gains = []
        for run in completed:
            s = _state(run)
            for attempt in s.get("attempts") or []:
                if attempt.get("role") in {
                    "unsupported_before",
                    "unsupported_after",
                } and not attempt.get("correct"):
                    mistakes[
                        (
                            resolved_area(s),
                            reason_name(attempt.get("structured_error_code"), research_subject(s)),
                        )
                    ] += 1
            if s.get("validity") == "valid" and _gain(s) is not None:
                gains.append(
                    {
                        "episode_id": s["episode_id"],
                        "area_id": resolved_area(s),
                        "title": area_title(resolved_area(s)),
                        "gain": str(_gain(s)),
                        "at": run["updated_at"].isoformat(),
                    }
                )
        timestamps = [
            episode_summary(r)["started_at"] or episode_summary(r)["updated_at"] for r in runs
        ]
        timestamps = sorted(t for t in timestamps if t)
        return {
            **identity,
            "name": identity.get("display_name") or f"Learner {str(learner_id)[:4]}",
            "first_game": timestamps[0] if timestamps else None,
            "last_game": timestamps[-1] if timestamps else None,
            "games_played": len(completed),
            "mistakes": [
                {"title": area_title(area), "reason": reason, "count": n}
                for (area, reason), n in mistakes.most_common()
            ],
            "preferences": self._skill_table(completed),
            "gains": gains,
            "independent_successes": sum(is_independent(_state(r)) for r in completed),
            "measured_games": len(gains),
            "areas_played": {
                subject: sorted(
                    {
                        resolved_area(_state(r))
                        for r in completed
                        if research_subject(_state(r)) == subject
                    }
                )
                for subject in ("MAT", "ENG")
            },
            "areas_available": {"MAT": 16, "ENG": 18},
        }

    def accuracy(self, learner_id):
        runs = self._reader.runs(learner_id)
        key = (
            str(learner_id),
            tuple(
                (str(_state(r).get("episode_id")), str(r["updated_at"]), r["status"]) for r in runs
            ),
        )
        cached = _ACCURACY_CACHE.get(key)
        if cached and monotonic() - cached[0] < 60:
            return cached[1]
        result = accuracy_report(runs, all_runs=self._reader.all_runs())
        # Parameter replays run on this child's stored games, so they stay current.
        result["offline"] = replay_report(runs, learner_id)
        result["simulation"] = None
        if SIMULATION_REPORT.exists():
            try:
                result["simulation"] = present_simulation(json.loads(SIMULATION_REPORT.read_text()))
            except (ValueError, OSError):
                pass
        if len(_ACCURACY_CACHE) > 32:
            _ACCURACY_CACHE.clear()
        _ACCURACY_CACHE[key] = (monotonic(), result)
        return result

    def _summary(self, run: Mapping[str, object]) -> dict[str, object]:
        summary = episode_summary(run)
        status = play_status(run, self._now())
        summary["play_status"] = status
        summary["status_label"] = STATUS_LABELS[status]
        return summary

    def _skill_table(self, runs: list[dict[str, object]]) -> list[dict[str, object]]:
        by_skill: dict[str, list[dict[str, object]]] = defaultdict(list)
        for run in runs:
            by_skill[str(_state(run).get("skill_id"))].append(run)
        table = []
        for skill_id, skill_runs in sorted(by_skill.items()):
            area_id = next(
                (str(_state(run)["area_id"]) for run in skill_runs if _state(run).get("area_id")),
                None,
            )
            if area_id is None:
                continue
            completed = [_state(run) for run in skill_runs if run["status"] == "completed"]
            ranking = rank_support_history(completed, order=SUBJECT_ORDERS[subject_of(area_id)])
            decisions = [
                _state(run)["model2"]
                for run in skill_runs
                if isinstance(_state(run).get("model2"), Mapping)
                and "support_order" in _state(run)["model2"]  # type: ignore[operator]
            ]
            latest = decisions[-1] if decisions else {}
            table.append(
                {
                    "skill_id": skill_id,
                    "area_id": area_id,
                    "area_title": area_title(area_id),
                    "episodes": len(skill_runs),
                    "completed": len(completed),
                    "preferred": ranking.preferred,
                    "by_support": ranking.as_record()["by_support"],
                    "latest_mode": latest.get("support_selection_mode") if latest else None,  # type: ignore[union-attr]
                    "latest_first": (latest.get("support_order") or [None])[0] if latest else None,  # type: ignore[union-attr]
                }
            )
        return table


def _state(run: Mapping[str, object]) -> Mapping[str, object]:
    state = run["state"]
    assert isinstance(state, Mapping)
    return state


def _gain(state: Mapping[str, object]) -> Decimal | None:
    """The episode's raw gain; older episodes keep it beside the measurement, not inside it."""

    measurement = state.get("measurement")
    value = measurement.get("raw_independence_gain") if isinstance(measurement, Mapping) else None
    value = value if value is not None else state.get("raw_independence_gain")
    return None if value is None else Decimal(str(value))


def _utc(value: object) -> datetime:
    assert isinstance(value, datetime)
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _pipeline(state: Mapping[str, object]) -> list[dict[str, object]]:
    """Which stage of the loop the episode has reached."""

    status = str(state.get("status"))
    events = {str(event.get("event_type")) for event in state.get("events") or []}
    loop = state.get("support_loop") if isinstance(state.get("support_loop"), Mapping) else {}
    stages = [
        ("answer", "First answer (no help)", "unsupported_before_scored" in events),
        ("difficulty", "Difficulty detected", "difficulty_detected" in events),
        ("model1", "Why it went wrong", isinstance(state.get("model1"), Mapping)),
        ("model2", "Help chosen", isinstance(state.get("model2"), Mapping)),
        ("help", "Help rounds", bool(loop.get("rounds")) if loop else False),
        ("withdrawal", "Help removed", isinstance(state.get("withdrawal"), Mapping)),
        (
            "after",
            "Try alone",
            any(str(row.get("role")) == "unsupported_after" for row in state.get("attempts") or []),
        ),
        ("model3", "Result", isinstance(state.get("measurement"), Mapping)),
        ("update", "What the system learned", bool(state.get("policy_updates"))),
    ]
    return [
        {"key": key, "label": label, "reached": reached, "terminal": status in TERMINAL}
        for key, label, reached in stages
    ]


def _activity_or_update(run: Mapping[str, object]) -> datetime:
    activity = last_child_activity(run)
    if activity is not None:
        return activity
    updated = run.get("updated_at")
    if isinstance(updated, datetime):
        return updated if updated.tzinfo else updated.replace(tzinfo=UTC)
    return datetime.min.replace(tzinfo=UTC)


def _on_live_view(run: Mapping[str, object], now: datetime) -> bool:
    if _state(run).get("seed_source"):
        return False
    status = play_status(run, now)
    if status == "live":
        return True
    if status not in {"finished", "abandoned"}:
        return False
    stamp = _activity_or_update(run)
    return now - stamp <= RECENT_WINDOW


def _weeks(completed: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    for run in completed:
        state = _state(run)
        moment = _first_event(run)
        if moment is None:
            continue
        monday = moment.date() - timedelta(days=moment.weekday())
        key = monday.isoformat()
        bucket = buckets.setdefault(
            key,
            {
                "start": key,
                "label": f"{monday.day} {monday.strftime('%b')}",
                "alone": 0,
                "still": 0,
                "right": 0,
            },
        )
        before = next(
            (
                row
                for row in state.get("attempts") or []
                if isinstance(row, Mapping) and row.get("role") == "unsupported_before"
            ),
            None,
        )
        helped = bool(state.get("support_loop") or state.get("measurement"))
        if is_independent(state):
            bucket["alone"] = int(bucket["alone"]) + 1
        elif helped:
            bucket["still"] = int(bucket["still"]) + 1
        elif before and before.get("correct"):
            bucket["right"] = int(bucket["right"]) + 1
    return [buckets[key] for key in sorted(buckets)]


def _board(completed: list[dict[str, object]]) -> list[dict[str, object]]:
    played: dict[str, int] = defaultdict(int)
    for run in completed:
        played[resolved_area(_state(run))] += 1
    board = []
    for area_id in sorted(area_titles()):
        if not str(area_id).startswith("G5-AREA-"):
            continue
        subject = "ENG" if "-SIN-" in area_id or "-ENG-" in area_id else "MAT"
        board.append(
            {
                "area_id": area_id,
                "title": english_title(area_id),
                "subject": subject,
                "played": played.get(area_id, 0),
            }
        )
    return board


def _first_event(run: Mapping[str, object]) -> datetime | None:
    events = _state(run).get("events") or []
    if isinstance(events, list) and events and isinstance(events[0], Mapping):
        parsed = parse_time(events[0].get("occurred_at"))
        if parsed is not None:
            return parsed
    return parse_time(run.get("updated_at"))
