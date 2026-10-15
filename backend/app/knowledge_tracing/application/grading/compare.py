"""Compares what a child wrote with the answer key. Pure: text in, decision out.

The principle: the code calls a part CORRECT only when it is sure, and WRONG only when the
reading is clearly different. Everything in between waits for the parent. A "wrong" that is not
really wrong is the most harmful error, because it feeds the mastery model.

Decision order for a part that has a text, number or choice key (first match wins):

   1  empty, blank, "-", "?" after normalising                      -> blank
   2  equal to an alternative after normalising                     -> correct   (exact)
   3  choice part: the same label written differently               -> correct   (choice-equivalent)
   4  choice part: two or more labels                               -> parent    (two_marks)
   5  choice part: words but no label                               -> parent    (choice_text_given)
   6  choice part: one different label                              -> wrong
   7  Roman numeral against an Arabic number (XVIII / 18)           -> parent    (roman_arabic)
   8  number part: numerically equal (6 = 06 = 6.0, 1/2 = 0.5 = ½)   -> correct   (numeric equal)
   9  number part: that one number plus words (6 more)              -> correct   (number found in text)
  10  ... but the words reverse it (6 less, not 6)                  -> parent    (negation_words)
  11  number part: a different number, or two or more numbers       -> wrong
  12  unit key (31 kg 400 g): same numbers, same units in any spelling -> correct (units equivalent)
  13  ... a unit is missing                                         -> parent    (unit_missing)
  14  ... a unit is not in the table and differs                    -> parent    (unit_unknown)
  15  ... a number differs, a value is missing, units are swapped   -> wrong
  16  text part: equal once spaces and punctuation are removed       -> correct   (loose)
  17  the key sits inside a longer answer                           -> parent    (extra_words)
  18  the same words in a different order                           -> parent    (word_order)
  19  two different Roman numerals                                  -> wrong
  20  long key (15+ characters) and similarity of 0.60 or more       -> wrong + parent (long_text_close)
  21  short key (4+ characters, no digits) and similarity 0.80+      -> wrong + parent (near_miss)
  22  anything else                                                 -> wrong

Rows 1, 2, 3 (with a bare label), 4, 6, 8 (plain), 9, 11, 16, 21 and 22 are the original rules;
the rest are the extended rules. The unit table and the list of reversing words are starter
lists: a Sinhala and a Tamil speaker should review and extend them.
"""

import re
import unicodedata
from decimal import InvalidOperation
from difflib import SequenceMatcher
from fractions import Fraction

from app.knowledge_tracing.application.grading.types import (
    GradingConfig,
    KeyPart,
    PartGrade,
    PartRead,
    PartStatus,
    ReviewReason,
)

_ZERO_WIDTH = re.compile("[\u200b‌‍⁠﻿]")
_DASHES = re.compile("[‐-―−]")  # hyphens, en/em dash, the minus sign
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_EDGE = " \t\r\n.,;:!?\"'“”‘’«»"

# A number: "1 1/2", "1/2", ".5", "0.50", "6".
_NUM_RE = re.compile(r"(\d+)\s+(\d+)\s*/\s*(\d+)|(\d+)\s*/\s*(\d+)|\d*\.\d+|\d+")
_CURRENCY = re.compile(
    r"(?<!\w)(?:rs\.?|රු\.?|රුපියල්"
    r"|රුපියල|ரூபாய்|ரூ\.?)"
    r"(?=\s|\d|$|[^\w])"
)
_BLANK_MARKS = {"blank", "none", "null", "n/a", "na", "-", "—", "?", "unreadable"}
_ROMAN_RE = re.compile(
    r"^(?=[ivxlcdm]{2,}$)m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$"
)
_WORD_SPLIT = re.compile(r"[^\s\d.,;:!?\"'()\[\]/\\+\-=×÷*]+")
_CHOICE_TOKEN = re.compile(r"(?<![a-z0-9])(iv|iii|ii|i|[1-4])(?![a-z0-9])")
_CHOICES = {"1", "2", "3", "4", "i", "ii", "iii", "iv"}
_CHOICE_VALUE = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}

# Words that reverse the meaning of a number ("6 less", "not 6"). STARTER LIST.
NEGATORS = {
    "not", "less", "fewer", "minus", "never", "without",
    "අඩු", "නැත", "නැහැ", "නෑ",
    "නොවේ", "නොවෙයි",
    "குறைவு", "குறைய",
    "இல்லை", "அல்ல",
}

