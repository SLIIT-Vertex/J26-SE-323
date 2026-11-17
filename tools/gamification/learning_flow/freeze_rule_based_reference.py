"""Freeze what today's rule-based Model 1 and Model 2 return, as reference fixtures.

The research models are to replace the authored rules in the games. Before they learn anything
new they must reproduce what the rules return now, so this tool records it for every game in
``GAME_FLOW_TYPES``:

- Model 1 (``rule_based_beliefs.json``): each game's ``infer_belief`` for every code it lists and
  one it does not, plain and sparse, and for the Sinhala packages with motor and rendering
  evidence; the belief the game really builds, through its own belief hook and the learner prior,
  for every kind of input it can receive; and ``apply_learner_prior`` over fixed answer histories.
- Model 2 (``rule_based_support_orders.json``): the reason family of every label each subject's
  games can return, and the record ``choose_support_order`` returns for each subject, reason
  family, Learning State reading, help history and set of drawable helps. Sinhala entries also
  record the order the package really delivers from its authored sequence and cursor.

The fixtures hold no commit hash, so a second run writes the same bytes. The manifest records the
source commit, whether the worktree was dirty, and SHA-256 hashes of the fixtures and of the source
files whose rules they freeze.

    PYTHONPATH=backend python3 tools/gamification/learning_flow/freeze_rule_based_reference.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

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
from app.gamification.content import area_support_catalog, sinhala_common
from app.gamification.modeling.misconception_inference import learner_prior
from app.gamification.modeling.support_selection import support_order

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIRECTORY = ROOT / "backend" / "tests" / "gamification" / "fixtures"
BELIEFS_FILE = "rule_based_beliefs.json"
ORDERS_FILE = "rule_based_support_orders.json"
MANIFEST_FILE = "rule_based_reference_manifest.json"
REFERENCE_VERSION = "rule-based-reference-v1"

SUBJECTS = ("MAT", "ENG", "SIN")
REASON_FAMILIES = ("representation", "procedure", "relation", "prerequisite", "unclear")
UNKNOWN = "unknown_or_other"
# A code no game lists, so each game's fallback is frozen too.
UNLISTED_CODE = "code_not_in_any_catalogue"
UNCERTAIN_FLAGS = ("abstained", "low_confidence", "fallback_used")
RESPONSE_TIME_MS = 4_000
# Timing fields every game accepts in its interaction summary.
TIMING_SUMMARY: dict[str, object] = {"first_action_ms": 800, "active_time_ms": 4_000}

_SUPPORT_NEED_READING = {
    "age_ms": 1_000,
    "observed_at": "2026-11-18T09:00:00+00:00",
    "session_id": "reference-session",
}
LEARNING_STATE_READINGS: dict[str, dict[str, object]] = {
    "not_available": {"status": "not_available", "reason": "NOT_FOUND"},
    "calm": {"status": "available", "state": "calm", "support_need": 0.2, **_SUPPORT_NEED_READING},
    "confused": {
        "status": "available",
        "state": "confused",
        "support_need": 0.7,
        **_SUPPORT_NEED_READING,
    },
    "disengaged": {
        "status": "available",
        "state": "disengaged",
        "support_need": 0.4,
        **_SUPPORT_NEED_READING,
    },
}

Input = tuple[str, int | None, dict[str, object]]


# --- Model 1 --------------------------------------------------------------------------------


def _is_sinhala(flow_type: type[AreaGameFlow]) -> bool:
    return issubclass(flow_type, SinhalaAreaFlow)


def _game_inputs(flow_type: type[AreaGameFlow]) -> tuple[Input, ...]:
    """Every kind of input that can change what this game's belief hook returns."""

    if _is_sinhala(flow_type):
        # Timing is ignored on purpose; the interaction summary carries motor and rendering signals.
        return (
            ("no_interaction_signal", RESPONSE_TIME_MS, dict(TIMING_SUMMARY)),
            ("no_response_time", None, dict(TIMING_SUMMARY)),
            ("motor_corrections", RESPONSE_TIME_MS, {**TIMING_SUMMARY, "correction_count": 3}),
            (
                "motor_cancelled_drags",
                RESPONSE_TIME_MS,
                {**TIMING_SUMMARY, "cancelled_drag_count": 2},
            ),
            (
                "rendering_problem",
                RESPONSE_TIME_MS,
                {**TIMING_SUMMARY, "rendering_issue_reported": True},
            ),
            (
                "motor_and_rendering",
                RESPONSE_TIME_MS,
                {**TIMING_SUMMARY, "correction_count": 3, "rendering_issue_reported": True},
            ),
        )
    inputs: list[Input] = [
        ("timed", RESPONSE_TIME_MS, dict(TIMING_SUMMARY)),
        ("untimed", None, {}),
    ]
    if "_infer_belief" in vars(flow_type):
        # These games read evidence quality from the summary, so an empty one changes the belief.
        inputs += [
            ("timed_without_summary", RESPONSE_TIME_MS, {}),
            ("untimed_with_summary", None, dict(TIMING_SUMMARY)),
            # What the phone sends for these games today.
            (
                "phone_evidence_quality",
                RESPONSE_TIME_MS,
                {**TIMING_SUMMARY, "evidence_quality": 0.8},
            ),
        ]
    return tuple(inputs)


