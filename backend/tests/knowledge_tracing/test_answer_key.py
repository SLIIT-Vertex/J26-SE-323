import pytest

from app.knowledge_tracing.application.answer_key import AnswerKeyError, parse_answer_key


def kinds(raw: str) -> list[tuple[str, tuple[str, ...]]]:
    return [(p.answer_kind, p.alternatives) for p in parse_answer_key(raw)]


def test_single_choice_digit() -> None:
    [part] = parse_answer_key("3")

    assert (part.part_type, part.answer_kind) == ("mcq", "choice")
    assert part.correct_option == "3"
    assert part.option_labels == ("1", "2", "3")


def test_choice_in_brackets_is_unwrapped() -> None:
    [part] = parse_answer_key("(iii)")

    assert part.correct_option == "iii"
    assert part.option_labels == ("i", "ii", "iii")
    assert part.alternatives == ("(iii)",)


def test_option_labels_widen_to_include_the_key() -> None:
    assert parse_answer_key("4")[0].option_labels == ("1", "2", "3", "4")
    assert parse_answer_key("iv")[0].option_labels == ("i", "ii", "iii", "iv")


def test_uppercase_roman_style_is_kept() -> None:
    [part] = parse_answer_key("II")

    assert part.option_labels == ("I", "II", "III")
    assert part.correct_option == "II"


def test_comma_with_space_makes_parts() -> None:
    parts = parse_answer_key("2, 3")

    assert [p.part_no for p in parts] == [1, 2]
    assert [p.alternatives for p in parts] == [("2",), ("3",)]


def test_thousand_comma_does_not_split() -> None:
    [part] = parse_answer_key("80,004")

    assert part.answer_kind == "number"
    assert part.alternatives == ("80,004",)


def test_comma_then_space_after_number_splits() -> None:
    assert [p.alternatives for p in parse_answer_key("1000, 90")] == [("1000",), ("90",)]


def test_slash_makes_alternatives_but_not_a_fraction() -> None:
    assert parse_answer_key("ආච්චි/අත්තම්මා")[0].alternatives == ("ආච්චි", "අත්තම්මා")
    [fraction] = parse_answer_key("1/2")
    assert fraction.alternatives == ("1/2",)
    assert fraction.answer_kind == "text"


def test_labels_are_removed_and_kept() -> None:
    parts = parse_answer_key("i.වාහන, ii. සෙල්ලම්")

    assert [p.label for p in parts] == ["i", "ii"]
    assert [p.alternatives for p in parts] == [("වාහන",), ("සෙල්ලම්",)]


def test_bracket_dot_label_and_numeric_label() -> None:
    parts = parse_answer_key("(i). first , (ii). second")
    assert [(p.label, p.alternatives) for p in parts] == [("i", ("first",)), ("ii", ("second",))]

    numbered = parse_answer_key("1.BUTTERFLY, 2.VEGETABLES")
    assert [(p.label, p.alternatives) for p in numbered] == [
        ("1", ("BUTTERFLY",)),
        ("2", ("VEGETABLES",)),
    ]


def test_a_decimal_is_not_a_label() -> None:
    [part] = parse_answer_key("3.5")

    assert part.label is None
    assert part.answer_kind == "number"


def test_instruction_only_part() -> None:
    [part] = parse_answer_key('"color three boxes"')

    assert part.answer_kind == "instruction"
    assert part.instruction == "color three boxes"
    assert part.alternatives == ()
    assert part.part_type == "short"


def test_answer_with_instruction() -> None:
    [part] = parse_answer_key('12 "also check the unit"')

    assert part.alternatives == ("12",)
    assert part.instruction == "also check the unit"
    assert part.answer_kind == "number"


def test_curly_quotes_are_ordinary_text() -> None:
    [part] = parse_answer_key("“අපි සෙල්ලම් කරමු” පවනි කීවා ය.")

    assert part.instruction is None
    assert part.answer_kind == "text"
    assert part.alternatives[0].startswith("“")


def test_escaped_comma_stays_in_one_answer() -> None:
    [part] = parse_answer_key(r"red\, green")

    assert part.alternatives == ("red, green",)


def test_comma_inside_quotes_does_not_split() -> None:
    [part] = parse_answer_key('"check a, b and c"')

    assert part.instruction == "check a, b and c"


def test_mixed_choice_and_text_parts() -> None:
    assert kinds("2, ගස") == [("choice", ("2",)), ("text", ("ගස",))]


def test_number_with_unit_is_text() -> None:
    assert parse_answer_key("31 kg 400 g")[0].answer_kind == "text"


def test_equation_parts() -> None:
    assert len(parse_answer_key("1572 − 645 = 927, 937 − 154 = 783")) == 2


@pytest.mark.parametrize("raw", ["", "   ", "a,, b", "a, ", '"unclosed', 'x "y'])
def test_bad_keys_are_rejected(raw: str) -> None:
    with pytest.raises(AnswerKeyError):
        parse_answer_key(raw)
