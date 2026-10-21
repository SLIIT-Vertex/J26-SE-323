"""Abandoned games stay in the record, and they stop looking live after ten idle minutes."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.gamification.application.research_accuracy import accuracy_report, present_simulation
from app.gamification.application.research_dashboard import ResearchDashboardService
from app.gamification.application.research_history import model_history
from app.gamification.application.research_play_status import IDLE_TIMEOUT, play_status

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
LEARNER = UUID("00000000-0000-4000-8000-0000000000aa")


def _run(status, *, events=None, updated_at=None, **state):
    return {
        "status": status,
        "updated_at": updated_at,
        "state": {
            "episode_id": "00000000-0000-4000-8000-0000000000e1",
            "area_id": "G5-AREA-MAT-03",
            "skill_id": "G5-MAT-PAT-RATIO-2-01",
            "condition": "proposed",
            "events": events if events is not None else [],
            **state,
        },
    }


def _at(delta: timedelta) -> str:
    return (NOW - delta).isoformat()


def test_play_status_follows_the_idle_rule():
    fresh = _run("support_active", events=[{"occurred_at": _at(IDLE_TIMEOUT)}], updated_at=NOW)
    idle = _run(
        "support_active",
        events=[{"occurred_at": _at(IDLE_TIMEOUT + timedelta(seconds=1))}],
        updated_at=NOW,
    )
    assert play_status(fresh, NOW) == "live"
    assert play_status(idle, NOW) == "abandoned"
    assert play_status(_run("support_active", events=[], updated_at=None), NOW) == "abandoned"
    touched = _run(
        "support_active",
        events=[{"occurred_at": _at(timedelta(minutes=11))}],
        updated_at=NOW,
    )
    assert play_status(touched, NOW) == "abandoned"
    assert play_status(_run("completed", events=[], updated_at=None), NOW) == "finished"
    assert play_status(_run("invalidated", events=[], updated_at=NOW), NOW) == "invalid"


def test_history_labels_an_idle_game_as_stopped():
    run = _run(
        "support_active",
        events=[{"occurred_at": _at(timedelta(minutes=11)), "event_type": "opened"}],
        updated_at=NOW - timedelta(minutes=11),
        attempts=[{"role": "unsupported_before", "correct": False}],
    )

    entry = model_history([run], "support", now=NOW)[0]

    assert entry["in_progress"] is False
    assert entry["play_status"] == "abandoned"
    assert entry["status"] == "Stopped partway · not counted"


class _Reader:
    def __init__(self, runs):
        self._runs = runs

    def runs(self, learner_id):
        return self._runs

    def run(self, episode_id):
        return self._runs[0]

    def learner_state(self, learner_id):
        return []

    def profile(self, learner_id):
        return {"display_name": "Test", "learner_id": str(learner_id)}

    def all_runs(self):
        return self._runs


def test_live_and_counts_ignore_abandoned_games():
    abandoned = _run(
        "support_active",
        events=[{"occurred_at": _at(timedelta(minutes=11)), "event_type": "opened"}],
        updated_at=NOW - timedelta(minutes=11),
    )
    live = _run(
        "support_active",
        events=[{"occurred_at": _at(timedelta(minutes=1)), "event_type": "opened"}],
        updated_at=NOW,
    )
    live["state"]["episode_id"] = "00000000-0000-4000-8000-0000000000e2"
    service = ResearchDashboardService(_Reader([abandoned]), now=lambda: NOW)

    assert service.live(LEARNER)["active"] is False
    assert service.overview(LEARNER)["counts"]["in_progress"] == 0
    assert service.overview(LEARNER)["counts"]["abandoned"] == 1

    active = ResearchDashboardService(_Reader([live]), now=lambda: NOW)
    assert active.live(LEARNER)["active"] is True


def test_accuracy_ignores_an_abandoned_game_with_a_before_answer():
    abandoned = _run(
        "support_active",
        events=[{"occurred_at": _at(timedelta(minutes=11))}],
        updated_at=NOW - timedelta(minutes=11),
        attempts=[
            {
                "role": "unsupported_before",
                "correct": False,
                "structured_error_code": "wrong_direction",
                "assistance_state": "none",
            }
        ],
        model1={"probabilities": {"wrong_direction": 0.8}, "predicted_label": "wrong_direction"},
    )

    report = accuracy_report([abandoned])

    assert all(metric["count"] == 0 for model in report["models"] for metric in model["metrics"])


def test_simulated_blocks_carry_a_headline_and_only_the_child_tiles_are_marked():
    simulation = present_simulation(
        {
            "models": [
                {
                    "name": "Probabilistic Misconception",
                    "metrics": [{"title": "Found the true kind of mistake", "value": 0.9}],
                },
                {
                    "name": "Contextual Support Selection",
                    "metrics": [
                        {
                            "title": "First help was the one that really works (proposed)",
                            "value": 0.7,
                        },
                        {
                            "title": "First help was the one that really works (comparison group)",
                            "value": 0.3,
                        },
                    ],
                },
                {
                    "name": "Independence Gain",
                    "metrics": [{"title": "Measured gain agrees with real learning", "value": 0.8}],
                },
            ]
        }
    )
    assert simulation is not None
    for model in simulation["models"]:
        assert model["headline"]
        assert "value" in model["reference"]

    tiles = [
        metric["key"]
        for model in accuracy_report([])["models"]
        for metric in model["metrics"]
        if metric["tile"]
    ]
    assert tiles == ["agreement", "calibration", "first", "preference", "fair", "repeat"]