def _unexplained_answer_inputs(flow_type: type[AreaGameFlow]) -> tuple[Input, ...]:
    """Summaries a game uses to explain an ``unknown_or_other`` answer, if it has that rule."""

    if not hasattr(sys.modules[flow_type.__module__], "apply_interaction_evidence"):
        return ()
    signals = (
        ("started_from_ones", False),
        ("alignment_valid", False),
        ("invalid_exchange_count", 1),
        ("operation_changes", 1),
        ("story_reorder_count", 1),
    )
    return tuple(
        (f"explained_by_{key}", RESPONSE_TIME_MS, {**TIMING_SUMMARY, key: value})
        for key, value in signals
    )


def _encode(value: object, codes: tuple[str, ...]) -> object:
    """JSON-ready copy. A mapping over exactly the game's codes becomes a list in ``codes`` order."""

    if isinstance(value, Mapping):
        if set(value) == set(codes):
            return [_encode(value[code], codes) for code in codes]
        return {str(key): _encode(item, codes) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item, codes) for item in value]
    return value


def _model1_reading(belief: Mapping[str, object]) -> dict[str, object]:
    """What Model 2 reads from a belief."""

    return {
        "model1_label": _model1_label(belief),
        "model1_uncertain": _model1_uncertain(belief),
        "uncertain_because": [flag for flag in UNCERTAIN_FLAGS if belief.get(flag) is True],
    }


def _answer(code: str | None, *, role: str = "unsupported_before", assisted: bool = False):
    return {
        "role": role,
        "assistance_state": "active" if assisted else "none",
        "correct": code is None,
        "structured_error_code": code,
    }


def _prior_histories(codes: tuple[str, ...]) -> dict[str, list[dict[str, object]]]:
    """Stored-episode answer histories, built from the game's own first two listed codes."""

    first, second = [code for code in codes if code != UNKNOWN][:2]
    supported = _answer(first, role="supported_practice", assisted=True)
    return {
        "none": [],
        "two_unaided_same_code": [{"attempts": [_answer(first)]}, {"attempts": [_answer(first)]}],
        "two_unaided_other_code": [
            {"attempts": [_answer(second)]},
            {"attempts": [_answer(second)]},
        ],
        "mixed_with_correct_and_supported": [
            {
                "attempts": [
                    _answer(first),
                    supported,
                    _answer(None, role="unsupported_after"),
                ]
            },
            {"attempts": [_answer(second), _answer(UNKNOWN, role="unsupported_after")]},
        ],
        # More than five answers: only the last five count, and a correct one keeps its place.
        "seven_unaided_answers": [
            {
                "attempts": [
                    _answer(second),
                    _answer(second),
                    _answer(second),
                    _answer(first),
                    _answer(None, role="unsupported_after"),
                    _answer(first),
                    _answer(UNKNOWN),
                ]
            }
        ],
        "supported_answers_only": [{"attempts": [supported, supported, supported]}],
    }


def _game_belief_record(belief: Mapping[str, object], codes: tuple[str, ...]) -> dict[str, object]:
    """The belief after the learner prior, without ``posterior``, which repeats ``probabilities``."""

    if belief["posterior"] != belief["probabilities"]:
        raise ValueError("the learner prior's posterior no longer equals its probabilities")
    return {
        "belief": _encode({k: v for k, v in belief.items() if k != "posterior"}, codes),
        **_model1_reading(belief),
    }


