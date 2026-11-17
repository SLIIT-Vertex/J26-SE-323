"""Replay stored game episodes through today's rule-based Model 1 and Model 2. Read-only.

For every stored episode with a Model 1 record, the belief is rebuilt from the inputs the record
holds (error code, response time, interaction summary and learner-prior window) and compared with
the stored belief. For every episode whose Model 2 record has the current order policy, the help
order is rebuilt from the stored Model 1 reading, Learning State reading and drawable helps, and
the learner's completed episodes of that skill that finished before the decision. Sinhala episodes
are compared with the order the package delivered, through its authored sequence and cursor.

This shows whether the frozen reference fixtures describe what the app really did, and how older
records differ. Only counts are printed: no learner, episode or answer data is written anywhere.

    PYTHONPATH=backend python3 tools/gamification/learning_flow/replay_stored_rule_decisions.py
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

import app.main  # noqa: F401  imports every mapped model, as the API does
from app.gamification.application.engine.area_flow import (
    AreaGameFlow,
    _model1_label,
    _model1_uncertain,
)
from app.gamification.application.engine.sinhala_area_flow import (
    AUTHORED_SEQUENCE,
    SinhalaAreaFlow,
    _support_cursor,
    activity_order,
)
from app.gamification.application.learning_flow_orchestration import GAME_FLOW_TYPES
from app.gamification.infrastructure.db.models import LearningFlowEpisodeRunModel
from app.gamification.modeling.misconception_inference.bayesian_model import GAME_MODEL_VERSION
from app.gamification.modeling.misconception_inference.learner_prior import apply_learner_prior
from app.gamification.modeling.support_selection.support_order import (
    ORDER_POLICY_VERSION,
    choose_support_order,
    subject_of,
)

PROBABILITY_TOLERANCE = 1e-12
# Fields choose_support_order adds to the Learning State reading it stores.
_READING_OUTPUT_FIELDS = ("changed_first_help", "changed_order")
FLOWS: dict[str, type[AreaGameFlow]] = {
    flow_type.experience_id: flow_type for flow_type in GAME_FLOW_TYPES
}


def _flow_type(state: Mapping[str, object]) -> type[AreaGameFlow] | None:
    flow_type = FLOWS.get(str(state.get("experience_id")))
    if flow_type is None:
        flow_type = next(
            (f for f in GAME_FLOW_TYPES if f.area_id == state.get("area_id")),
            None,
        )
    return flow_type


def replay_model1(state: Mapping[str, object]) -> str:
    """``match``, ``differs:<fields>``, ``not_rule_based`` or ``not_replayable:<reason>``.

    Beliefs written by the expert-initialised Bayesian model are not rule decisions and are
    counted as ``not_rule_based``; their own checks are in the demo-seed verifier.
    """

    flow_type = _flow_type(state)
    stored = state.get("model1")
    if flow_type is None:
        return "not_replayable:unknown_game"
    if not isinstance(stored, Mapping) or "structured_error_code" not in stored:
        return "not_replayable:no_error_code"
    if stored.get("model_version") == GAME_MODEL_VERSION:
        return "not_rule_based"
    flow = flow_type.__new__(flow_type)
    belief = flow._infer_belief(
        str(stored["structured_error_code"]),
        response_time_ms=stored.get("response_time_ms"),
        interaction_summary=dict(stored.get("structured_response") or {}),
    )
    if "prior_version" in stored:
        belief = apply_learner_prior(belief, list(stored.get("prior_window") or []))
    differences = []
    expected, recorded = belief["probabilities"], stored.get("probabilities") or {}
    if set(expected) != set(recorded) or any(
        not math.isclose(expected[code], float(recorded[code]), abs_tol=PROBABILITY_TOLERANCE)
        for code in expected
    ):
        differences.append("probabilities")
    if _model1_label(belief) != _model1_label(stored):
        differences.append("label")
    if _model1_uncertain(belief) != _model1_uncertain(stored):
        differences.append("uncertain")
    return "match" if not differences else "differs:" + ",".join(differences)


def replay_model2(state: Mapping[str, object], history: Iterable[Mapping[str, object]]) -> str:
    """``match``, ``differs:<fields>``, ``older_policy:<version>`` or ``not_replayable:<reason>``.

    ``history`` is the learner's completed episodes of the skill that finished before this
    episode's decision, oldest first, as the store returned them at the time.
    """

    flow_type = _flow_type(state)
    stored = state.get("model2")
    model1 = state.get("model1")
    if flow_type is None:
        return "not_replayable:unknown_game"
    if not isinstance(stored, Mapping) or not isinstance(model1, Mapping):
        return "not_replayable:no_decision"
    version = stored.get("order_policy_version")
    if version != ORDER_POLICY_VERSION:
        return f"older_policy:{version}"
    condition = str(stored.get("condition", state.get("condition")))
    proposed = condition == "proposed"
    sinhala = issubclass(flow_type, SinhalaAreaFlow)
    history = tuple(history)
    if sinhala:
        history = tuple(
            row for row in history if row.get("experience_id") == flow_type.experience_id
        )
    reading = {
        key: value
        for key, value in dict(stored.get("learning_state_input") or {}).items()
        if key not in _READING_OUTPUT_FIELDS
    }
    renderable = tuple(stored.get("renderable_actions") or ())
    decision = choose_support_order(
        subject=subject_of(flow_type.area_id),
        condition=condition,
        model1_label=_model1_label(model1),
        model1_uncertain=_model1_uncertain(model1),
        eligible=tuple(stored.get("eligible_actions") or ()),
        renderable=renderable,
        history=history if proposed else (),
        learning_state_input=reading,
    )
    order = decision.order
    differences = []
    if sinhala:
        authored = tuple(support for support in AUTHORED_SEQUENCE if support in renderable)
        cursor = _support_cursor(history, proposed=proposed)
        order, reason = activity_order(
            decision, authored=authored, cursor=cursor, proposed=proposed
        )
        if reason != stored.get("selection_reason"):
            differences.append("selection_reason")
    if list(order) != list(stored.get("support_order") or ()):
        differences.append("first_help" if order[0] != stored.get("selected_action") else "order")
    if decision.reason_family != stored.get("reason_family"):
        differences.append("reason_family")
    if decision.selection_mode != stored.get("support_selection_mode"):
        differences.append("selection_mode")
    return "match" if not differences else "differs:" + ",".join(differences)


def _decided_at(state: Mapping[str, object]) -> datetime | None:
    model2 = state.get("model2")
    created = model2.get("created_at") if isinstance(model2, Mapping) else None
    return datetime.fromisoformat(str(created)) if created else None


def replay(session: Session) -> dict[str, object]:
    """Counts of replay outcomes over every stored episode, grouped by subject and version."""

    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET TRANSACTION READ ONLY"))
    rows = session.execute(
        select(
            LearningFlowEpisodeRunModel.learner_id,
            LearningFlowEpisodeRunModel.skill_id,
            LearningFlowEpisodeRunModel.status,
            LearningFlowEpisodeRunModel.environment,
            LearningFlowEpisodeRunModel.updated_at,
            LearningFlowEpisodeRunModel.state_json,
        ).order_by(LearningFlowEpisodeRunModel.updated_at, LearningFlowEpisodeRunModel.episode_id)
    ).all()
    completed: dict[tuple[object, str], list[tuple[datetime, Mapping[str, object]]]] = defaultdict(
        list
    )
    for row in rows:
        if row.status == "completed":
            completed[(row.learner_id, row.skill_id)].append(
                (_aware(row.updated_at), row.state_json)
            )

    model1: Counter[tuple[str, str, str, str]] = Counter()
    model2: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        state = row.state_json
        if not isinstance(state, Mapping) or "model1" not in state:
            continue
        flow_type = _flow_type(state)
        subject = subject_of(flow_type.area_id) if flow_type else "unknown"
        stored1 = state.get("model1") or {}
        model1[
            (subject, row.environment, str(stored1.get("model_version")), replay_model1(state))
        ] += 1
        if "model2" not in state:
            continue
        decided = _decided_at(state)
        history = [
            earlier
            for finished, earlier in completed[(row.learner_id, row.skill_id)]
            if decided is not None and finished < decided and earlier is not state
        ]
        stored2 = state.get("model2") or {}
        model2[
            (
                subject,
                row.environment,
                str(stored2.get("order_policy_version")),
                replay_model2(state, history),
            )
        ] += 1
    session.rollback()

    def table(counts: Counter[tuple[str, str, str, str]]) -> list[dict[str, object]]:
        return [
            {
                "subject": subject,
                "environment": environment,
                "version": version,
                "outcome": outcome,
                "episodes": count,
            }
            for (subject, environment, version, outcome), count in sorted(counts.items())
        ]

    return {
        "episodes_read": len(rows),
        "order_policy_version_replayed": ORDER_POLICY_VERSION,
        "model1": table(model1),
        "model2": table(model2),
    }


def _aware(moment: datetime) -> datetime:
    # SQLite returns the stored UTC time without its zone.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    from app.shared.database.session import SessionLocal

    with SessionLocal() as session:
        print(json.dumps(replay(session), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
