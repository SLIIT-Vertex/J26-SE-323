import json
import re

import pytest

from app.gamification.content import sinhala_riddles as r


def test_all_23_riddles_keep_lines_answers_and_order():
    riddles = r.riddles()
    assert list(riddles) == list(range(1, 24))
    answers = [riddles[n]["printed_answer_si"] for n in range(1, 24)]
    assert answers == [
        "කොකා", "කොස්ස", "ගොවියා", "දොර", "මොනරා", "රොටී", "ඉටිපන්දම", "ජිරාෆ්", "හඳ", "බෝලය", "කුඩය", "කෝච්චිය",
        "දේදුන්න", "ඔරලෝසුව", "සමනලයා", "අහස", "කොකා", "කරවිල", "යතුර", "පනාව", "ඉදල", "සරුංගලය", "බිම්මල",
    ]
    assert riddles[15]["printed_lines_si"][:2] == ["මලක් උඩ මලක්", "පියාඹන මලක්"]
    assert riddles[23]["clue_lines_nfc"] == ["ගසක නොපිපෙන මල්"]
    assert riddles[7]["printed_lines_si"][1] == "උසම උසයි" and riddles[8]["printed_lines_si"][0] == "උස ම උසයි"
    assert riddles[16]["printed_answer_si"] == "අහස"  # never "cloud"
    assert [riddles[n]["photograph"] for n in (12, 13)] == ["IMG_7486.heic", "IMG_7487.heic"]
    issues = json.dumps(r.source_transcription(), ensure_ascii=False)
    for flag in ("SHARED_ANSWER_WITH_1", "KEEP_DISTINCT_FROM_IDALA", "ILLUSTRATION_VS_ANSWER", "TRADITIONAL_LANGUAGE",
                 "BRIEF_SUMMARY_MISMATCH", "FIGURATIVE_NO_STEREOTYPE", "MIXED_GRADE_COLLECTION", "SINGLE_LINE"):
        assert flag in issues
    assert not re.search("්[රය]", issues)


def test_kossa_and_idala_stay_distinct_and_never_compete():
    assert r.family_of(2) != r.family_of(21)
    for number, distractors in r.DISTRACTORS.items():
        families = {r.family_of(number), *(r.family_of(d) for d in distractors)}
        assert not {"kossa", "idala"} <= families, number


def test_riddle_1_and_17_are_one_answer_family():
    assert r.family_of(1) == r.family_of(17)
    revealed = {"kokaa"}
    for seed in range(200):
        chosen, fresh = r.fresh_seed("G5-SIN-RID-FIGURATIVE-01", seed, revealed)
        if fresh:
            _, before, after = r.probe_riddles("G5-SIN-RID-FIGURATIVE-01", chosen)
            assert 17 not in (before, after)


def test_revision_is_stable_per_riddle_whatever_the_shuffle():
    one = r.build_item("G5-SIN-RID-DIRECT-01", "direct:short", 3, role="unsupported_before", salt="a")
    two = r.build_item("G5-SIN-RID-DIRECT-01", "direct:short", 3, role="unsupported_after", salt="b")
    assert one.revision_id == two.revision_id
    assert one.game_data["answer_cards"] != two.game_data["answer_cards"]


@pytest.mark.parametrize("skill_id", list(r.SKILLS))
def test_public_manifest_hides_answers_and_illustrations(skill_id):
    item = r.generate_item(skill_id, role="unsupported_before", seed=4)
    public = r.public_game_data(item)
    text = json.dumps(public, ensure_ascii=False)
    for secret in ("rubric", "answer_card_id", "card_errors", "reveal_key", "illustration", "equivalence", "answer_family"):
        assert secret not in text
    assert not any(emoji in text for emoji in r.REVEAL_EMOJI.values())
    # The answer appears only as one of four equally formatted cards.
    assert {tuple(sorted(card)) for card in public["answer_cards"]} == {("card_id", "text_si")}
    assert all(re.fullmatch(r"card-[0-9a-f]{12}", c["card_id"]) for c in public["answer_cards"])


def test_scoring_is_by_answer_only_and_refusals_are_typed():
    item = r.generate_item("G5-SIN-RID-DIRECT-01", role="unsupported_before", seed=1)
    answer = r.correct_response(item.game_data)
    assert r.validate_constructed_response(item, {**answer, "evidence_span_ids": []})[0]
    wrong = next(c["card_id"] for c in item.game_data["answer_cards"] if c["card_id"] != answer["answer_card_id"])
    correct, code, normalized = r.validate_constructed_response(item, {**answer, "answer_card_id": wrong})
    assert not correct and code in r.MISCONCEPTIONS and normalized["evidence_span_count"] == len(answer["evidence_span_ids"])
    for bad, expected in (
        ({**answer, "answer_card_id": ""}, "INCOMPLETE_RESPONSE"),
        ({**answer, "answer_card_id": "card-000000000000"}, "UNKNOWN_TOKEN"),
        ({**answer, "evidence_span_ids": answer["evidence_span_ids"][:1] * 2}, "DUPLICATE_TOKEN"),
        ({**answer, "extra": 1}, "MALFORMED_RESPONSE"),
        ({**answer, "schema_version": "x"}, "SCHEMA_MISMATCH"),
    ):
        with pytest.raises(r.ResponseError, match=expected):
            r.validate_constructed_response(item, bad)


def test_single_line_riddle_support_never_asks_for_a_remaining_clue():
    item = r.build_item("G5-SIN-RID-FIGURATIVE-01", "figurative:metaphor", 23, role="supported_practice", salt="s")
    for kind in r.common.SCAFFOLDS:
        assert not any("ඉතිරි" in s or "අනෙක්" in s for s in r.worked_steps(item.game_data, kind, item.skill_id))


def test_household_distractor_maps_to_household_confusion():
    item = r.build_item("G5-SIN-RID-DIRECT-01", "direct:short", 2, role="unsupported_before", salt="h")
    errors = item.game_data["rubric"]["card_errors"]
    door = next(c["card_id"] for c in item.game_data["answer_cards"] if c["text_si"] == "දොර")
    assert errors[door] == "similar_household_referent_confusion"


def test_exhausted_pool_is_reported():
    everything = {r.family_of(n) for n in r.riddles()}
    assert r.fresh_seed("G5-SIN-RID-DIRECT-01", 1, everything) == (1, False)
