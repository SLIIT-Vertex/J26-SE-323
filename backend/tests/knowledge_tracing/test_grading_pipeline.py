"""The grading pipeline with a scripted reader: blind reading, errors, second opinion."""

import json
from pathlib import Path

import pytest

from app.knowledge_tracing.application.grading import (
    PROMPT_VERSION,
    GradingConfig,
    ItemRead,
    KeyPart,
    PartRead,
    PartSpec,
    VisionError,
    blind_prompt,
    grade_item,
    parse_item_read,
    part_specs,
)
from app.knowledge_tracing.application.question_import import ImageInfo, build_plan, load_files
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider, reading

CROP = b"not-a-real-image"


def mcq(part_no: int, correct: str, labels: tuple[str, ...] = ("1", "2", "3")) -> KeyPart:
    return KeyPart(part_no, "choice", (correct,), option_labels=labels)


def short(part_no: int, *alternatives: str, kind: str = "text") -> KeyPart:
    return KeyPart(part_no, kind, alternatives)  # type: ignore[arg-type]


def grade(key: list[KeyPart], provider: MockProvider, **kwargs):
    return grade_item(key, provider, CROP, "si", **kwargs)


# ---- the reader is never told the answer -------------------------------------------------------


def test_the_reader_is_never_told_any_answer() -> None:
    key = [
        mcq(1, "3"),
        short(2, "elephant-answer", "alt-answer"),
        short(3, "80,004", kind="number"),
        KeyPart(4, "instruction", (), instruction="check the boxes are coloured"),
    ]
    provider = MockProvider(reading("3", "x", "80004", "coloured"))

    grade(key, provider)

    call = provider.calls[0]
    secrets = ["elephant-answer", "alt-answer", "80,004", "80004"]
    for secret in secrets:
        assert secret not in call.prompt
        assert secret not in repr(call.parts)
    assert "check the boxes are coloured" in call.prompt  # an instruction to look is allowed


def test_the_prompt_is_the_same_whatever_the_correct_answer_is() -> None:
    """Blindness as a property: change only the answer key and the prompt must not change."""
    options = ("1", "2", "3")
    prompts = []
    for correct in options:
        key = [mcq(1, correct), short(2, f"word-for-{correct}"), short(3, correct, kind="number")]
        provider = MockProvider(reading("1", "x", "1"))
        grade(key, provider)
        prompts.append(provider.calls[0].prompt)

    assert len(set(prompts)) == 1


def test_part_specs_have_no_field_that_could_hold_an_answer() -> None:
    assert set(PartSpec.model_fields) == {"index", "label", "kind", "option_labels", "instruction"}
    specs = part_specs([mcq(1, "2"), short(2, "word")])

    dumped = json.dumps([s.model_dump() for s in specs])
    assert "word" not in dumped
    assert specs[0].option_labels == ("1", "2", "3")  # every option, in order
    assert specs[1].option_labels is None


def test_the_prompt_lists_every_part_and_the_blank_reference() -> None:
    specs = [
        PartSpec(index=1, label="i", kind="text"),
        PartSpec(index=2, label="ii", kind="number"),
    ]

    prompt = blind_prompt(specs, "ta", has_reference=True)

    assert "Tamil" in prompt
    assert "This question has 2 answer parts" in prompt
    assert "Part 1 (labelled 'i.')" in prompt
    assert "SECOND image" in prompt
    assert "do NOT solve the question" in prompt
    assert "LETTER BY LETTER" in prompt
    assert "SECOND image" not in blind_prompt(specs, "si", has_reference=False)


def test_the_provider_receives_the_reference_flag_and_language() -> None:
    provider = MockProvider(reading("2"))

    grade_item([mcq(1, "2")], provider, CROP, "ta", blank_reference=b"blank")

    assert provider.calls[0].had_reference is True
    assert provider.calls[0].language == "ta"


# ---- grading a question -----------------------------------------------------------------------


def test_a_correct_single_answer() -> None:
    result = grade([mcq(1, "2")], MockProvider(reading("ii")))

    assert result.question.status == "correct"
    assert result.provider == "mock"
    assert result.prompt_version == PROMPT_VERSION


def test_a_wrong_answer_is_wrong_and_final() -> None:
    result = grade([mcq(1, "2")], MockProvider(reading("3")))

    assert result.question.status == "wrong"
    assert not result.question.needs_review


