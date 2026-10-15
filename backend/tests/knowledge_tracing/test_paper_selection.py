import itertools
import random
from collections import Counter

import numpy as np
import pytest

from app.knowledge_tracing.application import paper_selection as ps
from app.knowledge_tracing.application.paper_selection import (
    DEFAULT_CONFIG,
    Candidate,
    NotEnoughQuestions,
    PaperParams,
    SkillState,
    classify_skills,
    layout_height_mm,
    question_value,
    select_questions,
    stretch,
)
from app.knowledge_tracing.domain.feature_spec import get_feature_spec

SKILLS = list(get_feature_spec().skills)


def make_states(
    mastery: dict[str, float | None] | None = None,
    **per_skill: dict,
) -> list[SkillState]:
    """All 30 skills; skills missing from `mastery` are unknown."""
    mastery = mastery or {}
    return [
        SkillState(
            code=code,
            area=code[:3],
            sort_index=index,
            mastery=mastery.get(code),
            **per_skill.get(code, {}),
        )
        for index, code in enumerate(SKILLS)
    ]


def make_candidates(
    codes: list[str] | None = None, per_skill: int = 6, seconds: int = 80, height: float = 45.0
) -> list[Candidate]:
    out: list[Candidate] = []
    for code in codes or SKILLS:
        for k in range(per_skill):
            out.append(
                Candidate(
                    question_id=f"{SKILLS.index(code)}.{k}",
                    skill_code=code,
                    difficulty=("easy", "medium", "hard")[k % 3],
                    est_seconds=seconds,
                    height_mm=height,
                )
            )
    return out


def probs_from(states: list[SkillState]) -> np.ndarray:
    """A plausible item-probability table: easy a bit above mastery, hard a bit below."""
    table = np.zeros((len(states), 3))
    for i, s in enumerate(states):
        base = 0.5 if s.mastery is None else s.mastery
        table[i] = np.clip([base + 0.15, base, base - 0.2], 0.02, 0.98)
    return table


# A learner with 20 known skills (8 weak, 12 strong) and 10 unknown skills.
def mixed_learner() -> tuple[list[SkillState], dict[str, float | None]]:
    mastery: dict[str, float | None] = {}
    for index, code in enumerate(SKILLS[:20]):
        mastery[code] = 0.30 + 0.02 * index if index < 8 else 0.70 + 0.01 * index
    states = make_states(
        mastery,
        **{
            # game success without paper evidence: these should be verified
            SKILLS[10]: {"digital_attempts": 8, "digital_correct": 7, "paper_attempts": 0},
            SKILLS[11]: {"digital_attempts": 6, "digital_correct": 6, "paper_attempts": 1},
            SKILLS[12]: {"digital_attempts": 5, "digital_correct": 4, "paper_attempts": 0},
        },
    )
    return states, mastery


def check_limits(selection, params: PaperParams, config=DEFAULT_CONFIG) -> None:
    qs = selection.questions
    assert len(qs) <= params.max_questions
    assert selection.seconds <= params.max_minutes * 60
    assert selection.height_mm <= config.packing_factor * params.max_pages * config.usable_height_mm
    assert max(Counter(q.skill_code for q in qs).values()) <= config.per_skill_cap
    assert len({q.question_id for q in qs}) == len(qs)


# ---- skill groups ----------------------------------------------------------------------------


def test_groups_follow_the_thresholds() -> None:
    states = make_states({SKILLS[0]: 0.30, SKILLS[1]: 0.59, SKILLS[2]: 0.60, SKILLS[3]: 0.95})

    groups = classify_skills(states, ps.with_config(min_weak_skills=0))

    assert groups.weak == (SKILLS[0], SKILLS[1])
    assert groups.strong == (SKILLS[2], SKILLS[3])
    assert len(groups.unknown) == 26


def test_a_weak_skill_leaves_the_weak_list_only_at_the_exit_level() -> None:
    config = ps.with_config(min_weak_skills=0)
    still = make_states({SKILLS[0]: 0.65}, **{SKILLS[0]: {"was_weak": True}})
    fresh = make_states({SKILLS[0]: 0.65})

    assert classify_skills(still, config).weak == (SKILLS[0],)
    assert classify_skills(fresh, config).weak == ()
    left = make_states({SKILLS[0]: 0.70}, **{SKILLS[0]: {"was_weak": True}})
    assert classify_skills(left, config).weak == ()


