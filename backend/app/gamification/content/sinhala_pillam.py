"""Draft, photograph-linked content and server scoring for G5-AREA-SIN-01 (පිල්ලම් හඳුනාගනිමු).

The only source is one textbook photograph (``IMG_7483.heic``): a 19-row table of sign names,
sign forms, represented vowels and examples. Its transcription is stored once, hash-bound, in
``data/gamification/grade5-sinhala-pillam/v1``. Every probe, demonstration and support item here
is built from that table; consonants beyond the photographed ක/ල/ර/ව are draft and unreviewed.

The package is blocked from production. Skill ids are provisional internal ids, not official
curriculum codes, and the trace to ``G5-SIN-C03-L01-K01`` stays draft.

Responses are semantic: the child places opaque card ids. The server rebuilds the construction
from its own rubric, normalises to NFC and scores 0 or 1. Clients receive the cards and how each
card composes, never which card is right.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

AREA_ID = "G5-AREA-SIN-01"
# Draft crosswalk: orthography. Not reviewed for this area.
UNIVERSAL_SKILL_ID = "LAN-ORT"
PACKAGE_VERSION = "g5-sin-pillam-journey-draft-v1"
CATALOGUE_VERSION = "g5-sin-pillam-misconceptions-v1"
FEATURE_VERSION = "g5-sin-pillam-features-v1"
MAPPING_VERSION = "g5-sin-pillam-evidence-mapping-v1"
MODEL_VERSION = "g5-sin-pillam-authored-probabilistic-v1"
POLICY_VERSION = "g5-sin-pillam-raw-ig-shadow-v1"
SCORING_VERSION = "g5-sin-pillam-scoring-v1"
EQUIVALENCE_VERSION = "g5-sin-pillam-parallel-v1"
RESPONSE_SCHEMA_VERSION = "sinhala-pillam-response-v1"
ITEM_SCHEMA_VERSION = "sinhala-pillam-item-v1"
SOURCE_NODE_ID = "G5-SIN-C03-L01-K01"
SOURCE_MAPPING_STATUS = "draft_blocked_pending_review"

DATA_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "data" / "gamification" / "grade5-sinhala-pillam" / "v1"
)

DOTTED_CIRCLE = "◌"
ZWJ = "‍"

Chapter = Literal["pillam_friends", "akshara_workshop", "compound_garden"]
Role = Literal["unsupported_before", "unsupported_after"]
ScaffoldType = Literal["visual_guidance", "worked_parallel_example", "step_by_step_guidance"]

SCAFFOLDS: tuple[ScaffoldType, ...] = (
    "visual_guidance",
    "worked_parallel_example",
    "step_by_step_guidance",
)
DONE_LINE = "දැන් ඔයාම කරලා බලන්න! 💪"


class PillamResponseError(ValueError):
    """A response the server refuses to score. ``code`` is machine-readable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- Source ----------------------------------------------------------------------------------