def test_a_blank_question_is_blank() -> None:
    result = grade([mcq(1, "2")], MockProvider(reading(None)))

    assert result.question.status == "blank"


def test_parts_are_compared_part_by_part_in_order() -> None:
    key = [mcq(1, "2"), short(2, "cat"), short(3, "12", kind="number")]

    all_right = grade(key, MockProvider(reading("2", "Cat", "12")))
    one_wrong = grade(key, MockProvider(reading("2", "dog", "12")))

    assert all_right.question.status == "correct"
    assert one_wrong.question.status == "wrong"
    assert (one_wrong.question.correct_parts, one_wrong.question.total_parts) == (2, 3)
    assert [p.status for p in one_wrong.question.parts] == ["correct", "wrong", "correct"]


def test_a_cross_out_and_a_double_mark_wait_for_the_parent() -> None:
    result = grade([mcq(1, "2")], MockProvider(reading("ii+iii")))

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "two_marks"


def test_a_near_miss_waits_for_the_parent() -> None:
    result = grade([short(1, "rabbit")], MockProvider(reading("rabite")))

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "near_miss"
    assert result.question.parts[0].status == "wrong"  # the rule's view, pending confirmation


def test_a_low_confidence_reading_waits_for_the_parent() -> None:
    result = grade([short(1, "cat")], MockProvider(reading(("cat", 0.4))))

    assert result.question.status == "pending_review"
    assert result.question.parts[0].review_reason == "low_confidence"


def test_a_settled_part_keeps_its_result_while_another_waits() -> None:
    key = [mcq(1, "2"), short(2, "rabbit")]

    result = grade(key, MockProvider(reading("2", "rabite")))

    assert result.question.status == "pending_review"
    assert result.question.parts[0].status == "correct"
    assert not result.question.parts[0].needs_review
    assert result.question.parts[1].needs_review


# ---- when the reader misbehaves, nothing becomes "wrong" ---------------------------------------


def test_a_part_count_mismatch_sends_every_part_to_the_parent() -> None:
    key = [mcq(1, "2"), short(2, "cat"), short(3, "dog")]

    result = grade(key, MockProvider(reading("2", "cat")))  # two readings for three parts

    assert result.question.status == "pending_review"
    assert {p.review_reason for p in result.question.parts} == {"part_count_mismatch"}
    assert all(p.status == "ambiguous" for p in result.question.parts)


def test_a_reading_for_the_wrong_part_numbers_is_a_mismatch() -> None:
    odd = ItemRead(parts=[PartRead(part=5, answer="2", confidence=0.9)])

    result = grade([mcq(1, "2")], MockProvider(odd))

    assert result.question.parts[0].review_reason == "part_count_mismatch"


@pytest.mark.parametrize("code", ["quota_daily", "rate_limit", "timeout", "invalid_json", "boom"])
def test_a_vision_error_is_never_a_wrong_answer(code: str) -> None:
    key = [mcq(1, "2"), short(2, "cat")]

    result = grade(key, MockProvider(VisionError(code, "details")))

    assert result.question.status == "pending_review"
    assert {p.review_reason for p in result.question.parts} == {"vision_error"}
    assert result.errors == (code,)
    assert result.calls == ()


def test_an_exhausted_mock_reports_an_error_not_a_crash() -> None:
    result = grade([mcq(1, "2")], MockProvider())

    assert result.question.status == "pending_review"
    assert result.errors == ("mock_empty",)


# ---- second opinion ---------------------------------------------------------------------------


def test_two_readers_that_agree_are_accepted() -> None:
    primary, second = MockProvider(reading("ii")), MockProvider(reading("(ii)"))

    result = grade([mcq(1, "2")], primary, second_provider=second)

    assert result.question.status == "correct"
    assert len(result.calls) == 2


def test_two_readers_that_disagree_go_to_the_parent_with_the_first_reading_kept() -> None:
    primary, second = MockProvider(reading("2")), MockProvider(reading("3"))

    result = grade([mcq(1, "2")], primary, second_provider=second)

    part = result.question.parts[0]
    assert result.question.status == "pending_review"
    assert part.review_reason == "models_disagree"
    assert part.read_text == "2"  # the primary reading is what the parent sees


def test_a_blank_and_an_answer_disagree() -> None:
    primary, second = MockProvider(reading(None)), MockProvider(reading("2"))

    result = grade([mcq(1, "2")], primary, second_provider=second)

    assert result.question.parts[0].review_reason == "models_disagree"


