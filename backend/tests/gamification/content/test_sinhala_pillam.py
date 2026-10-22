import json
import unicodedata

import pytest

from app.gamification.content import sinhala_pillam as p


def test_all_nineteen_photographed_rows_are_preserved_in_printed_order() -> None:
    rows = p.source_rows()
    assert [row["row"] for row in rows] == list(range(1, 20))
    assert [row["printed_name_si"] for row in rows][:3] == ["ඇලපිල්ල", "කෙටි ඇදපිල්ල", "දික් ඇදපිල්ල"]
    assert rows[7]["printed_name_si"] == "කෙටි ඇද පාපිල්ල"  # spacing kept as printed
    assert [row["printed_vowel_si"] for row in rows] == list("ආඇඈඉඊඋඋඋඌඌඌඑඒඔඕඍඎඓඖ")
    assert [row["printed_examples_si"][0] for row in rows] == [
        "කා", "කැ", "කෑ", "කි", "කී", "ලු", "කු", "රු", "ලූ", "කූ", "රූ",
        "කෙ", "කේ", "කො", "කෝ", "කෘ", "කෲ", "කෛ", "කෞ",
    ]
    # Row 13 keeps both printed examples; the photograph reads වේ, not the prompt's මේ.
    assert rows[12]["printed_examples_si"] == ["කේ", "වේ"]
    assert "SECOND_EXAMPLE_READS_VE_NOT_ME" in rows[12]["review_flags"]
    for row in rows:
        assert row["locator"] == f"IMG_7483.heic#table-row-{row['row']}"
        assert all(unicodedata.is_normalized("NFC", text) for text in row["normalized_examples_nfc"])


def test_source_is_hash_bound_and_records_every_gap() -> None:
    source = p.source_transcription()["source"]
    assert source["sha256"] == "1f1a4e092f4fe25c2b1cd5a0200db9e24527ff404609e1d1ee52973283a1eaa1"
    assert source["printed_page_number"] is None and source["rights_statement"] is None
    gaps = " ".join(p.source_transcription()["recorded_gaps"])
    for needle in ("section number", "TEACHER_GUIDE", "SENTENCE_COVERAGE", "NEW_MATERIAL", "FONT_RENDERING"):
        assert needle in gaps


def test_compose_follows_logical_order_and_reviewed_explicit_forms() -> None:
    assert p.compose("ක", ["comp:alapilla", "comp:kombuva"]) == "කො"
    assert p.compose("ක", ["comp:hal", "comp:alapilla", "comp:kombuva"]) == "කෝ"
    assert p.compose("ක", ["comp:kombuva", "comp:hal"]) == "කේ"
    assert p.compose("ක", ["comp:kombuva", "comp:gayanukitta"]) == "කෞ"
    assert p.compose("ක", ["comp:kombuva", "comp:kombuva"]) == "කෛ"
    assert p.compose("ක", ["comp:gaeta", "comp:gaeta"]) == "කෲ"
    # Two marks that make no reviewed sign are refused, never shown as a broken akshara.
    assert p.compose("ක", ["comp:alapilla", "comp:hal"]) is None
    for text in ("කො", "කෝ", "කේ", "කෞ"):
        assert unicodedata.is_normalized("NFC", text)


def test_graphemes_keep_marks_and_zwj_conjuncts_whole() -> None:
    assert p.graphemes("කෝලු") == ("කෝ", "ලු")
    # ක්‍ෂ: virama + ZWJ joins the next consonant; the ZWJ is significant and retained.
    assert p.graphemes("ක්‍ෂ") == ("ක්‍ෂ",)
    assert "‍" in p.graphemes("ක්‍ෂ")[0]