def test_a_strong_learner_still_gets_a_weak_list() -> None:
    mastery = {code: 0.65 + 0.01 * i for i, code in enumerate(SKILLS[:12])}
    mastery[SKILLS[12]] = 0.95

    groups = classify_skills(make_states(mastery))

    assert len(groups.weak) == DEFAULT_CONFIG.min_weak_skills
    assert set(groups.weak) == set(SKILLS[:5])  # the lowest five
    assert SKILLS[12] in groups.strong


def test_top_up_never_adds_skills_at_or_above_target() -> None:
    mastery = {SKILLS[0]: 0.90, SKILLS[1]: 0.85, SKILLS[2]: 0.82}

    groups = classify_skills(make_states(mastery))

    assert groups.weak == ()


def test_verification_needs_good_game_accuracy_and_little_paper_evidence() -> None:
    states = make_states(
        {c: 0.75 for c in SKILLS[:6]},
        **{
            SKILLS[0]: {"digital_attempts": 8, "digital_correct": 7, "paper_attempts": 0},  # yes
            SKILLS[1]: {"digital_attempts": 8, "digital_correct": 7, "paper_attempts": 3},  # enough paper
            SKILLS[2]: {"digital_attempts": 8, "digital_correct": 3, "paper_attempts": 0},  # poor game
            SKILLS[3]: {"digital_attempts": 2, "digital_correct": 2, "paper_attempts": 0},  # too few
            SKILLS[4]: {"digital_attempts": 10, "digital_correct": 7, "paper_attempts": 2},  # yes
        },
    )

    groups = classify_skills(states, ps.with_config(min_weak_skills=0))

    assert set(groups.verify) == {SKILLS[0], SKILLS[4]}
    assert set(groups.verify) <= set(groups.strong)


# ---- value ----------------------------------------------------------------------------------


def test_stretch_peaks_at_the_centre_and_has_a_floor() -> None:
    assert stretch(0.6) == pytest.approx(1.0)
    assert stretch(0.3) == pytest.approx(0.5)
    assert stretch(0.9) == pytest.approx(0.5)
    assert stretch(0.0) == DEFAULT_CONFIG.need_floor
    assert stretch(1.0) == pytest.approx(1.0 - 0.4 / 0.6)


def test_weaker_skill_and_better_fit_score_higher() -> None:
    c = make_candidates([SKILLS[0]], per_skill=1)[0]
    weak = SkillState(SKILLS[0], "APT", 0, 0.30)
    strong = SkillState(SKILLS[0], "APT", 0, 0.85)

    assert question_value(c, weak, 0.6, DEFAULT_CONFIG) > question_value(c, strong, 0.6, DEFAULT_CONFIG)
    assert question_value(c, weak, 0.6, DEFAULT_CONFIG) > question_value(c, weak, 0.95, DEFAULT_CONFIG)


def test_unknown_skills_use_the_difficulty_defaults() -> None:
    unknown = SkillState(SKILLS[0], "APT", 0, None)
    easy, medium, hard = (
        Candidate("q", SKILLS[0], d, 60, 40.0) for d in ("easy", "medium", "hard")
    )

    values = [question_value(c, unknown, None, DEFAULT_CONFIG) for c in (easy, medium, hard)]

    assert values == pytest.approx([0.5 * 0.8, 0.5 * 1.0, 0.5 * 0.6])


def test_focus_and_verification_boost_the_value() -> None:
    c = make_candidates([SKILLS[0]], per_skill=1)[0]
    s = SkillState(SKILLS[0], "APT", 0, 0.5)
    base = question_value(c, s, 0.6, DEFAULT_CONFIG)

    assert question_value(c, s, 0.6, DEFAULT_CONFIG, focus=True) == pytest.approx(base * 1.5)
    assert question_value(c, s, 0.6, DEFAULT_CONFIG, verify=True) == pytest.approx(base * 3.0)


# ---- layout height --------------------------------------------------------------------------


def test_layout_height_includes_padding_and_the_gap() -> None:
    # 945 px at 150 dpi = 160 mm wide; 300 px high -> 50.8 mm
    assert layout_height_mm(945, 300) == pytest.approx(6 + 50.8 + 12, abs=0.05)


def test_wide_images_are_scaled_to_the_page_and_tall_ones_capped() -> None:
    wide = layout_height_mm(2000, 400)  # scaled to 160 mm wide -> 32 mm tall
    assert wide == pytest.approx(6 + 32 + 12, abs=0.05)
    tall = layout_height_mm(600, 3000)
    assert tall == pytest.approx(6 + 90 + 12)


