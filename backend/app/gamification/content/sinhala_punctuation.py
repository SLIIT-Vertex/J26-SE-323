"""Draft content and server scoring for G5-AREA-SIN-02 (විරාම ලක්ෂණ හඳුනාගනිමු).

Source: two textbook photographs (``IMG_7484.HEIC``, ``IMG_7485.heic``) of explanatory pages:
seven marks, their rules and one to three examples each. The pages hold no exercises, so every
interaction is a pedagogical adaptation, and the textbook examples serve only as unscored
demonstrations. Probe items are draft authored sentences (``authoring_status``) that need
Sinhala and educator review; none is presented as textbook content.

Measurement is unavailable where fresh equivalent probes cannot exist: an abbreviation has one
correct dotting whatever its carrier sentence, so ABBREV is practice only, and LINEBREAK has no
approved word-division rule, so its scored content is blocked.

A sentence is a list of tokens with opaque boundaries between them. A boundary never falls
inside a token, so a mark can never split an akshara, a pilla or a ZWJ conjunct.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

from app.gamification.content import sinhala_common as common
from app.gamification.content.sinhala_common import DONE_LINE, UNKNOWN, nfc
from app.gamification.content.sinhala_common import SinhalaResponseError as ResponseError

AREA_ID = "G5-AREA-SIN-02"
# Draft crosswalk to Sinhala writing conventions; not reviewed for this area.
UNIVERSAL_SKILL_ID = "LAN-WRT"
PACKAGE_VERSION = "g5-sin-punctuation-draft-v1"
CATALOGUE_VERSION = "g5-sin-punctuation-misconceptions-v1"
FEATURE_VERSION = "g5-sin-punctuation-features-v1"
MAPPING_VERSION = "g5-sin-punctuation-evidence-mapping-v1"
MODEL_VERSION = "g5-sin-punctuation-authored-probabilistic-v1"
POLICY_VERSION = "g5-sin-punctuation-raw-ig-shadow-v1"
SCORING_VERSION = "g5-sin-punctuation-scoring-v1"
EQUIVALENCE_VERSION = "g5-sin-punctuation-parallel-v1"
RESPONSE_SCHEMA_VERSION = "sinhala-punctuation-response-v1"
ITEM_SCHEMA_VERSION = "sinhala-punctuation-item-v1"
VISUAL_EMPHASIS = "outline_relevant_region"
SOURCE_LINKS = ("G5-SIN-C03-L01-K03", "G5-SIN-C04-L01-K03", "G5-SIN-C03-L01-O04", "G5-SIN-C04-L01-O02")

DATA_DIRECTORY = (
    Path(__file__).resolve().parents[4]
    / "data" / "gamification" / "grade5-sinhala-punctuation" / "v1"
)

Chapter = Literal["sentence_rail", "small_marks_workshop", "said_and_extra", "short_dash_path"]

MARKS = {
    "full_stop": (".", "තිත"),
    "question_mark": ("?", "ප්‍රශ්නාර්ථ ලකුණ"),
    "exclamation_mark": ("!", "විස්මයාදි ලකුණ"),
    "comma": (",", "කොමාව"),
    "open_quote": ("“", "ආරම්භක උඩු කොමාව"),
    "close_quote": ("”", "අවසාන උඩු කොමාව"),
    "open_paren": ("(", "ආරම්භක වරහන"),
    "close_paren": (")", "අවසාන වරහන"),
    # Printed as a short hyphen (U+002D); never modernised to an en dash.
    "short_dash": ("-", "කෙටි ඉර"),
}


@cache
def source_transcription() -> dict[str, object]:
    manifest = json.loads((DATA_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    raw = (DATA_DIRECTORY / "source-transcription.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["source-transcription.json"]:
        raise RuntimeError("SINHALA_PUNCTUATION_SOURCE_HASH_MISMATCH")
    return json.loads(raw)


def source_examples() -> list[dict[str, object]]:
    return [
        example
        for section in source_transcription()["sections"]  # type: ignore[union-attr]
        for rule in section["rules"]
        for example in rule["examples"]
    ]


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    activity_id: str
    name_si: str
    goal_si: str
    difficulty: str
    response_kind: Literal["sinhala_punctuation_placement", "sinhala_punctuation_span", "sinhala_linebreak"]
    source_locator: str
    prerequisites: tuple[str, ...]
    review_blocked: bool = False
    outcome_provenance: str = "provisional_internal_id_draft_trace"


def _locator(photo: str, section: int, rule: int) -> str:
    return f"{photo}#section-{section}/rule-{rule}"


P1, P2 = "IMG_7484.HEIC", "IMG_7485.heic"
ATOMIC_SKILLS = (
    AtomicSkill("G5-SIN-PUNC-END-01", "sentence_rail", "end_rail", "වාක්‍ය අවසානය",
                "අද අපි ප්‍රකාශ වාක්‍යයක් අවසන් කරන තිත යොදමු 🌟", "easy",
                "sinhala_punctuation_placement", _locator(P1, 1, 1), ()),
    AtomicSkill("G5-SIN-PUNC-QUESTION-01", "sentence_rail", "question_rail", "ප්‍රශ්න වාක්‍ය",
                "අද අපි ප්‍රශ්න වාක්‍යයක අගට ප්‍රශ්නාර්ථ ලකුණ යොදමු 🌟", "easy",
                "sinhala_punctuation_placement", _locator(P1, 2, 1), ("G5-SIN-PUNC-END-01",)),
    AtomicSkill("G5-SIN-PUNC-EXCLAIM-01", "sentence_rail", "exclaim_rail", "හැඟීම් වාක්‍ය",
                "අද අපි හැඟීමක් ප්‍රබලව පෙන්වන විට විස්මයාදි ලකුණ යොදමු 🌟", "medium",
                "sinhala_punctuation_placement", _locator(P2, 5, 1), ("G5-SIN-PUNC-END-01",)),
    AtomicSkill("G5-SIN-PUNC-INITIALS-01", "small_marks_workshop", "initials_nameplate", "මුලකුරු",
                "අද අපි නමක මුලකුරු පසු තිත යොදමු 🌟", "easy",
                "sinhala_punctuation_placement", _locator(P1, 1, 2), ()),
    AtomicSkill("G5-SIN-PUNC-ABBREV-01", "small_marks_workshop", "abbreviation_labels", "කෙටි නාම",
                "අද අපි කෙටි කර ලියන නම්වල තිත යොදමු 🌟", "medium",
                "sinhala_punctuation_placement", _locator(P1, 1, 3), ("G5-SIN-PUNC-INITIALS-01",)),
    AtomicSkill("G5-SIN-PUNC-COMMA-LIST-01", "small_marks_workshop", "list_strip", "ලැයිස්තු කොමාව",
                "අද අපි ලැයිස්තුවක නාම පද වෙන් කිරීමට කොමාව යොදමු 🌟", "medium",
                "sinhala_punctuation_placement", _locator(P1, 3, 1), ()),
    AtomicSkill("G5-SIN-PUNC-COMMA-PAUSE-01", "small_marks_workshop", "pause_strip", "විරාම කොමාව",
                "අද අපි වාක්‍යයක් තුළ විරාමයක් පෙන්වන කොමාව යොදමු 🌟", "medium",
                "sinhala_punctuation_placement", _locator(P1, 3, 2), ("G5-SIN-PUNC-COMMA-LIST-01",)),
    AtomicSkill("G5-SIN-PUNC-QUOTE-01", "said_and_extra", "quote_handles", "කියූ වචන",
                "අද අපි කෙනෙකු කියූ වචන යුගල උඩු කොමාවලින් වෙන් කරමු 🌟", "medium_hard",
                "sinhala_punctuation_span", _locator(P2, 4, 1), ("G5-SIN-PUNC-END-01",)),
    AtomicSkill("G5-SIN-PUNC-PAREN-01", "said_and_extra", "paren_handles", "අමතර තොරතුරු",
                "අද අපි අමතර තොරතුරු සරල වරහන් තුළ තබමු 🌟", "medium_hard",
                "sinhala_punctuation_span", _locator(P2, 6, 1), ("G5-SIN-PUNC-COMMA-LIST-01",)),
    AtomicSkill("G5-SIN-PUNC-RANGE-01", "short_dash_path", "range_cards", "පිටු පරාසය",
                "අද අපි පිටු අංක පරාසයක් පෙන්වීමට කෙටි ඉර යොදමු 🌟", "easy",
                "sinhala_punctuation_placement", _locator(P2, 7, 1), ()),
    AtomicSkill("G5-SIN-PUNC-LINEBREAK-01", "short_dash_path", "linebreak_board", "පේළි බෙදීම",
                "අද අපි පේළියක් අවසානයේ පදයක් බෙදා ලියන විට කෙටි ඉර යොදන හැටි බලමු 🌟", "hard",
                "sinhala_linebreak", _locator(P2, 7, 2), ("G5-SIN-PUNC-RANGE-01",), review_blocked=True),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}
LINEBREAK_SKILL = "G5-SIN-PUNC-LINEBREAK-01"

MISCONCEPTIONS = (
    "sentence_end_internal_dot_confusion",
    "question_declaration_confusion",
    "unsupported_exclamation_choice",
    "exclamation_context_missed",
    "missing_abbreviation_dots",
    "list_pause_comma_confusion",
    "quotation_boundary_confusion",
    "missing_or_reversed_paired_marks",
    "reporting_clause_inclusion",
    "parenthetical_span_confusion",
    "range_placement_confusion",
    "range_versus_subtraction_confusion",
    "invalid_word_division",
    UNKNOWN,
)


def misconception_catalogue() -> list[dict[str, object]]:
    def entry(code, evidence, counter, skills, locators, observable=True):
        return {
            "code": code,
            "catalogue_version": CATALOGUE_VERSION,
            "mapping_version": MAPPING_VERSION,
            "evidence_patterns": evidence,
            "counter_evidence": counter,
            "supported_skills": skills,
            "source_basis": locators,
            "eligible_support": list(common.SCAFFOLDS),
            "observable_in_current_mechanics": observable,
            "review_status": "draft_unreviewed",
        }

    return [
        entry("sentence_end_internal_dot_confusion", ["WRONG_BOUNDARY: a full stop inside the sentence", "MISSING_MARK on initials"],
              ["independent correct end placement"], ["G5-SIN-PUNC-END-01", "G5-SIN-PUNC-INITIALS-01"], [_locator(P1, 1, 1), _locator(P1, 1, 2)]),
        entry("question_declaration_confusion", ["WRONG_MARK: '.' on a question or '?' on a statement"],
              ["independent correct question and statement endings"], ["G5-SIN-PUNC-END-01", "G5-SIN-PUNC-QUESTION-01"], [_locator(P1, 2, 1)]),
        entry("unsupported_exclamation_choice", ["WRONG_MARK: '!' on a plain statement with no stated feeling"],
              ["independent '.' on plain statements"], ["G5-SIN-PUNC-END-01"], [_locator(P2, 5, 1)]),
        entry("exclamation_context_missed", ["WRONG_MARK: '.' or '?' where the reviewed context states a strong feeling"],
              ["independent '!' on contextualised items"], ["G5-SIN-PUNC-EXCLAIM-01"], [_locator(P2, 5, 1)]),
        entry("missing_abbreviation_dots", ["MISSING_MARK on an abbreviation or initials"],
              ["all dots placed independently"], ["G5-SIN-PUNC-ABBREV-01", "G5-SIN-PUNC-INITIALS-01"], [_locator(P1, 1, 3)]),
        entry("list_pause_comma_confusion", ["WRONG_BOUNDARY or EXTRA_MARK with commas"],
              ["independent list and pause commas"], ["G5-SIN-PUNC-COMMA-LIST-01", "G5-SIN-PUNC-COMMA-PAUSE-01"], [_locator(P1, 3, 1), _locator(P1, 3, 2)]),
        entry("quotation_boundary_confusion", ["WRONG_SPAN on a quotation"], ["independent correct span"],
              ["G5-SIN-PUNC-QUOTE-01"], [_locator(P2, 4, 1)]),
        entry("missing_or_reversed_paired_marks", ["REVERSED_PAIR", "WRONG_MARK on a paired mark"],
              ["independent correctly oriented pair"], ["G5-SIN-PUNC-QUOTE-01", "G5-SIN-PUNC-PAREN-01"], [_locator(P2, 4, 1), _locator(P2, 6, 1)]),
        entry("reporting_clause_inclusion", ["REPORTING_CLAUSE_ENCLOSED"], ["independent span excluding the reporting clause"],
              ["G5-SIN-PUNC-QUOTE-01"], [_locator(P2, 4, 1)]),
        entry("parenthetical_span_confusion", ["WRONG_SUPPLEMENTARY_SPAN"], ["independent correct bracket span"],
              ["G5-SIN-PUNC-PAREN-01"], [_locator(P2, 6, 1)]),
        entry("range_placement_confusion", ["INCORRECT_RANGE_PLACEMENT", "WRONG_MARK between endpoints"],
              ["independent correct range"], ["G5-SIN-PUNC-RANGE-01"], [_locator(P2, 7, 1)]),
        entry("range_versus_subtraction_confusion", ["not observable: the cards offer no arithmetic reading"], [],
              ["G5-SIN-PUNC-RANGE-01"], [_locator(P2, 7, 1)], observable=False),
        entry("invalid_word_division", ["INVALID_WORD_DIVISION", "BROKEN_GRAPHEME"], [],
              [LINEBREAK_SKILL], [_locator(P2, 7, 2)]),
        entry(UNKNOWN, ["no pattern above, sparse evidence, motor or wrapping difficulty, ambiguous item"], [],
              list(SKILLS), []),
    ]


# --- Item pools ------------------------------------------------------------------------------
# A pool row: tokens, the boundaries the child may use (indices 0..len), and the target.
# Placement targets: {boundary index: mark kind}. Span targets: (start, end, open, close).
# Every authored row is draft: "authoring_status" travels into the item for review.

@dataclass(frozen=True, slots=True)
class PoolRow:
    key: str
    tokens: tuple[str, ...]
    boundaries: tuple[int, ...]
    target: object
    context_si: str | None = None


def _row(key: str, tokens: Sequence[str], boundaries: Sequence[int], target: object, context: str | None = None) -> PoolRow:
    return PoolRow(key, tuple(nfc(t) for t in tokens), tuple(boundaries), target, None if context is None else nfc(context))


def _end(words: Sequence[str]) -> int:
    return len(words)


END_SENTENCES = (
    ("මල්ලී", "පාසලට", "ගියේ", "ය"),
    ("අක්කා", "පොතක්", "කියෙව්වා", "ය"),
    ("සීයා", "ගස්", "හිටෙව්වේ", "ය"),
    ("ළමයි", "පිට්ටනියේ", "සෙල්ලම්", "කළහ"),
    ("අපේ", "ගෙදර", "පූසෙක්", "ඉන්නවා"),
)
QUESTIONS_DA = (
    ("ඔයා", "පාසල්", "ගියා", "ද"),
    ("මල්ලී", "කෑම", "කෑවා", "ද"),
    ("අපි", "වෙරළට", "යනවා", "ද"),
    ("ඔබ", "පොත", "කියෙව්වා", "ද"),
)
QUESTIONS_OPEN = (
    ("කවුද", "දොරට", "තට්ටු", "කළේ"),
    ("ඔයාගේ", "නම", "මොකක්", "අනේ"),
    ("අපි", "කීයටද", "පිටත්", "වෙන්නේ"),
    ("පාර", "කොයි", "පැත්තෙන්ද", "තියෙන්නේ"),
)
EXCLAIM_CONTEXT = (
    ("නංගීට ලස්සන තෑග්ගක් ලැබුණා. ඇය සතුටින් කෑ ගැසුවා.", ("මට", "හරිම", "සතුටුයි")),
    ("ආච්චි මුණුබුරාට ආශීර්වාද කළා.", ("සුබ", "උපන්දිනයක්", "වේවා")),
    ("මල්ලීගේ සුරතල් පැටියා නැති වුණා. ඔහු දුකින් කීවා.", ("අනේ", "මගේ", "පැටියා")),
    ("රවී අහසේ දේදුන්නක් දැක පුදුම වුණා.", ("හරිම", "ලස්සන", "දේදුන්නක්")),
)
EXCLAIM_REPORTING = (
    ("ගුරුතුමිය චිත්‍රය දැක පුදුම වුණා.", ("අපූරුයි",), ("ගුරුතුමිය", "කීවා", "ය.")),
    ("අම්මා දැක්කේ වැටුණු කෝප්පයයි.", ("අපොයි",), ("අම්මා", "කීවා", "ය.")),
    ("තරගය දිනූ විට ළමයි සතුටු වුණා.", ("ජයවේවා",), ("ළමයි", "කෑ", "ගැසූහ.")),
    ("සීයා තෑග්ග දැක සතුටු වුණා.", ("නියමයි",), ("සීයා", "කීවේ", "ය.")),
)
INITIALS = (
    ("ජී", "කේ", "නිමාෂි", "සඳමාලි"),
    ("එස්", "පී", "රුවන්", "කුමාර"),
    ("ටී", "එම්", "දිල්ෂාන්", "පෙරේරා"),
    ("බී", "එන්", "කවින්දි", "සෙව්වන්දි"),
)
# The three photographed abbreviation families; carrier sentences are draft.
ABBREVIATIONS = {
    "lgm": (("ලං", "ග", "ම"), "(ලංකා ගමනාගමන මණ්ඩලය)", ("බසය", "පැමිණියා"), ("ඩිපෝව", "ළඟයි"), ("බස්", "රථයක්")),
    "pw": (("ප", "ව"), "(පස්වරු)", ("හතරට", "පාසල"), ("දෙකට", "රැස්වීම"), ("පහට", "පන්තිය")),
    "ru": (("රු",), "80/= (රුපියල් 80/=)", ("පොතේ", "මිල"), ("ටිකට්", "පතේ"), ("කෑමේ", "මිල")),
}
COMMA_LISTS = (
    ("පොල්", "කිතුල්", "පුවක්", "යන", "ගස්", "වත්තේ", "තිබේ"),
    ("පෑන", "පැන්සල", "මකනය", "යන", "දේ", "බෑගයේ", "තිබේ"),
    ("බළලා", "බල්ලා", "හාවා", "යන", "සතුන්", "ගෙදර", "ඉන්නවා"),
    ("රතු", "කොළ", "නිල්", "යන", "පාට", "චිත්‍රයේ", "තිබේ"),
)
COMMA_PAUSES = (
    ("ඔව්", "ඔව්", "මම", "හෙට", "එනවා"),
    ("හරි", "හරි", "අපි", "දැන්", "යමු"),
    ("එපා", "එපා", "ඒක", "හරිම", "උණුයි"),
    ("ඉන්න", "ඉන්න", "මමත්", "එනවා", "ගන්න"),
)
QUOTE_ONE = (
    ("අද", "වැස්ස", "වහියි", "අම්මා", "කීවා ය."),
    ("මම", "ඉක්මනට", "එන්නම්", "නංගී", "කීවා ය."),
    ("පොත", "මෙතන", "තියන්න", "ගුරුතුමිය", "කීවා ය."),
    ("අපි", "ගහක්", "හිටවමු", "අයියා", "කීවේ ය."),
)
QUOTE_TWO = (
    ("එන්න.", "අපි", "යමු.", "අක්කා", "කීවා ය."),
    ("ඉඳගන්න.", "තේ", "බොන්න.", "ආච්චි", "කීවා ය."),
    ("හරි.", "මම", "එනවා.", "යාළුවා", "කීවා ය."),
    ("බලන්න.", "අහසේ", "සඳ.", "නංගී", "කීවා ය."),
)
PAREN_LISTS = (
    ("අපේ වත්තේ", "ගස් තුනක්", "අඹ,", "කොස්,", "පොල්", "තිබේ."),
    ("චිත්‍රයට", "පාට තුනක්", "රතු,", "කහ,", "නිල්", "යෙදුවා."),
    ("අද", "විෂය තුනක්", "සිංහල,", "ගණිතය,", "විද්‍යාව", "ඉගෙනගත්තා."),
    ("ගෙදර", "සතුන් තුන් දෙනෙක්", "බළලා,", "බල්ලා,", "හාවා", "ඉන්නවා."),
)
RANGES = (
    ("අපේ ගම", "12", "18"),
    ("කුරුලු ලෝකය", "24", "31"),
    ("මල් උයන", "40", "46"),
    ("වැසි දිනය", "52", "57"),
)
IG_UNAVAILABLE_SKILLS = frozenset({"G5-SIN-PUNC-ABBREV-01", LINEBREAK_SKILL})


def subfamilies(skill_id: str) -> dict[str, dict[str, object]]:
    """Every subfamily of a skill: probe pool, fixed demo (a textbook example), card inventory."""

    every = lambda words: range(1, len(words) + 1)
    if skill_id.endswith("END-01"):
        return {
            "end:final": {
                "pool": [_row(f"s{i}", w, (len(w),), {len(w): "full_stop"}) for i, w in enumerate(END_SENTENCES)],
                "demo": "තාත්තා ගෙදර ආවේ ය.",
                "cards": ("full_stop", "question_mark", "exclamation_mark"),
            },
            "end:choose-boundary": {
                "pool": [_row(f"s{i}", w, every(w), {_end(w): "full_stop"}) for i, w in enumerate(END_SENTENCES)],
                "demo": "තාත්තා ගෙදර ආවේ ය.",
                "cards": ("full_stop", "question_mark", "exclamation_mark"),
            },
        }
    if skill_id.endswith("QUESTION-01"):
        return {
            f"question:{name}": {
                "pool": [_row(f"q{i}", w, (len(w),), {len(w): "question_mark"}) for i, w in enumerate(rows)],
                "demo": demo,
                "cards": ("question_mark", "full_stop", "exclamation_mark"),
            }
            for name, rows, demo in (("da", QUESTIONS_DA, "අපි ඊළඟට යන්නේ කොහේ ද?"), ("open", QUESTIONS_OPEN, "වයලීනය කොහෙද අනේ?"))
        }
    if skill_id.endswith("EXCLAIM-01"):
        return {
            "exclaim:context": {
                "pool": [_row(f"e{i}", w, (len(w),), {len(w): "exclamation_mark"}, c) for i, (c, w) in enumerate(EXCLAIM_CONTEXT)],
                "demo": "ඇයගේ කැපවීම පුදුමාකාර ය !",
                "cards": ("exclamation_mark", "full_stop", "question_mark"),
            },
            "exclaim:reporting": {
                "pool": [
                    _row(f"r{i}", (*u, *rest), range(1, len(u) + len(rest)), {len(u): "exclamation_mark"}, c)
                    for i, (c, u, rest) in enumerate(EXCLAIM_REPORTING)
                ],
                "demo": "ලංකාව ! ඔහු කී ය.",
                "cards": ("exclamation_mark", "full_stop", "question_mark"),
            },
        }
    if skill_id.endswith("INITIALS-01"):
        return {
            "initials:two": {
                "pool": [_row(f"n{i}", w, (1, 2, 3), {1: "full_stop", 2: "full_stop"}) for i, w in enumerate(INITIALS)],
                "demo": "කේ. එල්. මියුම් ආකර්ෂා",
                "cards": ("full_stop", "full_stop", "comma"),
            }
        }
    if skill_id.endswith("ABBREV-01"):
        result = {}
        for name, (units, expansion, *carriers) in ABBREVIATIONS.items():
            pool = []
            for index, carrier in enumerate(carriers):
                tokens = (*units, expansion, *carrier)
                pool.append(_row(f"{name}{index}", tokens, range(1, len(units) + 1),
                                 {position: "full_stop" for position in range(1, len(units) + 1)}))
            result[f"abbrev:{name}"] = {
                "pool": pool,
                "demo": {"lgm": "ලං.ග.ම. (ලංකා ගමනාගමන මණ්ඩලය)", "pw": "ප. ව. (පස්වරු)", "ru": "රු. 80/= (රුපියල් 80/=)"}[name],
                "cards": ("full_stop",) * len(units) + ("comma",),
            }
        return result
    if skill_id.endswith("COMMA-LIST-01"):
        return {
            "comma:list-three": {
                "pool": [_row(f"l{i}", w, (1, 2, 3), {1: "comma", 2: "comma"}) for i, w in enumerate(COMMA_LISTS)],
                "demo": "කජු, මාදන්, අඹ යන ආදී ගස්වලට වැඩි විශාල වෘක්ෂයන් නොවූව ද...",
                "cards": ("comma", "comma", "full_stop"),
            }
        }
    if skill_id.endswith("COMMA-PAUSE-01"):
        return {
            "comma:pause-repeat": {
                "pool": [_row(f"p{i}", w, (1, 2, 3), {2: "comma"}) for i, w in enumerate(COMMA_PAUSES)],
                "demo": "නැහැ නැහැ, ඊ මේල් කියන්නේ විද්‍යුත් තැපෑල",
                "cards": ("comma", "full_stop", "question_mark"),
            }
        }
    if skill_id.endswith("QUOTE-01"):
        return {
            f"quote:{name}": {
                "pool": [_row(f"{name}{i}", w, range(len(w) + 1), (0, 3, "open_quote", "close_quote")) for i, w in enumerate(rows)],
                "demo": demo,
                "cards": ("open_quote", "close_quote", "open_paren", "close_paren"),
            }
            for name, rows, demo in (
                ("one-sentence", QUOTE_ONE, "“අපට අද හොඳින් නැරඹිය හැකියි” ඔහු පිළිතුරු දුන්නේ ය."),
                ("two-sentence", QUOTE_TWO, "“අර දිග පුටුව කවිච්චිය. ඒක මං දන්නවා.” කවීෂා කීවා ය."),
            )
        }
    if skill_id.endswith("PAREN-01"):
        return {
            "paren:list": {
                "pool": [_row(f"b{i}", w, range(len(w) + 1), (2, 5, "open_paren", "close_paren")) for i, w in enumerate(PAREN_LISTS)],
                "demo": "බෞද්ධ කොඩිය වර්ණ පහකින් (නිල්, කහ, රතු, සුදු, තැඹිලි) සමන්විත වේ.",
                "cards": ("open_paren", "close_paren", "open_quote", "close_quote"),
            }
        }
    if skill_id.endswith("RANGE-01"):
        return {
            "range:page": {
                "pool": [_row(f"g{i}", w, (1, 2, 3), {2: "short_dash"}) for i, w in enumerate(RANGES)],
                "demo": "අසිරිමත් ලෝකය 75 - 79",
                "cards": ("short_dash", "comma", "full_stop"),
            }
        }
    if skill_id == LINEBREAK_SKILL:
        # No approved word-division rule or example exists: the gate is closed.
        return {}
    raise ValueError("SINHALA_PUNCTUATION_SKILL_NOT_FOUND")


@dataclass(frozen=True, slots=True)
class PunctuationItem:
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


def _require_open(skill_id: str) -> None:
    if skill_id not in SKILLS:
        raise ValueError("SINHALA_PUNCTUATION_SKILL_NOT_FOUND")
    if SKILLS[skill_id].review_blocked:
        raise ValueError("SINHALA_LINEBREAK_CONTENT_REVIEW_BLOCKED")


def episode_subfamily(skill_id: str, seed: int) -> str:
    _require_open(skill_id)
    names = sorted(subfamilies(skill_id))
    return names[common.digest(skill_id, "subfamily", seed) % len(names)]


def probe_rows(skill_id: str, seed: int) -> tuple[str, PoolRow, PoolRow]:
    family = episode_subfamily(skill_id, seed)
    pool = list(subfamilies(skill_id)[family]["pool"])  # type: ignore[arg-type]
    random.Random(common.digest(skill_id, family, "probes", seed)).shuffle(pool)
    return family, pool[0], pool[1]


def support_rows(skill_id: str, seed: int) -> list[PoolRow]:
    family, before, after = probe_rows(skill_id, seed)
    rest = [r for r in subfamilies(skill_id)[family]["pool"] if r.key not in {before.key, after.key}]  # type: ignore[union-attr]
    random.Random(common.digest(skill_id, family, "support", seed)).shuffle(rest)
    return rest


PROMPTS = {
    "END-01": "වාක්‍ය රේල් පාරේ අවසානයට ගැළපෙන ලකුණ යොදන්න.",
    "QUESTION-01": "මේ වාක්‍යයේ අගට ගැළපෙන ලකුණ යොදන්න.",
    "EXCLAIM-01": "සිද්ධිය කියවා, කියූ වචනවලට ගැළපෙන ලකුණ යොදන්න.",
    "INITIALS-01": "නාම පුවරුවේ නමට ගැළපෙන ලකුණු යොදන්න.",
    "ABBREV-01": "කෙටි කර ලියූ නාමයට ගැළපෙන ලකුණු යොදන්න.",
    "COMMA-LIST-01": "කියවීමේ තීරුවේ නාම පද වෙන් කරන්න.",
    "COMMA-PAUSE-01": "මේ කතාවේ විරාමයට ගැළපෙන ලකුණ යොදන්න.",
    "QUOTE-01": "කෙනෙකු කියූ වචනවල දෙපසට ගැළපෙන ලකුණු යොදන්න.",
    "PAREN-01": "අමතර තොරතුරු කොටසේ දෙපසට ගැළපෙන ලකුණු යොදන්න.",
    "RANGE-01": "පිටු අංක කාඩ්පතට ගැළපෙන ලකුණ යොදන්න.",
}


def build_item(skill_id: str, family: str, row: PoolRow, *, role: str, salt: str) -> PunctuationItem:
    skill = SKILLS[skill_id]
    spec = subfamilies(skill_id)[family]
    rng = random.Random(common.digest(salt, row.key))
    cards = [
        {
            "token_id": common.token("mark", f"{kind}:{index}", salt),
            "display_si": MARKS[kind][0],
            "accessible_label_si": MARKS[kind][1],
            "kind": kind,
        }
        for index, kind in enumerate(spec["cards"])  # type: ignore[union-attr]
    ]
    kind_by_token = {card["token_id"]: card.pop("kind") for card in cards}
    rng.shuffle(cards)
    boundaries = [
        {"boundary_id": common.token("gap", position, salt), "after_token_index": position - 1}
        for position in row.boundaries
    ]
    position_by_boundary = {b["boundary_id"]: position for b, position in zip(boundaries, row.boundaries, strict=True)}
    game: dict[str, object] = {
        "activity_id": skill.activity_id,
        "response_kind": skill.response_kind,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "subfamily": family,
        "goal_si": skill.goal_si,
        "source_locator": skill.source_locator,
        "authoring_status": "draft_authored_unreviewed",
        "tokens": [{"text_si": text} for text in row.tokens],
        "boundaries": boundaries,
        "mark_cards": cards,
    }
    if row.context_si:
        game["context_si"] = row.context_si
    if skill.response_kind == "sinhala_punctuation_span":
        start, end, open_kind, close_kind = row.target  # type: ignore[misc]
        reporting = list(range(end, len(row.tokens))) if skill_id.endswith("QUOTE-01") else []
        rubric = {"kind": "span", "start": start, "end": end, "open": open_kind, "close": close_kind, "reporting_tokens": reporting}
    else:
        rubric = {"kind": "placement", "targets": {str(k): v for k, v in row.target.items()}}  # type: ignore[union-attr]
    rubric.update(kind_by_token=kind_by_token, position_by_boundary=position_by_boundary)
    game["rubric"] = rubric
    game["equivalence"] = {
        "skill_id": skill_id,
        "subfamily": family,
        "response_kind": skill.response_kind,
        "token_count": len(row.tokens),
        "boundary_count": len(row.boundaries),
        "card_inventory": sorted(spec["cards"]),  # type: ignore[arg-type]
        "target_count": 2 if skill.response_kind == "sinhala_punctuation_span" else len(row.target),  # type: ignore[arg-type]
        "has_context": row.context_si is not None,
        "difficulty": skill.difficulty,
        "maximum_score": 1,
        "accepted_variants": "none_until_reviewed",
        "ig_available": skill_id not in IG_UNAVAILABLE_SKILLS,
    }
    fingerprint = hashlib.sha256(f"{family}:{row.key}:{salt}".encode()).hexdigest()[:12]
    suffix = {"unsupported_before": "B", "unsupported_after": "A"}.get(role, "S")
    return PunctuationItem(
        item_id=f"{skill_id}:{family}:{row.key}",
        revision_id=f"{skill_id}:{suffix}:{fingerprint}@v1",
        parallel_family_id=f"{skill_id}:{family}:parallel-v1",
        skill_id=skill_id,
        chapter=skill.chapter,
        measurement_role=role,
        prompt_si=PROMPTS[skill_id.split("-", 3)[3]],
        options=(),
        correct_option_id="constructed-response",
        error_codes={},
        game_data=game,
    )


def generate_item(skill_id: str, *, role: str, seed: int) -> PunctuationItem:
    if role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("INVALID_MEASUREMENT_ROLE")
    family, before, after = probe_rows(skill_id, seed)
    return build_item(skill_id, family, before if role == "unsupported_before" else after, role=role,
                      salt=f"{skill_id}:{role}:{seed}")


def generate_support_item(skill_id: str, *, seed: int, index: int) -> PunctuationItem:
    rows = support_rows(skill_id, seed)
    family = episode_subfamily(skill_id, seed)
    return build_item(skill_id, family, rows[index % len(rows)], role="supported_practice",
                      salt=f"{skill_id}:support:{seed}:{index}")


def opening_demonstration(skill_id: str, family: str) -> dict[str, object] | None:
    """A textbook example, shown unscored. It is never in a probe pool (pools are authored)."""

    spec = subfamilies(skill_id).get(family)
    if spec is None:
        return None
    text = nfc(str(spec["demo"]))
    example = next((e for e in source_examples() if e["display_nfc"] == text), None)
    if example is None:
        return None
    return {
        "demonstration_id": f"{skill_id}:{family}:demo@v1",
        "goal_si": SKILLS[skill_id].goal_si,
        "source_locators": [example["example_locator"]],
        "shown_si": text,
        "unscored": True,
    }


# --- Scoring ---------------------------------------------------------------------------------

_PLACEMENT_KEYS = {"kind", "schema_version", "placements"}
_SPAN_KEYS = {"kind", "schema_version", "opening_mark_token_id", "closing_mark_token_id", "start_boundary_id", "end_boundary_id"}
_LINEBREAK_KEYS = {"kind", "schema_version", "word_token_id", "break_boundary_id", "mark_token_id"}
SEMANTIC_TO_HYPOTHESIS = {
    "WRONG_MARK": None,  # refined per skill below
    "WRONG_BOUNDARY": None,
    "MISSING_MARK": None,
    "EXTRA_MARK": None,
    "REVERSED_PAIR": "missing_or_reversed_paired_marks",
    "REPORTING_CLAUSE_ENCLOSED": "reporting_clause_inclusion",
    "WRONG_SUPPLEMENTARY_SPAN": "parenthetical_span_confusion",
    "WRONG_QUOTATION_SPAN": "quotation_boundary_confusion",
    "INCORRECT_RANGE_PLACEMENT": "range_placement_confusion",
    "INVALID_WORD_DIVISION": "invalid_word_division",
    "BROKEN_GRAPHEME": "invalid_word_division",
}
_PLACEMENT_HYPOTHESIS = {
    "END-01": {"WRONG_MARK": "question_declaration_confusion", "WRONG_BOUNDARY": "sentence_end_internal_dot_confusion"},
    "QUESTION-01": {"WRONG_MARK": "question_declaration_confusion", "WRONG_BOUNDARY": "question_declaration_confusion"},
    "EXCLAIM-01": {"WRONG_MARK": "exclamation_context_missed", "WRONG_BOUNDARY": "exclamation_context_missed"},
    "INITIALS-01": {"MISSING_MARK": "missing_abbreviation_dots", "WRONG_BOUNDARY": "sentence_end_internal_dot_confusion"},
    "ABBREV-01": {"MISSING_MARK": "missing_abbreviation_dots", "WRONG_BOUNDARY": "missing_abbreviation_dots"},
    "COMMA-LIST-01": {"WRONG_BOUNDARY": "list_pause_comma_confusion", "MISSING_MARK": "list_pause_comma_confusion", "EXTRA_MARK": "list_pause_comma_confusion"},
    "COMMA-PAUSE-01": {"WRONG_BOUNDARY": "list_pause_comma_confusion", "EXTRA_MARK": "list_pause_comma_confusion"},
    "RANGE-01": {"WRONG_BOUNDARY": "range_placement_confusion", "WRONG_MARK": "range_placement_confusion"},
}


def _game(item: PunctuationItem | Mapping[str, object]) -> Mapping[str, object]:
    game = item.game_data if isinstance(item, PunctuationItem) else item.get("game_data")
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_SINHALA_PUNCTUATION_ITEM")
    return game


def validate_constructed_response(
    item: PunctuationItem | Mapping[str, object], response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = _game(item)
    skill_key = str(item.skill_id if isinstance(item, PunctuationItem) else item["skill_id"]).split("-", 3)[3]
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    kind = response.get("kind")
    if kind not in {"sinhala_punctuation_placement", "sinhala_punctuation_span", "sinhala_linebreak"}:
        raise ResponseError("MALFORMED_RESPONSE")
    if kind != game["response_kind"]:
        raise ResponseError("RESPONSE_KIND_MISMATCH")
    if response.get("schema_version") != RESPONSE_SCHEMA_VERSION:
        raise ResponseError("SCHEMA_MISMATCH")
    kinds = rubric["kind_by_token"]
    positions = rubric["position_by_boundary"]
    assert isinstance(kinds, Mapping) and isinstance(positions, Mapping)
    if kind == "sinhala_punctuation_placement":
        return _score_placement(skill_key, rubric, kinds, positions, response)
    return _score_span(skill_key, rubric, kinds, positions, response)


def _score_placement(skill_key, rubric, kinds, positions, response):
    if set(response) != _PLACEMENT_KEYS or not isinstance(response["placements"], list):
        raise ResponseError("MALFORMED_RESPONSE")
    placements = response["placements"]
    if not placements:
        raise ResponseError("INCOMPLETE_RESPONSE")
    if len(placements) > len(kinds):
        raise ResponseError("MALFORMED_RESPONSE")
    placed: dict[int, str] = {}
    used: set[str] = set()
    order = []
    for row in placements:
        if not isinstance(row, Mapping) or set(row) != {"mark_token_id", "boundary_id"}:
            raise ResponseError("MALFORMED_RESPONSE")
        mark, boundary = row["mark_token_id"], row["boundary_id"]
        if not isinstance(mark, str) or not isinstance(boundary, str):
            raise ResponseError("MALFORMED_RESPONSE")
        if mark not in kinds or boundary not in positions:
            raise ResponseError("UNKNOWN_TOKEN")
        position = int(positions[boundary])
        if mark in used or position in placed:
            raise ResponseError("DUPLICATE_TOKEN")
        used.add(mark)
        placed[position] = str(kinds[mark])
        order.append({"mark_token_id": mark, "boundary_id": boundary})
    targets = {int(k): v for k, v in rubric["targets"].items()}
    normalized = {"kind": "sinhala_punctuation_placement", "placements": order, "placement_order": [r["mark_token_id"] for r in order]}
    if placed == targets:
        normalized["semantic_error"] = None
        normalized["component_errors"] = []
        return True, "correct", normalized
    # Diagnostic component errors only; the score stays 0 (no unreviewed partial credit).
    errors = []
    for position, mark in targets.items():
        if position not in placed:
            errors.append("MISSING_MARK")
        elif placed[position] != mark:
            errors.append("WRONG_MARK")
    extra = [p for p in placed if p not in targets]
    if extra:
        errors.append("WRONG_BOUNDARY" if any(e == "MISSING_MARK" for e in errors) else "EXTRA_MARK")
        if "WRONG_BOUNDARY" in errors:
            errors.remove("MISSING_MARK")
    if skill_key == "RANGE-01" and ("WRONG_BOUNDARY" in errors or "WRONG_MARK" in errors):
        errors.insert(0, "INCORRECT_RANGE_PLACEMENT")
    semantic = errors[0]
    if skill_key == "END-01" and semantic == "WRONG_MARK" and placed.get(next(iter(targets))) == "exclamation_mark":
        hypothesis = "unsupported_exclamation_choice"
    else:
        hypothesis = SEMANTIC_TO_HYPOTHESIS.get(semantic) or _PLACEMENT_HYPOTHESIS.get(skill_key, {}).get(semantic, UNKNOWN)
    normalized.update(semantic_error=semantic, component_errors=errors)
    return False, hypothesis, normalized


def _score_span(skill_key, rubric, kinds, positions, response):
    if response.get("kind") == "sinhala_linebreak":
        raise ResponseError("SINHALA_LINEBREAK_CONTENT_REVIEW_BLOCKED")
    if set(response) != _SPAN_KEYS:
        raise ResponseError("MALFORMED_RESPONSE")
    ids = [response[k] for k in ("opening_mark_token_id", "closing_mark_token_id", "start_boundary_id", "end_boundary_id")]
    if not all(isinstance(v, str) and v for v in ids):
        raise ResponseError("INCOMPLETE_RESPONSE")
    open_id, close_id, start_id, end_id = ids
    if open_id not in kinds or close_id not in kinds or start_id not in positions or end_id not in positions:
        raise ResponseError("UNKNOWN_TOKEN")
    if open_id == close_id or start_id == end_id:
        raise ResponseError("DUPLICATE_TOKEN")
    start, end = int(positions[start_id]), int(positions[end_id])
    opening, closing = kinds[open_id], kinds[close_id]
    normalized = {
        "kind": "sinhala_punctuation_span",
        "opening_mark_token_id": open_id, "closing_mark_token_id": close_id,
        "start_boundary_id": start_id, "end_boundary_id": end_id,
    }
    if (start, end, opening, closing) == (rubric["start"], rubric["end"], rubric["open"], rubric["close"]):
        normalized.update(semantic_error=None, component_errors=[])
        return True, "correct", normalized
    errors = []
    if start > end or (opening, closing) == (rubric["close"], rubric["open"]):
        errors.append("REVERSED_PAIR")
    elif {opening, closing} != {rubric["open"], rubric["close"]}:
        errors.append("WRONG_MARK")
    if start != rubric["start"] or end != rubric["end"]:
        enclosed = set(range(min(start, end), max(start, end)))
        if rubric["reporting_tokens"] and enclosed & set(rubric["reporting_tokens"]):
            errors.append("REPORTING_CLAUSE_ENCLOSED")
        else:
            errors.append("WRONG_QUOTATION_SPAN" if skill_key == "QUOTE-01" else "WRONG_SUPPLEMENTARY_SPAN")
    semantic = errors[0]
    hypothesis = "missing_or_reversed_paired_marks" if semantic == "WRONG_MARK" else SEMANTIC_TO_HYPOTHESIS[semantic]
    normalized.update(semantic_error=semantic, component_errors=errors)
    return False, str(hypothesis), normalized


def validate_linebreak(
    word_graphemes: Sequence[str],
    approved_break_after: int | None,
    response_break_after: int,
) -> tuple[bool, str]:
    """The line-break mechanic, ready for reviewed content.

    Boundaries exist only between grapheme clusters, so a pilla or ZWJ conjunct is never split
    (``BROKEN_GRAPHEME`` is unreachable through the board). A grapheme boundary is still not a
    linguistically valid division: without an approved rule and example the content is blocked.
    """

    if approved_break_after is None:
        raise ResponseError("SINHALA_LINEBREAK_CONTENT_REVIEW_BLOCKED")
    if not 0 < response_break_after < len(word_graphemes):
        raise ResponseError("BROKEN_GRAPHEME")
    if response_break_after != approved_break_after:
        return False, "INVALID_WORD_DIVISION"
    return True, "correct"


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    kinds = dict(rubric["kind_by_token"])  # type: ignore[arg-type]
    by_position = {int(p): b for b, p in rubric["position_by_boundary"].items()}  # type: ignore[union-attr]
    if rubric["kind"] == "span":
        open_id = next(t for t, k in kinds.items() if k == rubric["open"])
        close_id = next(t for t, k in kinds.items() if k == rubric["close"])
        return {
            "kind": "sinhala_punctuation_span", "schema_version": RESPONSE_SCHEMA_VERSION,
            "opening_mark_token_id": open_id, "closing_mark_token_id": close_id,
            "start_boundary_id": by_position[int(rubric["start"])], "end_boundary_id": by_position[int(rubric["end"])],
        }
    placements = []
    free = dict(kinds)
    for position, mark in sorted(rubric["targets"].items()):  # type: ignore[union-attr]
        card = next(t for t, k in free.items() if k == mark)
        free.pop(card)
        placements.append({"mark_token_id": card, "boundary_id": by_position[int(position)]})
    return {"kind": "sinhala_punctuation_placement", "schema_version": RESPONSE_SCHEMA_VERSION, "placements": placements}


def rendered(game: Mapping[str, object]) -> str:
    """The sentence with its reviewed marks, for post-scoring feedback and worked examples."""

    rubric = game["rubric"]
    assert isinstance(rubric, Mapping)
    tokens = [str(t["text_si"]) for t in game["tokens"]]  # type: ignore[union-attr,index]
    if rubric["kind"] == "span":
        start, end = int(rubric["start"]), int(rubric["end"])
        tokens[start] = MARKS[str(rubric["open"])][0] + tokens[start]
        tokens[end - 1] = tokens[end - 1] + MARKS[str(rubric["close"])][0]
        return " ".join(tokens)
    for position, mark in rubric["targets"].items():  # type: ignore[union-attr]
        index = int(position) - 1
        tokens[index] = tokens[index] + MARKS[str(mark)][0]
    return " ".join(tokens)


HIDDEN_GAME_KEYS = frozenset({"rubric", "equivalence"})


def public_game_data(item: PunctuationItem) -> dict[str, object]:
    return {"chapter": item.chapter, **{k: v for k, v in item.game_data.items() if k not in HIDDEN_GAME_KEYS}}


def feedback_si(game: Mapping[str, object], correct: bool) -> str:
    if correct:
        return "හරි! ලකුණ නිවැරදි තැනට ආවා 🎉"
    return f"බලන්න: {rendered(game)} — රීතිය මතක තියාගමු."


def worked_display(game: Mapping[str, object]) -> dict[str, object]:
    return {"result_text_si": rendered(game)}


# --- Models ----------------------------------------------------------------------------------

def infer_belief(error_code: str, *, sparse: bool = False, interaction_summary: Mapping[str, object] | None = None) -> dict[str, object]:
    return common.infer_belief(error_code, MISCONCEPTIONS, catalogue_version=CATALOGUE_VERSION, sparse=sparse,
                               interaction_summary=interaction_summary)


_AFFINITY = {
    "visual_guidance": {"sentence_end_internal_dot_confusion", "range_placement_confusion", "parenthetical_span_confusion"},
    "worked_parallel_example": {"question_declaration_confusion", "exclamation_context_missed", "unsupported_exclamation_choice", "list_pause_comma_confusion"},
    "step_by_step_guidance": {"missing_abbreviation_dots", "missing_or_reversed_paired_marks", "reporting_clause_inclusion", "quotation_boundary_confusion"},
}


def scaffold_decision(skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int) -> dict[str, object]:
    return common.scaffold_decision(skill_id, condition, belief, seed=seed, policy_version=POLICY_VERSION, affinity=_AFFINITY)


# --- Support copy (draft, newly authored; not textbook language) ------------------------------

RULE_CARDS = {
    "END-01": ("සම්පූර්ණ අදහස අවසන් වන්නේ කොතැනද?", "ප්‍රකාශ වාක්‍යයක් අවසන් කිරීමට තිත යොදමු."),
    "QUESTION-01": ("මෙහි කෙනෙක් ප්‍රශ්නයක් අසනවාද?", "ප්‍රශ්න වාක්‍යයක අගට ප්‍රශ්නාර්ථ ලකුණ යොදමු."),
    "EXCLAIM-01": ("මෙහි පෙන්වන්නේ කුමන හැඟීමක්ද?", "විස්මය, ප්‍රාර්ථනාව, සතුට හෝ ශෝකය ප්‍රබලව පෙන්වන විට විස්මයාදි ලකුණ යොදමු."),
    "INITIALS-01": ("සම්පූර්ණ නම වෙනුවට මුලකුරු තිබෙන්නේ කොතැනද?", "නමක මුලකුරු පසු තිත යොදමු."),
    "ABBREV-01": ("කෙටි කර ලියූ කොටස් හඳුනාගන්න පුළුවන්ද?", "මේ කෙටි නාමයේ තිත් යෙදෙන තැන් මතක තියාගමු."),
    "COMMA-LIST-01": ("මෙහි වෙන් වෙන්ව කියවෙන නාම පද මොනවාද?", "ලැයිස්තුවේ නාම පද වෙන් කිරීමට කොමාව යොදමු."),
    "COMMA-PAUSE-01": ("අදහස තවම අවසන් නොවී විරාමයක් තිබෙන්නේ කොතැනද?", "මේ වාක්‍යයේ අතරමැදි විරාමය කොමාවෙන් පෙන්වමු."),
    "QUOTE-01": ("කෙනෙකු කියූ වචන කොතැනින් පටන්ගෙන කොතැනින් අවසන් වෙනවාද?", "කියූ වචනවල දෙපස යුගල උඩු කොමා යොදමු."),
    "PAREN-01": ("අමතර විස්තරය කුමන කොටසද?", "අමතර විස්තරයේ දෙපස සරල වරහන් යොදමු."),
    "RANGE-01": ("මුල් පිටු අංකයත් අවසාන පිටු අංකයත් කොතැනද?", "පිටු අංක පරාසයේ අංක දෙක අතර කෙටි ඉර යොදමු."),
    "LINEBREAK-01": ("පදයේ ඉතිරි කොටස ඊළඟ පේළියට යන්නේ කොතැනින්ද?", "අනුමත බෙදුම් තැන පමණක් භාවිත කරමු. අකුරක කොටස් වෙන් නොකරමු."),
}
_READ_FIRST = {
    "INITIALS-01": "මුලින්ම නාම පුවරුව කියවමු.",
    "ABBREV-01": "මුලින්ම කෙටි නාමයත් එහි සම්පූර්ණ නමත් කියවමු.",
    "COMMA-LIST-01": "මුලින්ම නාම පද ලැයිස්තුව කියවමු.",
    "RANGE-01": "මුලින්ම පොතේ නමත් පිටු අංකත් කියවමු.",
}


def support_copy(skill_id: str, family: str) -> dict[str, object]:
    del family
    key = skill_id.split("-", 3)[3]
    question, rule = RULE_CARDS[key]
    paired = key in {"QUOTE-01", "PAREN-01"}
    guided = ["පළමුව අදාළ කොටස තෝරන්න.", "දැන් ගැළපෙන ලකුණ තෝරන්න."]
    guided += ["දැන් ආරම්භක ලකුණ සුදුසු තැන තබන්න.", "දැන් අවසාන ලකුණ සුදුසු තැන තබන්න."] if paired else ["දැන් සුදුසු තැන තබන්න."]
    return {
        "visual": f"බලන්න, හොයාගන්න: {question}",
        "worked": (_READ_FIRST.get(key, "මුලින්ම වාක්‍යය කියවමු."), f"{question} {rule}", "ඊළඟට ලකුණ යොදමු.", "බලන්න, දැන් අදහස පැහැදිලියි."),
        "guided": tuple(guided),
        "recap": f"මතක තියාගන්න 💡 {rule}",
    }


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
        "sources": [p["sha256"] for p in source_transcription()["photographs"]],  # type: ignore[union-attr,index]
        "skills": list(SKILLS),
        "misconceptions": list(MISCONCEPTIONS),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


__all__ = ["DONE_LINE", "ResponseError"]
