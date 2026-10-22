import json
import re
import unicodedata

import pytest

from app.gamification.content import sinhala_punctuation as p

OPEN_SKILLS = [s for s, skill in p.SKILLS.items() if not skill.review_blocked]


def test_every_photographed_rule_and_example_is_in_the_ledger():
    sections = p.source_transcription()["sections"]
    assert [s["mark"] for s in sections] == [
        "full_stop", "question_mark", "comma", "quotation_marks", "exclamation_mark", "parentheses", "short_dash",
    ]
    examples = [e["printed_si"] for e in p.source_examples()]
    assert len(examples) == 19
    for needle in ("තාත්තා ගෙදර ආවේ ය.", "කේ. එල්. මියුම් ආකර්ෂා", "ලං.ග.ම. (ලංකා ගමනාගමන මණ්ඩලය)", "ප. ව. (පස්වරු)",
                   "අයියේ සීනිබෝල ගෙනාවා ද?", "වයලීනය කොහෙද අනේ?", "නැහැ නැහැ, ඊ මේල් කියන්නේ විද්‍යුත් තැපෑල",
                   "ලංකාව ! ඔහු කී ය.", "අසිරිමත් ලෝකය 75 - 79"):
        assert needle in examples
    # Continuation dots and the printed hyphen stay as printed.
    assert any(e.endswith("නොවූව ද...") for e in examples)
    assert all("–" not in e for e in examples)
    issues = json.dumps(p.source_transcription(), ensure_ascii=False)
    for flag in ("LINE_BREAK_NOT_DEMONSTRATED", "RULE_PRINT_GAP", "NAME_UNCERTAIN", "PAGE_RANGES_ARE_CONTENT", "SPELLING_READ"):
        assert flag in issues
    photos = p.source_transcription()["photographs"]
    assert [ph["sha256"][:8] for ph in photos] == ["e080b9ce", "20c87df0"]


def test_sinhala_conjuncts_carry_their_zwj_and_are_nfc():
    text = json.dumps(p.source_transcription(), ensure_ascii=False) + json.dumps(p.RULE_CARDS, ensure_ascii=False)
    text += json.dumps(p.MARKS, ensure_ascii=False)
    assert not re.search("්[රය]", text), "virama + ra/ya must carry a ZWJ"
    assert unicodedata.is_normalized("NFC", text)


def test_line_break_content_is_blocked_but_the_mechanic_is_grapheme_safe():
    with pytest.raises(ValueError, match="CONTENT_REVIEW_BLOCKED"):
        p.generate_item(p.LINEBREAK_SKILL, role="unsupported_before", seed=1)
    with pytest.raises(p.ResponseError, match="CONTENT_REVIEW_BLOCKED"):
        p.validate_linebreak(["ක", "ළු", "ම"], None, 1)
    with pytest.raises(p.ResponseError, match="BROKEN_GRAPHEME"):
        p.validate_linebreak(["ක", "ළු"], 1, 2)
    assert p.validate_linebreak(["ක", "ළු", "ම"], 2, 1) == (False, "INVALID_WORD_DIVISION")


@pytest.mark.parametrize("skill_id", OPEN_SKILLS)
def test_probes_are_fresh_equivalent_and_never_textbook_examples(skill_id):
    textbook = {e["display_nfc"] for e in p.source_examples()}
    for seed in range(40):
        before = p.generate_item(skill_id, role="unsupported_before", seed=seed)
        after = p.generate_item(skill_id, role="unsupported_after", seed=seed)
        assert before.game_data["equivalence"] == after.game_data["equivalence"]
        assert before.item_id != after.item_id
        for item in (before, after):
            assert p.rendered(item.game_data) not in textbook
            assert p.validate_constructed_response(item, p.correct_response(item.game_data))[0]
        support = {p.generate_support_item(skill_id, seed=seed, index=i).item_id for i in range(3)}
        assert before.item_id not in support and after.item_id not in support


@pytest.mark.parametrize("skill_id", OPEN_SKILLS)
def test_public_manifest_has_no_answers(skill_id):
    item = p.generate_item(skill_id, role="unsupported_before", seed=3)
    public = json.dumps(p.public_game_data(item), ensure_ascii=False)
    for secret in ("rubric", "targets", "kind_by_token", "position_by_boundary", "equivalence", "reporting_tokens"):
        assert secret not in public
    # Ids are opaque: no position or mark name inside them.
    for card in p.public_game_data(item)["mark_cards"]:
        assert re.fullmatch(r"mark-[0-9a-f]{12}", card["token_id"])


