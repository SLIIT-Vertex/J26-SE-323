"""Chooses the questions of one learner's weekly paper.

Pure logic: no database, no network. Everything it needs is passed in, so it can be tested with
made-up data and always gives the same paper for the same inputs and seed.

The idea, in plain words
------------------------
* Mastery says how likely the child is to answer a medium paper question of a skill correctly.
* About 70% of the paper goes to weak skills (and a few unknown ones), about 30% to strong skills.
* The strong part is spent first on VERIFICATION: skills where the game looks good but there is
  little or no paper evidence, so the paper can confirm that the game success is real.
* Inside those groups a knapsack (OR-Tools CP-SAT) picks the highest-value set that fits the
  time, page and variety limits. A greedy solver is the baseline and the fallback.

The numbers (0.60, 0.70, 0.80, 5 ...) are design assumptions held in `SelectionConfig`. They are
not validated findings and are meant to be tuned once real data exists.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
from ortools.sat.python import cp_model

AREA_ORDER = ("APT", "MAT", "LAN", "ENV")
DIFFICULTIES = ("easy", "medium", "hard")  # column order of the model's item probabilities

Role = Literal["weak", "strong", "verify", "unknown", "diagnostic"]
Method = Literal["cp_sat", "greedy", "diagnostic"]


class NotEnoughQuestions(Exception):
    """The candidate pool and the limits do not allow even one question."""


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    # --- skill groups -------------------------------------------------------------------------
    weak_enter: float = 0.60  # known mastery below this is weak
    weak_exit: float = 0.70  # a skill that was weak stays weak until it reaches this
    target_mastery: float = 0.80  # the level the paper is trying to bring skills to
    min_weak_skills: int = 5  # top up the weak list with the lowest skills below target
    # --- paper shape --------------------------------------------------------------------------
    weak_share: float = 0.70  # share of questions for weak/unknown skills
    unknown_share_cap: float = 0.25  # at most this share of the paper may be unknown skills
    per_skill_cap: int = 3
    verify_per_skill_cap: int = 2  # spread verification over more skills
    coverage_skills: int = 3  # the weakest known skills that must each get a question
    # --- verification of game success on paper ------------------------------------------------
    verify_min_digital: int = 3
    verify_min_accuracy: float = 0.70
    verify_max_paper: int = 3  # "fewer than 3 paper answers"
    verify_boost: float = 3.0
    # --- value of a question ------------------------------------------------------------------
    stretch_center: float = 0.60  # best predicted P(correct): hard enough to teach, not hopeless
    unknown_need: float = 0.50
    need_floor: float = 0.05
    focus_boost: float = 1.5
    unknown_fit: tuple[float, float, float] = (0.8, 1.0, 0.6)  # easy / medium / hard
    # --- diagnostic mode ----------------------------------------------------------------------
    diagnostic_unknown_threshold: int = 15  # more unknown skills than this: diagnostic paper
    # --- page layout --------------------------------------------------------------------------
    usable_height_mm: float = 232.0
    packing_factor: float = 0.92  # allowance for packing waste when pages are filled
    gap_mm: float = 12.0  # clear space after every question
    padding_mm: float = 3.0
    max_image_width_mm: float = 160.0
    max_image_height_mm: float = 90.0
    image_dpi: float = 150.0
    # --- solver -------------------------------------------------------------------------------
    solver_seconds: float = 5.0


DEFAULT_CONFIG = SelectionConfig()


@dataclass(frozen=True, slots=True)
class PaperParams:
    max_questions: int = 15
    max_minutes: int = 25
    max_pages: int = 3
    seed: int = 0
    mode: Literal["auto", "practice", "diagnostic"] = "auto"
    focus_skills: tuple[str, ...] = ()
    covered_diagnostic_skills: tuple[str, ...] = ()  # skills an earlier diagnostic paper covered


@dataclass(frozen=True, slots=True)
class SkillState:
    """What is known about one learner and one skill."""

    code: str
    area: str
    sort_index: int
    mastery: float | None  # None: fewer than 3 answers
    digital_attempts: int = 0
    digital_correct: int = 0
    paper_attempts: int = 0
    was_weak: bool = False  # in the weak list on the previous paper (for hysteresis)


@dataclass(frozen=True, slots=True)
class Candidate:
    question_id: str
    skill_code: str
    difficulty: str
    est_seconds: int
    height_mm: float  # printed height including padding and the gap after the question


@dataclass(frozen=True, slots=True)
class Selected:
    question_id: str
    skill_code: str
    difficulty: str
    role: Role
    value: float
    predicted_p: float | None
    est_seconds: int
    height_mm: float


@dataclass(frozen=True, slots=True)
class Selection:
    questions: tuple[Selected, ...]
    mode: Literal["practice", "diagnostic"]
    method: Method
    total_value: float
    weak_skills: tuple[str, ...]
    strong_skills: tuple[str, ...]
    unknown_skills: tuple[str, ...]
    verify_skills: tuple[str, ...]
    skipped_skills: tuple[str, ...]  # wanted but with no candidate question
    diagnostic_skills: tuple[str, ...]
    notes: tuple[str, ...]
    seconds: int
    height_mm: float
    solve_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class SkillGroups:
    weak: tuple[str, ...]
    strong: tuple[str, ...]
    unknown: tuple[str, ...]
    verify: tuple[str, ...]  # a subset of strong


# ---------------------------------------------------------------------------------------------
# Layout height
# ---------------------------------------------------------------------------------------------


def layout_height_mm(width_px: int, height_px: int, config: SelectionConfig = DEFAULT_CONFIG) -> float:
    """Printed height of one question block, including padding and the gap that follows it."""
    width_mm = min(config.max_image_width_mm, width_px * 25.4 / config.image_dpi)
    height_mm = height_px * (width_mm / width_px)
    height_mm = min(height_mm, config.max_image_height_mm)
    return round(2 * config.padding_mm + height_mm + config.gap_mm, 2)


# ---------------------------------------------------------------------------------------------
# Skill groups
# ---------------------------------------------------------------------------------------------


def classify_skills(
    states: Sequence[SkillState], config: SelectionConfig = DEFAULT_CONFIG
) -> SkillGroups:
    known = [s for s in states if s.mastery is not None]
    unknown = [s.code for s in states if s.mastery is None]

    weak: dict[str, SkillState] = {}
    for s in known:
        assert s.mastery is not None
        limit = config.weak_exit if s.was_weak else config.weak_enter
        if s.mastery < limit:
            weak[s.code] = s

    # Keep the weak share meaningful for a strong learner: top up with the lowest skills that
    # are still below the target.
    if len(weak) < config.min_weak_skills:
        below_target = sorted(
            (s for s in known if s.code not in weak and (s.mastery or 0.0) < config.target_mastery),
            key=lambda s: (s.mastery, s.sort_index),
        )
        for s in below_target:
            if len(weak) >= config.min_weak_skills:
                break
            weak[s.code] = s

    strong = [s for s in known if s.code not in weak]
    verify = [s.code for s in strong if _needs_verification(s, config)]
    order = {s.code: s.sort_index for s in states}
    return SkillGroups(
        weak=tuple(sorted(weak, key=order.__getitem__)),
        strong=tuple(sorted((s.code for s in strong), key=order.__getitem__)),
        unknown=tuple(sorted(unknown, key=order.__getitem__)),
        verify=tuple(sorted(verify, key=order.__getitem__)),
    )


def _needs_verification(state: SkillState, config: SelectionConfig) -> bool:
    """Game accuracy is high, but the paper has not confirmed it yet."""
    if state.digital_attempts < config.verify_min_digital:
        return False
    accuracy = state.digital_correct / state.digital_attempts
    return accuracy >= config.verify_min_accuracy and state.paper_attempts < config.verify_max_paper


# ---------------------------------------------------------------------------------------------
# Value of a question
# ---------------------------------------------------------------------------------------------


def stretch(p: float, config: SelectionConfig = DEFAULT_CONFIG) -> float:
    """1.0 when the child has a fair chance (about 0.6), falling to the floor at 0 and 1."""
    return max(config.need_floor, 1.0 - abs(p - config.stretch_center) / config.stretch_center)


def question_value(
    candidate: Candidate,
    state: SkillState,
    predicted_p: float | None,
    config: SelectionConfig,
    *,
    focus: bool = False,
    verify: bool = False,
) -> float:
    if state.mastery is None or predicted_p is None:
        need = config.unknown_need
        fit = config.unknown_fit[DIFFICULTIES.index(candidate.difficulty)]
    else:
        need = max(config.need_floor, config.target_mastery - state.mastery)
        fit = stretch(predicted_p, config)
    value = need * fit
    if focus:
        value *= config.focus_boost
    if verify:
        value *= config.verify_boost
    return value


# ---------------------------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------------------------


@dataclass(slots=True)
class _Item:
    candidate: Candidate
    role: Role
    value: float
    predicted_p: float | None
    score: int = 0  # integer objective used by the solver (value plus a seeded tie-break)


def select_questions(
    states: Sequence[SkillState],
    item_probs: np.ndarray | None,
    candidates: Sequence[Candidate],
    params: PaperParams = PaperParams(),  # noqa: B008
    config: SelectionConfig = DEFAULT_CONFIG,
    *,
    solver: Literal["cp_sat", "greedy"] = "cp_sat",
) -> Selection:
    """Pick the questions of one weekly paper.

    `item_probs` has shape (skills, 3): the model's P(correct) for easy/medium/hard on paper,
    rows in the same order as `states`. It is None for a learner with no history.
    `solver="greedy"` skips the knapsack (the baseline used in the evaluation).
    """
    groups = classify_skills(states, config)
    mode = _resolve_mode(params, groups, item_probs, config)
    if mode == "diagnostic":
        return _select_diagnostic(states, groups, candidates, params, config)
    return _select_practice(states, groups, item_probs, candidates, params, config, solver)


def _resolve_mode(
    params: PaperParams,
    groups: SkillGroups,
    item_probs: np.ndarray | None,
    config: SelectionConfig,
) -> Literal["practice", "diagnostic"]:
    if params.mode == "diagnostic":
        return "diagnostic"
    if params.mode == "practice":
        return "practice"
    if item_probs is None or len(groups.unknown) > config.diagnostic_unknown_threshold:
        return "diagnostic"
    return "practice"


def _limits(params: PaperParams, config: SelectionConfig) -> tuple[int, float]:
    seconds = params.max_minutes * 60
    height = config.packing_factor * params.max_pages * config.usable_height_mm
    return seconds, height


# ---- practice mode ---------------------------------------------------------------------------


def _select_practice(
    states: Sequence[SkillState],
    groups: SkillGroups,
    item_probs: np.ndarray | None,
    candidates: Sequence[Candidate],
    params: PaperParams,
    config: SelectionConfig,
    solver: Literal["cp_sat", "greedy"] = "cp_sat",
) -> Selection:
    by_code = {s.code: s for s in states}
    weak, unknown, verify = set(groups.weak), set(groups.unknown), set(groups.verify)
    focus = set(params.focus_skills)
    rng = random.Random(params.seed)

    items: list[_Item] = []
    for candidate in candidates:
        state = by_code.get(candidate.skill_code)
        if state is None or candidate.difficulty not in DIFFICULTIES:
            continue
        p = None
        if item_probs is not None:
            p = float(item_probs[state.sort_index, DIFFICULTIES.index(candidate.difficulty)])
        if candidate.skill_code in weak:
            role: Role = "weak"
        elif candidate.skill_code in unknown:
            role = "unknown"
        elif candidate.skill_code in verify:
            role = "verify"
        else:
            role = "strong"
        value = question_value(
            candidate,
            state,
            p,
            config,
            focus=candidate.skill_code in focus,
            verify=role == "verify",
        )
        items.append(_Item(candidate, role, value, p))

    # A seeded tie-break: the same seed always gives the same paper, another seed another one.
    for item in items:
        item.score = round(item.value * 1000) * 10 + rng.randrange(10)

    seconds_limit, height_limit = _limits(params, config)
    n = params.max_questions
    weak_target = round(config.weak_share * n)
    strong_cap = n - weak_target
    unknown_cap = math.floor(config.unknown_share_cap * n)

    present = {item.candidate.skill_code for item in items}
    skipped = tuple(
        sorted(
            (c for c in (*groups.weak, *groups.verify) if c not in present),
            key=lambda c: by_code[c].sort_index,
        )
    )

    # The weakest known skills must each appear (when they have candidate questions).
    weakest = sorted(
        (by_code[c] for c in groups.weak if c in present and by_code[c].mastery is not None),
        key=lambda s: (s.mastery, s.sort_index),
    )[: config.coverage_skills]
    coverage = tuple(s.code for s in weakest)
    verify_present = tuple(c for c in groups.verify if c in present)
    if len(verify_present) <= strong_cap:
        # Room for all of them: every verification skill gets a question on the paper.
        coverage = tuple(dict.fromkeys((*coverage, *verify_present)))
        verify_min = 0
    else:
        # More than fit: the whole strong part goes to verification, best value first.
        verify_min = strong_cap

    notes: list[str] = []
    started = _now_ms()
    chosen: list[_Item] | None
    method: Method
    if solver == "greedy":
        chosen = _solve_greedy(
            items, n, seconds_limit, height_limit, strong_cap, unknown_cap, coverage,
            verify_min, config,
        )
        method = "greedy"
    else:
        chosen, method = _solve_cp_sat(
            items, n, seconds_limit, height_limit, strong_cap, unknown_cap, coverage,
            verify_min, params.seed, config,
        )
    if chosen is None:
        # Too tight for the coverage/verification minimums: try without them.
        chosen, method = _solve_cp_sat(
            items, n, seconds_limit, height_limit, strong_cap, unknown_cap, (), 0,
            params.seed, config,
        )
        if chosen is not None:
            notes.append("coverage and verification minimums relaxed: limits were too tight")
    if chosen is None:
        chosen = _solve_greedy(
            items, n, seconds_limit, height_limit, strong_cap, unknown_cap, coverage,
            verify_min, config,
        )
        method = "greedy"
        notes.append("the solver found no solution in time; greedy fallback used")
    solve_ms = _now_ms() - started

    if not chosen:
        raise NotEnoughQuestions("no question fits the time, page and variety limits")
    return _build_selection(
        chosen, "practice", method, groups, skipped, (), tuple(notes), by_code, solve_ms
    )


def _now_ms() -> float:
    import time

    return time.perf_counter() * 1000.0


def _solve_cp_sat(
    items: Sequence[_Item],
    n: int,
    seconds_limit: int,
    height_limit: float,
    strong_cap: int,
    unknown_cap: int,
    coverage: Sequence[str],
    verify_min: int,
    seed: int,
    config: SelectionConfig,
) -> tuple[list[_Item] | None, Method]:
    if not items:
        return [], "cp_sat"
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x{i}") for i in range(len(items))]

    model.add(sum(it.candidate.est_seconds * v for it, v in zip(items, x, strict=True)) <= seconds_limit)
    model.add(
        sum(round(it.candidate.height_mm * 10) * v for it, v in zip(items, x, strict=True))
        <= int(height_limit * 10)
    )
    model.add(sum(x) <= n)

    by_skill: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        by_skill.setdefault(item.candidate.skill_code, []).append(index)
    for indexes in by_skill.values():
        cap = _skill_cap(items[indexes[0]].role, config)
        model.add(sum(x[i] for i in indexes) <= cap)

    strong_idx = [i for i, it in enumerate(items) if it.role in ("strong", "verify")]
    unknown_idx = [i for i, it in enumerate(items) if it.role == "unknown"]
    verify_idx = [i for i, it in enumerate(items) if it.role == "verify"]
    model.add(sum(x[i] for i in strong_idx) <= strong_cap)
    model.add(sum(x[i] for i in unknown_idx) <= unknown_cap)

    for skill in coverage:
        model.add(sum(x[i] for i in by_skill[skill]) >= 1)
    if verify_min > 0 and verify_idx:
        model.add(sum(x[i] for i in verify_idx) >= verify_min)

    model.maximize(sum(it.score * v for it, v in zip(items, x, strict=True)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.solver_seconds
    solver.parameters.random_seed = seed
    solver.parameters.num_workers = 1  # one worker keeps the result repeatable
    status = solver.solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [it for it, v in zip(items, x, strict=True) if solver.value(v)], "cp_sat"
    if status == cp_model.INFEASIBLE:
        return None, "cp_sat"
    return None, "cp_sat"  # unknown (timed out without a solution)


def _skill_cap(role: Role, config: SelectionConfig) -> int:
    """Most questions one skill may contribute to a paper."""
    if role == "verify":
        return min(config.per_skill_cap, config.verify_per_skill_cap)
    return config.per_skill_cap


def _solve_greedy(
    items: Sequence[_Item],
    n: int,
    seconds_limit: int,
    height_limit: float,
    strong_cap: int,
    unknown_cap: int,
    coverage: Sequence[str],
    verify_min: int,
    config: SelectionConfig,
) -> list[_Item]:
    """Value per second, best first, adding a question only while every limit still holds.

    Coverage questions go first, then verification, then everything else.
    """
    order = sorted(items, key=lambda it: (-it.score / max(1, it.candidate.est_seconds), it.candidate.question_id))
    picked: list[_Item] = []
    state = {"seconds": 0, "height": 0.0, "strong": 0, "unknown": 0}
    per_skill: dict[str, int] = {}

    def fits(it: _Item) -> bool:
        c = it.candidate
        if len(picked) >= n or it in picked:
            return False
        if state["seconds"] + c.est_seconds > seconds_limit:
            return False
        if state["height"] + c.height_mm > height_limit:
            return False
        if per_skill.get(c.skill_code, 0) >= _skill_cap(it.role, config):
            return False
        if it.role in ("strong", "verify") and state["strong"] >= strong_cap:
            return False
        return not (it.role == "unknown" and state["unknown"] >= unknown_cap)

    def take(it: _Item) -> None:
        c = it.candidate
        picked.append(it)
        state["seconds"] += c.est_seconds
        state["height"] += c.height_mm
        per_skill[c.skill_code] = per_skill.get(c.skill_code, 0) + 1
        if it.role in ("strong", "verify"):
            state["strong"] += 1
        if it.role == "unknown":
            state["unknown"] += 1

    for skill in coverage:
        for it in order:
            if it.candidate.skill_code == skill and fits(it):
                take(it)
                break
    verified = 0
    for it in order:
        if verified >= verify_min:
            break
        if it.role == "verify" and fits(it):
            take(it)
            verified += 1
    for it in order:
        if fits(it):
            take(it)
    return picked


# ---- diagnostic mode -------------------------------------------------------------------------


def _select_diagnostic(
    states: Sequence[SkillState],
    groups: SkillGroups,
    candidates: Sequence[Candidate],
    params: PaperParams,
    config: SelectionConfig,
) -> Selection:
    """One easy and one medium question for each skill the model knows nothing about.

    Skills are taken by area (APT, MAT, LAN, ENV) and then by index, skipping skills an earlier
    diagnostic paper already covered, so successive papers walk through all 30 skills.
    """
    by_code = {s.code: s for s in states}
    rng = random.Random(params.seed)
    seconds_limit, height_limit = _limits(params, config)
    covered = set(params.covered_diagnostic_skills)

    by_skill: dict[str, list[Candidate]] = {}
    for c in candidates:
        if c.skill_code in by_code:
            by_skill.setdefault(c.skill_code, []).append(c)

    todo = sorted(
        (c for c in groups.unknown if c not in covered),
        key=lambda c: (AREA_ORDER.index(by_code[c].area), by_code[c].sort_index),
    )
    if not todo:  # everything was covered already: start the walk again
        todo = sorted(
            groups.unknown, key=lambda c: (AREA_ORDER.index(by_code[c].area), by_code[c].sort_index)
        )

    picked: list[Candidate] = []
    skipped: list[str] = []
    notes: list[str] = []
    used_seconds, used_height = 0, 0.0
    diagnostic: list[str] = []

    def pick(pool: list[Candidate], difficulty: str) -> Candidate | None:
        options = sorted((c for c in pool if c.difficulty == difficulty), key=lambda c: c.question_id)
        return options[rng.randrange(len(options))] if options else None

    stopped_early = False
    for code in todo:
        pool = by_skill.get(code, [])
        if not pool:
            skipped.append(code)
            continue
        wanted = [c for c in (pick(pool, "easy"), pick(pool, "medium")) if c is not None]
        if not wanted:  # no easy or medium question: any single question still measures the skill
            fallback = pick(pool, "hard")
            wanted = [fallback] if fallback else []
            if wanted:
                notes.append(f"{code}: only a hard question was available")
        fits_all = (
            len(picked) + len(wanted) <= params.max_questions
            and used_seconds + sum(c.est_seconds for c in wanted) <= seconds_limit
            and used_height + sum(c.height_mm for c in wanted) <= height_limit
        )
        if not fits_all:
            stopped_early = True
            break
        picked.extend(wanted)
        used_seconds += sum(c.est_seconds for c in wanted)
        used_height += sum(c.height_mm for c in wanted)
        diagnostic.append(code)

    if not picked:
        raise NotEnoughQuestions("no diagnostic question fits the limits")
    if stopped_early:
        remaining = [c for c in todo if c not in diagnostic and c not in skipped]
        notes.append(f"{len(remaining)} unknown skills are left for the next diagnostic paper")

    ordered = sorted(
        picked,
        key=lambda c: (
            AREA_ORDER.index(by_code[c.skill_code].area),
            by_code[c.skill_code].sort_index,
            DIFFICULTIES.index(c.difficulty),
        ),
    )
    chosen = [_Item(c, "diagnostic", 0.0, None) for c in ordered]
    return _build_selection(
        chosen, "diagnostic", "diagnostic", groups, tuple(skipped), tuple(diagnostic),
        tuple(notes), by_code, 0.0,
    )


# ---- output ----------------------------------------------------------------------------------


def _build_selection(
    chosen: Sequence[_Item],
    mode: Literal["practice", "diagnostic"],
    method: Method,
    groups: SkillGroups,
    skipped: tuple[str, ...],
    diagnostic: tuple[str, ...],
    notes: tuple[str, ...],
    by_code: dict[str, SkillState],
    solve_ms: float,
) -> Selection:
    ordered = sorted(
        chosen,
        key=lambda it: (
            AREA_ORDER.index(by_code[it.candidate.skill_code].area),
            DIFFICULTIES.index(it.candidate.difficulty),
            by_code[it.candidate.skill_code].sort_index,
            it.candidate.question_id,
        ),
    )
    questions = tuple(
        Selected(
            question_id=it.candidate.question_id,
            skill_code=it.candidate.skill_code,
            difficulty=it.candidate.difficulty,
            role=it.role,
            value=round(it.value, 4),
            predicted_p=None if it.predicted_p is None else round(it.predicted_p, 3),
            est_seconds=it.candidate.est_seconds,
            height_mm=it.candidate.height_mm,
        )
        for it in ordered
    )
    return Selection(
        questions=questions,
        mode=mode,
        method=method,
        total_value=round(sum(q.value for q in questions), 4),
        weak_skills=groups.weak,
        strong_skills=groups.strong,
        unknown_skills=groups.unknown,
        verify_skills=groups.verify,
        skipped_skills=skipped,
        diagnostic_skills=diagnostic,
        notes=notes,
        seconds=sum(q.est_seconds for q in questions),
        height_mm=round(sum(q.height_mm for q in questions), 2),
        solve_ms=round(solve_ms, 2),
    )


def with_config(**changes: float) -> SelectionConfig:
    """A copy of the default configuration with some values changed (handy in tests)."""
    return replace(DEFAULT_CONFIG, **changes)


# Re-exported so callers need only this module.
__all__ = [
    "AREA_ORDER",
    "DEFAULT_CONFIG",
    "DIFFICULTIES",
    "Candidate",
    "NotEnoughQuestions",
    "PaperParams",
    "Selected",
    "Selection",
    "SelectionConfig",
    "SkillGroups",
    "SkillState",
    "classify_skills",
    "layout_height_mm",
    "question_value",
    "select_questions",
    "stretch",
    "with_config",
]