@pytest.mark.parametrize("skill_id", list(p.SKILLS))
def test_probes_are_equivalent_fresh_and_never_the_demonstration(skill_id: str) -> None:
    for seed in range(60):
        before = p.generate_item(skill_id, role="unsupported_before", seed=seed)
        after = p.generate_item(skill_id, role="unsupported_after", seed=seed)
        assert before.parallel_family_id == after.parallel_family_id
        assert before.game_data["equivalence"] == after.game_data["equivalence"]
        assert before.item_id != after.item_id
        assert before.game_data["rubric"] != after.game_data["rubric"]
        demo = p.demonstration(skill_id, seed)["demonstration_id"].split(":demo:")[1].removesuffix("@v1")
        assert not before.item_id.endswith(demo) and not after.item_id.endswith(demo)
        support = {p.generate_support_item(skill_id, seed=seed, index=i).item_id for i in range(5)}
        assert after.item_id not in support and before.item_id not in support


@pytest.mark.parametrize("skill_id", list(p.SKILLS))
def test_public_manifest_hides_rubric_and_correctness(skill_id: str) -> None:
    item = p.generate_item(skill_id, role="unsupported_before", seed=5)
    public = json.dumps(p.public_game_data(item), ensure_ascii=False)
    for secret in ("rubric", "accepted", "target_kinds", "target_text", "equivalence", "correct"):
        assert secret not in public
    # Emojis stay out of scored linguistic clues (the goal line is decorative only).
    assert "🌟" not in item.prompt_si


def _answer(item):
    return p.correct_response(item.game_data)


def test_every_skill_accepts_its_reviewed_answer_in_any_placement_order() -> None:
    item = p.generate_item("G5-SIN-PIL-COMPOUND-01", role="unsupported_before", seed=1)
    answer = _answer(item)
    assert p.validate_constructed_response(item, answer)[0] is True
    answer["ordered_pilla_ids"] = list(reversed(answer["ordered_pilla_ids"]))
    correct, _code, normalized = p.validate_constructed_response(item, answer)
    assert correct and normalized["placement_order"] == answer["ordered_pilla_ids"]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda a, i: a.update(extra=1), "MALFORMED_RESPONSE"),
        (lambda a, i: a.update(schema_version="v0"), "SCHEMA_MISMATCH"),
        (lambda a, i: a.update(kind="sinhala_pillam_match"), "RESPONSE_KIND_MISMATCH"),
        (lambda a, i: a.update(ordered_pilla_ids=[]), "INCOMPLETE_RESPONSE"),
        (lambda a, i: a.update(ordered_pilla_ids=["card-000000000000"]), "UNKNOWN_TOKEN"),
        (lambda a, i: a.update(base_consonant_id="base-000000000000"), "UNKNOWN_TOKEN"),
        (lambda a, i: a.update(ordered_pilla_ids=a["ordered_pilla_ids"][:1] * 2), "DUPLICATE_TOKEN"),
    ],
)
def test_build_refusals_are_machine_readable(mutate, code) -> None:
    item = p.generate_item("G5-SIN-PIL-COMPOUND-01", role="unsupported_before", seed=2)
    answer = _answer(item)
    mutate(answer, item)
    with pytest.raises(p.PillamResponseError) as error:
        p.validate_constructed_response(item, answer)
    assert error.value.code == code


def _tokens(item, kind):
    return [t for t, k in item.game_data["rubric"]["kind_by_token"].items() if k == kind]


def test_build_errors_classify_without_partial_credit() -> None:
    for seed in range(40):
        item = p.generate_item("G5-SIN-PIL-COMPOUND-01", role="unsupported_before", seed=seed)
        if item.game_data["subfamily"] == "compound:row-15":  # ෝ = kombuva + alapilla + hal
            break
    answer = _answer(item)
    hal = _tokens(item, "comp:hal")[0]
    answer["ordered_pilla_ids"] = [t for t in answer["ordered_pilla_ids"] if t != hal]
    correct, code, normalized = p.validate_constructed_response(item, answer)
    assert (correct, code, normalized["semantic_error"]) == (False, "compound_component_missing", "MISSING_COMPONENT")
    answer["ordered_pilla_ids"] += [hal, _tokens(item, "comp:gayanukitta")[0]]
    assert p.validate_constructed_response(item, answer)[1] == "compound_component_extra"


