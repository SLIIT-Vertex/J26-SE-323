"""Draft content and server scoring for G5-AREA-SIN-03 (තේරවිලි).

Source: two textbook photographs (``IMG_7486.heic``, ``IMG_7487.heic``) of 23 numbered riddles,
each with a printed answer and an answer-revealing illustration. The collection is prescribed
for Grades 1 to 5, so no riddle is assumed to have Grade 5 difficulty.

Only these 23 riddles are used; no folk riddle is invented. The printed answers and
illustrations are restricted: they stay server-side and appear only after scoring, in support,
or in the unscored demonstration. The child selects original clue lines as evidence and places
a plain answer card; only the answer is scored. Evidence is recorded for diagnosis.

Freshness is a property of the learner, not of a revision id: an item is the riddle itself
(``revision_id`` is stable per riddle), and a riddle whose answer family the learner has already
met (riddles 1 and 17 share කොකා) is never treated as an unexposed probe.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from app.gamification.content import sinhala_common as common
from app.gamification.content.sinhala_common import DONE_LINE, UNKNOWN
from app.gamification.content.sinhala_common import SinhalaResponseError as ResponseError

AREA_ID = "G5-AREA-SIN-03"
# Draft crosswalk to Sinhala reading comprehension; not reviewed for this area.
UNIVERSAL_SKILL_ID = "LAN-CMP"
PACKAGE_VERSION = "g5-sin-riddles-draft-v1"
CATALOGUE_VERSION = "g5-sin-riddles-misconceptions-v1"
FEATURE_VERSION = "g5-sin-riddles-features-v1"
MAPPING_VERSION = "g5-sin-riddles-evidence-mapping-v1"
MODEL_VERSION = "g5-sin-riddles-authored-probabilistic-v1"
POLICY_VERSION = "g5-sin-riddles-raw-ig-shadow-v1"
SCORING_VERSION = "g5-sin-riddles-answer-scoring-v1"
EQUIVALENCE_VERSION = "g5-sin-riddles-parallel-v1"
RESPONSE_SCHEMA_VERSION = "sinhala-riddle-response-v1"
ITEM_SCHEMA_VERSION = "sinhala-riddle-item-v1"
VISUAL_EMPHASIS = "outline_selected_spans"

DATA_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "data" / "gamification" / "grade5-sinhala-riddles" / "v1"
)

Chapter = Literal["clue_path", "clue_bridge", "word_secret_box"]


@cache
def source_transcription() -> dict[str, object]:
    manifest = json.loads((DATA_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    raw = (DATA_DIRECTORY / "source-transcription.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["source-transcription.json"]:
        raise RuntimeError("SINHALA_RIDDLE_SOURCE_HASH_MISMATCH")
    return json.loads(raw)


@cache
def riddles() -> dict[int, dict[str, object]]:
    return {int(r["number"]): r for r in source_transcription()["riddles"]}  # type: ignore[union-attr,index]


def answer_of(number: int) -> str:
    return str(riddles()[number]["printed_answer_si"])


def family_of(number: int) -> str:
    return str(riddles()[number]["answer_family"])


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    name_si: str
    difficulty: str
    response_kind: str = "sinhala_riddle_solution"
    outcome_provenance: str = "provisional_internal_id_draft_trace"
    chapter: Chapter = "clue_path"


ATOMIC_SKILLS = (
    AtomicSkill("G5-SIN-RID-DIRECT-01", "ඉඟි එකතු කර පිළිතුර සොයාගැනීම", "easy_to_hard"),
    AtomicSkill("G5-SIN-RID-FIGURATIVE-01", "සැඟවුණු අදහස තේරුම් ගැනීම", "medium_hard", chapter="word_secret_box"),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

# Provisional grouping (educator classification pending). Each subfamily's demonstration
# riddle is outside its probe pool.
SUBFAMILIES: dict[str, dict[str, dict[str, object]]] = {
    "G5-SIN-RID-DIRECT-01": {
        "direct:short": {"chapter": "clue_path", "pool": (2, 3, 4, 5, 6, 9, 13), "demo": 22,
                         "goal": "අද අපි තේරවිල්ලක ඉඟි කියවා පිළිතුර සොයාගනිමු 🌟"},
        "direct:rich": {"chapter": "clue_bridge", "pool": (1, 8, 12, 14, 18), "demo": 19,
                        "goal": "අද අපි ඉඟි කිහිපයක් එකට ගළපා පිළිතුර තහවුරු කරමු 🌟"},
    },
    "G5-SIN-RID-FIGURATIVE-01": {
        "figurative:metaphor": {"chapter": "word_secret_box", "pool": (7, 10, 11, 15, 16, 17, 21, 23), "demo": 20,
                                "goal": "අද අපි තේරවිල්ලක සැඟවුණු අදහස තේරුම්ගෙන පිළිතුර සොයමු 🌟"},
    },
}
# Draft distractors: printed answers of other riddles that fit one clue but fail another.
# Ambiguous pairs are never offered together (කොස්ස with ඉදල, අහස with හඳ).
DISTRACTORS = {
    1: (5, 15, 3), 2: (4, 19, 20), 3: (1, 5, 8), 4: (19, 14, 2), 5: (1, 15, 9), 6: (18, 23, 10),
    7: (9, 8, 11), 8: (5, 1, 12), 9: (7, 13, 15), 10: (6, 14, 12), 11: (22, 15, 5), 12: (14, 22, 10),
    13: (16, 9, 15), 14: (12, 4, 19), 15: (5, 11, 23), 16: (9, 13, 11), 17: (3, 5, 8), 18: (6, 23, 15),
    19: (4, 14, 20), 20: (2, 19, 11), 21: (20, 11, 3), 22: (11, 15, 12), 23: (18, 15, 11),
}
HOUSEHOLD = frozenset({"kossa", "idala", "dora", "yathura", "panaawa", "oralosuwa"})
# (riddle, distractor) pairs where the distractor matches the figurative words taken literally.
LITERAL_READINGS = frozenset({(15, 23), (23, 15), (16, 11), (11, 15), (7, 9), (21, 20)})
NEVER_TOGETHER = (frozenset({"kossa", "idala"}),)

MISCONCEPTIONS = (
    "single_clue_contradiction_ignored",
    "figurative_taken_literally",
    "clue_combination_failure",
    "similar_household_referent_confusion",
    "vocabulary_or_referent_unfamiliarity",
    "familiar_answer_recall_without_checking",
    UNKNOWN,
)


def misconception_catalogue() -> list[dict[str, object]]:
    def entry(code, evidence, counter, skills, observable=True):
        return {
            "code": code, "catalogue_version": CATALOGUE_VERSION, "mapping_version": MAPPING_VERSION,
            "evidence_patterns": evidence, "counter_evidence": counter, "supported_skills": skills,
            "source_basis": ["IMG_7486.heic", "IMG_7487.heic"], "eligible_support": list(common.SCAFFOLDS),
            "observable_in_current_mechanics": observable, "review_status": "draft_unreviewed",
            "alternative_explanations": ["vocabulary unfamiliarity", "motor error", "ambiguous distractor", "rendering failure"],
        }

    both = list(SKILLS)
    return [
        entry("single_clue_contradiction_ignored", ["a distractor that fits one line but contradicts another"],
              ["correct answer on a fresh same-skill riddle"], both),
        entry("figurative_taken_literally", ["a distractor matching the figurative word's literal sense"],
              ["correct figurative answer on a fresh riddle"], ["G5-SIN-RID-FIGURATIVE-01"]),
        entry("clue_combination_failure", ["wrong answer on a riddle of three or more clue lines"],
              ["correct answer on a fresh multi-clue riddle"], both),
        entry("similar_household_referent_confusion", ["one household object chosen for another"],
              ["correct household referent independently"], both),
        entry("vocabulary_or_referent_unfamiliarity", ["not separable from reasoning in the current mechanics"], [],
              both, observable=False),
        entry("familiar_answer_recall_without_checking", ["needs exposure history linked to the choice; not yet derived"], [],
              both, observable=False),
        entry(UNKNOWN, ["sparse evidence, motor difficulty, rendering problem, ambiguous item"], [], both),
    ]


# --- Selection with exposure ----------------------------------------------------------------

def _clue_lines(number: int) -> list[str]:
    return list(riddles()[number]["clue_lines_nfc"])  # type: ignore[arg-type]


def _bucket(number: int) -> str:
    """Equivalent probes have the same number of clue lines: a single-line riddle pairs with
    nothing, so it is only ever practice."""

    return f"lines-{len(_clue_lines(number))}"


def episode_subfamily(skill_id: str, seed: int) -> str:
    names = sorted(SUBFAMILIES[skill_id])
    return names[common.digest(skill_id, "subfamily", seed) % len(names)]


def probe_riddles(skill_id: str, seed: int) -> tuple[str, int, int]:
    """Subfamily, before and after riddles: same bucket, different answer families."""

    family = episode_subfamily(skill_id, seed)
    spec = SUBFAMILIES[skill_id][family]
    pool = list(spec["pool"])  # type: ignore[arg-type]
    random.Random(common.digest(skill_id, family, "probes", seed)).shuffle(pool)
    for first in pool:
        for second in pool:
            if second != first and _bucket(first) == _bucket(second) and family_of(first) != family_of(second):
                return family, first, second
    raise ValueError("SINHALA_RIDDLE_POOL_INSUFFICIENT")


def episode_families(skill_id: str, seed: int) -> set[str]:
    """Every answer family one episode shows: probes, distractors, support and demonstration."""

    family, before, after = probe_riddles(skill_id, seed)
    shown = {before, after, int(SUBFAMILIES[skill_id][family]["demo"]), *support_riddles(skill_id, seed)}
    for number in (before, after):
        shown.update(DISTRACTORS[number])
    return {family_of(n) for n in shown}


def revealed_families(skill_id: str, seed: int) -> set[str]:
    """Families whose riddle-to-answer link the episode reveals (not mere distractors)."""

    family, before, after = probe_riddles(skill_id, seed)
    return {family_of(n) for n in (before, after, int(SUBFAMILIES[skill_id][family]["demo"]), *support_riddles(skill_id, seed))}


def support_riddles(skill_id: str, seed: int) -> list[int]:
    family, before, after = probe_riddles(skill_id, seed)
    reserved = {family_of(before), family_of(after)}
    pool = [n for n in SUBFAMILIES[skill_id][family]["pool"] if family_of(n) not in reserved]  # type: ignore[union-attr]
    random.Random(common.digest(skill_id, family, "support", seed)).shuffle(pool)
    return pool or [int(SUBFAMILIES[skill_id][family]["demo"])]


def fresh_seed(
    skill_id: str,
    base_seed: int,
    exposed: Iterable[str],
    *,
    reserved_after: Iterable[int] = (),
    tries: int = 512,
) -> tuple[int, bool]:
    """A seed whose probes avoid every answer family this learner has already had revealed.

    Returns (seed, fresh). When no fresh pair exists the learner's pool is exhausted: the episode
    runs as practice with measurement unavailable, still never re-reserving an earlier after
    probe. If even that is impossible, ``SINHALA_RIDDLE_POOL_EXHAUSTED`` is raised.
    """

    seen, used = set(exposed), set(reserved_after)
    seeds = [(base_seed + attempt * 7_919) % 2**32 for attempt in range(tries)]
    fallback = None
    for seed in seeds:
        family, before, after = probe_riddles(skill_id, seed)
        if after in used:
            continue
        demo = int(SUBFAMILIES[skill_id][family]["demo"])
        if not {family_of(before), family_of(after)} & (seen | {family_of(demo)}):
            return seed, True
        fallback = fallback if fallback is not None else seed
    if fallback is None:
        raise ValueError("SINHALA_RIDDLE_POOL_EXHAUSTED")
    return fallback, False


# --- Items -----------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RiddleItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: str
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _error_for(number: int, distractor: int) -> str:
    families = {family_of(number), family_of(distractor)}
    if families <= HOUSEHOLD:
        return "similar_household_referent_confusion"
    if (number, distractor) in LITERAL_READINGS:
        return "figurative_taken_literally"
    if len(_clue_lines(number)) >= 3:
        return "clue_combination_failure"
    return "single_clue_contradiction_ignored"


def build_item(skill_id: str, family: str, number: int, *, role: str, salt: str) -> RiddleItem:
    spec = SUBFAMILIES[skill_id][family]
    rng = random.Random(common.digest(salt, number))
    candidates = [number, *DISTRACTORS[number]]
    for pair in NEVER_TOGETHER:
        if pair <= {family_of(n) for n in candidates}:
            raise ValueError("SINHALA_RIDDLE_AMBIGUOUS_CANDIDATES")
    cards = [{"card_id": common.token("card", n, salt), "text_si": answer_of(n)} for n in candidates]
    card_errors = {card["card_id"]: ("correct" if n == number else _error_for(number, n)) for card, n in zip(cards, candidates, strict=True)}
    answer_card = cards[0]["card_id"]
    rng.shuffle(cards)
    spans = [{"span_id": common.token("span", index, salt), "text_si": line} for index, line in enumerate(_clue_lines(number))]
    figurative = str(riddles()[number]["provisional_classification"]) == "figurative"
    game: dict[str, object] = {
        "activity_id": str(spec["chapter"]),
        "response_kind": "sinhala_riddle_solution",
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "subfamily": family,
        "goal_si": spec["goal"],
        "source_locator": riddles()[number]["locator"],
        # The whole original riddle, line by line; the answer and illustration stay server-side.
        "riddle_lines_si": [span["text_si"] for span in spans],
        "clue_spans": spans,
        "answer_cards": cards,
        "evidence_limit": len(spans),
        "rubric": {
            "answer_card_id": answer_card,
            "card_errors": card_errors,
            "answer_si": answer_of(number),
            "answer_family": family_of(number),
            "reveal_key": family_of(number),
            "riddle_number": number,
            "decisive_line_si": spans[-1]["text_si"] if len(spans) > 1 else spans[0]["text_si"],
        },
        "equivalence": {
            "skill_id": skill_id,
            "subfamily": family,
            "clue_bucket": _bucket(number),
            "figurative": figurative,
            "single_line": len(spans) == 1,
            "candidate_count": len(cards),
            "evidence_interaction": "optional_span_selection_unscored",
            "maximum_score": 1,
            "accepted_variants": "none_until_reviewed",
            "difficulty_review": None,
            "ig_available": True,
        },
    }
    return RiddleItem(
        item_id=f"{skill_id}:{family}:riddle-{number}",
        # Stable per riddle: reshuffling cards or re-issuing ids never makes a riddle fresh.
        revision_id=f"{skill_id}:riddle-{number}@v1",
        parallel_family_id=f"{skill_id}:{family}:parallel-v1",
        skill_id=skill_id,
        chapter=spec["chapter"],  # type: ignore[arg-type]
        measurement_role=role,
        prompt_si="තේරවිල්ල කියවා, ඉඟි තෝරා, පිළිතුරු කාඩ්පත පෙට්ටියට තබන්න.",
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def generate_item(skill_id: str, *, role: str, seed: int) -> RiddleItem:
    if skill_id not in SKILLS:
        raise ValueError("SINHALA_RIDDLE_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    family, before, after = probe_riddles(skill_id, seed)
    return build_item(skill_id, family, before if role == "unsupported_before" else after, role=role, salt=f"{skill_id}:{role}:{seed}")


def generate_support_item(skill_id: str, *, seed: int, index: int) -> RiddleItem:
    numbers = support_riddles(skill_id, seed)
    family = episode_subfamily(skill_id, seed)
    return build_item(skill_id, family, numbers[index % len(numbers)], role="supported_practice",
                      salt=f"{skill_id}:support:{seed}:{index}")


def opening_demonstration(skill_id: str, family: str) -> dict[str, object] | None:
    spec = SUBFAMILIES[skill_id].get(family)
    if spec is None:
        return None
    number = int(spec["demo"])
    return {
        "demonstration_id": f"{skill_id}:{family}:demo:riddle-{number}@v1",
        "goal_si": spec["goal"],
        "source_locators": [riddles()[number]["locator"]],
        "riddle_lines_si": _clue_lines(number),
        "shown_si": answer_of(number),
        "reveal_key": family_of(number),
        "unscored": True,
    }


# --- Scoring ---------------------------------------------------------------------------------

_KEYS = {"kind", "schema_version", "answer_card_id", "evidence_span_ids"}


def validate_constructed_response(
    item: RiddleItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, RiddleItem) else item["game_data"]
    assert isinstance(game, Mapping)
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    if response.get("kind") != "sinhala_riddle_solution":
        raise ResponseError("RESPONSE_KIND_MISMATCH" if isinstance(response.get("kind"), str) else "MALFORMED_RESPONSE")
    if response.get("schema_version") != RESPONSE_SCHEMA_VERSION:
        raise ResponseError("SCHEMA_MISMATCH")
    if set(response) != _KEYS:
        raise ResponseError("MALFORMED_RESPONSE")
    answer, spans = response["answer_card_id"], response["evidence_span_ids"]
    if answer is None or answer == "":
        raise ResponseError("INCOMPLETE_RESPONSE")
    if not isinstance(answer, str) or not isinstance(spans, list) or not all(isinstance(s, str) for s in spans):
        raise ResponseError("MALFORMED_RESPONSE")
    allowed_spans = {span["span_id"] for span in game["clue_spans"]}  # type: ignore[union-attr,index]
    errors = rubric["card_errors"]
    assert isinstance(errors, Mapping)
    if answer not in errors or any(s not in allowed_spans for s in spans):
        raise ResponseError("UNKNOWN_TOKEN")
    if len(set(spans)) != len(spans):
        raise ResponseError("DUPLICATE_TOKEN")
    correct = answer == rubric["answer_card_id"]
    normalized = {
        "kind": "sinhala_riddle_solution",
        "answer_card_id": answer,
        "evidence_span_ids": list(spans),
        # Diagnostic only: evidence never changes the score.
        "evidence_span_count": len(spans),
        "semantic_error": None if correct else "WRONG_REFERENT",
    }
    return correct, "correct" if correct else str(errors[answer]), normalized


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    return {
        "kind": "sinhala_riddle_solution",
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "answer_card_id": rubric["answer_card_id"],
        "evidence_span_ids": [span["span_id"] for span in game["clue_spans"]],  # type: ignore[union-attr,index]
    }


HIDDEN_GAME_KEYS = frozenset({"rubric", "equivalence"})


def public_game_data(item: RiddleItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{k: v for k, v in item.game_data.items() if k not in HIDDEN_GAME_KEYS}}


REVEAL_EMOJI = {
    "monaraa": "🦚", "jiraaf": "🦒", "itipandama": "🕯️", "handa": "🌙", "bolaya": "⚽", "kudaya": "☂️",
    "kochchiya": "🚂", "dedunna": "🌈", "samanalayaa": "🦋", "yathura": "🔑", "sarungalaya": "🪁", "bimmala": "🍄",
}


def feedback_si(game: Mapping[str, object], correct: bool) -> str:
    """After scoring only: link the answer to the riddle's actual words."""

    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    emoji = REVEAL_EMOJI.get(str(rubric["reveal_key"]), "")
    answer = f"{emoji} {rubric['answer_si']}".strip()
    line = rubric["decisive_line_si"]
    if correct:
        return f"හරි! {answer} — '{line}' ඉඟියටත් ගැළපෙනවා 🎉"
    return f"පිළිතුර {answer}. '{line}' ඇතුළු ඉඟි සියල්ලට ගැළපෙන්නේ එයයි."


