"""The product default: the parent only sees what the reader could not make sense of.

Rule-level doubts (a near miss, an extra word, a missing unit ...) are settled automatically.
A reading the reader was unsure about, or could not make, always goes to the parent.
"""

import pytest

from app.knowledge_tracing.application.grading import (
    GradingConfig,
    ItemRead,
    KeyPart,
    PartRead,
    compare_part,
    grade_item,
)
from app.knowledge_tracing.application.grading.types import ReviewPolicy, VisionError
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading


def read(answer: str = "", *, blank: bool = False, confidence: float = 0.95, met: bool | None = None):
    return PartRead(part=1, answer=answer, blank=blank, confidence=confidence, instruction_met=met)


def text(*alts: str) -> KeyPart:
    return KeyPart(1, "text", alts)


def number(value: str) -> KeyPart:
    return KeyPart(1, "number", (value,))


def choice(correct: str) -> KeyPart:
    return KeyPart(1, "choice", (correct,), option_labels=("1", "2", "3", "4"))


# ---- rule-level doubts are settled without the parent -----------------------------------------


@pytest.mark.parametrize(
    ("answer", "key", "status"),
    [
        ("rabite", text("rabbit"), "wrong"),  # near miss: a spelling slip
        ("the quick brown fox jumpd ovr", text("the quick brown fox jumps over"), "wrong"),
        ("the cat", text("cat"), "correct"),  # the key is there with more words
        ("big red ball", text("red big ball"), "wrong"),  # same words, other order
        ("18", text("XVIII"), "wrong"),  # the key asks for the Roman numeral
        ("43 140", text("43 L 140 mL"), "correct"),  # numbers right, unit missing
        ("43 L 140 xyz", text("43 L 140 mL"), "correct"),  # numbers right, unusual unit
        ("6 less", number("6"), "wrong"),  # reverses the number
    ],
)
def test_a_rule_level_doubt_is_decided_without_the_parent(answer: str, key: KeyPart, status: str) -> None:
    result = compare_part(read(answer), key)

    assert result.status == status
    assert not result.needs_review
    assert result.review_reason is None
    assert "settled as" in result.how  # the audit trail says it was a policy decision


def test_the_same_doubts_all_go_to_the_parent_under_the_strict_policy() -> None:
    strict = GradingConfig(review_policy=ReviewPolicy.strict())
    cases = [
        ("rabite", text("rabbit")),
        ("the cat", text("cat")),
        ("big red ball", text("red big ball")),
        ("18", text("XVIII")),
        ("43 140", text("43 L 140 mL")),
        ("6 less", number("6")),
    ]

    for answer, key in cases:
        assert compare_part(read(answer), key, strict).needs_review, answer


def test_a_single_reason_can_be_put_back_to_review() -> None:
    policy = ReviewPolicy(actions={**ReviewPolicy.reader_unsure().actions, "near_miss": "review"})

    result = compare_part(read("rabite"), text("rabbit"), GradingConfig(review_policy=policy))

    assert result.needs_review
    assert result.review_reason == "near_miss"


# ---- when the reader is unsure, the parent decides --------------------------------------------


def test_a_low_confidence_reading_always_goes_to_the_parent() -> None:
    for answer, key in [("cat", text("cat")), ("dog", text("cat")), ("rabite", text("rabbit"))]:
        result = compare_part(read(answer, confidence=0.4), key)
        assert result.needs_review, answer
        assert result.review_reason == "low_confidence"


def test_the_reader_not_being_sure_beats_a_settled_doubt() -> None:
    sure = compare_part(read("rabite", confidence=0.9), text("rabbit"))
    unsure = compare_part(read("rabite", confidence=0.5), text("rabbit"))

    assert not sure.needs_review and sure.status == "wrong"
    assert unsure.needs_review and unsure.review_reason == "low_confidence"


def test_two_marks_and_text_instead_of_a_label_still_go_to_the_parent() -> None:
    assert compare_part(read("ii+iii"), choice("2")).review_reason == "two_marks"
    assert compare_part(read("the bus"), choice("2")).review_reason == "choice_text_given"


def test_readers_that_disagree_go_to_the_parent() -> None:
    result = compare_part(read("cat"), text("cat"), second_agrees=False)

    assert result.needs_review
    assert result.review_reason == "models_disagree"