def test_length_and_papili_errors() -> None:
    for seed in range(40):
        item = p.generate_item("G5-SIN-PIL-LENGTH-01", role="unsupported_before", seed=seed)
        family = item.game_data["subfamily"].split(":")[1]
        short, long, _, _ = p.LENGTH_FAMILIES[family]
        wanted = item.game_data["rubric"]["target_kinds"][0]
        partner = long if wanted == short else short
        answer = _answer(item)
        answer["ordered_pilla_ids"] = _tokens(item, partner)
        assert p.validate_constructed_response(item, answer)[2]["semantic_error"] == "SHORT_LONG_CONFUSION"
    item = p.generate_item("G5-SIN-PIL-PAPILI-01", role="unsupported_before", seed=0)
    base = item.game_data["base"]["text_si"]
    length = item.game_data["subfamily"].split(":")[1]
    wrong_shape = next(s for s in ("kon", "vak", "aeda") if s != p.PAPILI_ALLOGRAPH_BY_BASE[base])
    answer = _answer(item)
    answer["ordered_pilla_ids"] = _tokens(item, f"papili:{wrong_shape}:{length}")
    correct, _code, normalized = p.validate_constructed_response(item, answer)
    # The font draws the same ු either way: the server scores the chosen shape, not the mark.
    assert not correct and normalized["semantic_error"] == "WRONG_BASE_ALLOGRAPH"


def test_vowel_mode_lets_two_papili_share_one_destination() -> None:
    for seed in range(80):
        item = p.generate_item("G5-SIN-PIL-VOWEL-01", role="unsupported_before", seed=seed)
        if item.game_data["subfamily"] == "vowel:shared-papili":
            break
    answer = _answer(item)
    assert len({row["destination_id"] for row in answer["placements"]}) == 1
    assert p.validate_constructed_response(item, answer)[0] is True
    answer["match_mode"] = "name"
    with pytest.raises(p.PillamResponseError, match="MATCH_MODE_MISMATCH"):
        p.validate_constructed_response(item, answer)


def test_model1_distribution_normalizes_and_falls_back_safely() -> None:
    belief = p.infer_belief("short_long_confusion")
    assert abs(sum(belief["probabilities"].values()) - 1) < 1e-9
    assert set(belief["probabilities"]) == set(p.MISCONCEPTIONS)
    assert belief["top_hypothesis"] == "short_long_confusion"
    sparse = p.infer_belief("short_long_confusion", sparse=True)
    assert sparse["top_hypothesis"] == p.UNKNOWN and sparse["abstained"]
    motor = p.infer_belief("short_long_confusion", interaction_summary={"correction_count": 5})
    assert motor["motor_difficulty_suspected"] and motor["low_confidence"]
    assert motor["confidence"] < belief["confidence"]
    clipped = p.infer_belief("sign_name_confusion", interaction_summary={"rendering_issue_reported": True})
    assert clipped["top_hypothesis"] == p.UNKNOWN
    assert p.UNKNOWN_CODE_MAPPING["shared_code"] == "unknown_or_other"


def test_catalogue_covers_every_hypothesis_with_evidence_and_counter_evidence() -> None:
    catalogue = p.misconception_catalogue()
    assert [row["code"] for row in catalogue] == list(p.MISCONCEPTIONS)
    for row in catalogue:
        assert row["evidence_patterns"] and row["source_basis"] and row["eligible_support"]
        assert row["code"] == p.UNKNOWN or row["counter_evidence"]


def test_rare_double_gaeta_family_is_practice_only() -> None:
    family = p.subfamilies("G5-SIN-PIL-COMPOUND-01")["compound:row-17"]
    item = p.build_item("G5-SIN-PIL-COMPOUND-01", "compound:row-17", family["pool"][0], role="unsupported_before", salt="t")
    assert item.game_data["equivalence"]["ig_available"] is False