def worked_display(game: Mapping[str, object]) -> dict[str, object]:
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    return {"result_text_si": rubric["answer_si"], "reveal_key": rubric["reveal_key"]}


def reveal_key(game: Mapping[str, object]) -> str:
    return str(game["rubric"]["reveal_key"])  # type: ignore[index]


# --- Models ----------------------------------------------------------------------------------

def infer_belief(error_code: str, *, sparse: bool = False, interaction_summary: Mapping[str, object] | None = None) -> dict[str, object]:
    return common.infer_belief(error_code, MISCONCEPTIONS, catalogue_version=CATALOGUE_VERSION, sparse=sparse,
                               interaction_summary=interaction_summary)


_AFFINITY = {
    "visual_guidance": {"single_clue_contradiction_ignored"},
    "worked_parallel_example": {"figurative_taken_literally", "similar_household_referent_confusion"},
    "step_by_step_guidance": {"clue_combination_failure"},
}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    return common.scaffold_decision(skill_id, condition, belief, seed=seed, policy_version=POLICY_VERSION, affinity=_AFFINITY)


# --- Support copy (draft, newly authored; not textbook language) ------------------------------

_DIRECT = {
    "visual": "තේරවිල්ලේ පෙනුම, කරන වැඩය හෝ සිටින තැන කියන කොටස් සොයමු. ඔයා තෝරන පිළිතුරට මේ ඉඟි සියල්ල ගැළපෙනවාද?",
    "worked": ("මුලින්ම මේ වෙනත් තේරවිල්ල කියවමු.", "ඊළඟට පෙනුම ගැන කියන ඉඟියත් කරන වැඩය ගැන කියන ඉඟියත් බලමු.",
               "දැන් ඒ ඉඟි දෙකටම ගැළපෙන පිළිතුර සොයමු.", "බලන්න, පිළිතුර ඉඟි සමඟ ගැළපෙනවා."),
    "guided": ("පළමුව වැදගත් ඉඟියක් තෝරන්න.", "දැන් එයට ගැළපෙන දෙයක් තෝරන්න.",
               "ඉතිරි ඉඟියත් ඒ පිළිතුරට ගැළපෙනවාද බලන්න.", "දැන් පිළිතුර පෙට්ටියට තබන්න."),
    "recap": "මතක තියාගන්න 💡 එක ඉඟියකට පමණක් නොව, තේරවිල්ලේ ඉඟි සියල්ලට ගැළපෙන පිළිතුර සොයන්න.",
}
_FIGURATIVE = {
    "visual": "මේ වචනවලින් කියන්නේ පෙනෙන අර්ථයමද? වෙනත් දෙයකට සමාන කර කියන කොටසක් තිබෙනවාද?",
    "worked": ("මුලින්ම මේ වෙනත් තේරවිල්ලේ සැඟවුණු අදහස බලමු.", "මෙහි කියන වචනයේ සාමාන්‍ය අර්ථය ගැන සිතමු.",
               "ඊළඟට ඒ හැඩයට හෝ වැඩයට සමාන වෙනත් දෙයක් සොයමු.", "දැන් ඉතිරි ඉඟි සමඟත් ගළපා බලමු."),
    "guided": ("සැඟවුණු අදහසක් ඇති වචන කොටස තෝරන්න.", "එය සමාන කර කියන්නේ කුමන ලක්ෂණයකටද බලන්න.",
               "ඒ ලක්ෂණය ඇති දෙයක් තෝරන්න.", "දැන් අනෙක් ඉඟිත් ගැළපෙනවාද පරීක්ෂා කරන්න."),
    "recap": "මතක තියාගන්න 💡 තේරවිලිවල වචන සමහරවිට වෙනත් දෙයක් සමාන කර කියනවා. ඉඟි සමඟ ගළපා අර්ථය සොයන්න.",
}


