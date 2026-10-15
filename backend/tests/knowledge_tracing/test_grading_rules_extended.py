"""The extended comparison rules (rows 7 to 21 of the decision table), one behaviour at a time."""

import pytest

from app.knowledge_tracing.application.grading import KeyPart, PartRead, compare_part, norm
from app.knowledge_tracing.application.grading.compare import UNIT_ALIASES


def read(answer: str = "", *, blank: bool = False, confidence: float = 0.95) -> PartRead:
    return PartRead(part=1, answer=answer, blank=blank, confidence=confidence)


def text(*alternatives: str) -> KeyPart:
    return KeyPart(1, "text", alternatives)


def number(*alternatives: str) -> KeyPart:
    return KeyPart(1, "number", alternatives)


def choice(correct: str, labels: tuple[str, ...] = ("1", "2", "3", "4")) -> KeyPart:
    return KeyPart(1, "choice", (correct,), option_labels=labels)


def decide(answer: str, key: KeyPart, **kwargs):
    return compare_part(read(answer, **kwargs), key)


# ---- normalising ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (".5", ".5"),  # a leading dot before a digit is kept
        ("½", "1/2"),  # one-half
        ("Rs. 50", "rs. 50"),
        ("1 ½", "1 1/2"),
        ("50.", "50"),
    ],
)
def test_norm_keeps_what_numbers_need(raw: str, expected: str) -> None:
    assert norm(raw) == expected


# ---- blanks -----------------------------------------------------------------------------------


@pytest.mark.parametrize("mark", ["-", "—", "?", "none", "N/A", "unreadable", "blank"])
def test_a_dash_or_a_question_mark_is_a_blank(mark: str) -> None:
    result = decide(mark, text("cat"))

    assert result.status == "blank"
    assert not result.needs_review


# ---- choice parts -----------------------------------------------------------------------------


def test_a_label_with_words_around_it_is_correct() -> None:
    result = decide("2 වන", choice("ii"))  # "2 වන" (the 2nd)

    assert (result.status, result.how) == ("correct", "choice in text")
    assert not result.needs_review


def test_words_instead_of_a_label_go_to_the_parent() -> None:
    result = decide("the bus", choice("2"))

    assert result.status == "ambiguous"
    assert result.review_reason == "choice_text_given"


def test_one_different_label_in_words_is_wrong() -> None:
    result = decide("option 3 I think", choice("2"))

    assert result.review_reason == "two_marks"  # "I" and "3": two labels, so the parent decides


def test_a_single_different_label_is_wrong() -> None:
    result = decide("(iii)", choice("2"))

    assert result.status == "wrong"
    assert not result.needs_review


# ---- Roman against Arabic ---------------------------------------------------------------------


@pytest.mark.parametrize(("key", "answer"), [("XVIII", "18"), ("18", "XVIII"), ("xiv", "14")])
def test_roman_and_arabic_of_the_same_value_go_to_the_parent(key: str, answer: str) -> None:
    result = decide(answer, text(key))

    assert result.status == "ambiguous"
    assert result.review_reason == "roman_arabic"


def test_two_different_roman_numerals_are_wrong() -> None:
    result = decide("XVII", text("XVIII"))

    assert result.status == "wrong"
    assert not result.needs_review


def test_the_owner_can_accept_both_forms_as_alternatives() -> None:
    key = text("XVIII", "18")

    assert decide("18", key).status == "correct"
    assert decide("XVIII", key).status == "correct"


# ---- numbers ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "answer"),
    [
        ("6", "06"),
        ("6", "6.0"),
        ("0.5", ".5"),
        ("0.5", "0.50"),
        ("0.5", "1/2"),
        ("0.5", "½"),
        ("1.5", "1 1/2"),
        ("1.5", "1½"),
        ("50", "Rs. 50"),
        ("50", "රු. 50"),  # රු. 50
        ("50", "50/="),
        ("50", "Rs.50"),
        ("80,004", "80004"),
    ],
)
def test_numbers_equal_in_value_are_correct(key: str, answer: str) -> None:
    result = decide(answer, number(key))

    assert result.status == "correct", (key, answer, result.how)
    assert not result.needs_review


@pytest.mark.parametrize("answer", ["6 less", "not 6", "6 අඩු", "6 minus"])
def test_a_number_with_a_reversing_word_goes_to_the_parent(answer: str) -> None:
    result = decide(answer, number("6"))

    assert result.status == "ambiguous"
    assert result.review_reason == "negation_words"


@pytest.mark.parametrize(("answer", "how"), [("16 more", "different number"), ("6 and 3", "not exactly one number")])
def test_a_different_or_a_second_number_is_wrong(answer: str, how: str) -> None:
    result = decide(answer, number("6"))

    assert (result.status, result.how) == ("wrong", how)
    assert not result.needs_review