def _area_beliefs(flow_type: type[AreaGameFlow]) -> dict[str, list[dict[str, object]]]:
    # Only the belief hooks are called, and they need no store, so no constructor runs.
    flow = flow_type.__new__(flow_type)
    area_id = flow_type.area_id
    infer_belief = flow_type.infer_belief
    codes = tuple(infer_belief(UNKNOWN)["probabilities"])
    observed = (*codes, UNLISTED_CODE)
    inputs = _game_inputs(flow_type)
    unexplained = _unexplained_answer_inputs(flow_type)
    histories = _prior_histories(codes)

    calls: list[tuple[str, dict[str, object]]] = [("plain", {}), ("sparse", {"sparse": True})]
    if _is_sinhala(flow_type):
        calls += [(name, {"interaction_summary": summary}) for name, _, summary in inputs[2:]]
    raw = [
        {
            "area_id": area_id,
            "error_code": code,
            "call": name,
            "belief": _encode(infer_belief(code, **kwargs), codes),
        }
        for code in observed
        for name, kwargs in calls
    ]

    def game_belief(code: str, response_time_ms: int | None, summary, errors=()):
        belief = flow._infer_belief(
            code, response_time_ms=response_time_ms, interaction_summary=summary
        )
        return learner_prior.apply_learner_prior(belief, errors)

    game = [
        {
            "area_id": area_id,
            "error_code": code,
            "input": name,
            **_game_belief_record(game_belief(code, response_time_ms, summary), codes),
        }
        for code in observed
        for name, response_time_ms, summary in inputs + (unexplained if code == UNKNOWN else ())
    ]

    first = next(code for code in codes if code != UNKNOWN)
    prior = []
    for history_name, history in histories.items():
        window = learner_prior.prior_errors(history)
        for code, (name, response_time_ms, summary) in (
            (first, inputs[0]),
            (UNKNOWN, inputs[0]),
            (first, inputs[1]),
        ):
            prior.append(
                {
                    "area_id": area_id,
                    "history": history_name,
                    "error_code": code,
                    "input": name,
                    "prior_window": window,
                    **_game_belief_record(
                        game_belief(code, response_time_ms, summary, window), codes
                    ),
                }
            )

    area = {
        "area_id": area_id,
        "subject": support_order.subject_of(area_id),
        "game": flow_type.__name__,
        "experience_id": flow_type.experience_id,
        "model_version": flow_type.model_version,
        "catalogue_version": flow_type.catalogue_version,
        "package_sha256": flow_type.package_hash(),
        "codes": list(codes),
        "inputs": {
            name: {"response_time_ms": response_time_ms, "interaction_summary": summary}
            for name, response_time_ms, summary in inputs + unexplained
        },
        "prior_histories": histories,
    }
    return {"areas": [area], "infer_belief": raw, "game_belief": game, "learner_prior": prior}


def build_beliefs() -> dict[str, object]:
    sections: dict[str, list[dict[str, object]]] = {
        "areas": [],
        "infer_belief": [],
        "game_belief": [],
        "learner_prior": [],
    }
    for flow_type in GAME_FLOW_TYPES:
        for name, records in _area_beliefs(flow_type).items():
            sections[name] += records
    return {
        "reference_version": REFERENCE_VERSION,
        "learner_prior_version": learner_prior.PRIOR_VERSION,
        "learner_prior_cap": learner_prior.PRIOR_CAP,
        "unlisted_code": UNLISTED_CODE,
        "notes": [
            "Every mapping over a game's codes is a list in that area's codes order.",
            (
                "game_belief and learner_prior hold the belief after the learner prior; its "
                "posterior always equals probabilities, so it is left out."
            ),
        ],
        **sections,
    }


# --- Model 2 --------------------------------------------------------------------------------


def _games_by_subject() -> dict[str, list[type[AreaGameFlow]]]:
    games: dict[str, list[type[AreaGameFlow]]] = {subject: [] for subject in SUBJECTS}
    for flow_type in GAME_FLOW_TYPES:
        games[support_order.subject_of(flow_type.area_id)].append(flow_type)
    return games