@cache
def source_transcription() -> dict[str, object]:
    """The hash-bound photograph transcription. A changed file fails closed."""

    manifest = json.loads((DATA_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    raw = (DATA_DIRECTORY / "source-transcription.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["source-transcription.json"]:
        raise RuntimeError("SINHALA_PILLAM_SOURCE_HASH_MISMATCH")
    return json.loads(raw)


def source_rows() -> tuple[dict[str, object], ...]:
    return tuple(source_transcription()["rows"])  # type: ignore[arg-type]


def row(number: int) -> dict[str, object]:
    return source_rows()[number - 1]


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


# --- Orthography -------------------------------------------------------------------------------

KA, LA, RA = "ක", "ල", "ර"
PHOTOGRAPHED_BASES = frozenset({"ක", "ල", "ර", "ව"})
# Draft consonants for probes. They are not in the photograph: educator review required.
DRAFT_BASES = ("ග", "ත", "ද", "ප", "බ", "ම", "ස", "න")
# ඍ-forms are rare after most consonants; this smaller set needs review before any use.
DRAFT_GAETA_BASES = ("ත", "ද", "ප", "ම", "ස")

# Whole-sign cards (one sign, one card). Value: (mark, logical rank, visual placement).
SIGN_CARDS: dict[str, tuple[str, int, str]] = {
    "sign:aa": ("ා", 1, "right"),
    "sign:ae": ("ැ", 1, "right"),
    "sign:aee": ("ෑ", 1, "right"),
    "sign:i": ("ි", 1, "above"),
    "sign:ii": ("ී", 1, "above"),
    "sign:u": ("ු", 1, "below"),
    "sign:uu": ("ූ", 1, "below"),
    "sign:e": ("ෙ", 0, "left"),
    "sign:ee": ("ේ", 0, "left_and_above"),
    "sign:o": ("ො", 0, "left_and_right"),
    "sign:oo": ("ෝ", 0, "left_and_right"),
}
# Compound component cards. The same component may appear twice in one palette.
COMPONENT_CARDS: dict[str, tuple[str, int, str, str]] = {
    "comp:kombuva": ("ෙ", 0, "left", "කොම්බුව"),
    "comp:alapilla": ("ා", 1, "right", "ඇලපිල්ල"),
    "comp:gayanukitta": ("ෟ", 1, "right", "ගයනුකිත්ත"),
    "comp:gaeta": ("ෘ", 1, "right", "ගැටඇලපිල්ල"),
    "comp:hal": ("්", 2, "above", "හල් කිරීමේ ලකුණ"),
}
# Consonant-specific papili. One Unicode mark per length; the shape is chosen by the font, so
# the card names the printed shape and the server scores the chosen allograph, not the mark.
PAPILI_CARDS: dict[str, tuple[str, str, str]] = {
    "papili:kon:short": ("ු", "kon", "කෙටි කොන් පාපිල්ල"),
    "papili:vak:short": ("ු", "vak", "කෙටි වක් පාපිල්ල"),
    "papili:aeda:short": ("ු", "aeda", "කෙටි ඇද පාපිල්ල"),
    "papili:kon:long": ("ූ", "kon", "දික් කොන් පාපිල්ල"),
    "papili:vak:long": ("ූ", "vak", "දික් වක් පාපිල්ල"),
    "papili:aeda:long": ("ූ", "aeda", "දික් ඇද පාපිල්ල"),
}
# Photograph rows 6-11: which printed shape each photographed consonant takes.
PAPILI_ALLOGRAPH_BY_BASE = {LA: "kon", KA: "vak", RA: "aeda"}

# Reviewed compositions that canonical normalisation cannot produce: two kombu → ෛ, two
# gaeta → ෲ. Every other construction is the NFC of its marks in logical order.
EXPLICIT_COMPOSITIONS = {
    ("ෙ", "ෙ"): "ෛ",
    ("ෘ", "ෘ"): "ෲ",
}
# The vowel signs a construction may end in. Anything else is not a reviewed akshara.
REVIEWED_SIGNS = frozenset(
    {
        "ා", "ැ", "ෑ", "ි", "ී", "ු", "ූ", "ෘ",
        "ෙ", "ේ", "ෛ", "ො", "ෝ", "ෞ", "ෲ",
    }
)


def card_mark(kind: str) -> str:
    if kind in SIGN_CARDS:
        return SIGN_CARDS[kind][0]
    if kind in COMPONENT_CARDS:
        return COMPONENT_CARDS[kind][0]
    if kind in PAPILI_CARDS:
        return PAPILI_CARDS[kind][0]
    raise PillamResponseError("UNKNOWN_TOKEN")


def card_rank(kind: str) -> int:
    if kind in SIGN_CARDS:
        return SIGN_CARDS[kind][1]
    if kind in COMPONENT_CARDS:
        return COMPONENT_CARDS[kind][1]
    return 1


def compose(base: str, kinds: Sequence[str]) -> str | None:
    """The NFC akshara a base and its cards make, or ``None`` when it is not a reviewed form.

    The placement order the child used does not matter: marks are sorted into logical Unicode
    order (pre-base kombuva, then the right/below sign, then hal).
    """

    marks = tuple(card_mark(kind) for kind in sorted(kinds, key=lambda kind: (card_rank(kind), kind)))
    if not marks:
        return None
    joined = EXPLICIT_COMPOSITIONS.get(marks)
    text = nfc(base + (joined if joined is not None else "".join(marks)))
    sign = text[len(base) :]
    if len(sign) != 1 or sign not in REVIEWED_SIGNS:
        return None
    return text


def graphemes(value: str) -> tuple[str, ...]:
    """Extended grapheme clusters for Sinhala, keeping a ZWJ inside its conjunct.

    A base consonant takes every following dependent mark, virama and ZWJ; a ZWJ after a virama
    joins the next consonant into the same cluster. This is the subset of UAX #29 the package's
    strings use; tests compare it with the client's ``Intl.Segmenter``.
    """

    clusters: list[str] = []
    for char in nfc(value):
        category = unicodedata.category(char)
        joins = bool(clusters) and (
            category in {"Mn", "Mc"}
            or char == ZWJ
            or (clusters[-1].endswith("්" + ZWJ))
        )
        if joins:
            clusters[-1] += char
        else:
            clusters.append(char)
    return tuple(clusters)


# --- Skills ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    activity_id: str
    name_si: str
    goal_si: str
    difficulty: str
    response_kind: Literal["sinhala_pillam_match", "sinhala_akshara_build"]
    match_mode: Literal["name", "vowel"] | None
    source_rows: tuple[int, ...]
    prerequisites: tuple[str, ...]
    source_node_id: str = SOURCE_NODE_ID
    outcome_provenance: str = "provisional_internal_id_draft_trace"


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-SIN-PIL-NAME-01",
        "pillam_friends",
        "pillam_mithuro",
        "පිල්ලම් මිතුරෝ",
        "අද අපි පිල්ලම්වල හැඩයත් නමත් හඳුනාගනිමු 🌟",
        "easy",
        "sinhala_pillam_match",
        "name",
        tuple(range(1, 20)),
        (),
    ),
    AtomicSkill(
        "G5-SIN-PIL-VOWEL-01",
        "pillam_friends",
        "swara_palama",
        "ස්වර පාලම",
        "අද අපි එක් එක් පිල්ලමෙන් නියෝජනය වන ස්වරය හඳුනාගනිමු 🌟",
        "easy",
        "sinhala_pillam_match",
        "vowel",
        tuple(range(1, 20)),
        ("G5-SIN-PIL-NAME-01",),
    ),
    AtomicSkill(
        "G5-SIN-PIL-BUILD-01",
        "akshara_workshop",
        "akuru_wadapola",
        "අකුරු වැඩපොළ",
        "අද අපි අකුරකට පිල්ලමක් යොදා අලුත් අකුරු හදමු 🌟",
        "medium",
        "sinhala_akshara_build",
        None,
        (1, 2, 3, 4, 5, 12),
        ("G5-SIN-PIL-NAME-01", "G5-SIN-PIL-VOWEL-01"),
    ),
    AtomicSkill(
        "G5-SIN-PIL-LENGTH-01",
        "akshara_workshop",
        "keti_dik",
        "කෙටිද දික්ද?",
        "අද අපි කෙටි සහ දික් ස්වරවලට ගැළපෙන පිල්ලම් යොදමු 🌟",
        "medium",
        "sinhala_akshara_build",
        None,
        (2, 3, 4, 5, 7, 10, 12, 13, 14, 15),
        ("G5-SIN-PIL-BUILD-01",),
    ),
    AtomicSkill(
        "G5-SIN-PIL-PAPILI-01",
        "compound_garden",
        "papili_maruwa",
        "පාපිලි මාරුව",
        "අද අපි ල, ක, ර අකුරුවලට ගැළපෙන පාපිලි යොදමු 🌟",
        "medium_hard",
        "sinhala_akshara_build",
        None,
        (6, 7, 8, 9, 10, 11),
        ("G5-SIN-PIL-VOWEL-01", "G5-SIN-PIL-LENGTH-01"),
    ),
    AtomicSkill(
        "G5-SIN-PIL-COMPOUND-01",
        "compound_garden",
        "sanyuktha_uyana",
        "සංයුක්ත පිල්ලම් උයන",
        "අද අපි පිල්ලම් කොටස් එක් කර අකුරු හදමු 🌟",
        "hard",
        "sinhala_akshara_build",
        None,
        (13, 14, 15, 16, 17, 18, 19),
        ("G5-SIN-PIL-BUILD-01", "G5-SIN-PIL-LENGTH-01"),
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}

# --- Misconception catalogue -------------------------------------------------------------------

UNKNOWN = "unknown_or_other"
MISCONCEPTIONS = (
    "sign_name_confusion",
    "short_long_confusion",
    "wrong_vowel_association",
    "papili_allograph_confusion",
    "compound_component_missing",
    "compound_component_extra",
    "kombu_family_confusion",
    "gaeta_single_double_confusion",
    UNKNOWN,
)
# The package's unknown code and the shared one are the same string; this records that it was
# reconciled on purpose, so a later rename cannot silently create an incompatible code.
UNKNOWN_CODE_MAPPING = {
    "mapping_version": "g5-sin-pillam-unknown-reconciliation-v1",
    "package_code": UNKNOWN,
    "shared_code": "unknown_or_other",
}
# Semantic error → hypothesis. Several errors refine by the item's subfamily below.
SEMANTIC_TO_HYPOTHESIS = {
    "WRONG_SIGN": "sign_name_confusion",
    "SHORT_LONG_CONFUSION": "short_long_confusion",
    "WRONG_VOWEL_MAPPING": "wrong_vowel_association",
    "WRONG_BASE_ALLOGRAPH": "papili_allograph_confusion",
    "MISSING_COMPONENT": "compound_component_missing",
    "EXTRA_COMPONENT": "compound_component_extra",
    "KOMBU_FAMILY_CONFUSION": "kombu_family_confusion",
    "GAETA_COUNT_CONFUSION": "gaeta_single_double_confusion",
}


def misconception_catalogue() -> list[dict[str, object]]:
    """Versioned draft catalogue: evidence, counter-evidence, skills, source and support."""

    def entry(code, evidence, counter, skills, rows, support):
        return {
            "code": code,
            "catalogue_version": CATALOGUE_VERSION,
            "mapping_version": MAPPING_VERSION,
            "evidence_patterns": evidence,
            "counter_evidence": counter,
            "supported_skills": skills,
            "source_basis": [f"IMG_7483.heic#table-row-{number}" for number in rows],
            "eligible_support": support,
            "review_status": "draft_unreviewed",
        }

    every = list(SCAFFOLDS)
    return [
        entry(
            "sign_name_confusion",
            ["WRONG_SIGN in name mode on an unrelated sign"],
            ["correct independent name match on the same sign"],
            ["G5-SIN-PIL-NAME-01"],
            range(1, 20),
            every,
        ),
        entry(
            "short_long_confusion",
            ["SHORT_LONG_CONFUSION: the length partner chosen in a build, name or vowel item"],
            ["correct independent response inside the same contrast family"],
            ["G5-SIN-PIL-NAME-01", "G5-SIN-PIL-VOWEL-01", "G5-SIN-PIL-BUILD-01",
             "G5-SIN-PIL-LENGTH-01", "G5-SIN-PIL-PAPILI-01"],
            (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
            every,
        ),
        entry(
            "wrong_vowel_association",
            ["WRONG_VOWEL_MAPPING to a vowel outside the sign's length partner"],
            ["correct independent vowel match on the same sign"],
            ["G5-SIN-PIL-VOWEL-01", "G5-SIN-PIL-BUILD-01"],
            range(1, 20),
            every,
        ),
        entry(
            "papili_allograph_confusion",
            ["WRONG_BASE_ALLOGRAPH: the right vowel, another consonant's printed papili shape"],
            ["correct independent allograph for ල, ක and ර"],
            ["G5-SIN-PIL-PAPILI-01", "G5-SIN-PIL-VOWEL-01"],
            (6, 7, 8, 9, 10, 11),
            every,
        ),
        entry(
            "compound_component_missing",
            ["MISSING_COMPONENT: a strict subset of the reviewed components"],
            ["correct independent compound of the same subfamily"],
            ["G5-SIN-PIL-COMPOUND-01"],
            (13, 14, 15, 17, 18, 19),
            every,
        ),
        entry(
            "compound_component_extra",
            ["EXTRA_COMPONENT: the reviewed components plus another"],
            ["correct independent compound of the same subfamily"],
            ["G5-SIN-PIL-COMPOUND-01", "G5-SIN-PIL-BUILD-01"],
            (13, 14, 15, 16, 18, 19),
            every,
        ),
        entry(
            "kombu_family_confusion",
            ["KOMBU_FAMILY_CONFUSION: another එ/ඒ/ඔ/ඕ/ඓ/ඖ form chosen or built"],
            ["correct independent kombu-family response"],
            ["G5-SIN-PIL-NAME-01", "G5-SIN-PIL-COMPOUND-01", "G5-SIN-PIL-LENGTH-01"],
            (12, 13, 14, 15, 18, 19),
            every,
        ),
        entry(
            "gaeta_single_double_confusion",
            ["GAETA_COUNT_CONFUSION: ඍ built or named for ඎ, or the reverse"],
            ["correct independent ඍ or ඎ response"],
            ["G5-SIN-PIL-NAME-01", "G5-SIN-PIL-COMPOUND-01"],
            (16, 17),
            every,
        ),
        entry(
            UNKNOWN,
            ["no pattern above, sparse evidence, motor or rendering difficulty"],
            [],
            list(SKILLS),
            range(1, 20),
            every,
        ),
    ]


# --- Item pools ------------------------------------------------------------------------------

# Rows whose standalone sign shows its own shape (rows 6-11 share one mark per length).
NAME_DISTINCT_ROWS = (1, 4, 12, 16, 19)
NAME_CLOSE_PARTNER = {2: 3, 3: 2, 4: 5, 5: 4, 12: 13, 13: 12, 14: 15, 15: 14, 16: 17, 17: 16}
VOWEL_SINGLE_ROWS = (1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19)
VOWEL_LENGTH_PARTNER = {
    "ආ": "අ", "ඇ": "ඈ", "ඈ": "ඇ", "ඉ": "ඊ", "ඊ": "ඉ", "උ": "ඌ", "ඌ": "උ",
    "එ": "ඒ", "ඒ": "එ", "ඔ": "ඕ", "ඕ": "ඔ", "ඍ": "ඎ", "ඎ": "ඍ", "ඓ": "එ", "ඖ": "ඔ",
}
# Pairs of photographed papili examples that share one vowel destination.
VOWEL_SHARED_PAIRS = ((6, 7), (7, 8), (6, 8), (9, 10), (10, 11), (9, 11))
SIMPLE_BUILD_KIND = {1: "sign:aa", 2: "sign:ae", 3: "sign:aee", 4: "sign:i", 5: "sign:ii", 12: "sign:e"}
LENGTH_FAMILIES = {
    "ae": ("sign:ae", "sign:aee", 2, 3),
    "i": ("sign:i", "sign:ii", 4, 5),
    "u": ("sign:u", "sign:uu", 7, 10),
    "e": ("sign:e", "sign:ee", 12, 13),
    "o": ("sign:o", "sign:oo", 14, 15),
}
COMPOUND_TARGETS = {
    13: ("comp:kombuva", "comp:hal"),
    14: ("comp:kombuva", "comp:alapilla"),
    15: ("comp:kombuva", "comp:alapilla", "comp:hal"),
    16: ("comp:gaeta",),
    17: ("comp:gaeta", "comp:gaeta"),
    18: ("comp:kombuva", "comp:kombuva"),
    19: ("comp:kombuva", "comp:gayanukitta"),
}
KOMBU_ROWS = frozenset({12, 13, 14, 15, 18, 19})
# Subfamilies whose pool cannot yet support fresh equivalent probes: practice only.
IG_UNAVAILABLE_SUBFAMILIES = frozenset({"compound:row-17"})


@dataclass(frozen=True, slots=True)
class PillamItem:
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


@dataclass(frozen=True, slots=True)
class PoolMember:
    """One possible item of a subfamily: what it asks, never how it is shown."""

    key: str
    rows: tuple[int, ...]
    base: str | None = None
    target_kinds: tuple[str, ...] = ()
    vowel: str | None = None


def _vowel(number: int) -> str:
    return str(row(number)["printed_vowel_si"])


def subfamilies(skill_id: str) -> dict[str, dict[str, object]]:
    """Every subfamily of one skill: its probe pool and its fixed demonstration.

    The demonstration is always outside the pool, so no shown example is ever a probe.
    """

    if skill_id.endswith("NAME-01"):
        return {
            "name:distinct": {
                "pool": [PoolMember(f"row-{n}", (n,)) for n in NAME_DISTINCT_ROWS[1:]],
                "demo": PoolMember("row-1", (1,)),
            },
            "name:close": {
                "pool": [PoolMember(f"row-{n}", (n,)) for n in (3, 4, 5, 13, 14, 15, 16, 17)],
                "demo": PoolMember("row-2", (2,)),
            },
        }
    if skill_id.endswith("VOWEL-01"):
        return {
            "vowel:single": {
                "pool": [PoolMember(f"row-{n}", (n,)) for n in VOWEL_SINGLE_ROWS[1:]],
                "demo": PoolMember("row-1", (1,)),
            },
            "vowel:shared-papili": {
                "pool": [PoolMember(f"rows-{a}-{b}", (a, b)) for a, b in VOWEL_SHARED_PAIRS[1:]],
                "demo": PoolMember("rows-6-7", (6, 7)),
            },
        }
    if skill_id.endswith("BUILD-01"):
        return {
            f"build:row-{n}": {
                "pool": [
                    PoolMember(f"{base}-row-{n}", (n,), base, (kind,), _vowel(n))
                    for base in DRAFT_BASES
                ],
                "demo": PoolMember(f"{KA}-row-1", (1,), KA, ("sign:aa",), _vowel(1)),
            }
            for n, kind in SIMPLE_BUILD_KIND.items()
        }
    if skill_id.endswith("LENGTH-01"):
        result = {}
        for family, (short, long, short_row, long_row) in LENGTH_FAMILIES.items():
            bases = tuple(base for base in DRAFT_BASES if base not in {LA, RA})
            for length, kind, number in (("short", short, short_row), ("long", long, long_row)):
                demo_number = long_row if length == "short" else short_row
                demo_kind = long if length == "short" else short
                result[f"length:{family}:{length}"] = {
                    "pool": [
                        PoolMember(f"{base}-row-{number}", (number,), base, (kind,), _vowel(number))
                        for base in bases
                    ],
                    # The other member of the same contrast, on the photographed ක.
                    "demo": PoolMember(
                        f"{KA}-row-{demo_number}", (demo_number,), KA, (demo_kind,), _vowel(demo_number)
                    ),
                }
        return result
    if skill_id.endswith("PAPILI-01"):
        def member(base: str, length: str) -> PoolMember:
            number = {(LA, "short"): 6, (KA, "short"): 7, (RA, "short"): 8,
                      (LA, "long"): 9, (KA, "long"): 10, (RA, "long"): 11}[(base, length)]
            kind = f"papili:{PAPILI_ALLOGRAPH_BY_BASE[base]}:{length}"
            return PoolMember(f"{base}-{length}", (number,), base, (kind,), _vowel(number))

        return {
            "papili:short": {"pool": [member(KA, "short"), member(RA, "short")], "demo": member(LA, "short")},
            "papili:long": {"pool": [member(KA, "long"), member(RA, "long"), member(LA, "long")],
                            "demo": member(LA, "short")},
        }
    if skill_id.endswith("COMPOUND-01"):
        result = {}
        for number, kinds in COMPOUND_TARGETS.items():
            bases = DRAFT_GAETA_BASES if number in {16, 17} else DRAFT_BASES
            result[f"compound:row-{number}"] = {
                "pool": [PoolMember(f"{base}-row-{number}", (number,), base, kinds, _vowel(number)) for base in bases],
                "demo": PoolMember(f"{KA}-row-{number}", (number,), KA, kinds, _vowel(number)),
            }
        return result
    raise ValueError("SINHALA_PILLAM_SKILL_NOT_FOUND")


def _digest(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def episode_subfamily(skill_id: str, seed: int) -> str:
    names = sorted(subfamilies(skill_id))
    return names[_digest(skill_id, "subfamily", seed) % len(names)]


def probe_members(skill_id: str, seed: int) -> tuple[str, PoolMember, PoolMember]:
    """The episode's subfamily and its distinct before and after members."""

    family = episode_subfamily(skill_id, seed)
    pool = list(subfamilies(skill_id)[family]["pool"])  # type: ignore[arg-type]
    random.Random(_digest(skill_id, family, "probes", seed)).shuffle(pool)
    return family, pool[0], pool[1]


def support_members(skill_id: str, seed: int) -> tuple[PoolMember, ...]:
    """Assisted material: the subfamily's pool minus both reserved probes, then its demo."""

    family, before, after = probe_members(skill_id, seed)
    spec = subfamilies(skill_id)[family]
    rest = [m for m in spec["pool"] if m.key not in {before.key, after.key}]  # type: ignore[union-attr]
    random.Random(_digest(skill_id, family, "support", seed)).shuffle(rest)
    return (*rest, spec["demo"])  # type: ignore[return-value]


def _token(prefix: str, value: object, salt: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def _display(mark: str) -> str:
    return DOTTED_CIRCLE + mark


def _name_docks(skill_id: str, family: str, member: PoolMember, rng: random.Random) -> list[int]:
    target = member.rows[0]
    if family == "name:close":
        partner = NAME_CLOSE_PARTNER[target]
        others = [n for n in NAME_DISTINCT_ROWS if n not in {target, partner}]
        return [target, partner, rng.choice(others)]
    others = [n for n in NAME_DISTINCT_ROWS if n != target]
    return [target, *rng.sample(others, 2)]


def _vowel_docks(member: PoolMember, rng: random.Random) -> list[str]:
    vowels = [_vowel(n) for n in member.rows]
    docks = list(dict.fromkeys(vowels))
    partner = VOWEL_LENGTH_PARTNER.get(vowels[0])
    if partner and partner not in docks:
        docks.append(partner)
    pool = sorted({str(r["printed_vowel_si"]) for r in source_rows()} - set(docks))
    while len(docks) < 3:
        docks.append(pool.pop(rng.randrange(len(pool))))
    return docks


def _build_palette(skill_id: str, family: str, member: PoolMember, rng: random.Random) -> list[str]:
    """Card kinds offered: the reviewed answer's cards plus plausible competitors."""

    if skill_id.endswith("BUILD-01"):
        target = member.target_kinds[0]
        others = [k for k in SIMPLE_BUILD_KIND.values() if k != target]
        # Competitors exclude the target's length partner: that contrast is LENGTH's job.
        partner = {"sign:ae": "sign:aee", "sign:aee": "sign:ae", "sign:i": "sign:ii", "sign:ii": "sign:i"}
        others = [k for k in others if k != partner.get(target)]
        return [target, *rng.sample(others, 2)]
    if skill_id.endswith("LENGTH-01"):
        short, long, _, _ = LENGTH_FAMILIES[family.split(":")[1]]
        unrelated = [k for k in ("sign:aa", "sign:i", "sign:e", "sign:u") if k not in {short, long}]
        return [short, long, rng.choice(unrelated)]
    if skill_id.endswith("PAPILI-01"):
        length = family.split(":")[1]
        other = "long" if length == "short" else "short"
        correct = member.target_kinds[0]
        return [f"papili:{shape}:{length}" for shape in ("kon", "vak", "aeda")] + [
            correct.replace(f":{length}", f":{other}")
        ]
    if family in {"compound:row-16", "compound:row-17"}:
        return ["comp:gaeta", "comp:gaeta", "comp:alapilla", "comp:kombuva"]
    return ["comp:kombuva", "comp:kombuva", "comp:alapilla", "comp:hal", "comp:gayanukitta"]


def _card(kind: str, token: str) -> dict[str, object]:
    if kind in PAPILI_CARDS:
        mark, shape, name = PAPILI_CARDS[kind]
        return {
            "token_id": token,
            "compose_si": mark,
            "logical_rank": 1,
            "visual_placement": "below",
            "allograph_shape": shape,
            "label_si": name,
            "display_si": _display(mark),
            "accessible_label_si": name,
        }
    if kind in COMPONENT_CARDS:
        mark, rank, placement, name = COMPONENT_CARDS[kind]
        return {
            "token_id": token,
            "compose_si": mark,
            "logical_rank": rank,
            "visual_placement": placement,
            "label_si": name,
            "display_si": _display(mark),
            "accessible_label_si": f"{name} කොටස",
        }
    mark, rank, placement = SIGN_CARDS[kind]
    return {
        "token_id": token,
        "compose_si": mark,
        "logical_rank": rank,
        "visual_placement": placement,
        "display_si": _display(mark),
        "accessible_label_si": "පිල්ලම් කාඩ්පත",
    }


def build_item(
    skill_id: str, family: str, member: PoolMember, *, role: str, salt: str
) -> PillamItem:
    """One item for one pool member. Card ids are opaque and their order is shuffled."""

    skill = SKILLS[skill_id]
    rng = random.Random(_digest(salt, member.key))
    game: dict[str, object] = {
        "activity_id": skill.activity_id,
        "response_kind": skill.response_kind,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "subfamily": family,
        "source_locators": [str(row(n)["locator"]) for n in member.rows],
        "goal_si": skill.goal_si,
    }
    if skill.response_kind == "sinhala_pillam_match":
        game["match_mode"] = skill.match_mode
        if skill.match_mode == "name":
            rows = _name_docks(skill_id, family, member, rng)
            target = member.rows[0]
            card_token = _token("sign", target, salt)
            cards = [{**_card_from_row(target), "token_id": card_token}]
            docks = [
                {"destination_id": _token("name", n, salt), "text_si": str(row(n)["printed_name_si"])}
                for n in rows
            ]
            rng.shuffle(docks)
            accepted = {card_token: [_token("name", target, salt)]}
            partners = {card_token: [_token("name", NAME_CLOSE_PARTNER[target], salt)]} if target in NAME_CLOSE_PARTNER else {}
            dest_rows = {_token("name", n, salt): n for n in rows}
            prompt = "මේ පිල්ලමේ හැඩය බලා එහි නම ළඟට ගෙන යන්න."
        else:
            vowels = _vowel_docks(member, rng)
            cards = []
            accepted = {}
            partners = {}
            for index, number in enumerate(member.rows):
                token = _token("sign", f"{number}:{index}", salt)
                cards.append({**_card_from_row(number, in_context=len(member.rows) > 1), "token_id": token})
                accepted[token] = [_token("vowel", _vowel(number), salt)]
                partner = VOWEL_LENGTH_PARTNER.get(_vowel(number))
                if partner:
                    partners[token] = [_token("vowel", partner, salt)]
            docks = [{"destination_id": _token("vowel", v, salt), "text_si": v} for v in vowels]
            rng.shuffle(docks)
            rng.shuffle(cards)
            dest_rows = {}
            prompt = (
                "මේ පිල්ලමෙන් නියෝජනය වන ස්වරය සොයා එය ස්වර පාලමට සම්බන්ධ කරන්න."
                if len(member.rows) == 1
                else "එක් එක් අකුරේ පාපිල්ලෙන් නියෝජනය වන ස්වරයට සම්බන්ධ කරන්න. එක ස්වරයකට අකුරු කිහිපයක් යා හැක."
            )
        game.update(sign_cards=cards, destinations=docks)
        game["rubric"] = {
            "accepted": accepted,
            "length_partner": partners,
            "destination_rows": dest_rows,
            "target_rows": list(member.rows),
        }
    else:
        assert member.base is not None and member.vowel is not None
        base_token = _token("base", member.base, salt)
        kinds = _build_palette(skill_id, family, member, rng)
        tokens = [_token("card", f"{kind}:{index}", salt) for index, kind in enumerate(kinds)]
        cards = [_card(kind, token) for kind, token in zip(kinds, tokens, strict=True)]
        rng.shuffle(cards)
        game.update(
            base={"token_id": base_token, "text_si": member.base, "accessible_label_si": f"මුල් අකුර {member.base}"},
            target_vowel_si=member.vowel,
            component_cards=cards,
            maximum_components=4,
        )
        target_text = compose(member.base, member.target_kinds)
        if target_text is None:
            raise ValueError("SINHALA_PILLAM_UNREVIEWED_TARGET")
        game["rubric"] = {
            "base_token": base_token,
            "kind_by_token": dict(zip(tokens, kinds, strict=True)),
            "target_kinds": sorted(member.target_kinds),
            "target_text_nfc": target_text,
            "target_rows": list(member.rows),
            "papili_allograph": PAPILI_ALLOGRAPH_BY_BASE.get(member.base) if skill_id.endswith("PAPILI-01") else None,
        }
        prompt = {
            "BUILD-01": f"{member.base} අකුරට පිල්ලමක් යොදා '{member.vowel}' ස්වරය ඇති අකුර හදන්න.",
            "LENGTH-01": f"{member.base} අකුරට '{member.vowel}' ස්වරය ලැබෙන්න කෙටි හෝ දික් පිල්ලම යොදන්න.",
            "PAPILI-01": f"{member.base} අකුරට '{member.vowel}' ස්වරය ලැබෙන්න ගැළපෙන පාපිල්ල යොදන්න.",
            "COMPOUND-01": f"{member.base} අකුරට '{member.vowel}' ස්වරය ලැබෙන්න අවශ්‍ය පිල්ලම් කොටස් යොදන්න.",
        }[skill_id.split("-", 3)[3]]
    game["equivalence"] = {
        "skill_id": skill_id,
        "subfamily": family,
        "response_kind": skill.response_kind,
        "match_mode": skill.match_mode,
        "card_count": len(game.get("sign_cards") or game.get("component_cards") or []),
        "destination_count": len(game.get("destinations") or []),
        "component_count": len(member.target_kinds) if member.target_kinds else len(member.rows),
        "consonant_familiarity": (
            None if member.base is None else ("photographed" if member.base in PHOTOGRAPHED_BASES else "draft")
        ),
        "maximum_score": 1,
        "accepted_response_flexibility": "any_placement_order_same_final_composition",
        "ig_available": family not in IG_UNAVAILABLE_SUBFAMILIES,
    }
    fingerprint = hashlib.sha256(
        json.dumps({"member": member.key, "family": family, "salt": salt}, ensure_ascii=False).encode()
    ).hexdigest()[:12]
    suffix = {"unsupported_before": "B", "unsupported_after": "A"}.get(role, "S")
    return PillamItem(
        item_id=f"{skill_id}:{family}:{member.key}",
        revision_id=f"{skill_id}:{suffix}:{fingerprint}@v1",
        parallel_family_id=f"{skill_id}:{family}:parallel-v1",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,
        prompt_si=prompt,
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def _card_from_row(number: int, *, in_context: bool = False) -> dict[str, object]:
    record = row(number)
    if in_context:
        # A papili shape exists only on its consonant: the card shows the photographed example.
        text = str(record["normalized_examples_nfc"][0])  # type: ignore[index]
        return {
            "display_si": text,
            "accessible_label_si": f"අකුර {text}",
            "in_consonant_context": True,
        }
    return {
        "display_si": str(record["printed_sign_display_si"]),
        "accessible_label_si": "පිල්ලම් කාඩ්පත",
        "in_consonant_context": False,
    }


def generate_item(skill_id: str, *, role: str, seed: int) -> PillamItem:
    if skill_id not in SKILLS:
        raise ValueError("SINHALA_PILLAM_SKILL_NOT_FOUND")
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    family, before, after = probe_members(skill_id, seed)
    member = before if role == "unsupported_before" else after
    return build_item(skill_id, family, member, role=role, salt=f"{skill_id}:{role}:{seed}")


def generate_support_item(skill_id: str, *, seed: int, index: int) -> PillamItem:
    """Assisted material for one support stage: never a reserved before or after member."""

    members = support_members(skill_id, seed)
    member = members[index % len(members)]
    family = episode_subfamily(skill_id, seed)
    return build_item(
        skill_id, family, member, role="supported_practice", salt=f"{skill_id}:support:{seed}:{index}"
    )


def demonstration(skill_id: str, seed: int) -> dict[str, object]:
    """The activity's unscored opening demonstration: fixed, photographed, never a probe."""

    family = episode_subfamily(skill_id, seed)
    demo: PoolMember = subfamilies(skill_id)[family]["demo"]  # type: ignore[assignment]
    skill = SKILLS[skill_id]
    record: dict[str, object] = {
        "demonstration_id": f"{skill_id}:{family}:demo:{demo.key}@v1",
        "goal_si": skill.goal_si,
        "source_locators": [str(row(n)["locator"]) for n in demo.rows],
        "unscored": True,
    }
    if skill.match_mode == "name":
        number = demo.rows[0]
        record.update(
            sign_display_si=str(row(number)["printed_sign_display_si"]),
            shown_si=str(row(number)["printed_name_si"]),
        )
    elif skill.match_mode == "vowel":
        record.update(
            sign_display_si=" ".join(str(row(n)["normalized_examples_nfc"][0]) for n in demo.rows)  # type: ignore[index]
            if len(demo.rows) > 1
            else str(row(demo.rows[0])["printed_sign_display_si"]),
            shown_si=_vowel(demo.rows[0]),
        )
    else:
        assert demo.base is not None
        record.update(
            base_si=demo.base,
            target_vowel_si=demo.vowel,
            shown_si=compose(demo.base, demo.target_kinds),
        )
    return record


# --- Scoring ---------------------------------------------------------------------------------

_MATCH_KEYS = {"kind", "schema_version", "match_mode", "placements"}
_BUILD_KEYS = {"kind", "schema_version", "base_consonant_id", "ordered_pilla_ids"}


def _game(item: PillamItem | Mapping[str, object]) -> Mapping[str, object]:
    game = item.game_data if isinstance(item, PillamItem) else item.get("game_data")
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_SINHALA_PILLAM_ITEM")
    return game


def validate_constructed_response(
    item: PillamItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    """Score one response from the item's own rubric. Refusals raise ``PillamResponseError``.

    Returns (correct, hypothesis code, normalized response). The normalized response keeps the
    child's placement order and the semantic error, for telemetry and Model 1.
    """

    game = _game(item)
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    kind = response.get("kind")
    if kind not in {"sinhala_pillam_match", "sinhala_akshara_build"}:
        raise PillamResponseError("MALFORMED_RESPONSE")
    if kind != game["response_kind"]:
        raise PillamResponseError("RESPONSE_KIND_MISMATCH")
    if response.get("schema_version") != RESPONSE_SCHEMA_VERSION:
        raise PillamResponseError("SCHEMA_MISMATCH")
    if kind == "sinhala_pillam_match":
        return _score_match(game, rubric, response)
    return _score_build(game, rubric, response)


def _score_match(
    game: Mapping[str, object], rubric: Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    if set(response) != _MATCH_KEYS:
        raise PillamResponseError("MALFORMED_RESPONSE")
    if response["match_mode"] not in {"name", "vowel"}:
        raise PillamResponseError("MALFORMED_RESPONSE")
    if response["match_mode"] != game["match_mode"]:
        raise PillamResponseError("MATCH_MODE_MISMATCH")
    placements = response["placements"]
    if not isinstance(placements, list) or len(placements) > 4:
        raise PillamResponseError("MALFORMED_RESPONSE")
    cards = {str(card["token_id"]) for card in game["sign_cards"]}  # type: ignore[union-attr,index]
    docks = {str(dock["destination_id"]) for dock in game["destinations"]}  # type: ignore[union-attr,index]
    seen: dict[str, str] = {}
    order: list[str] = []
    for placement in placements:
        if not isinstance(placement, Mapping) or set(placement) != {"source_token_id", "destination_id"}:
            raise PillamResponseError("MALFORMED_RESPONSE")
        source, destination = placement["source_token_id"], placement["destination_id"]
        if not isinstance(source, str) or not isinstance(destination, str):
            raise PillamResponseError("MALFORMED_RESPONSE")
        if source not in cards or destination not in docks:
            raise PillamResponseError("UNKNOWN_TOKEN")
        if source in seen:
            raise PillamResponseError("DUPLICATE_TOKEN")
        seen[source] = destination
        order.append(source)
    if set(seen) != cards:
        raise PillamResponseError("INCOMPLETE_RESPONSE")
    if game["match_mode"] == "name" and len(set(seen.values())) != len(seen):
        raise PillamResponseError("DUPLICATE_TOKEN")
    accepted = rubric["accepted"]
    partners = rubric["length_partner"]
    assert isinstance(accepted, Mapping) and isinstance(partners, Mapping)
    wrong = [source for source, destination in seen.items() if destination not in accepted[source]]
    normalized = {
        "kind": "sinhala_pillam_match",
        "match_mode": game["match_mode"],
        "placements": [{"source_token_id": s, "destination_id": seen[s]} for s in order],
        "placement_order": order,
    }
    if not wrong:
        normalized["semantic_error"] = None
        return True, "correct", normalized
    source = wrong[0]
    partner_hit = seen[source] in partners.get(source, [])
    if game["match_mode"] == "vowel":
        semantic = "SHORT_LONG_CONFUSION" if partner_hit else "WRONG_VOWEL_MAPPING"
    else:
        target_rows = rubric["target_rows"]
        chosen_row = rubric["destination_rows"].get(seen[source])  # type: ignore[union-attr]
        target = int(target_rows[0])  # type: ignore[index]
        if {target, chosen_row} <= {16, 17}:
            semantic = "GAETA_COUNT_CONFUSION"
        elif target in KOMBU_ROWS and chosen_row in KOMBU_ROWS:
            semantic = "KOMBU_FAMILY_CONFUSION"
        elif partner_hit:
            semantic = "SHORT_LONG_CONFUSION"
        else:
            semantic = "WRONG_SIGN"
    normalized["semantic_error"] = semantic
    return False, SEMANTIC_TO_HYPOTHESIS[semantic], normalized


def _score_build(
    game: Mapping[str, object], rubric: Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    if set(response) != _BUILD_KEYS:
        raise PillamResponseError("MALFORMED_RESPONSE")
    base_id, ids = response["base_consonant_id"], response["ordered_pilla_ids"]
    if not isinstance(base_id, str) or not isinstance(ids, list):
        raise PillamResponseError("MALFORMED_RESPONSE")
    if base_id != rubric["base_token"]:
        raise PillamResponseError("UNKNOWN_TOKEN")
    if not ids:
        raise PillamResponseError("INCOMPLETE_RESPONSE")
    if len(ids) > int(game["maximum_components"]):  # type: ignore[call-overload]
        raise PillamResponseError("MALFORMED_RESPONSE")
    kinds_by_token = rubric["kind_by_token"]
    assert isinstance(kinds_by_token, Mapping)
    if not all(isinstance(value, str) for value in ids):
        raise PillamResponseError("MALFORMED_RESPONSE")
    if any(value not in kinds_by_token for value in ids):
        raise PillamResponseError("UNKNOWN_TOKEN")
    if len(set(ids)) != len(ids):
        raise PillamResponseError("DUPLICATE_TOKEN")
    kinds = [str(kinds_by_token[value]) for value in ids]
    base = str(game["base"]["text_si"])  # type: ignore[index]
    papili = [kind for kind in kinds if kind in PAPILI_CARDS]
    if papili and len(kinds) != 1:
        raise PillamResponseError("MALFORMED_RESPONSE")
    built = compose(base, kinds)
    target = sorted(str(kind) for kind in rubric["target_kinds"])  # type: ignore[union-attr]
    normalized: dict[str, object] = {
        "kind": "sinhala_akshara_build",
        "base_consonant_id": base_id,
        "ordered_pilla_ids": list(ids),
        "placement_order": list(ids),
        "built_text_nfc": built,
    }
    if sorted(kinds) == target and built == rubric["target_text_nfc"]:
        normalized["semantic_error"] = None
        return True, "correct", normalized
    semantic = _build_error(kinds, target, rubric)
    normalized["semantic_error"] = semantic
    return False, SEMANTIC_TO_HYPOTHESIS[semantic], normalized


_LENGTH_PAIRS = {
    frozenset({"sign:ae", "sign:aee"}), frozenset({"sign:i", "sign:ii"}),
    frozenset({"sign:u", "sign:uu"}), frozenset({"sign:e", "sign:ee"}),
    frozenset({"sign:o", "sign:oo"}),
}


def _build_error(kinds: list[str], target: list[str], rubric: Mapping[str, object]) -> str:
    if len(kinds) == 1 and len(target) == 1:
        chosen, wanted = kinds[0], target[0]
        if chosen in PAPILI_CARDS and wanted in PAPILI_CARDS:
            same_shape = PAPILI_CARDS[chosen][1] == PAPILI_CARDS[wanted][1]
            return "SHORT_LONG_CONFUSION" if same_shape else "WRONG_BASE_ALLOGRAPH"
        if frozenset({chosen, wanted}) in _LENGTH_PAIRS:
            return "SHORT_LONG_CONFUSION"
    submitted, wanted_count = Counter(kinds), Counter(target)
    gaeta = {"comp:gaeta"}
    if set(submitted) <= gaeta and set(wanted_count) <= gaeta:
        return "GAETA_COUNT_CONFUSION"
    if submitted < wanted_count:
        return "MISSING_COMPONENT"
    if wanted_count < submitted:
        return "EXTRA_COMPONENT"
    if "comp:kombuva" in submitted and "comp:kombuva" in wanted_count:
        return "KOMBU_FAMILY_CONFUSION"
    if set(kinds) & {"sign:e", "sign:ee", "sign:o", "sign:oo"} and set(target) & {
        "sign:e", "sign:ee", "sign:o", "sign:oo"
    }:
        return "KOMBU_FAMILY_CONFUSION"
    return "WRONG_SIGN"


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    """A response the rubric accepts, for demonstrations only. Never sent with a probe."""

    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    if game["response_kind"] == "sinhala_pillam_match":
        accepted = rubric["accepted"]
        assert isinstance(accepted, Mapping)
        return {
            "kind": "sinhala_pillam_match",
            "schema_version": RESPONSE_SCHEMA_VERSION,
            "match_mode": game["match_mode"],
            "placements": [
                {"source_token_id": source, "destination_id": destinations[0]}
                for source, destinations in accepted.items()
            ],
        }
    kinds_by_token = rubric["kind_by_token"]
    assert isinstance(kinds_by_token, Mapping)
    remaining = Counter(str(kind) for kind in rubric["target_kinds"])  # type: ignore[union-attr]
    chosen = []
    for token, kind in kinds_by_token.items():
        if remaining[kind] > 0:
            chosen.append(token)
            remaining[kind] -= 1
    return {
        "kind": "sinhala_akshara_build",
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "base_consonant_id": rubric["base_token"],
        "ordered_pilla_ids": chosen,
    }


HIDDEN_GAME_KEYS = frozenset({"rubric", "equivalence"})


def public_game_data(item: PillamItem) -> dict[str, object]:
    """Visible material, response inventory and accessibility metadata only."""

    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key not in HIDDEN_GAME_KEYS},
    }


def feedback_si(game: Mapping[str, object], correct: bool) -> str:
    """Short explanatory feedback, given only after the server has scored."""

    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    if correct:
        return "හරි! හොඳින් ගැළපුවා 🎉"
    if game["response_kind"] == "sinhala_akshara_build":
        return f"බලන්න, හරි අකුර {rubric['target_text_nfc']}. පිල්ලමේ හැඩය සසඳා බලමු."
    rows = rubric["target_rows"]
    first = row(int(rows[0]))  # type: ignore[index]
    if game["match_mode"] == "name":
        return f"මේ පිල්ලම '{first['printed_name_si']}'. හැඩය මතක තියාගමු."
    return f"මේ පිල්ලමෙන් '{first['printed_vowel_si']}' ස්වරය නියෝජනය වේ."


# --- Model 1 ---------------------------------------------------------------------------------

_MOTOR_CORRECTIONS = 3
_MOTOR_CANCELS = 2


def infer_belief(
    error_code: str,
    *,
    sparse: bool = False,
    interaction_summary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """A full normalized distribution over the catalogue, with a safe unknown fallback.

    Motor difficulty (many corrected drags or cancelled drags) and a reported clipped glyph are
    not linguistic evidence: they move mass to ``unknown_or_other`` and are recorded as flags.
    """

    summary = interaction_summary or {}
    motor = (
        int(summary.get("correction_count", 0) or 0) >= _MOTOR_CORRECTIONS
        or int(summary.get("cancelled_drag_count", 0) or 0) >= _MOTOR_CANCELS
    )
    rendering = bool(summary.get("rendering_issue_reported", False))
    primary = error_code if error_code in MISCONCEPTIONS else UNKNOWN
    weights = {code: 1.0 for code in MISCONCEPTIONS}
    if sparse or rendering:
        weights[UNKNOWN] = 8.0
    elif primary != UNKNOWN:
        weights[primary] = 3.0 if motor else 9.0
        weights[UNKNOWN] = 3.0 if motor else 1.5
    else:
        weights[UNKNOWN] = 6.0
    total = sum(weights.values())
    probabilities = {code: weight / total for code, weight in weights.items()}
    top = max(probabilities, key=probabilities.__getitem__)
    confidence = probabilities[top]
    entropy = -sum(p * math.log(p) for p in probabilities.values() if p > 0)
    return {
        "probabilities": probabilities,
        "unknown_probability": probabilities[UNKNOWN],
        "top_hypothesis": top,
        "confidence": confidence,
        "entropy": entropy,
        "abstained": top == UNKNOWN,
        "low_confidence": sparse or rendering or motor or confidence < 0.5,
        "motor_difficulty_suspected": motor,
        "rendering_failure_suspected": rendering,
        "evidence_window": "unsupported_before_only",
        "unknown_code_mapping": dict(UNKNOWN_CODE_MAPPING),
        "catalogue_version": CATALOGUE_VERSION,
    }


# --- Model 2 reference decision ----------------------------------------------------------------

_AFFINITY = {
    "visual_guidance": {"sign_name_confusion", "papili_allograph_confusion", "gaeta_single_double_confusion"},
    "worked_parallel_example": {"wrong_vowel_association", "kombu_family_confusion", "short_long_confusion"},
    "step_by_step_guidance": {"compound_component_missing", "compound_component_extra"},
}


def scaffold_decision(
    skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int
) -> dict[str, object]:
    """Predicted raw IG and uncertainty for every candidate; selection is fixed in baseline."""

    top = str(belief.get("top_hypothesis"))
    abstained = bool(belief.get("abstained"))
    candidates = [
        {
            "scaffold_type": scaffold,
            "eligible": True,
            "exclusion_reasons": [],
            "predicted_raw_ig": round(0.06 + (0.08 if top in _AFFINITY[scaffold] else 0.0), 6),
            "uncertainty": 0.2 if abstained else 0.1,
            "propensity": 1.0 if condition == "baseline" and scaffold == "visual_guidance" else None,
        }
        for scaffold in SCAFFOLDS
    ]
    if condition == "baseline":
        selected, mode = "visual_guidance", "deterministic_baseline"
    elif abstained:
        selected, mode = "visual_guidance", "proposed_shadow_conservative_fallback"
    else:
        selected = max(candidates, key=lambda c: float(c["predicted_raw_ig"]))["scaffold_type"]
        mode = "proposed_shadow"
    return {
        "policy_version": POLICY_VERSION,
        "skill_id": skill_id,
        "condition": condition,
        "mode": mode,
        "objective": "predicted_raw_independence_gain",
        "uses_complete_model1_distribution": condition != "baseline",
        "seed": seed,
        "exploration": None,
        "selected_action": selected,
        "candidates": candidates,
    }


# --- Support copy (newly authored draft, not textbook language) --------------------------------

SUPPORT_COPY: dict[str, dict[str, object]] = {
    "NAME-01": {
        "visual": "පිල්ලමේ හැඩය හොඳින් බලන්න. වෙනස් වන කොටස කොතැනද?",
        "worked": ("මුලින්ම මේ වෙනත් පිල්ලම බලමු.", "ඊළඟට එහි හැඩය නම සමඟ ගළපමු.",
                   "බලන්න, දැන් හැඩයත් නමත් ගැළපුණා."),
        "guided": ("පළමුව පිල්ලම තෝරන්න.", "දැන් එයට ගැළපෙන නම ළඟ තබන්න."),
        "recap": "මතක තියාගන්න 💡 පිල්ලමේ හැඩයත් නමත් එකට මතක තියාගමු.",
    },
    "VOWEL-01": {
        "visual": "පිල්ලමත් නියෝජනය වන ස්වරයත් වෙන වෙනම බලමු. මේ පිල්ලම යෙදූ විට ලැබෙන්නේ කුමන ස්වරයද?",
        "worked": ("මුලින්ම වෙනත් පිල්ලමක් ගනිමු.", "ඊළඟට එය නියෝජනය කරන ස්වරය බලමු.",
                   "දැන් ඒ දෙක සම්බන්ධ කරමු."),
        "guided": ("පිල්ලම තෝරන්න.", "එය නියෝජනය කරන ස්වරය තෝරන්න.", "දැන් දෙක සම්බන්ධ කරන්න."),
        "recap": "මතක තියාගන්න 💡 පිල්ලම නියෝජනය කරන ස්වරය හඳුනාගෙන ගළපන්න.",
    },
    "BUILD-01": {
        "visual": "මුල් අකුරත් ඉල්ලා ඇති ස්වරයත් බලන්න. පිල්ලම යෙදෙන්නේ කොතැනටද?",
        "worked": ("මුලින්ම ක අකුර ගනිමු.", "ඊළඟට ඇලපිල්ල යොදමු.", "බලන්න, දැන් කා සෑදුණා."),
        "guided": ("මුල් අකුර තෝරන්න.", "ඉල්ලා ඇති ස්වරයට ගැළපෙන පිල්ලම තෝරන්න.", "දැන් අකුරට යොදා බලන්න."),
        "recap": "මතක තියාගන්න 💡 පිල්ලම යෙදූ විට අකුරේ ස්වරය වෙනස් වෙනවා.",
    },
    "LENGTH-01": {
        "visual": "කෙටි සහ දික් රූප දෙක බලන්න. වෙනස පෙනෙන්නේ කොතැනද?",
        "worked": ("මුලින්ම කි බලමු.", "ඊළඟට දික් ඉස්පිල්ල යොදමු.", "බලන්න, දැන් කී සෑදුණා."),
        "guided": ("ඉල්ලා ඇති ස්වරය බලන්න.", "එය කෙටිද දික්ද තෝරන්න.", "ගැළපෙන පිල්ලම යොදන්න."),
        "recap": "මතක තියාගන්න 💡 කෙටි සහ දික් ස්වරවලට ගැළපෙන පිල්ලම් වෙනස් වෙනවා.",
    },
    "PAPILI-01": {
        "visual": "ල, ක, ර සමඟ ඇති පාපිලි බලන්න. ස්වරය එකම වුණත් හැඩය එකමද?",
        "worked": ("මුලින්ම ල අකුර බලමු.", "උ ස්වරයට ගැළපෙන කෙටි කොන් පාපිල්ල යොදමු.", "බලන්න, දැන් ලු සෑදුණා."),
        "guided": ("මුල් අකුර හඳුනාගන්න.", "කෙටිද දික්ද බලන්න.", "මේ අකුරට ගැළපෙන පාපිල්ල යොදන්න."),
        "recap": "මතක තියාගන්න 💡 ලු, කු, රු තුළ උ නියෝජනය වුණත් පාපිල්ලේ හැඩය වෙනස් වෙනවා.",
        "recap_long": "මතක තියාගන්න 💡 ලූ, කූ, රූ තුළ ඌ නියෝජනය වුණත් පාපිල්ලේ හැඩය වෙනස් වෙනවා.",
    },
    "COMPOUND-01": {
        "visual": "අකුරේ වමත් දකුණත් බලන්න. අවශ්‍ය කොටස් සියල්ල තිබෙනවාද?",
        "worked": ("මුලින්ම ක අකුර ගනිමු.", "ඊළඟට කොම්බුවත් ඇලපිල්ලත් යොදමු.", "බලන්න, දැන් කො සෑදුණා."),
        "guided": ("ඉල්ලා ඇති ස්වරය බලන්න.", "අවශ්‍ය කොටස් එකින් එක තෝරන්න.", "දැන් සෑදුණු අකුර පරීක්ෂා කරන්න."),
        "recap": "මතක තියාගන්න 💡 සංයුක්ත පිල්ලමක් හදන්න අවශ්‍ය කොටස් සියල්ල නිවැරදිව යොදන්න.",
    },
}
# Other compound subfamilies get their own reviewed-draft worked lines on the photographed ක.
_COMPOUND_WORKED = {
    "compound:row-13": ("ඊළඟට කොම්බුවත් හල් කිරීමේ ලකුණත් යොදමු.", "කේ"),
    "compound:row-14": ("ඊළඟට කොම්බුවත් ඇලපිල්ලත් යොදමු.", "කො"),
    "compound:row-15": ("ඊළඟට කොම්බුව, ඇලපිල්ල සහ හල් කිරීමේ ලකුණ යොදමු.", "කෝ"),
    "compound:row-16": ("ඊළඟට ගැටඇලපිල්ල යොදමු.", "කෘ"),
    "compound:row-17": ("ඊළඟට ගැටඇලපිලි දෙක යොදමු.", "කෲ"),
    "compound:row-18": ("ඊළඟට කොම්බු දෙක යොදමු.", "කෛ"),
    "compound:row-19": ("ඊළඟට කොම්බුවත් ගයනුකිත්තත් යොදමු.", "කෞ"),
}


def support_copy(skill_id: str, family: str) -> dict[str, object]:
    copy = dict(SUPPORT_COPY[skill_id.split("-", 3)[3]])
    if skill_id.endswith("COMPOUND-01") and family in _COMPOUND_WORKED:
        line, result = _COMPOUND_WORKED[family]
        copy["worked"] = ("මුලින්ම ක අකුර ගනිමු.", line, f"බලන්න, දැන් {result} සෑදුණා.")
    if skill_id.endswith("PAPILI-01") and family == "papili:long":
        copy["recap"] = copy["recap_long"]
    if skill_id.endswith("LENGTH-01"):
        short, long, short_row, long_row = LENGTH_FAMILIES[family.split(":")[1]]
        length = family.split(":")[2]
        demo_kind = long if length == "short" else short
        demo_row = long_row if length == "short" else short_row
        start = compose(KA, (short if length == "short" else long,))
        result = compose(KA, (demo_kind,))
        copy["worked"] = (
            f"මුලින්ම {start} බලමු.",
            f"ඊළඟට {row(demo_row)['printed_name_si']} යොදමු.",
            f"බලන්න, දැන් {result} සෑදුණා.",
        )
    copy.pop("recap_long", None)
    return copy


def worked_steps(game: Mapping[str, object], scaffold_type: str, skill_id: str) -> list[str]:
    copy = support_copy(skill_id, str(game["subfamily"]))
    if scaffold_type == "visual_guidance":
        return [str(copy["visual"])]
    if scaffold_type == "worked_parallel_example":
        return list(copy["worked"])  # type: ignore[arg-type]
    return list(copy["guided"])  # type: ignore[arg-type]


def package_hash() -> str:
    payload = {
        "area": AREA_ID,
        "version": PACKAGE_VERSION,
        "source_sha256": source_transcription()["source"]["sha256"],  # type: ignore[index]
        "skills": [skill.skill_id for skill in ATOMIC_SKILLS],
        "misconceptions": list(MISCONCEPTIONS),
        "scaffolds": list(SCAFFOLDS),
        "draft_bases": list(DRAFT_BASES),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# --- Shared Sinhala package interface -------------------------------------------------------

ResponseError = PillamResponseError
# Visual guidance enlarges the current sign; it never marks its answer.
VISUAL_EMPHASIS = "enlarge_current_sign"


def opening_demonstration(skill_id: str, family: str) -> dict[str, object] | None:
    """The fixed demonstration of one subfamily (every seed of it shares the same one)."""

    for seed in range(64):
        if episode_subfamily(skill_id, seed) == family:
            demo = demonstration(skill_id, seed)
            if "base_si" in demo and demo.get("shown_si") is None:
                return None
            return demo
    return None


def worked_display(game: Mapping[str, object]) -> dict[str, object]:
    """What a solved assisted example shows besides its card placement."""

    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    text = rubric.get("target_text_nfc")
    return {} if text is None else {"result_text_si": text}