def test_a_number_with_words_in_sinhala_is_correct() -> None:
    result = decide("6 ක් වැඩිය", number("6"))  # 6 ක් වැඩිය

    assert (result.status, result.how) == ("correct", "number found in text")


# ---- units ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "31 kg 400 g",
        "31kg 400g",
        "31 KG 400 G",
        "31 kilograms 400 grams",
        "31 කිලෝ 400 ග්‍රෑම්",  # 31 කිලෝ 400 ග්‍රෑම්
        "31 kg, 400 g",
    ],
)
def test_the_same_values_and_units_in_any_spelling_are_correct(answer: str) -> None:
    result = decide(answer, text("31 kg 400 g"))

    assert result.status == "correct", (answer, result.how)
    assert not result.needs_review


def test_a_unit_that_is_missing_goes_to_the_parent() -> None:
    result = decide("43 140", text("43 L 140 mL"))

    assert result.status == "ambiguous"
    assert result.review_reason == "unit_missing"


def test_an_unknown_unit_that_differs_goes_to_the_parent() -> None:
    result = decide("43 L 140 xyz", text("43 L 140 mL"))

    assert result.status == "ambiguous"
    assert result.review_reason == "unit_unknown"


@pytest.mark.parametrize("answer", ["31 kg 40 g", "31 g 400 kg", "30 kg 400 g", "31 kg"])
def test_a_wrong_number_swapped_units_or_a_missing_value_are_wrong(answer: str) -> None:
    result = decide(answer, text("31 kg 400 g"))

    assert result.status == "wrong", (answer, result.how)
    assert not result.needs_review


def test_a_unit_key_with_two_accepted_spellings() -> None:
    key = text("31 kg 400 g", "31.4 kg")

    assert decide("31 kg 400 g", key).status == "correct"
    assert decide("31.4 kg", key).status == "correct"
    assert decide("31.5 kg", key).status == "wrong"


def test_every_unit_has_a_canonical_name_and_no_spelling_is_shared() -> None:
    seen: dict[str, str] = {}
    for name, spellings in UNIT_ALIASES.items():
        for spelling in spellings:
            key = spelling.replace(" ", "").replace(".", "").casefold()
            assert seen.get(key, name) == name, f"{spelling!r} is listed for {seen[key]} and {name}"
            seen[key] = name


# ---- words ------------------------------------------------------------------------------------


def test_a_key_inside_a_longer_answer_goes_to_the_parent() -> None:
    result = decide("වාහන ය", text("වාහන"))  # වාහන ය

    assert result.status == "ambiguous"
    assert result.review_reason == "extra_words"


def test_the_same_words_in_another_order_go_to_the_parent() -> None:
    result = decide("big red ball", text("red big ball"))

    assert result.status == "ambiguous"
    assert result.review_reason == "word_order"


def test_a_spacing_difference_inside_sinhala_words_is_loose_correct() -> None:
    result = decide("ගිනිමැල", text("ගිනි මැල"))

    assert (result.status, result.how) == ("correct", "loose")  # ගිනිමැල = ගිනි මැල


def test_a_long_answer_that_is_close_waits_for_the_parent() -> None:
    key = text("the quick brown fox jumps over")  # 30 characters
    result = decide("the quick brown fox jumpd ovr", key)

    assert result.status == "wrong"
    assert result.needs_review
    assert result.review_reason == "long_text_close"


def test_a_long_answer_that_is_far_off_is_wrong_and_final() -> None:
    result = decide("completely different sentence here", text("the quick brown fox jumps over"))

    assert result.status == "wrong"
    assert not result.needs_review


def test_short_keys_use_the_near_miss_rule_and_very_short_ones_do_not() -> None:
    assert decide("rabite", text("RABBIT")).review_reason == "near_miss"
    assert not decide("dag", text("dog")).needs_review


# ---- signals around the text ------------------------------------------------------------------


def test_a_second_reader_that_disagrees_makes_a_text_part_ambiguous() -> None:
    result = compare_part(read("cat"), text("cat"), second_agrees=False)

    assert result.status == "ambiguous"
    assert result.review_reason == "models_disagree"
    assert result.read_text == "cat"  # the first reading is what the parent sees


def test_a_second_reader_that_agrees_changes_nothing() -> None:
    result = compare_part(read("cat"), text("cat"), second_agrees=True)

    assert result.status == "correct"
    assert not result.needs_review


def test_the_confidence_floor_is_sixty_percent() -> None:
    assert decide("cat", text("cat"), confidence=0.59).review_reason == "low_confidence"
    assert not decide("cat", text("cat"), confidence=0.60).needs_review
    assert not decide("cat", text("cat"), confidence=0.65).needs_review