def _eligible(flow_type: type[AreaGameFlow]) -> tuple[str, ...]:
    """The helps the game offers Model 2, as its flow computes them."""

    eligible = area_support_catalog.assignment(flow_type.area_id).eligible_support_types
    if _is_sinhala(flow_type):
        return tuple(support for support in eligible if support in AUTHORED_SEQUENCE)
    return tuple(eligible)


def _lead(subject: str, family: str) -> str:
    return support_order.SUBJECT_LEAD_BY_REASON.get(subject, support_order.LEAD_BY_REASON)[family]


def _episode(
    subject: str,
    rounds: list[tuple[str, str]],
    after_correct: bool,
    *,
    stop_reason: str | None = None,
    condition: str = "proposed",
    valid: bool = True,
    learning_state: str = "not_available",
    selection_reason: str = "activity_default",
) -> dict[str, object]:
    """One completed episode in the shape the store returns as support history."""

    earned = "1" if after_correct else "0"
    gain = earned if valid else None
    if stop_reason is None:
        stop_reason = "supported_success" if rounds[-1][1] == "succeeded" else "order_exhausted"
    episode: dict[str, object] = {
        "status": "completed",
        "condition": condition,
        "validity": "valid" if valid else "invalid",
        "measurement": {
            "before_earned": "0",
            "before_maximum": "1",
            "after_earned": earned,
            "after_maximum": "1",
            "raw_independence_gain": gain,
            "valid": valid,
        },
        "raw_independence_gain": gain,
        "support_loop": {
            "order": [support for support, _ in rounds],
            "types_used": [support for support, _ in rounds],
            "rounds": [
                {"scaffold_type": support, "outcome": outcome} for support, outcome in rounds
            ],
            "stop_reason": stop_reason,
        },
        "model2": {"learning_state_input": dict(LEARNING_STATE_READINGS[learning_state])},
    }
    if subject == "SIN":
        episode["support_cursor"] = {"start_position": AUTHORED_SEQUENCE.index(rounds[0][0])}
        episode["model2"]["selection_reason"] = selection_reason  # type: ignore[index]
    return episode


def _support_histories(subject: str) -> dict[str, list[dict[str, object]]]:
    """Help histories named after the demo seed's patterns, in this subject's help types."""

    order = support_order.SUBJECT_ORDERS[subject]
    first, second = order[0], order[1]
    simpler = "simpler_same_game" if "simpler_same_game" in order else order[-1]

    def episode(*args, **kwargs):
        return _episode(subject, *args, **kwargs)

    def works_on_round_two(**kwargs):
        return episode([(first, "failed"), (second, "succeeded")], True, **kwargs)

    old_single_help = {
        "status": "completed",
        "condition": "proposed",
        "validity": "valid",
        "measurement": {"after_earned": "1", "after_maximum": "1", "raw_independence_gain": "1"},
        "model2": {"selected_action": second},
    }
    return {
        "none": [],
        "responds_to_round_1": [episode([(first, "succeeded")], True)],
        "responds_to_round_2": [works_on_round_two()],
        "responds_to_round_2_twice": [works_on_round_two(), works_on_round_two()],
        "needs_two_tries": [
            episode([(first, "failed"), (second, "succeeded")], False),
            works_on_round_two(),
        ],
        "helped_but_not_independent": [episode([(first, "succeeded")], False)],
        "all_rounds_fail": [episode([(support, "failed") for support in order], True)],
        "watched_demonstration": [
            episode(
                [(first, "failed"), ("worked_parallel_example", "viewed")],
                True,
                stop_reason="support_viewed",
            )
        ],
        "exits_after_help": [episode([(first, "succeeded")], False, valid=False)],
        "baseline_episode": [works_on_round_two(condition="baseline")],
        "succeeded_while_confused_twice": [
            episode([(simpler, "succeeded")], True, learning_state="confused"),
            episode([(simpler, "succeeded")], True, learning_state="confused"),
        ],
        "learned_preference_then_failed": [
            works_on_round_two(),
            works_on_round_two(),
            episode(
                [(second, "succeeded")],
                False,
                selection_reason="learned_activity_preference",
            ),
        ],
        "old_single_help_record": [old_single_help],
    }