# canonical unit -> spellings (compared with spaces and dots removed, lower case). STARTER TABLE.
UNIT_ALIASES: dict[str, list[str]] = {
    "kg": ["kg", "kilogram", "kilograms", "kilo", "කිලෝ",
           "කිලෝග්රෑම්",
           "කිලෝග්‍රෑම්",
           "කි.ග්‍රෑ",
           "கிலோ", "கிலோகிராம்"],
    "g": ["g", "gram", "grams", "ග්රෑම්",
          "ග්‍රෑම්", "ග්‍රෑ",
          "கிராம்"],
    "l": ["l", "litre", "litres", "liter", "liters", "ලීටර්",
          "ලිටර්", "ල්", "லிட்டர்"],
    "ml": ["ml", "millilitre", "milliliter", "මිලිලීටර්",
           "මිලි ලීටර්", "මි.ලි",
           "மில்லிலிட்டர்",
           "மில்லி லிட்டர்"],
    "km": ["km", "kilometre", "kilometer", "කිලෝමීටර්",
           "කි.මී", "கிலோமீட்டர்"],
    "m": ["m", "metre", "meter", "metres", "මීටර්", "මී",
          "மீட்டர்"],
    "cm": ["cm", "centimetre", "centimeter",
           "සෙන්ටිමීටර්",
           "සෙ.මී", "සෙමී",
           "சென்டிமீட்டர்"],
    "mm": ["mm", "millimetre", "millimeter",
           "මිලිමීටර්", "මි.මී",
           "மில்லிமீட்டர்"],
    "rs": ["rs", "rupee", "rupees", "රු", "රුපියල්",
           "රුපියල", "ரூ", "ரூபாய்"],
    "cent": ["cent", "cents", "ශත", "ශත්", "சதம்"],
    "min": ["min", "mins", "minute", "minutes", "මිනිත්තු",
            "මිනිත්තුව", "විනාඩි",
            "විනාඩිය", "நிமிடம்",
            "நிமிடங்கள்"],
    "h": ["h", "hr", "hrs", "hour", "hours", "පැය", "மணி",
          "மணித்தியாலம்"],
    "s": ["s", "sec", "secs", "second", "seconds", "තත්පර",
          "තත්පරය", "விநாடி",
          "விநாடி"],
}
_UNIT_LOOKUP = {
    re.sub(r"[\s.]", "", spelling).casefold(): name
    for name, spellings in UNIT_ALIASES.items()
    for spelling in spellings
}


# ---- normalising -----------------------------------------------------------------------------


def _strip_edges(text: str) -> str:
    """Remove edge punctuation and quotes, but keep a leading dot that starts a number (.5)."""
    start, end = 0, len(text)
    while start < end and text[start] in _EDGE:
        if text[start] == "." and start + 1 < end and text[start + 1].isdigit():
            break
        start += 1
    while end > start and text[end - 1] in _EDGE:
        end -= 1
    return text[start:end]


def _space_before_fractions(text: str) -> str:
    """"1½" must read as "1 1/2", not "11/2": put a space between a digit and a fraction sign."""
    out: list[str] = []
    for ch in text:
        if (
            out
            and out[-1].isdigit()
            and unicodedata.decomposition(ch).startswith("<fraction>")
        ):
            out.append(" ")
        out.append(ch)
    return "".join(out)