# ---- instruction parts ------------------------------------------------------------------------


def instruction() -> KeyPart:
    return KeyPart(1, "instruction", (), instruction="check the boxes are coloured")


def test_a_confident_instruction_reading_is_accepted_without_a_second_reader() -> None:
    done = compare_part(read("coloured", met=True), instruction())
    undone = compare_part(read("not coloured", met=False), instruction())

    assert (done.status, done.needs_review) == ("correct", False)
    assert (undone.status, undone.needs_review) == ("wrong", False)


def test_an_instruction_the_reader_could_not_judge_goes_to_the_parent() -> None:
    result = compare_part(read("hard to see", met=None), instruction())

    assert result.needs_review
    assert result.review_reason == "instruction_check"


def test_an_unsure_instruction_reading_goes_to_the_parent() -> None:
    result = compare_part(read("coloured", met=True, confidence=0.3), instruction())

    assert result.needs_review


def test_the_strict_policy_wants_a_second_reader_for_instructions() -> None:
    strict = GradingConfig(review_policy=ReviewPolicy.strict())

    alone = compare_part(read("coloured", met=True), instruction(), strict)
    agreed = compare_part(read("coloured", met=True), instruction(), strict, second_agrees=True)

    assert alone.needs_review
    assert not agreed.needs_review


# ---- a whole page --------------------------------------------------------------------------------


def test_a_realistic_page_sends_the_parent_only_what_the_reader_could_not_read() -> None:
    """Ten questions, with the usual messy mix of child answers."""
    cases = [
        (KeyPart(1, "choice", ("2",), option_labels=("1", "2", "3")), reading("ii")),
        (KeyPart(1, "choice", ("3",), option_labels=("1", "2", "3")), reading("1")),  # wrong
        (KeyPart(1, "number", ("80,004",)), reading("80004")),
        (KeyPart(1, "number", ("6",)), reading("6 more")),
        (KeyPart(1, "text", ("rabbit",)), reading("rabite")),  # a spelling slip
        (KeyPart(1, "text", ("cat",)), reading("the cat")),
        (KeyPart(1, "text", ("31 kg 400 g",)), reading("31kg 400g")),
        (KeyPart(1, "text", ("dog",)), reading(None)),  # left blank
        (KeyPart(1, "text", ("sun",)), reading(("sun", 0.3))),  # the reader was unsure
        (KeyPart(1, "choice", ("1",), option_labels=("1", "2", "3")), reading("1 and 2")),
    ]

    graded = [grade_item([key], MockProvider(read_), b"x", "si") for key, read_ in cases]
    statuses = [g.question.status for g in graded]
    sent = [i for i, g in enumerate(graded) if g.question.needs_review]

    assert statuses == [
        "correct", "wrong", "correct", "correct", "wrong", "correct", "correct", "blank",
        "pending_review", "pending_review",
    ]
    assert sent == [8, 9]  # only the unsure reading and the double mark


def test_a_failed_reader_never_becomes_a_decision() -> None:
    result = grade_item([text("cat")], MockProvider(VisionError("rate_limit")), b"x", "si")

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "vision_error"


def test_a_wrong_number_of_readings_goes_to_the_parent() -> None:
    two = reading("a", "b")

    result = grade_item([text("a"), text("b"), text("c")], MockProvider(two), b"x", "si")

    assert {p.review_reason for p in result.question.parts} == {"part_count_mismatch"}


def test_the_default_config_uses_the_reader_unsure_policy() -> None:
    config = GradingConfig()

    assert config.review_policy.action_for("near_miss") == "wrong"
    assert config.review_policy.action_for("low_confidence") == "review"
    assert config.review_policy.action_for("vision_error") == "review"
    assert config.review_policy.instruction_needs_second_reader is False


def test_an_item_read_with_every_part_unsure_is_checked_in_full() -> None:
    item = ItemRead(
        parts=[
            PartRead(part=1, answer="a", confidence=0.2),
            PartRead(part=2, answer="b", confidence=0.2),
        ]
    )

    result = grade_item([text("a"), text("b")], MockProvider(item), b"x", "si")

    assert result.question.status == "pending_review"
    assert all(p.needs_review for p in result.question.parts)