def test_a_failing_second_reader_checks_everything_with_the_parent() -> None:
    primary, second = MockProvider(reading("2")), MockProvider(VisionError("quota_daily"))

    result = grade([mcq(1, "2")], primary, second_provider=second)

    assert result.question.status == "pending_review"
    assert result.errors == ("quota_daily",)


def test_a_second_reader_makes_an_instruction_part_final() -> None:
    key = [KeyPart(1, "instruction", (), instruction="check the boxes are coloured")]
    one = ItemRead(parts=[PartRead(part=1, answer="coloured", confidence=0.95, instruction_met=True)])

    alone = grade(key, MockProvider(one))
    agreed = grade(key, MockProvider(one), second_provider=MockProvider(one))

    assert alone.question.status == "pending_review"
    assert agreed.question.status == "correct"


# ---- parsing what a real model returns --------------------------------------------------------


def test_parse_plain_json() -> None:
    parsed = parse_item_read('{"parts":[{"part":1,"answer":"ii","blank":false,"confidence":0.9}]}')

    assert parsed.parts[0].answer == "ii"
    assert parsed.parts[0].confidence == 0.9


def test_parse_strips_code_fences_and_thinking() -> None:
    reply = (
        "<think>the child wrote two</think>\n```json\n"
        '{"parts":[{"part":1,"answer":"2","blank":false,"confidence":1}],"notes":"ok"}\n```'
    )

    parsed = parse_item_read(reply)

    assert parsed.parts[0].answer == "2"
    assert parsed.notes == "ok"


@pytest.mark.parametrize(
    "reply",
    ["", "no json here", '{"parts": "not a list"}', '{"parts":[{"answer":"x"}]}', "{broken"],
)
def test_unusable_replies_are_invalid_json_errors(reply: str) -> None:
    with pytest.raises(VisionError) as caught:
        parse_item_read(reply)

    assert caught.value.code == "invalid_json"


def test_confidence_outside_zero_to_one_is_rejected() -> None:
    with pytest.raises(VisionError):
        parse_item_read('{"parts":[{"part":1,"answer":"x","confidence":7}]}')


# ---- the real question bank -------------------------------------------------------------------

BANK = Path(__file__).parents[2] / "data" / "question_bank"


class _Anything:
    def describe(self, language: str, question_id: str) -> ImageInfo:
        return ImageInfo(f"{language}/{question_id}", 800, 400, f"{language}-{question_id}")


@pytest.mark.skipif(not BANK.is_dir(), reason="question bank folder not present")
def test_every_real_part_is_correct_for_its_own_answer_and_blank_for_nothing() -> None:
    """The strongest check: feed every answer key back as the reading.

    Reading exactly the key's first alternative must be graded correct for all of the real
    parts (Sinhala and Tamil), and reading nothing must be graded blank. If a key were written in
    a way the comparison cannot match (a stray character, an unusual digit), this finds it.
    """
    plan = build_plan(load_files(BANK), _Anything())
    assert plan.ok

    checked = 0
    problems: list[str] = []
    for question in plan.questions:
        for language, variant in question.variants.items():
            for part in variant.parts:
                key = KeyPart(
                    part_no=part.part_no,
                    kind=part.answer_kind,  # type: ignore[arg-type]
                    alternatives=tuple(part.alternatives),
                    option_labels=tuple(part.option_labels) if part.option_labels else None,
                    instruction=part.instruction,
                )
                checked += 1
                if key.kind == "instruction":
                    continue  # judged from what the reader sees, not from text
                for alternative in key.alternatives:
                    own = PartRead(part=part.part_no, answer=alternative, confidence=0.95)
                    from app.knowledge_tracing.application.grading import compare_part

                    result = compare_part(own, key, GradingConfig())
                    if result.status != "correct" or result.needs_review:
                        problems.append(f"{question.id}/{language} part {part.part_no}: "
                                        f"{alternative!r} -> {result.status} ({result.how})")
                empty = compare_part(
                    PartRead(part=part.part_no, answer="", blank=True, confidence=0.95), key
                )
                if empty.status != "blank":
                    problems.append(f"{question.id}/{language} part {part.part_no}: blank -> {empty.status}")

    assert checked >= 700
    assert not problems, problems[:10]