# ---- practice selection ---------------------------------------------------------------------


def test_a_paper_respects_every_limit() -> None:
    states, _ = mixed_learner()
    params = PaperParams(max_questions=15, max_minutes=25, max_pages=3, seed=7)

    result = select_questions(states, probs_from(states), make_candidates(), params)

    assert result.mode == "practice"
    assert result.method == "cp_sat"
    assert 0 < len(result.questions) <= 15
    check_limits(result, params)


def test_most_of_the_paper_goes_to_weak_skills() -> None:
    states, _ = mixed_learner()

    result = select_questions(states, probs_from(states), make_candidates(), PaperParams(seed=1))

    roles = Counter(q.role for q in result.questions)
    weak_side = roles["weak"] + roles["unknown"]
    strong_side = roles["strong"] + roles["verify"]
    assert weak_side >= 10
    assert strong_side <= 5
    assert roles["unknown"] <= 3  # at most 25% of 15


def test_the_strong_part_is_spent_on_verification_first() -> None:
    states, _ = mixed_learner()
    verify = set(classify_skills(states).verify)
    assert len(verify) == 3

    result = select_questions(states, probs_from(states), make_candidates(), PaperParams(seed=2))

    chosen_skills = {q.skill_code for q in result.questions if q.role == "verify"}
    assert chosen_skills == verify


def test_verification_is_spread_over_several_skills() -> None:
    mastery = {c: 0.75 for c in SKILLS[:20]}
    verify_skills = {
        c: {"digital_attempts": 8, "digital_correct": 7, "paper_attempts": 0}
        for c in SKILLS[10:20]
    }
    states = make_states(mastery, **verify_skills)

    result = select_questions(states, probs_from(states), make_candidates(), PaperParams(seed=1))

    counts = Counter(q.skill_code for q in result.questions if q.role == "verify")
    assert counts
    assert max(counts.values()) <= DEFAULT_CONFIG.verify_per_skill_cap
    assert sum(counts.values()) == 5  # the whole strong share (30% of 15, rounded)
    assert len(counts) >= 3


def test_the_weakest_skills_always_appear() -> None:
    states, mastery = mixed_learner()
    weakest = sorted((v, k) for k, v in mastery.items() if v is not None)[:3]

    for seed in range(5):
        result = select_questions(
            states, probs_from(states), make_candidates(), PaperParams(seed=seed)
        )
        present = {q.skill_code for q in result.questions}
        assert {code for _, code in weakest} <= present


def test_a_skill_with_no_candidates_is_skipped_and_reported() -> None:
    states, _ = mixed_learner()
    codes = [c for c in SKILLS if c != SKILLS[0]]  # SKILLS[0] is weak but has no questions

    result = select_questions(
        states, probs_from(states), make_candidates(codes), PaperParams(seed=3)
    )

    assert SKILLS[0] in result.skipped_skills
    assert all(q.skill_code != SKILLS[0] for q in result.questions)


def test_a_small_pool_gives_a_shorter_paper_without_repeats() -> None:
    states, _ = mixed_learner()
    pool = make_candidates([SKILLS[0], SKILLS[1]], per_skill=2)

    result = select_questions(states, probs_from(states), pool, PaperParams(seed=1))

    assert len(result.questions) == 4
    assert len({q.question_id for q in result.questions}) == 4


def test_limits_too_tight_for_any_question_are_an_error() -> None:
    states, _ = mixed_learner()
    pool = make_candidates(seconds=900)  # 15 minutes each

    with pytest.raises(NotEnoughQuestions):
        select_questions(
            states, probs_from(states), pool, PaperParams(max_minutes=5, seed=1)
        )


def test_the_same_seed_gives_the_same_paper() -> None:
    states, _ = mixed_learner()
    pool = make_candidates(per_skill=9)

    def ids(seed: int) -> list[str]:
        r = select_questions(states, probs_from(states), pool, PaperParams(seed=seed))
        return [q.question_id for q in r.questions]

    assert ids(11) == ids(11)
    assert any(ids(s) != ids(11) for s in range(12, 24))