def norm(text: str | None) -> str:
    """Make two spellings of the same answer comparable (applied to key and reading alike).

    NFKC (a Unicode Roman numeral becomes plain letters, one-half becomes 1/2), zero-width
    characters removed, every kind of digit (Sinhala, Tamil, ...) turned into 0-9, dashes made
    alike, lower case, thousand separators removed, spaces collapsed, edge punctuation and quotes
    stripped (a leading dot before a digit is kept), one pair of brackets unwrapped.
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", _space_before_fractions(text)).replace("⁄", "/")
    s = _ZERO_WIDTH.sub("", s)
    s = "".join(
        str(unicodedata.digit(ch)) if unicodedata.category(ch) == "Nd" else ch for ch in s
    )
    s = _DASHES.sub("-", s).casefold()
    s = _THOUSANDS.sub("", s)
    s = _strip_edges(" ".join(s.split()))
    if s.startswith("(") and s.endswith(")") and s.count("(") == 1 and s.count(")") == 1:
        s = s[1:-1]
    return _strip_edges(s)


def loose(text: str | None) -> str:
    """The answer with every space and punctuation mark removed (letters and signs are kept)."""
    return "".join(
        ch for ch in norm(text) if unicodedata.category(ch)[0] not in "PZ" and not ch.isspace()
    )


# ---- small helpers ---------------------------------------------------------------------------


def _words(text: str) -> set[str]:
    """Words of a text. (Sinhala and Tamil vowel signs are not word characters, so a plain
    word regex would cut their words apart.)"""
    return set(_WORD_SPLIT.findall(text))


def _numbers(text: str) -> list[Fraction]:
    found: list[Fraction] = []
    for match in _NUM_RE.finditer(text):
        try:
            if match.group(1):
                found.append(int(match.group(1)) + Fraction(int(match.group(2)), int(match.group(3))))
            elif match.group(4):
                found.append(Fraction(int(match.group(4)), int(match.group(5))))
            else:
                found.append(Fraction(match.group(0)))
        except (ZeroDivisionError, ValueError, InvalidOperation):
            return []
    return found


def _strip_currency(text: str) -> str:
    """Remove currency markers (Rs., a rupee word, 50/=) so "Rs. 50" is read as the number 50."""
    cleaned = _CURRENCY.sub(" ", text).replace("/=", " ")
    return _strip_edges(re.sub(r"\s+", " ", cleaned))


def _is_plain_number(alternative: str) -> bool:
    return bool(_NUM_RE.fullmatch(_strip_currency(norm(alternative))))


def _unit_name(text: str) -> str | None:
    return _UNIT_LOOKUP.get(re.sub(r"[\s.]", "", text).casefold())


def _number_unit_pairs(text: str) -> list[tuple[Fraction, str]] | None:
    """'43 L 140 mL' -> [(43, 'l'), (140, 'ml')]; None if the text between numbers is not a unit."""
    s = norm(text)
    matches = list(_NUM_RE.finditer(s))
    if not matches:
        return None
    pairs: list[tuple[Fraction, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(s)
        unit = s[match.end() : end].strip(" .,;:")
        if unit and not all(
            ch.isalpha() or unicodedata.category(ch).startswith("M") or ch in " ." for ch in unit
        ):
            return None  # operators and the like: not a plain unit
        values = _numbers(match.group(0))
        if not values:
            return None
        pairs.append((values[0], unit.strip()))
    return pairs


def _roman_value(text: str) -> int | None:
    s = text.casefold()
    if not _ROMAN_RE.match(s) or s in _CHOICES:
        return None
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    for index, ch in enumerate(s):
        value = values[ch]
        total += -value if index + 1 < len(s) and values[s[index + 1]] > value else value
    return total


def _choice_value(label: str) -> str:
    return _CHOICE_VALUE.get(label, label)


# ---- building results ------------------------------------------------------------------------


def _grade(
    key: KeyPart,
    status: PartStatus,
    how: str,
    read: PartRead,
    *,
    review: ReviewReason | None = None,
) -> PartGrade:
    return PartGrade(
        part_no=key.part_no,
        status=status,
        how=how,
        needs_review=review is not None,
        review_reason=review,
        read_text=read.answer,
        confidence=read.confidence,
        instruction_met=read.instruction_met,
    )


def _flag(grade: PartGrade, reason: ReviewReason) -> PartGrade:
    return PartGrade(
        part_no=grade.part_no,
        status=grade.status,
        how=grade.how,
        needs_review=True,
        review_reason=reason,
        read_text=grade.read_text,
        confidence=grade.confidence,
        instruction_met=grade.instruction_met,
    )


# ---- the text, number and choice rules --------------------------------------------------------


def _compare_text(read: PartRead, key: KeyPart, config: GradingConfig) -> PartGrade:
    answer = norm(read.answer)
    if read.blank or not answer or answer in _BLANK_MARKS:
        return _grade(key, "blank", "empty", read)

    alternatives = [norm(a) for a in key.alternatives if norm(a)]

    # rows 2 .. 6: choice parts
    if answer in alternatives:
        return _grade(key, "correct", "exact", read)
    if key.kind == "choice":
        return _compare_choice(read, key, answer, alternatives)

    # row 7: the same value as a Roman numeral and as an Arabic number
    for alternative in alternatives:
        roman_answer, roman_key = _roman_value(answer), _roman_value(alternative)
        if (roman_key is not None and re.fullmatch(r"\d+", answer) and int(answer) == roman_key) or (
            roman_answer is not None and re.fullmatch(r"\d+", alternative) and int(alternative) == roman_answer
        ):
            return _grade(key, "ambiguous", "same value, other numeral system", read, review="roman_arabic")

    # rows 8 .. 11: number parts
    if key.kind == "number" and key.alternatives and all(_is_plain_number(a) for a in key.alternatives):
        return _compare_number(read, key, answer)

    # rows 12 .. 15: keys with units
    unit_result = _compare_units(read, key)
    if unit_result is not None:
        return unit_result

    # rows 16 .. 22: words
    return _compare_words(read, key, answer, alternatives, config)


def _compare_choice(read: PartRead, key: KeyPart, answer: str, alternatives: list[str]) -> PartGrade:
    wanted = {_choice_value(a) for a in alternatives}
    labels = {_choice_value(t) for t in _CHOICE_TOKEN.findall(answer)}
    if len(labels) > 1:
        return _grade(key, "ambiguous", f"labels {sorted(labels)}", read, review="two_marks")
    if len(labels) == 1:
        if labels & wanted:
            bare = answer in _CHOICES
            return _grade(key, "correct", "choice-equivalent" if bare else "choice in text", read)
        return _grade(key, "wrong", "different option", read)
    return _grade(key, "ambiguous", "text instead of a label", read, review="choice_text_given")


def _compare_number(read: PartRead, key: KeyPart, answer: str) -> PartGrade:
    wanted = {n for a in key.alternatives for n in _numbers(_strip_currency(norm(a)))}
    cleaned = _strip_currency(answer)
    found = _numbers(cleaned)
    if len(found) != 1:
        return _grade(key, "wrong", "not exactly one number", read)
    if found[0] not in wanted:
        return _grade(key, "wrong", "different number", read)
    words = _words(_NUM_RE.sub(" ", cleaned))
    if words & NEGATORS:
        return _grade(key, "ambiguous", "number with a reversing word", read, review="negation_words")
    return _grade(key, "correct", "number found in text" if words else "numeric equal", read)


def _compare_units(read: PartRead, key: KeyPart) -> PartGrade | None:
    """None when the key has no units, so another rule applies."""
    is_unit_key = False
    for alternative in key.alternatives:
        key_pairs = _number_unit_pairs(alternative)
        if not (key_pairs and all(unit for _, unit in key_pairs)):
            continue
        is_unit_key = True
        answer_pairs = _number_unit_pairs(read.answer)
        if not answer_pairs or len(answer_pairs) != len(key_pairs):
            return _grade(key, "wrong", "different number of values", read)
        flags: list[str] = []
        different = False
        for (key_value, key_unit), (value, unit) in zip(key_pairs, answer_pairs, strict=True):
            if key_value != value:
                different = True
                break
            if not unit:
                flags.append("unit_missing")
                continue
            key_name, name = _unit_name(key_unit), _unit_name(unit)
            if key_name and name:
                if key_name != name:
                    different = True
                    break
            elif re.sub(r"[\s.]", "", key_unit) != re.sub(r"[\s.]", "", unit):
                flags.append("unit_unknown")
        if different:
            continue  # try the next accepted spelling
        if flags:
            reason: ReviewReason = "unit_missing" if "unit_missing" in flags else "unit_unknown"
            return _grade(key, "ambiguous", "numbers match, unit not confirmed", read, review=reason)
        return _grade(key, "correct", "units equivalent", read)
    if is_unit_key:
        return _grade(key, "wrong", "numbers or units differ", read)
    return None


def _compare_words(
    read: PartRead, key: KeyPart, answer: str, alternatives: list[str], config: GradingConfig
) -> PartGrade:
    answer_loose = loose(read.answer)
    if answer_loose and answer_loose in {loose(a) for a in key.alternatives}:
        return _grade(key, "correct", "loose", read)

    best = 0.0
    longest = 0
    for alternative in alternatives:
        longest = max(longest, len(alternative))
        roman_key, roman_answer = _roman_value(alternative), _roman_value(answer)
        if roman_key is not None and roman_answer is not None and roman_key != roman_answer:
            return _grade(key, "wrong", "different numeral", read)
        key_words, answer_words = alternative.split(), answer.split()
        if (
            key_words
            and len(answer_words) > len(key_words)
            and re.search(rf"(?<!\S){re.escape(alternative)}(?!\S)", answer)
        ):
            return _grade(key, "ambiguous", "key inside a longer answer", read, review="extra_words")
        if (
            len(key_words) >= 2
            and sorted(key_words) == sorted(answer_words)
            and key_words != answer_words
        ):
            return _grade(key, "ambiguous", "same words, other order", read, review="word_order")
        if not re.search(r"\d", alternative) and alternative not in _CHOICES:
            best = max(best, SequenceMatcher(None, alternative, answer).ratio())

    if longest >= config.long_length and best >= config.near_long_ratio:
        return _grade(key, "wrong", f"similar {best:.2f}", read, review="long_text_close")
    if longest >= config.near_miss_min_length and best >= config.near_miss_ratio:
        return _grade(key, "wrong", "similar", read, review="near_miss")
    return _grade(key, "wrong", "different", read)


# ---- one part with all signals ---------------------------------------------------------------


def compare_part(
    read: PartRead,
    key: KeyPart,
    config: GradingConfig = GradingConfig(),  # noqa: B008
    *,
    second_agrees: bool | None = None,
) -> PartGrade:
    """Decide one part.

    `second_agrees` is None with one reader, True when a second reader gave the same reading and
    False when it did not.
    """
    has_text = bool(key.alternatives)
    has_instruction = key.instruction is not None

    if has_text:
        grade = _compare_text(read, key, config)
    elif has_instruction:
        grade = _grade(key, "ambiguous", "instruction", read)
    else:  # a key with neither an answer nor an instruction cannot be graded
        return _grade(key, "ambiguous", "no key", read, review="instruction_check")

    if has_instruction:
        grade = _apply_instruction(grade, read, key, has_text, config, second_agrees)

    # Two readers that read different things: keep the first reading, the parent decides.
    if second_agrees is False and has_text:
        return PartGrade(
            part_no=key.part_no,
            status="ambiguous",
            how="readers disagree",
            needs_review=True,
            review_reason="models_disagree",
            read_text=read.answer,
            confidence=read.confidence,
            instruction_met=read.instruction_met,
        )

    # An uncertain reading goes to the parent, whatever the rules decided.
    if not grade.needs_review and read.confidence < config.confidence_min:
        grade = _flag(grade, "low_confidence")
    return grade


def _apply_instruction(
    grade: PartGrade,
    read: PartRead,
    key: KeyPart,
    has_text: bool,
    config: GradingConfig,
    second_agrees: bool | None,
) -> PartGrade:
    """A part with a grader instruction ("colour three boxes") is judged from what the reader
    saw, and always checked by the parent unless the reader was confident and a second reader
    agreed."""
    met = read.instruction_met
    if has_text and grade.status in ("wrong", "ambiguous"):
        instruction_status: PartStatus = grade.status
    elif met is True:
        instruction_status = "correct"
    elif met is False:
        instruction_status = "blank" if read.blank and not has_text else "wrong"
    else:
        instruction_status = "blank" if read.blank and not has_text else "ambiguous"

    if has_text:
        # text and instruction must both pass
        if grade.status == "blank" and met is not True:
            status: PartStatus = "blank"
        elif grade.status == "correct" and instruction_status == "correct":
            status = "correct"
        elif grade.status == "correct" and met is None:
            status = "ambiguous"
        else:
            status = "wrong" if "wrong" in (grade.status, instruction_status) else grade.status
    else:
        status = instruction_status

    confident_and_agreed = read.confidence >= config.confidence_min and second_agrees is True
    review: ReviewReason | None = grade.review_reason
    if review is None and (not confident_and_agreed or status == "ambiguous") and status != "blank":
        review = "instruction_check"
    how = "instruction" if not has_text else f"{grade.how} + instruction"
    return PartGrade(
        part_no=key.part_no,
        status=status,
        how=how,
        needs_review=review is not None,
        review_reason=review,
        read_text=read.answer,
        confidence=read.confidence,
        instruction_met=met,
    )