def _model1_variants(subject: str, labels: list[str]) -> list[tuple[str, bool]]:
    """One real label per reason family the subject's games can return, then an uncertain one."""

    variants = []
    for family in REASON_FAMILIES:
        members = [
            label
            for label in labels
            if support_order.reason_family(label, subject=subject) == family
        ]
        if members:
            variants.append((members[0], False))
    variants.append((variants[0][0], True))
    return variants


def _decision(
    subject: str,
    *,
    condition: str,
    label: str,
    uncertain: bool,
    helps: str,
    renderable: tuple[str, ...],
    eligible: tuple[str, ...],
    reading: str,
    history_name: str,
    history: list[dict[str, object]],
) -> dict[str, object]:
    proposed = condition == "proposed"
    # The games pass history only in the proposed condition.
    history = history if proposed else []
    decision = support_order.choose_support_order(
        subject=subject,
        condition=condition,
        model1_label=label,
        model1_uncertain=uncertain,
        eligible=eligible,
        renderable=renderable,
        history=history,
        learning_state_input=LEARNING_STATE_READINGS[reading],
    )
    entry: dict[str, object] = {
        "subject": subject,
        "condition": condition,
        "model1_label": label,
        "model1_uncertain": uncertain,
        "helps": helps,
        "renderable": list(renderable),
        "learning_state": reading,
        "history": history_name,
        "decision": decision.as_record(),
    }
    if subject == "SIN":
        cursor = _support_cursor(tuple(history), proposed=proposed)
        authored = tuple(support for support in AUTHORED_SEQUENCE if support in renderable)
        order, reason = activity_order(
            decision, authored=authored, cursor=cursor, proposed=proposed
        )
        entry["delivered"] = {
            "support_order": list(order),
            "selection_reason": reason,
            "support_cursor": cursor,
        }
    return entry


def build_orders() -> dict[str, object]:
    games = _games_by_subject()
    labels: dict[str, dict[str, list[str]]] = {subject: {} for subject in SUBJECTS}
    eligible: dict[str, tuple[str, ...]] = {}
    for subject, flow_types in games.items():
        for flow_type in flow_types:
            for code in flow_type.infer_belief(UNKNOWN)["probabilities"]:
                labels[subject].setdefault(code, []).append(flow_type.area_id)
            helps = _eligible(flow_type)
            if eligible.setdefault(subject, helps) != helps:
                raise ValueError(f"{flow_type.area_id} offers different helps from its subject")

    families: dict[str, dict[str, object]] = {}
    for subject in SUBJECTS:
        rows: dict[str, object] = {}
        for label in sorted(labels[subject]):
            family, decided_by = support_order.reason_family_match(label, subject=subject)
            rows[label] = {
                "reason_family": family,
                "decided_by": decided_by,
                "lead": _lead(subject, family),
                "games": labels[subject][label],
            }
        family, decided_by = support_order.reason_family_match(None, subject=subject)
        families[subject] = {
            "labels": rows,
            "missing_label": {"reason_family": family, "decided_by": decided_by},
        }

    histories = {subject: _support_histories(subject) for subject in SUBJECTS}
    decisions = []
    for subject in SUBJECTS:
        helps = eligible[subject]
        variants = _model1_variants(subject, sorted(labels[subject]))
        common = {"eligible": helps}
        for label, uncertain in variants:
            for reading in LEARNING_STATE_READINGS:
                for history_name, history in histories[subject].items():
                    decisions.append(
                        _decision(
                            subject,
                            condition="proposed",
                            label=label,
                            uncertain=uncertain,
                            helps="all_eligible",
                            renderable=helps,
                            reading=reading,
                            history_name=history_name,
                            history=history,
                            **common,
                        )
                    )
        for condition in ("proposed", "baseline"):
            for label, uncertain in variants:
                family = (
                    "unclear" if uncertain else support_order.reason_family(label, subject=subject)
                )
                lead = _lead(subject, family)
                help_sets = {
                    "lead_not_drawable": tuple(support for support in helps if support != lead),
                    "worked_example_only": ("worked_parallel_example",),
                }
                if condition == "baseline":
                    help_sets = {"all_eligible": helps, **help_sets}
                for helps_name, renderable in help_sets.items():
                    decisions.append(
                        _decision(
                            subject,
                            condition=condition,
                            label=label,
                            uncertain=uncertain,
                            helps=helps_name,
                            renderable=renderable,
                            reading="not_available",
                            history_name="none",
                            history=[],
                            **common,
                        )
                    )

    return {
        "reference_version": REFERENCE_VERSION,
        "order_policy_version": support_order.ORDER_POLICY_VERSION,
        "subject_orders": {
            subject: list(support_order.SUBJECT_ORDERS[subject]) for subject in SUBJECTS
        },
        "lead_by_reason": {
            subject: {family: _lead(subject, family) for family in REASON_FAMILIES}
            for subject in SUBJECTS
        },
        "eligible_helps": {
            subject: {
                "helps": list(eligible[subject]),
                "games": [f.area_id for f in games[subject]],
            }
            for subject in SUBJECTS
        },
        "sinhala_authored_sequence": list(AUTHORED_SEQUENCE),
        "learning_state_readings": LEARNING_STATE_READINGS,
        "histories": histories,
        "reason_families": families,
        "decisions": decisions,
    }