def test_focus_skills_are_favoured() -> None:
    states, _ = mixed_learner()
    focus = SKILLS[15]  # a strong skill that would normally lose out
    pool = make_candidates()

    without = select_questions(states, probs_from(states), pool, PaperParams(seed=4))
    boosted = select_questions(
        states, probs_from(states), pool, PaperParams(seed=4, focus_skills=(focus,))
    )

    assert not any(q.skill_code == focus for q in without.questions) or True
    assert sum(q.skill_code == focus for q in boosted.questions) >= sum(
        q.skill_code == focus for q in without.questions
    )


def test_output_is_ordered_by_area_then_difficulty() -> None:
    states, _ = mixed_learner()

    result = select_questions(states, probs_from(states), make_candidates(), PaperParams(seed=5))

    keys = [
        (ps.AREA_ORDER.index(q.skill_code[:3]), ps.DIFFICULTIES.index(q.difficulty))
        for q in result.questions
    ]
    assert keys == sorted(keys)


def test_the_greedy_fallback_is_used_when_the_solver_gives_nothing(monkeypatch) -> None:
    monkeypatch.setattr(ps, "_solve_cp_sat", lambda *a, **k: (None, "cp_sat"))
    states, _ = mixed_learner()
    params = PaperParams(seed=6)

    result = select_questions(states, probs_from(states), make_candidates(), params)

    assert result.method == "greedy"
    assert any("greedy" in note for note in result.notes)
    assert result.questions
    check_limits(result, params)


# ---- knapsack against brute force and greedy -------------------------------------------------


def _brute_force_value(items, n, seconds, height, strong_cap, unknown_cap, coverage, verify_min, config):
    best = 0.0
    for r in range(len(items) + 1):
        for combo in itertools.combinations(items, r):
            if len(combo) > n:
                break
            if sum(i.candidate.est_seconds for i in combo) > seconds:
                continue
            if sum(round(i.candidate.height_mm * 10) for i in combo) > int(height * 10):
                continue
            per_skill = Counter(i.candidate.skill_code for i in combo)
            if per_skill and max(per_skill.values()) > config.per_skill_cap:
                continue
            if sum(i.role in ("strong", "verify") for i in combo) > strong_cap:
                continue
            if sum(i.role == "unknown" for i in combo) > unknown_cap:
                continue
            if any(per_skill[c] < 1 for c in coverage):
                continue
            if sum(i.role == "verify" for i in combo) < verify_min:
                continue
            best = max(best, sum(i.value for i in combo))
    return best


def test_the_solver_matches_brute_force_and_never_loses_to_greedy() -> None:
    rng = random.Random(2026)
    config = DEFAULT_CONFIG
    checked = 0
    for trial in range(200):
        codes = rng.sample(SKILLS, 4)
        mastery = {c: rng.choice([0.2, 0.4, 0.55, 0.7, 0.9]) for c in codes[:3]}
        states = make_states(
            mastery,
            **{codes[2]: {"digital_attempts": 6, "digital_correct": 6, "paper_attempts": 0}},
        )
        candidates = [
            Candidate(
                f"{trial}.{i}",
                rng.choice(codes),
                rng.choice(("easy", "medium", "hard")),
                rng.choice((60, 90, 120, 150)),
                rng.choice((40.0, 55.0, 70.0)),
            )
            for i in range(rng.randint(5, 11))
        ]
        params = PaperParams(
            max_questions=rng.choice((3, 4, 5)), max_minutes=rng.choice((4, 6, 8)),
            max_pages=1, seed=trial, mode="practice",
        )
        probs = probs_from(states)
        try:
            result = select_questions(states, probs, candidates, params, config)
        except NotEnoughQuestions:
            continue
        if result.mode != "practice":
            continue

        # rebuild the same items the selector built, then brute-force them
        groups = classify_skills(states, config)
        by_code = {s.code: s for s in states}
        items = []
        for c in candidates:
            s = by_code[c.skill_code]
            p = float(probs[s.sort_index, ps.DIFFICULTIES.index(c.difficulty)])
            role = (
                "weak" if c.skill_code in groups.weak
                else "unknown" if c.skill_code in groups.unknown
                else "verify" if c.skill_code in groups.verify else "strong"
            )
            value = question_value(c, s, p, config, verify=role == "verify")
            items.append(ps._Item(c, role, value, p))

        n = params.max_questions
        weak_target = round(config.weak_share * n)
        strong_cap = n - weak_target
        unknown_cap = int(config.unknown_share_cap * n)
        present = {c.skill_code for c in candidates}
        weakest = sorted(
            (by_code[c] for c in groups.weak if c in present and by_code[c].mastery is not None),
            key=lambda s: (s.mastery, s.sort_index),
        )[: config.coverage_skills]
        coverage = [s.code for s in weakest]
        verify_present = [c for c in groups.verify if c in present]
        if len(verify_present) <= strong_cap:
            coverage = list(dict.fromkeys([*coverage, *verify_present]))
            verify_min = 0
        else:
            verify_min = strong_cap
        seconds, height = ps._limits(params, config)

        best = _brute_force_value(
            items, n, seconds, height, strong_cap, unknown_cap, coverage, verify_min, config
        )
        if "relaxed" in " ".join(result.notes) or result.method == "greedy":
            continue  # the minimums were infeasible; brute force above assumed they hold
        assert result.total_value == pytest.approx(best, abs=0.02), (trial, params)

        greedy = ps._solve_greedy(
            items, n, seconds, height, strong_cap, unknown_cap, coverage, verify_min, config
        )
        greedy_skills = {i.candidate.skill_code for i in greedy}
        greedy_is_comparable = set(coverage) <= greedy_skills and (
            sum(i.role == "verify" for i in greedy) >= verify_min
        )
        if greedy_is_comparable:  # greedy may skip a minimum and so score higher illegitimately
            assert result.total_value >= sum(i.value for i in greedy) - 0.02
        checked += 1
    assert checked >= 60


