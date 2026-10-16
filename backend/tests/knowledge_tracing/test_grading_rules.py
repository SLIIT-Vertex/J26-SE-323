"""The answer-comparison rules, one row of the decision table at a time."""

import pytest

from app.knowledge_tracing.application.grading import (
    GradingConfig,
    KeyPart,
    PartRead,
    combine_parts,
    loose,
    norm,
)
from app.knowledge_tracing.application.grading import compare_part as _compare_part
from app.knowledge_tracing.application.grading.types import ReviewPolicy

# These tests check the rule table itself, where every doubt goes to the parent. The product
# default settles some doubts automatically (see test_review_policy.py).
STRICT = GradingConfig(review_policy=ReviewPolicy.strict())


def compare_part(read, key, config=STRICT, **kwargs):
    return _compare_part(read, key, config, **kwargs)

def read(
    answer: str = "",
    *,
    blank: bool = False,
    confidence: float = 0.95,
    met: bool | None = None,
) -> PartRead:
    return PartRead(part=1, answer=answer, blank=blank, confidence=confidence, instruction_met=met)


def text_key(*alternatives: str) -> KeyPart:
    return KeyPart(1, "text", alternatives)


def number_key(value: str) -> KeyPart:
    return KeyPart(1, "number", (value,))


def choice_key(correct: str, labels: tuple[str, ...] = ("1", "2", "3")) -> KeyPart:
    return KeyPart(1, "choice", (correct,), option_labels=labels)


def instruction_key(text: str = "colour three boxes") -> KeyPart:
    return KeyPart(1, "instruction", (), instruction=text)


# ---- normalisation ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Rabbit. ", "rabbit"),
        ("RABBIT", "rabbit"),
        ("80,004", "80004"),
        ("1,000,000", "1000000"),
        ("1, 2", "1, 2"),  # a comma with a space is not a thousand separator
        ("(iii)", "iii"),
        ("(ii).", "ii"),
        ("Ⅳ", "iv"),  # the Unicode Roman numeral IV
        ("෧෪", "14"),  # Sinhala digits
        ("௩௫", "35"),  # Tamil digits
        ("ನ", "ನ"),  # letters of other scripts are left alone
        ("“quoted”", "quoted"),
        ("a\u200bb", "ab"),  # zero-width space removed
        ("1572 − 645", "1572 - 645"),  # the minus sign becomes a hyphen
        ("", ""),
    ],
)
def test_norm(raw: str, expected: str) -> None:
    assert norm(raw) == expected


def test_norm_of_none_is_empty() -> None:
    assert norm(None) == ""


def test_zero_width_joiner_makes_no_difference_to_sinhala_words() -> None:
    with_zwj = "ක්‍රිඩා"  # a word written with ZWJ
    without = "ක්රිඩා"

    assert norm(with_zwj) == norm(without)


def test_loose_removes_spaces_and_punctuation_only() -> None:
    assert loose("31 kg, 400 g.") == loose("31kg 400g") == "31kg400g"
    assert loose("31 kg 40 g") != loose("31 kg 400 g")


# ---- row by row ------------------------------------------------------------------------------


def test_row1_blank_flag_or_empty_text_is_blank() -> None:
    assert compare_part(read(blank=True), text_key("cat")).status == "blank"
    assert compare_part(read("   "), text_key("cat")).status == "blank"
    assert compare_part(read("..."), text_key("cat")).status == "blank"


def test_blank_is_not_wrong() -> None:
    result = compare_part(read(blank=True), number_key("6"))

    assert result.status == "blank"
    assert not result.needs_review


def test_row3_exact_match_after_normalising() -> None:
    result = compare_part(read("  Cat. "), text_key("CAT"))

    assert (result.status, result.how) == ("correct", "exact")


def test_alternatives_are_tried_one_by_one() -> None:
    key = text_key("ආච්චි", "අත්තම්මා")

    assert compare_part(read("අත්තම්මා"), key).status == "correct"
    assert compare_part(read("ආච්චි"), key).status == "correct"
    assert compare_part(read("මාසි"), key).status == "wrong"