def test_abbreviation_measurement_is_unavailable():
    item = p.generate_item("G5-SIN-PUNC-ABBREV-01", role="unsupported_before", seed=1)
    assert item.game_data["equivalence"]["ig_available"] is False


def _quote(seed=0):
    return p.generate_item("G5-SIN-PUNC-QUOTE-01", role="unsupported_before", seed=seed)


def test_span_errors_reversed_reporting_and_wrong_mark():
    item = _quote()
    game = item.game_data
    answer = p.correct_response(game)
    by_position = {v: k for k, v in game["rubric"]["position_by_boundary"].items()}
    reversed_ = {**answer, "opening_mark_token_id": answer["closing_mark_token_id"], "closing_mark_token_id": answer["opening_mark_token_id"]}
    assert p.validate_constructed_response(item, reversed_)[2]["semantic_error"] == "REVERSED_PAIR"
    enclosed = {**answer, "end_boundary_id": by_position[len(game["tokens"])]}
    assert p.validate_constructed_response(item, enclosed)[1] == "reporting_clause_inclusion"
    parens = [t for t, k in game["rubric"]["kind_by_token"].items() if k in {"open_paren", "close_paren"}]
    kinds = game["rubric"]["kind_by_token"]
    wrong_mark = {**answer,
                  "opening_mark_token_id": next(t for t in parens if kinds[t] == "open_paren"),
                  "closing_mark_token_id": next(t for t in parens if kinds[t] == "close_paren")}
    assert p.validate_constructed_response(item, wrong_mark)[1] == "missing_or_reversed_paired_marks"
    with pytest.raises(p.ResponseError, match="INCOMPLETE_RESPONSE"):
        p.validate_constructed_response(item, {**answer, "closing_mark_token_id": ""})
    with pytest.raises(p.ResponseError, match="UNKNOWN_TOKEN"):
        p.validate_constructed_response(item, {**answer, "start_boundary_id": "gap-000000000000"})


def test_placement_errors_and_refusals():
    item = p.generate_item("G5-SIN-PUNC-INITIALS-01", role="unsupported_before", seed=0)
    answer = p.correct_response(item.game_data)
    one_dot = {**answer, "placements": answer["placements"][:1]}
    correct, code, normalized = p.validate_constructed_response(item, one_dot)
    # Every specified dot is required: no partial credit.
    assert not correct and code == "missing_abbreviation_dots" and normalized["semantic_error"] == "MISSING_MARK"
    duplicated = {**answer, "placements": [answer["placements"][0], {**answer["placements"][1], "boundary_id": answer["placements"][0]["boundary_id"]}]}
    with pytest.raises(p.ResponseError, match="DUPLICATE_TOKEN"):
        p.validate_constructed_response(item, duplicated)
    with pytest.raises(p.ResponseError, match="INCOMPLETE_RESPONSE"):
        p.validate_constructed_response(item, {**answer, "placements": []})
    with pytest.raises(p.ResponseError, match="MALFORMED_RESPONSE"):
        p.validate_constructed_response(item, {**answer, "extra": 1})
    with pytest.raises(p.ResponseError, match="RESPONSE_KIND_MISMATCH"):
        p.validate_constructed_response(item, {**answer, "kind": "sinhala_punctuation_span"})


def test_end_exclamation_is_an_unsupported_choice():
    item = p.generate_item("G5-SIN-PUNC-END-01", role="unsupported_before", seed=0)
    game = item.game_data
    answer = p.correct_response(game)
    bang = next(t for t, k in game["rubric"]["kind_by_token"].items() if k == "exclamation_mark")
    answer["placements"][0]["mark_token_id"] = bang
    assert p.validate_constructed_response(item, answer)[1] == "unsupported_exclamation_choice"


def test_model1_catalogue_and_unknown_fallback():
    catalogue = p.misconception_catalogue()
    assert [row["code"] for row in catalogue] == list(p.MISCONCEPTIONS)
    belief = p.infer_belief("reporting_clause_inclusion")
    assert abs(sum(belief["probabilities"].values()) - 1) < 1e-9
    assert p.infer_belief("reporting_clause_inclusion", sparse=True)["top_hypothesis"] == p.UNKNOWN