def support_copy(skill_id: str, family: str) -> dict[str, object]:
    del family
    return dict(_FIGURATIVE if skill_id.endswith("FIGURATIVE-01") else _DIRECT)


def worked_steps(game: Mapping[str, object], scaffold_type: str, skill_id: str) -> list[str]:
    copy = support_copy(skill_id, str(game["subfamily"]))
    steps = {"visual_guidance": [copy["visual"]], "worked_parallel_example": list(copy["worked"]),
             "step_by_step_guidance": list(copy["guided"])}[scaffold_type]  # type: ignore[arg-type]
    if len(game["clue_spans"]) == 1:  # type: ignore[arg-type]
        # A single-line riddle has no "remaining clue": never invent one.
        steps = [s for s in steps if "ඉතිරි" not in str(s) and "අනෙක්" not in str(s)]
    return [str(s) for s in steps]


def package_hash() -> str:
    payload = {
        "area": AREA_ID, "version": PACKAGE_VERSION,
        "sources": [p["sha256"] for p in source_transcription()["photographs"]],  # type: ignore[union-attr,index]
        "skills": list(SKILLS), "misconceptions": list(MISCONCEPTIONS),
        "subfamilies": {s: {f: list(v["pool"]) for f, v in fams.items()} for s, fams in SUBFAMILIES.items()},  # type: ignore[arg-type]
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


__all__ = ["DONE_LINE", "ResponseError"]