@pytest.mark.parametrize(
    ("key", "answer"),
    [("3", "iii"), ("iii", "3"), ("2", "(ii)"), ("II", "2"), ("4", "iv"), ("1", "I")],
)
def test_row4_choice_labels_that_mean_the_same(key: str, answer: str) -> None:
    result = compare_part(read(answer), choice_key(key, ("1", "2", "3", "4")))

    assert result.status == "correct"
    assert result.how in {"choice-equivalent", "exact"}


def test_row4_a_different_choice_is_wrong() -> None:
    result = compare_part(read("ii"), choice_key("3"))

    assert result.status == "wrong"
    assert not result.needs_review


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        ("6", "correct"),
        ("6 more", "correct"),
        ("6 ක් වැඩිය", "correct"),  # "6 more" in Sinhala
        ("පහ 6", "correct"),
        ("16 more", "wrong"),  # a different number
        ("6 and 3", "wrong"),  # two numbers: ambiguous, so not accepted
        ("60", "wrong"),
        ("six", "wrong"),
    ],
)
def test_row5_a_number_inside_the_words(answer: str, status: str) -> None:
    result = compare_part(read(answer), number_key("6"))

    assert result.status == status
    if status == "correct" and answer != "6":
        assert result.how == "number found in text"


def test_row5_does_not_apply_to_text_keys() -> None:
    """A text key is not a number part: the extra word is not accepted on its own, and the key
    inside a longer answer waits for the parent instead (extended rule 17)."""
    result = compare_part(read("6 more"), text_key("6"))

    assert result.status == "ambiguous"
    assert result.review_reason == "extra_words"


def test_row5_numbers_with_separators_and_sinhala_digits() -> None:
    assert compare_part(read("80,004"), number_key("80004")).status == "correct"
    assert compare_part(read("80004"), number_key("80,004")).status == "correct"
    assert compare_part(read("෮෦෦෦෪"), number_key("80004")).status == "correct"
    assert compare_part(read("6.0"), number_key("6")).status == "correct"


def test_row6_loose_match_on_spacing_and_punctuation() -> None:
    key = text_key("31 kg 400 g")

    assert compare_part(read("31kg 400g"), key).status == "correct"
    assert compare_part(read("31 kg, 400 g"), key).status == "correct"
    assert compare_part(read("31 kg 40 g"), key).status == "wrong"


def test_row7_a_near_miss_is_wrong_but_goes_to_the_parent() -> None:
    result = compare_part(read("rabite"), text_key("rabbit"))

    assert result.status == "wrong"
    assert result.how == "similar"
    assert result.needs_review
    assert result.review_reason == "near_miss"


def test_row7_short_words_and_numbers_are_not_near_misses() -> None:
    assert not compare_part(read("cot"), text_key("cat")).needs_review  # too short
    assert not compare_part(read("1572"), text_key("1573")).needs_review  # has digits
    assert not compare_part(read("rabbit"), text_key("elephant")).needs_review  # not close


def test_row8_anything_else_is_wrong() -> None:
    result = compare_part(read("dog"), text_key("elephant"))

    assert (result.status, result.how) == ("wrong", "different")
    assert not result.needs_review


# ---- uncertainty goes to the parent, never to "wrong" ------------------------------------------


def test_two_options_marked_on_a_choice_part_is_ambiguous() -> None:
    for answer in ("ii+iii", "2, 3", "ii and iii", "2/3", "ii iii"):
        result = compare_part(read(answer), choice_key("2"))
        assert result.status == "ambiguous", answer
        assert result.review_reason == "two_marks"


def test_a_low_confidence_reading_goes_to_the_parent_whatever_it_says() -> None:
    right = compare_part(read("cat", confidence=0.4), text_key("cat"))
    wrong = compare_part(read("dog", confidence=0.4), text_key("cat"))

    assert (right.status, right.review_reason) == ("correct", "low_confidence")
    assert (wrong.status, wrong.review_reason) == ("wrong", "low_confidence")


