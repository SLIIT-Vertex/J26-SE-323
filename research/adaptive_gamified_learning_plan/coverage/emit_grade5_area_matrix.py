"""Emit the 57-row Grade 5 supplied-area coverage matrix.

The matrix records evidence. It does not approve outcomes, create atomic skills, or
author learner content. Re-run from the repository root:

    python3 research/adaptive_gamified_learning_plan/coverage/emit_grade5_area_matrix.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TRACE = ROOT / "data/curriculum/grade5-curriculum-trace/v1/curriculum_nodes.jsonl"
TERMS = ROOT / "data/curriculum/grade5-curriculum-trace/v1/curriculum_terms.jsonl"
OUT = Path(__file__).with_name("grade5-supplied-area-coverage-v1.jsonl")

GATE = (
    "HR-CUR-01, HR-RGT-01, HR-SIN-01, HR-EDU-01, HR-ACC-01, HR-LEAK-01, and HR-REL-01; "
    "security, privacy, ethics, consent, protocol, model-safety, and release gates remain "
    "blocked. No human approval is recorded."
)

ENV = [
    (1, "අපේ යහපැවැත්ම", "Our Well-being"),
    (2, "අපි ලක් වැසියෝ", "We Are Sri Lankans"),
    (3, "පැළෑටි හා ගස්වැල්", "Plants and Trees"),
    (4, "අප අවට සත්තු", "Animals Around Us"),
    (5, "අප පරිහරණය කරන දේ", "Things We Use"),
    (6, "අපේ ආහාර", "Our Food"),
    (7, "ආරක්ෂාව සහ පරිස්සම", "Safety and Care"),
    (8, "ජලය", "Water"),
    (9, "වැඩ පහසු කිරීමේ මං", "Ways to Make Work Easier"),
    (10, "ගෙවත්ත", "Home Garden"),
    (11, "ගමනාගමනය", "Transportation"),
    (12, "මිනිස් හැසිරීම්", "Human Behaviour"),
    (13, "පොළොව හා අහස", "Earth and Sky"),
    (14, "අපට කළ හැකි වෙනස්කම්", "Changes We Can Make"),
    (15, "මිනිසා සහ තොරතුරු", "Humans and Information"),
    (16, "අපේ අතීත විත්ති", "Stories from Our Past"),
]

MAT = [
    (1, "සංඛ්‍යා", "Numbers", "G5-MAT-C01", ["G5-MAT-U001", "G5-MAT-U002"], "MAT-NUM", "B-MAT-NUMBER-OPS"),
    (2, "එකතු කිරීම", "Addition", "G5-MAT-C06", ["G5-MAT-U003"], "MAT-OPS", "B-MAT-NUMBER-OPS"),
    (3, "සංඛ්‍යා රටා", "Number Patterns", "G5-MAT-C02", ["G5-MAT-U004", "G5-MAT-U031"], "APT-PAT", "B-MAT-PATTERNS"),
    (4, "අඩු කිරීම", "Subtraction", "G5-MAT-C07", ["G5-MAT-U005"], "MAT-OPS", "B-MAT-NUMBER-OPS"),
    (5, "භාග", "Fractions", "G5-MAT-C03", ["G5-MAT-U006"], "MAT-FRC", "B-MAT-FRACTIONS-REMAINDER"),
    (6, "ගුණ කිරීම", "Multiplication", "G5-MAT-C08", ["G5-MAT-U007", "G5-MAT-U021", "G5-MAT-U026"], "MAT-OPS", "B-MAT-NUMBER-OPS"),
    (7, "කාලය", "Time", "G5-MAT-C14", ["G5-MAT-U008", "G5-MAT-U022"], "MAT-TIM", "B-MAT-MEASURE"),
    (8, "බෙදීම", "Division", "G5-MAT-C09", ["G5-MAT-U009", "G5-MAT-U023", "G5-MAT-U028"], "MAT-OPS", "B-MAT-NUMBER-OPS"),
    (9, "දිග හා දුර", "Length and Distance", "G5-MAT-C11", ["G5-MAT-U010", "G5-MAT-U019"], "MAT-LEN", "B-MAT-MEASURE"),
    (10, "මුදල්", "Money", "G5-MAT-C15", ["G5-MAT-U011", "G5-MAT-U020"], "MAT-MON", "B-MAT-NUMBER-OPS"),
    (11, "පරිමාව හා ධාරිතාව", "Volume and Capacity", "G5-MAT-C13", ["G5-MAT-U013", "G5-MAT-U027"], "MAT-MAS", "B-MAT-MEASURE"),
    (12, "බර මැනීම", "Measuring Weight", "G5-MAT-C12", ["G5-MAT-U014", "G5-MAT-U030"], "MAT-MAS", "B-MAT-MEASURE"),
    (13, "හැඩතල හා ඝන වස්තු", "Shapes and Solid Objects", "G5-MAT-C16", ["G5-MAT-U016"], "MAT-GEO", "B-MAT-SHAPES-REVIEW"),
    (14, "දිශා", "Directions", "G5-MAT-C18", ["G5-MAT-U025"], "APT-DIR", "B-MAT-DIRECTIONS"),
    (15, "දශම", "Decimals", "G5-MAT-C05", ["G5-MAT-U018"], "MAT-FRC", "B-MAT-DECIMALS"),
    (16, "රෝම සංඛ්‍යාංක", "Roman Numerals", "G5-MAT-C04", ["G5-MAT-U029"], "MAT-NUM", "B-MAT-SYMBOLS"),
]

SIN = [
    (1, "පිල්ලම් හඳුනාගනිමු", "Identifying Vowel Signs", "MAPPED_DRAFT", "G5-SIN-C03-L01-K01", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (2, "විරාම ලක්ෂණ හඳුනාගනිමු", "Identifying Punctuation Marks", "MAPPED_DRAFT", "G5-SIN-C03-L01-K03", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (3, "තේරවිලි", "Riddles", "MAPPED_DRAFT", "G5-SIN-C01-L05-K02", "B-SIN-VOCABULARY"),
    (4, "සමානාර්ථ පද (සමාන පද)", "Synonyms", "MAPPED_DRAFT", "G5-SIN-C01-L05-K03", "B-SIN-VOCABULARY"),
    (5, "විරුද්ධාර්ථ පද (විරුද්ධ පද)", "Antonyms", "MAPPED_DRAFT", "G5-SIN-C01-L05-K04", "B-SIN-VOCABULARY"),
    (6, "යුගල පද", "Paired Words", "MAPPED_DRAFT", "G5-SIN-C01-L05-K06", "B-SIN-VOCABULARY"),
    (7, "ප්‍රස්තාව පිරුළු", "Proverbs", "MAPPED_DRAFT", "G5-SIN-C01-L05-K09", "B-SIN-VOCABULARY"),
    (8, "ඉඟි වැකි", "Idiomatic Expressions", "MAPPED_DRAFT", "G5-SIN-C01-L05-K08", "B-SIN-VOCABULARY"),
    (9, "ආප්තෝපදේශ", "Wise Sayings and Maxims", "MAPPED_DRAFT", "G5-SIN-C01-L05-K07", "B-SIN-VOCABULARY"),
    (10, "උපමා", "Similes", "MAPPED_DRAFT", "G5-SIN-C01-L05-K05", "B-SIN-VOCABULARY"),
    (11, "පොදුලිංග ලිපි", "Common-Gender Terms", "BLOCKED", None, "B-SIN-BLOCKED"),
    (12, "ආඛ්‍යාති පද", "Verbs and Predicates", "BLOCKED", None, "B-SIN-BLOCKED"),
    (13, "ආරාධනා පත්‍ර", "Invitation Letters", "MAPPED_DRAFT", "G5-SIN-C03-L06-K04", "B-SIN-WRITING"),
    (14, "ස්ත්‍රී ලිංග හා පුරුෂ ලිංග පද", "Feminine and Masculine Nouns", "MAPPED_DRAFT", "G5-SIN-C03-L10-K06", "B-SIN-GRAMMAR-REVIEW"),
    (15, "ඒකවචන හා බහුවචන පද", "Singular and Plural Words", "MAPPED_DRAFT", "G5-SIN-C03-L10-K07", "B-SIN-GRAMMAR-REVIEW"),
    (16, "අක්ෂර වින්‍යාසය", "Spelling and Orthography", "MAPPED_DRAFT", "G5-SIN-C04-L10-O08", "B-SIN-SPELLING"),
    (17, "න, ණ යෙදීම", "Usage of න and ණ", "MAPPED_DRAFT", "G5-SIN-C03-L10-K14", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (18, "ල, ළ යෙදීම", "Usage of ල and ළ", "MAPPED_DRAFT", "G5-SIN-C03-L10-K14", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (19, "ස, ශ, ෂ යෙදීම", "Usage of ස, ශ and ෂ", "MAPPED_DRAFT", "G5-SIN-C03-L10-K15", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (20, "අල්පප්‍රාණ සහ මහාප්‍රාණ අක්ෂර", "Unaspirated and Aspirated Consonants", "MAPPED_DRAFT", "G5-SIN-C03-L10-K16", "B-SIN-ORTHOGRAPHY-REVIEW"),
    (21, "නාම පද", "Nouns", "MAPPED_DRAFT", "G5-SIN-C03-L10-K04", "B-SIN-GRAMMAR-REVIEW"),
    (22, "ක්‍රියා පද", "Verbs", "MAPPED_DRAFT", "G5-SIN-C04-L10-O02", "B-SIN-GRAMMAR-REVIEW"),
    (23, "උක්ත සහ අනුක්ත පද", "Subject and Non-subject Forms", "MAPPED_DRAFT", "G5-SIN-C04-L10-O06", "B-SIN-SENTENCES"),
    (24, "සරල වාක්‍ය", "Simple Sentences", "MAPPED_DRAFT", "G5-SIN-C04-L10-O01", "B-SIN-SENTENCES"),
    (25, "ද / ත / ස / හා / සහ යෙදුණු වාක්‍ය රටා", "Sentence Patterns Using ද, ත, ස, හා and සහ", "MAPPED_DRAFT", "G5-SIN-C04-L10-O07", "B-SIN-ORTHOGRAPHY-REVIEW"),
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def base(area_id: str, subject: str, number: int, name_si: str, name_en: str, batch: str) -> dict:
    subject_names = {
        "ENV": ("පරිසරය ආශ්‍රිත ක්‍රියාකාරකම්", "Environmental Studies"),
        "MAT": ("ගණිතය", "Mathematics"),
        "SIN": ("සිංහල", "Sinhala"),
    }
    subject_si, subject_en = subject_names[subject]
    return {
        "area_id": area_id,
        "subject": subject,
        "subject_name_si": subject_si,
        "subject_name_en": subject_en,
        "supplied_number": number,
        "name_si": name_si,
        "name_en": name_en,
        "outcome_or_competency": None,
        "atomic_skill_ids": [],
        "candidate_node_ids": [],
        "source_document_id": None,
        "source_document_title": None,
        "evidence_locator": None,
        "related_universal_skill_ids": [],
        "mapping_status": "MAPPED_DRAFT",
        "content_status": "NONE",
        "blocker_or_review_note": "",
        "evidence_checked": "",
        "proposed_batch_id": batch,
        "human_review_gate": GATE,
        "implementation_blocked": True,
        "implementation_block_reason": (
            "No new learner content or game is authorized. The mobile vertical-slice report is "
            "partial and not ready for the next phase, and no passing research-pilot-readiness "
            "report exists."
        ),
    }


def env_rows(nodes: list[dict]) -> list[dict]:
    lessons = {
        n["curriculum_node_id"]: n
        for n in nodes
        if n["subject"] == "ENV" and n["node_type"] == "lesson" and n["source_id"] == "SRC-G5-ENV-TG-01"
    }
    comps = [
        n
        for n in nodes
        if n["subject"] == "ENV" and n["node_type"] == "competency" and n["source_id"] == "SRC-G5-ENV-TG-01"
    ]
    ordered = sorted(lessons.values(), key=lambda n: int(n["source_page_from"]))
    rows = []
    gloss_notes = {
        2: "Trace English gloss is 'We Sri Lankans', which is not the supplied English name.",
        7: "Trace lesson Sinhala is 'ආරක්ෂාව හා පරිස්සම' (හා). The supplied name uses සහ. Prototype game G5-ENV-G07 is titled 'ආරක්ෂාව සහ රැකවරණය', which matches neither string.",
        9: "Trace English gloss is 'Ways of Making Work Easier', which is not the supplied English name.",
        13: "Prototype game G5-ENV-G11 is titled 'පෘථිවිය හා අහස' and is not the trace lesson title.",
        15: "Trace lesson Sinhala is 'මිනිසා හා තොරතුරු' (හා). The supplied name uses සහ.",
        16: "Trace English gloss is 'Stories of Our Past', which is not the supplied English name.",
    }
    for number, name_si, name_en in ENV:
        lesson = lessons[f"G5-ENV-U{number:02d}"]
        start = int(lesson["source_page_from"])
        later = [int(item["source_page_from"]) for item in ordered if int(item["source_page_from"]) > start]
        end = (later[0] - 1) if later else int(lesson["source_page_to"])
        mine = [c for c in comps if start <= int(c["source_page_from"]) <= end]
        low = [c["curriculum_node_id"] for c in mine if c["extraction_confidence"] != "high"]
        row = base(f"G5-AREA-ENV-{number:02d}", "ENV", number, name_si, name_en, "B-ENV-VERIFY")
        row["candidate_node_ids"] = [lesson["curriculum_node_id"], *[c["curriculum_node_id"] for c in mine]]
        row["source_document_id"] = "SRC-G5-ENV-TG-01"
        row["source_document_title"] = "පරිසරය ආශ්‍රිත ක්‍රියාකාරකම් - විෂය නිර්දේශය හා ගුරු මාර්ගෝපදේශය"
        row["evidence_locator"] = (
            f"printed pages {lesson['source_page_from']}-{lesson['source_page_to']} "
            f"({lesson['source_page_basis']}); lesson {lesson['curriculum_node_id']}"
        )
        row["related_universal_skill_ids"] = {
            1: ["ENV-CIV"],
            2: ["ENV-CIV"],
            3: ["ENV-BIO"],
            4: ["ENV-BIO"],
            5: ["ENV-PHY", "ENV-CIV"],
            6: ["ENV-HLT"],
            7: ["ENV-HLT"],
            8: ["ENV-PHY"],
            9: ["ENV-PHY"],
            10: ["ENV-AGR"],
            11: ["ENV-CIV"],
            12: ["ENV-CIV"],
            13: ["ENV-GEO"],
            14: ["ENV-CIV"],
            15: ["ENV-CIV"],
            16: ["ENV-CIV"],
        }[number]
        row["mapping_status"] = "MAPPED_DRAFT"
        row["outcome_or_competency"] = {
            "kind": "lesson",
            "node_id": lesson["curriculum_node_id"],
            "official_outcome_code": None,
            "text_si": lesson["text_primary"],
            "text_en_gloss": lesson.get("text_en") or "",
            "extraction_confidence": lesson["extraction_confidence"],
            "verification_status": lesson["verification_status"],
            "adopted_as_atomic_skill": False,
        }
        extra = gloss_notes.get(number, "")
        row["blocker_or_review_note"] = (
            "The high-confidence lesson title is the draft mapping. Competency text on the unit "
            f"opening page is extraction_confidence=low and verification_status=needs_review. "
            f"{len(low)} competency rows were checked and are not outcome sentences. "
            "Draft universal parents are coarse thematic crosswalk labels, not coverage. "
            f"No atomic skill is derived. {extra} "
            "Supplementary activity-book sources were inspected in the source registry and are "
            "not official outcome evidence. Prototype games.jsonl rows are not learner content."
        ).strip()
        row["evidence_checked"] = (
            "data/curriculum/grade5-curriculum-trace/v1/curriculum_nodes.jsonl lesson and "
            f"competency rows for {lesson['curriculum_node_id']}; "
            "data/curriculum/grade5-curriculum-trace/v1/curriculum_sources.jsonl "
            "SRC-G5-ENV-TG-01 and SRC-G5-ENV-ACT-*; "
            "data/gamification/grade5-curriculum-game-dataset/v2/games.jsonl prototype rows."
        )
        rows.append(row)
    return rows


def mat_rows(nodes: dict[str, dict]) -> list[dict]:
    rows = []
    for number, name_si, name_en, competency_id, lessons, universal, batch in MAT:
        competency = nodes[competency_id]
        row = base(f"G5-AREA-MAT-{number:02d}", "MAT", number, name_si, name_en, batch)
        row["candidate_node_ids"] = [competency_id, *lessons]
        row["source_document_id"] = "SRC-G5-MAT-TG-01"
        row["source_document_title"] = "ගණිතය - ගුරු මාර්ගෝපදේශය - 5 ශ්‍රේණිය"
        row["related_universal_skill_ids"] = [universal]
        row["evidence_locator"] = (
            f"printed page {competency['source_page_from']} ({competency['source_page_basis']}); "
            f"competency {competency_id}; 2020 lesson nodes {', '.join(lessons)}"
        )
        row["evidence_checked"] = (
            "SRC-G5-MAT-TG-01 competency, competency-level, lesson, and learning-outcome nodes; "
            "SRC-G5-MAT-TB-01 parallel lesson titles were not used as a second outcome; "
            "SRC-G5-MAT-TG-02 (2009) was not merged. Draft crosswalk "
            "data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl."
        )
        row["mapping_status"] = "MAPPED_DRAFT"
        if competency["extraction_confidence"] != "high":
            raise SystemExit(f"{competency_id} is not high confidence")
        row["outcome_or_competency"] = {
            "kind": "competency",
            "node_id": competency_id,
            "official_outcome_code": None,
            "text_si": competency["text_primary"],
            "text_en_gloss": competency.get("text_en") or "",
            "extraction_confidence": competency["extraction_confidence"],
            "verification_status": competency["verification_status"],
            "adopted_as_atomic_skill": False,
        }
        row["blocker_or_review_note"] = (
            "High-confidence 2020 competency text is recorded as a draft mapping. "
            "It is not human-reviewed and it is not an atomic skill. Lesson-page learning "
            "outcomes under this competency stay unadopted where their extraction confidence "
            "is below high. The 2009 teacher's guide is a separate sequence. "
            f"Draft universal parent {universal} does not prove coverage."
        )
        if number == 5:
            row["atomic_skill_ids"] = ["G5-MAT-C03-L01-O01"]
            row["content_status"] = "IMPLEMENTED_UNREVIEWED"
            row["candidate_node_ids"].extend(
                ["G5-MAT-C03-L01", "G5-MAT-C03-L01-O01", "G5-MAT-C03-L01-O02", "G5-MAT-C03-L01-O03"]
            )
            row["blocker_or_review_note"] += (
                " Only G5-MAT-C03-L01-O01 has a skill package and the existing half-set template. "
                "Sibling nodes O02 and O03 have no skill package. Trace O01 is medium confidence "
                "and prints a spaced fraction; the curriculum slice transcribes the stacked "
                "fraction as 1/2 and remains pending human review. MAT-FRC also parents decimals, "
                "so that universal ID does not prove this area is covered."
            )
        if number == 11:
            row["blocker_or_review_note"] += (
                " The draft crosswalk parents G5-MAT-C13 to MAT-MAS (mass). That parent "
                "contradicts this volume-and-capacity competency and is not accepted."
            )
        if number == 15:
            row["blocker_or_review_note"] += (
                " MAT-FRC is a coarse fractions-and-decimals parent. It does not show that "
                "decimals have content or a separate approved mapping."
            )
        if number in {1, 16}:
            row["blocker_or_review_note"] += (
                " MAT-NUM is shared by the numbers competency and the Roman-numerals competency. "
                "One universal ID does not cover both supplied areas."
            )
        if number == 3:
            row["blocker_or_review_note"] += (
                " APT-PAT is a coarse pattern node, not a Grade 5 outcome."
            )
        if number == 13:
            row["blocker_or_review_note"] += (
                " Supplied Sinhala 'හැඩතල හා ඝන වස්තු' differs from lesson title 'හැඩ හා ඝන වස්තු' "
                "(G5-MAT-U016, printed pages 84-91). Adjacent competency G5-MAT-C17 stays outside "
                "this area. Draft universal parent MAT-GEO is not coverage."
            )
        if number == 14:
            row["blocker_or_review_note"] += (
                " APT-DIR is a coarse aptitude node, not a Grade 5 outcome."
            )
        rows.append(row)
    return rows


def sin_rows(nodes: dict[str, dict], terms: list[dict]) -> list[dict]:
    term_text = "\n".join(json.dumps(term, ensure_ascii=False) for term in terms)
    node_text = "\n".join(json.dumps(node, ensure_ascii=False) for node in nodes.values())
    rows = []
    notes = {
        1: "No node contains 'පිල්ලම්'. The draft locator is the high-confidence content point 'පිලි සහිත අකුරු' on printed page 6.",
        2: "The draft locator says 'විරාම ලකුණු' on printed page 6. Learning outcomes that say 'විරාම ලක්ෂණ' remain low confidence.",
        3: "The draft locator is content point 'තේරවිලි' on printed page 8. Outcome G5-SIN-C01-L05-O02 remains low confidence.",
        4: "The draft locator is 'සමානාර්ථ පද' on printed page 8. The supplied parenthetical 'සමාන පද' has no matching node.",
        5: "The draft locator is 'විරුද්ධාර්ථ පද' on printed page 8. The supplied parenthetical 'විරුද්ධ පද' has no matching node.",
        6: "The draft locator is 'යුගල පද' on printed page 8. Low-confidence outcome G5-SIN-C01-L05-O03 bundles several categories and is not the mapping.",
        7: "The draft locator is 'ප්‍රස්තාව පිරුළු' on printed page 8. The bundled low-confidence outcome is not the mapping.",
        8: "The draft locator is 'රූඪි/ඉඟි වැකි' on printed page 8, which is wider than the supplied name.",
        9: "The draft locator is 'ආප්තෝපදේශ' on printed page 8. The bundled low-confidence outcome is not the mapping.",
        10: "The draft locator is 'උපමා' on printed page 8.",
        13: "The draft locator is 'ආරාධනා පත්‍ර' on printed page 9. Outcomes G5-SIN-C03-L06-O01 and G5-SIN-C04-L06-O04 remain low confidence.",
        14: "The draft locator is 'ස්ත්‍රීලිංග සහ පුරුෂලිංග නාම පද' on printed page 10. That spelling differs from the supplied name.",
        15: "The draft locator is 'ඒකවචන හා බහුවචන නාමපද' on printed page 10. It adds නාම.",
        17: "The draft locator is the combined content point 'න,ණ,ල,ළ යෙදීම' on printed page 10. No separate න/ණ outcome was invented.",
        18: "The draft locator is the same combined content point 'න,ණ,ල,ළ යෙදීම'. No separate ල/ළ outcome was invented.",
        19: "The draft locator is 'ස, ශ, ෂ යෙදීම' on printed page 10. It is a content label, not a separate outcome sentence.",
        20: "The draft locator is 'අල්පප්‍රාණ, මහාප්‍රාණ භාවිතය' on printed page 10. The writing point on printed page 11 says 'මහප්‍රාණ' without ආ.",
        21: "The draft locator is 'නාම පද' on printed page 10. Narrower L10 outcomes are not separate skill packages.",
        22: "No content point is titled 'ක්‍රියා පද'. The draft locator is high-confidence outcome G5-SIN-C04-L10-O02 on printed page 264, which states how a verb is used.",
        25: "The draft locator is outcome G5-SIN-C04-L10-O07, whose particle list is ද/ත්/යි/හා/සහ. The supplied list is ද / ත / ස / හා / සහ.",
    }
    for number, name_si, name_en, status, outcome_id, batch in SIN:
        row = base(f"G5-AREA-SIN-{number:02d}", "SIN", number, name_si, name_en, batch)
        row["source_document_id"] = "SRC-G5-SIN-TG-01"
        row["source_document_title"] = "මව්බස - ගුරු මාර්ගෝපදේශය - 5 වන ශ්‍රේණිය"
        row["mapping_status"] = status
        row["related_universal_skill_ids"] = []
        if status == "BLOCKED":
            needle = "පොදුලිංග" if number == 11 else "ආඛ්‍යාත"
            row["evidence_locator"] = "no matching Grade 5 node or term"
            row["blocker_or_review_note"] = (
                f"No curriculum node or term contains '{needle}'. "
                "No Grade 5 outcome was invented and the area is not omitted. "
                "Grade 5 and Sinhala-medium scope are unchanged."
            )
            row["evidence_checked"] = (
                f"String '{needle}' present in curriculum_nodes.jsonl: {needle in node_text}. "
                f"Present in curriculum_terms.jsonl: {needle in term_text}. "
                "Sources checked: SRC-G5-SIN-TG-01 and SRC-G5-SIN-TB-01."
            )
        elif outcome_id:
            outcome = nodes[outcome_id]
            if outcome["extraction_confidence"] != "high":
                raise SystemExit(f"{outcome_id} is not high confidence")
            row["outcome_or_competency"] = {
                "kind": outcome["node_type"],
                "node_id": outcome_id,
                "official_outcome_code": None,
                "text_si": outcome["text_primary"],
                "text_en_gloss": outcome.get("text_en") or "",
                "extraction_confidence": outcome["extraction_confidence"],
                "verification_status": outcome["verification_status"],
                "adopted_as_atomic_skill": False,
            }
            row["candidate_node_ids"] = [outcome_id]
            row["evidence_locator"] = (
                f"printed page {outcome['source_page_from']} ({outcome['source_page_basis']}); "
                f"{outcome_id}"
            )
            caveat = notes.get(number, "")
            row["blocker_or_review_note"] = (
                "The cited Grade 5 trace text is the draft mapping. "
                "It is not human-reviewed and it is not an atomic skill package. "
                f"{caveat} No learner content exists."
            ).strip()
            row["evidence_checked"] = (
                "SRC-G5-SIN-TG-01 learning-outcome and content-point nodes; "
                "textbook lesson titles in SRC-G5-SIN-TB-01 do not use this category name."
            )
        else:
            raise SystemExit(f"{row['area_id']} has no draft mapping")
        rows.append(row)
    return rows


def main() -> None:
    nodes = {node["curriculum_node_id"]: node for node in load_jsonl(TRACE)}
    terms = load_jsonl(TERMS)
    rows = [*env_rows(list(nodes.values())), *mat_rows(nodes), *sin_rows(nodes, terms)]
    if len(rows) != 57:
        raise SystemExit(f"expected 57 rows, got {len(rows)}")
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