# --- Files ----------------------------------------------------------------------------------


def _compact(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _text(payload: Mapping[str, object]) -> str:
    """JSON with one top-level key, or one record of a record list, per line, for readable diffs."""

    lines = ["{"]
    keys = sorted(payload)
    for index, key in enumerate(keys):
        value = payload[key]
        comma = "," if index < len(keys) - 1 else ""
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            lines.append(f"{_compact(key)}:[")
            lines += [
                _compact(item) + ("," if position < len(value) - 1 else "")
                for position, item in enumerate(value)
            ]
            lines.append(f"]{comma}")
        else:
            lines.append(f"{_compact(key)}:{_compact(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_fixtures() -> dict[str, str]:
    """Fixture file name to its exact text."""

    return {BELIEFS_FILE: _text(build_beliefs()), ORDERS_FILE: _text(build_orders())}


def rule_sources() -> list[Path]:
    """Source files whose rules the fixtures freeze."""

    modules = {
        area_support_catalog,
        learner_prior,
        sinhala_common,
        support_order,
        sys.modules[AreaGameFlow.__module__],
        sys.modules[SinhalaAreaFlow.__module__],
    }
    for flow_type in GAME_FLOW_TYPES:
        modules.add(sys.modules[flow_type.__module__])
        modules.add(sys.modules[flow_type.infer_belief.__module__])
    return sorted({Path(inspect.getsourcefile(module) or "") for module in modules})


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def build_manifest(fixtures: Mapping[str, str]) -> dict[str, object]:
    return {
        "reference_version": REFERENCE_VERSION,
        "generator": "tools/gamification/learning_flow/freeze_rule_based_reference.py",
        "source_commit": _git("rev-parse", "HEAD"),
        "source_worktree_dirty": bool(_git("status", "--porcelain")),
        "fixtures": {name: _sha256(text) for name, text in sorted(fixtures.items())},
        "rule_sources": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in rule_sources()
        },
    }


def check(directory: Path = FIXTURE_DIRECTORY) -> list[str]:
    """Differences between the stored fixtures and a fresh build. Empty when they match."""

    fixtures = build_fixtures()
    problems = [
        f"{name} differs from a fresh build"
        for name, text in fixtures.items()
        if not (directory / name).is_file()
        or (directory / name).read_text(encoding="utf-8") != text
    ]
    manifest = json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
    problems += [
        f"{name} hash differs from the manifest"
        for name, text in fixtures.items()
        if manifest["fixtures"].get(name) != _sha256(text)
    ]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and fail if the stored fixtures or their hashes differ",
    )
    parser.add_argument("--output-dir", type=Path, default=FIXTURE_DIRECTORY)
    arguments = parser.parse_args()
    if arguments.check:
        problems = check(arguments.output_dir)
        for problem in problems:
            print(problem)
        if not problems:
            print("rule-based reference fixtures match a fresh build")
        return 1 if problems else 0
    fixtures = build_fixtures()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in fixtures.items():
        (arguments.output_dir / name).write_text(text, encoding="utf-8")
    (arguments.output_dir / MANIFEST_FILE).write_text(
        _text(build_manifest(fixtures)), encoding="utf-8"
    )
    print(f"wrote {', '.join(fixtures)} and {MANIFEST_FILE} to {arguments.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