def test_the_confidence_threshold_is_configurable() -> None:
    strict = GradingConfig(confidence_min=0.95)

    assert compare_part(read("cat", confidence=0.9), text_key("cat"), strict).needs_review
    assert not compare_part(read("cat", confidence=0.9), text_key("cat")).needs_review


def test_a_blank_with_low_confidence_is_also_checked() -> None:
    result = compare_part(read(blank=True, confidence=0.3), text_key("cat"))

    assert result.status == "blank"
    assert result.review_reason == "low_confidence"


# ---- instruction parts ------------------------------------------------------------------------


def test_instruction_part_is_judged_from_what_was_seen_and_always_checked() -> None:
    done = compare_part(read("three boxes coloured", met=True), instruction_key())
    undone = compare_part(read("two boxes coloured", met=False), instruction_key())

    assert done.status == "correct"
    assert undone.status == "wrong"
    assert done.needs_review and undone.needs_review
    assert done.review_reason == "instruction_check"


def test_instruction_part_with_a_confident_second_reader_is_final() -> None:
    result = compare_part(
        read("coloured", met=True, confidence=0.9), instruction_key(), second_agrees=True
    )

    assert result.status == "correct"
    assert not result.needs_review


def test_instruction_part_stays_checked_when_the_second_reader_disagrees() -> None:
    result = compare_part(read("coloured", met=True), instruction_key(), second_agrees=False)

    assert result.needs_review


def test_instruction_part_with_nothing_there_is_blank() -> None:
    result = compare_part(read(blank=True, met=False), instruction_key())

    assert result.status == "blank"


def test_instruction_unknown_is_ambiguous() -> None:
    result = compare_part(read("unclear", met=None), instruction_key())

    assert result.status == "ambiguous"
    assert result.needs_review


def test_text_and_instruction_must_both_pass() -> None:
    key = KeyPart(1, "text", ("12",), instruction="also check the unit is written")

    both = compare_part(read("12", met=True), key, second_agrees=True)
    wrong_text = compare_part(read("13", met=True), key, second_agrees=True)
    no_unit = compare_part(read("12", met=False), key, second_agrees=True)

    assert both.status == "correct" and not both.needs_review
    assert wrong_text.status == "wrong"
    assert no_unit.status == "wrong"


def test_a_key_with_nothing_to_compare_is_never_graded() -> None:
    result = compare_part(read("x"), KeyPart(1, "text", ()))

    assert result.status == "ambiguous"
    assert result.needs_review


# ---- combining parts --------------------------------------------------------------------------


def grade(status: str, review: str | None = None, part_no: int = 1):
    from app.knowledge_tracing.application.grading import PartGrade

    return PartGrade(part_no, status, "x", review is not None, review, "", 0.9)  # type: ignore[arg-type]


def test_all_correct_is_correct() -> None:
    result = combine_parts([grade("correct", part_no=1), grade("correct", part_no=2)])

    assert (result.status, result.correct_parts, result.total_parts) == ("correct", 2, 2)


def test_one_wrong_part_makes_the_question_wrong_but_keeps_the_part_counts() -> None:
    result = combine_parts(
        [grade("correct", part_no=1), grade("wrong", part_no=2), grade("correct", part_no=3)]
    )

    assert result.status == "wrong"
    assert (result.correct_parts, result.total_parts) == (2, 3)


def test_all_blank_is_blank_but_some_blank_is_wrong() -> None:
    assert combine_parts([grade("blank", part_no=1), grade("blank", part_no=2)]).status == "blank"
    assert combine_parts([grade("correct", part_no=1), grade("blank", part_no=2)]).status == "wrong"


def test_a_part_waiting_for_the_parent_holds_the_whole_question() -> None:
    result = combine_parts(
        [grade("correct", part_no=1), grade("wrong", "near_miss", part_no=2)]
    )

    assert result.status == "pending_review"
    assert result.needs_review
    assert result.parts[0].status == "correct"  # the settled part keeps its automatic result


def test_parts_are_put_in_order() -> None:
    result = combine_parts([grade("correct", part_no=3), grade("correct", part_no=1)])

    assert [p.part_no for p in result.parts] == [1, 3]
