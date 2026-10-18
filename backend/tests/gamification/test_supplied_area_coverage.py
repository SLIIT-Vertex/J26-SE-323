"""Lock the 57-row supplied-area inventory to the names and status rules."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MATRIX = (
    ROOT
    / "research"
    / "adaptive_gamified_learning_plan"
    / "coverage"
    / "grade5-supplied-area-coverage-v1.jsonl"
)
PLAN = (
    ROOT
    / "research"
    / "adaptive_gamified_learning_plan"
    / "coverage"
    / "staged-implementation-batches.md"
)

SUPPLIED = [
    ("ENV", "අපේ යහපැවැත්ම", "Our Well-being"),
    ("ENV", "අපි ලක් වැසියෝ", "We Are Sri Lankans"),
    ("ENV", "පැළෑටි හා ගස්වැල්", "Plants and Trees"),
    ("ENV", "අප අවට සත්තු", "Animals Around Us"),
    ("ENV", "අප පරිහරණය කරන දේ", "Things We Use"),
    ("ENV", "අපේ ආහාර", "Our Food"),
    ("ENV", "ආරක්ෂාව සහ පරිස්සම", "Safety and Care"),
    ("ENV", "ජලය", "Water"),
    ("ENV", "වැඩ පහසු කිරීමේ මං", "Ways to Make Work Easier"),
    ("ENV", "ගෙවත්ත", "Home Garden"),
    ("ENV", "ගමනාගමනය", "Transportation"),
    ("ENV", "මිනිස් හැසිරීම්", "Human Behaviour"),
    ("ENV", "පොළොව හා අහස", "Earth and Sky"),
    ("ENV", "අපට කළ හැකි වෙනස්කම්", "Changes We Can Make"),
    ("ENV", "මිනිසා සහ තොරතුරු", "Humans and Information"),
    ("ENV", "අපේ අතීත විත්ති", "Stories from Our Past"),
    ("MAT", "සංඛ්‍යා", "Numbers"),
    ("MAT", "එකතු කිරීම", "Addition"),
    ("MAT", "සංඛ්‍යා රටා", "Number Patterns"),
    ("MAT", "අඩු කිරීම", "Subtraction"),
    ("MAT", "භාග", "Fractions"),
    ("MAT", "ගුණ කිරීම", "Multiplication"),
    ("MAT", "කාලය", "Time"),
    ("MAT", "බෙදීම", "Division"),
    ("MAT", "දිග හා දුර", "Length and Distance"),
    ("MAT", "මුදල්", "Money"),
    ("MAT", "පරිමාව හා ධාරිතාව", "Volume and Capacity"),
    ("MAT", "බර මැනීම", "Measuring Weight"),
    ("MAT", "හැඩතල හා ඝන වස්තු", "Shapes and Solid Objects"),
    ("MAT", "දිශා", "Directions"),
    ("MAT", "දශම", "Decimals"),
    ("MAT", "රෝම සංඛ්‍යාංක", "Roman Numerals"),
    ("SIN", "පිල්ලම් හඳුනාගනිමු", "Identifying Vowel Signs"),
    ("SIN", "විරාම ලක්ෂණ හඳුනාගනිමු", "Identifying Punctuation Marks"),
    ("SIN", "තේරවිලි", "Riddles"),
    ("SIN", "සමානාර්ථ පද (සමාන පද)", "Synonyms"),
    ("SIN", "විරුද්ධාර්ථ පද (විරුද්ධ පද)", "Antonyms"),
    ("SIN", "යුගල පද", "Paired Words"),
    ("SIN", "ප්‍රස්තාව පිරුළු", "Proverbs"),
    ("SIN", "ඉඟි වැකි", "Idiomatic Expressions"),
    ("SIN", "ආප්තෝපදේශ", "Wise Sayings and Maxims"),
    ("SIN", "උපමා", "Similes"),
    ("SIN", "පොදුලිංග ලිපි", "Common-Gender Terms"),
    ("SIN", "ආඛ්‍යාති පද", "Verbs and Predicates"),
    ("SIN", "ආරාධනා පත්‍ර", "Invitation Letters"),
    ("SIN", "ස්ත්‍රී ලිංග හා පුරුෂ ලිංග පද", "Feminine and Masculine Nouns"),
    ("SIN", "ඒකවචන හා බහුවචන පද", "Singular and Plural Words"),
    ("SIN", "අක්ෂර වින්‍යාසය", "Spelling and Orthography"),
    ("SIN", "න, ණ යෙදීම", "Usage of න and ණ"),
    ("SIN", "ල, ළ යෙදීම", "Usage of ල and ළ"),
    ("SIN", "ස, ශ, ෂ යෙදීම", "Usage of ස, ශ and ෂ"),
    ("SIN", "අල්පප්‍රාණ සහ මහාප්‍රාණ අක්ෂර", "Unaspirated and Aspirated Consonants"),
    ("SIN", "නාම පද", "Nouns"),
    ("SIN", "ක්‍රියා පද", "Verbs"),
    ("SIN", "උක්ත සහ අනුක්ත පද", "Subject and Non-subject Forms"),
    ("SIN", "සරල වාක්‍ය", "Simple Sentences"),
    ("SIN", "ද / ත / ස / හා / සහ යෙදුණු වාක්‍ය රටා", "Sentence Patterns Using ද, ත, ස, හා and සහ"),
]

REQUIRED = {
    "area_id",
    "subject",
    "name_si",
    "name_en",
    "outcome_or_competency",
    "atomic_skill_ids",
    "source_document_id",
    "evidence_locator",
    "related_universal_skill_ids",
    "mapping_status",
    "content_status",
    "blocker_or_review_note",
    "evidence_checked",
    "proposed_batch_id",
    "human_review_gate",
}
MAPPING_STATUSES = {
    "MAPPED_DRAFT",
    "CONTENT_DRAFT",
    "IMPLEMENTED_UNREVIEWED",
    "NEEDS_REVIEW",
    "BLOCKED",
    "REVIEWED",
    "RELEASE_READY",
}


def _rows() -> list[dict]:
    return [json.loads(line) for line in MATRIX.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_supplied_areas_appear_exactly_once() -> None:
    rows = _rows()

    assert len(rows) == 57
    assert len(SUPPLIED) == 57
    assert [(row["subject"], row["name_si"], row["name_en"]) for row in rows] == SUPPLIED
    assert len({row["area_id"] for row in rows}) == 57
    assert [row["area_id"] for row in rows] == [
        f"G5-AREA-{subject}-{index:02d}"
        for subject, width in (("ENV", 16), ("MAT", 16), ("SIN", 25))
        for index in range(1, width + 1)
    ]
    assert all(row["subject"] != "ENG" for row in rows)


def test_statuses_stay_unapproved_and_only_the_fractions_skill_exists() -> None:
    rows = _rows()
    plan = PLAN.read_text(encoding="utf-8")

    for row in rows:
        assert REQUIRED <= row.keys()
        assert row["mapping_status"] in MAPPING_STATUSES
        assert row["mapping_status"] not in {"REVIEWED", "RELEASE_READY", "CONTENT_DRAFT"}
        assert row["content_status"] in {"NONE", "IMPLEMENTED_UNREVIEWED"}
        assert row["implementation_blocked"] is True
        assert row["blocker_or_review_note"]
        assert row["evidence_checked"]
        assert row["human_review_gate"]
        assert f"## {row['proposed_batch_id']}" in plan
        if row["mapping_status"] == "BLOCKED":
            assert row["outcome_or_competency"] is None
            assert row["atomic_skill_ids"] == []
        if row["mapping_status"] == "MAPPED_DRAFT":
            assert row["outcome_or_competency"]["text_si"]
            assert row["outcome_or_competency"]["adopted_as_atomic_skill"] is False
            assert row["outcome_or_competency"]["verification_status"] != "approved"

    fractions = next(row for row in rows if row["area_id"] == "G5-AREA-MAT-05")
    assert fractions["atomic_skill_ids"] == ["G5-MAT-C03-L01-O01"]
    assert fractions["content_status"] == "IMPLEMENTED_UNREVIEWED"
    assert fractions["mapping_status"] == "MAPPED_DRAFT"
    assert [row["area_id"] for row in rows if row["atomic_skill_ids"]] == ["G5-AREA-MAT-05"]
    assert [row["area_id"] for row in rows if row["content_status"] != "NONE"] == ["G5-AREA-MAT-05"]
    blocked = [row["area_id"] for row in rows if row["mapping_status"] == "BLOCKED"]
    assert blocked == ["G5-AREA-SIN-11", "G5-AREA-SIN-12"]
    assert all(row["mapping_status"] != "NEEDS_REVIEW" for row in rows)
    assert sum(row["mapping_status"] == "MAPPED_DRAFT" for row in rows) == 55