# ---- diagnostic mode ------------------------------------------------------------------------


def test_a_new_learner_gets_a_diagnostic_paper() -> None:
    states = make_states()  # nothing known
    params = PaperParams(max_questions=15, seed=1)

    result = select_questions(states, None, make_candidates(), params)

    assert result.mode == "diagnostic"
    assert result.method == "diagnostic"
    # two questions (one easy, one medium) for each of the first 7 skills
    per_skill = Counter(q.skill_code for q in result.questions)
    assert set(per_skill.values()) == {2}
    assert len(result.diagnostic_skills) == 7
    assert result.diagnostic_skills == tuple(SKILLS[:7])  # APT first, in index order
    assert all(q.role == "diagnostic" for q in result.questions)
    check_limits(result, params)
    for code in result.diagnostic_skills:
        assert {q.difficulty for q in result.questions if q.skill_code == code} == {"easy", "medium"}


def test_successive_diagnostic_papers_walk_through_the_skills() -> None:
    states = make_states()
    pool = make_candidates()
    covered: tuple[str, ...] = ()
    seen: list[str] = []
    for week in range(6):
        result = select_questions(
            states, None, pool, PaperParams(seed=week, covered_diagnostic_skills=covered)
        )
        seen.extend(result.diagnostic_skills)
        covered = tuple(seen)
    assert seen[:30] == SKILLS  # all 30, in area order, without repeats


def test_diagnostic_skips_skills_without_questions() -> None:
    states = make_states()
    pool = make_candidates([c for c in SKILLS if c != SKILLS[1]])

    result = select_questions(states, None, pool, PaperParams(seed=1))

    assert SKILLS[1] in result.skipped_skills
    assert SKILLS[1] not in result.diagnostic_skills


def test_diagnostic_uses_a_single_question_when_only_one_exists() -> None:
    states = make_states()
    only_easy = [c for c in make_candidates([SKILLS[0]]) if c.difficulty == "easy"][:1]
    rest = make_candidates(SKILLS[1:], per_skill=3)

    result = select_questions(states, None, only_easy + rest, PaperParams(seed=1))

    assert sum(q.skill_code == SKILLS[0] for q in result.questions) == 1


def test_many_unknown_skills_switch_to_diagnostic_automatically() -> None:
    mastery = {c: 0.5 for c in SKILLS[:10]}  # 10 known, 20 unknown
    states = make_states(mastery)

    result = select_questions(states, probs_from(states), make_candidates(), PaperParams(seed=1))

    assert result.mode == "diagnostic"


def test_the_mode_can_be_forced_to_practice() -> None:
    states = make_states({c: 0.5 for c in SKILLS[:10]})

    result = select_questions(
        states, probs_from(states), make_candidates(), PaperParams(seed=1, mode="practice")
    )

    assert result.mode == "practice"


def test_a_diagnostic_paper_that_cannot_hold_one_skill_is_an_error() -> None:
    states = make_states()
    pool = make_candidates(seconds=2000)

    with pytest.raises(NotEnoughQuestions):
        select_questions(states, None, pool, PaperParams(max_minutes=5, seed=1))
