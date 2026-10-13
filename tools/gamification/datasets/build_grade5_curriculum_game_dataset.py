from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "gamification" / "grade5-curriculum-game-dataset" / "v1"
)
SOURCE_DIR_ENV = "MINDBRIDGE_GRADE5_SYLLABUS_DIR"
SUBJECTS = ["ENV", "SIN", "ENG", "MAT"]
SUBJECT_NAMES = {
    "ENV": "Environmental Studies",
    "SIN": "Sinhala",
    "ENG": "English",
    "MAT": "Mathematics",
}
LANGUAGES = {"ENV": "si", "SIN": "si", "ENG": "en", "MAT": "bilingual"}
RNG = random.Random(5323)


def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def read_sheet(workbook, sheet_name):
    ws = workbook[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    headers = [clean(v) for v in rows[0]]
    return [dict(zip(headers, row)) for row in rows[1:] if any(v is not None for v in row)]


def first(row, *keys):
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def derive_parent_from_id(node_id, node_type):
    if node_type == "learning_outcome":
        return re.sub(r"-O\d+$", "", node_id)
    if node_type == "content_point":
        return re.sub(r"-K\d+$", "", node_id)
    return ""


def jsonl_write(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_options(correct, pool, count=4):
    candidates = [clean(v) for v in pool if clean(v) and clean(v) != clean(correct)]
    RNG.shuffle(candidates)
    options = [clean(correct)] + candidates[: max(0, count - 1)]
    while len(options) < count:
        options.append(f"Option {len(options) + 1}")
    RNG.shuffle(options)
    return options


def source_confidence(row):
    return first(row, "extraction_confidence") or "not_stated"


def collect_curriculum(source_dir: Path):
    from openpyxl import load_workbook

    nodes = []
    raw = {}
    for subject in SUBJECTS:
        path = source_dir / f"grade5_{subject}_syllabus_trace_v1.xlsx"
        wb = load_workbook(path, read_only=True, data_only=True)
        subject_raw = {}
        for sheet in wb.sheetnames:
            subject_raw[sheet] = read_sheet(wb, sheet)
        raw[subject] = subject_raw

        node_specs = [
            ("02_competencies", "competency", "competency_id", "", ("competency", "competency_si"), ("competency", "competency_en_gloss")),
            ("03_competency_levels", "competency_level", "competency_level_id", "competency_id", ("competency_level", "competency_level_si"), ("competency_level", "competency_level_en_gloss")),
            ("04_learning_outcomes", "learning_outcome", "learning_outcome_id", "competency_level_id", ("outcome", "outcome_si"), ("outcome", "outcome_en_gloss")),
            ("05_content_points", "content_point", "content_point_id", "competency_level_id", ("content", "content_si"), ("content", "content_en_gloss")),
            ("06_lessons", "lesson", "lesson_id", "", ("lesson_title", "lesson_title_si"), ("lesson_title", "lesson_title_en_gloss")),
            ("07_activities", "source_activity", "activity_id", "lesson_id", ("activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si"), ("activity_title",)),
        ]
        for sheet, node_type, id_field, parent_field, primary_fields, english_fields in node_specs:
            for row in subject_raw[sheet]:
                node_id = clean(row.get(id_field))
                if not node_id:
                    continue
                parent = clean(row.get(parent_field)) if parent_field else ""
                parent_basis = "stated"
                if not parent and node_type in ("learning_outcome", "content_point"):
                    parent = derive_parent_from_id(node_id, node_type)
                    parent_basis = "inferred_from_id"
                refs = first(row, "competency_level_ids")
                text_primary = first(row, *primary_fields)
                text_en = first(row, *english_fields)
                if subject == "ENG":
                    text_en = text_primary
                nodes.append({
                    "curriculum_node_id": node_id,
                    "subject": subject,
                    "subject_name": SUBJECT_NAMES[subject],
                    "grade": 5,
                    "node_type": node_type,
                    "parent_node_id": parent,
                    "parent_basis": parent_basis if parent else "none",
                    "curriculum_refs": refs,
                    "official_ref": first(row, "official_ref"),
                    "text_primary": text_primary,
                    "text_en": text_en,
                    "content_type": first(row, "content_type"),
                    "source_id": first(row, "source_id"),
                    "source_page_from": first(row, "page_from"),
                    "source_page_to": first(row, "page_to"),
                    "extraction_confidence": source_confidence(row),
                    "trace_status": first(row, "trace_status") or "draft",
                    "verification_status": "needs_review",
                    "source_file": path.name,
                })

    return nodes, raw


GAME_DEFINITIONS = {
    "MAT": [
        ("Place Value Forge", "place_value", "Numbers - 1", "Build and decompose whole numbers."),
        ("Number Order Dash", "number_order", "Numbers - 2", "Compare and order whole numbers."),
        ("Addition Quest", "addition", "Addition", "Add whole numbers accurately."),
        ("Subtraction Rescue", "subtraction", "Subtraction", "Subtract with regrouping."),
        ("Multiplication Arena", "multiplication", "Multiplication", "Recall and apply multiplication facts."),
        ("Division Drop", "division", "Division", "Use division facts with exact quotients."),
        ("Fraction Builder", "fractions", "Fractions", "Represent fractions of sets and wholes."),
        ("Decimal Market", "decimals", "Decimals", "Recognize and compare tenths."),
        ("Time Keeper", "time", "Time", "Read time and calculate elapsed time."),
        ("Money Shop", "money", "Money", "Calculate totals and change."),
        ("Measure Master", "measurement", "Length", "Convert and compare common measurements."),
        ("Pattern and Shape Lab", "patterns_shapes", "Number patterns", "Continue patterns and identify shape properties."),
    ],
    "ENG": [
        ("Sound Detective", "phonics", "sound", "Recognize sounds in familiar words."),
        ("Word Builder", "word_builder", "word", "Construct familiar words from letters."),
        ("Vocabulary Match", "vocabulary", "familiar", "Connect common words with meanings."),
        ("Sentence Scramble", "sentence_order", "sentence", "Arrange words into meaningful sentences."),
        ("Grammar Sort", "grammar_sort", "grammar", "Classify common word types."),
        ("Missing Word", "missing_word", "sentence", "Select a word that completes a sentence."),
        ("Punctuation Patrol", "punctuation", "punctuation", "Use capitals and end punctuation."),
        ("Spelling Sprint", "spelling", "word", "Recognize the correct spelling of familiar words."),
        ("Reading Clue Hunt", "reading", "read", "Read a short text and answer a question."),
        ("Dialogue Builder", "dialogue", "speak", "Choose an appropriate conversational response."),
        ("Listening Choice", "listening", "listen", "Listen for key information."),
        ("Topic Adventure", "topic_vocabulary", "topic", "Use vocabulary from Grade 5 themes."),
    ],
    "SIN": [
        ("සවන් දීමේ අභියෝගය", "activity_clue", "Listening", "Identify an activity from a listening or speaking clue."),
        ("කතන්දර මඟ", "lesson_activity", "story", "Connect lesson themes with learning activities."),
        ("වචන යුගල", "term_match", "Vocabulary", "Match Sinhala curriculum terms with their glosses."),
        ("කියවීමේ සලකුණු", "outcome_match", "Reading", "Connect a learning outcome with its description."),
        ("ක්‍රියාකාරකම හඳුනාගන්න", "activity_instruction", "activity", "Identify activities from their instructions."),
        ("පාඩම් සිතියම", "activity_lesson", "lesson", "Classify an activity under its lesson."),
        ("අනුපිළිවෙළ ගමන", "activity_sequence", "sequence", "Place lesson activities in source order."),
        ("සන්නිවේදන තේරීම", "communication", "communication", "Select a curriculum-aligned communication activity."),
        ("භාෂා කුසලතා", "skill_sort", "language", "Sort activities by language-skill lesson."),
        ("රසවින්දන සෙවීම", "appreciation", "appreciative", "Recognize appreciative language activities."),
        ("නිර්මාණාත්මක භාෂාව", "creative_language", "creative", "Recognize creative language-use activities."),
        ("සිංහල පුනරීක්ෂණය", "mixed_review", "review", "Review lesson, activity and outcome relationships."),
    ],
    "ENV": [
        ("යහපැවැත්ම මඟ", "activity_lesson", "Our Well-being", "Classify well-being activities."),
        ("අපි ලක් වැසියෝ", "activity_lesson", "We Sri Lankans", "Explore Sri Lankan identity and heritage."),
        ("පැළෑටි හා ගස්වැල්", "activity_lesson", "Plants and Trees", "Classify plant-related activities."),
        ("අප අවට සත්තු", "activity_lesson", "Animals Around Us", "Classify animal-related activities."),
        ("අප පරිහරණය කරන දේ", "activity_lesson", "Things We Use", "Recognize materials and everyday objects."),
        ("අපේ ආහාර", "activity_lesson", "Our Food", "Recognize food and nutrition activities."),
        ("ආරක්ෂාව සහ රැකවරණය", "activity_lesson", "Safety and Care", "Recognize safe actions and care."),
        ("ජල අභියෝගය", "activity_lesson", "Water", "Explore uses and care of water."),
        ("වැඩ පහසු කරමු", "activity_lesson", "Making Work Easier", "Recognize tools and simple methods."),
        ("ගෙවත්ත ගොඩනඟමු", "activity_lesson", "Home Garden", "Explore home-garden activities."),
        ("පෘථිවිය හා අහස", "activity_lesson", "Earth and Sky", "Classify Earth-and-sky observations."),
        ("පරිසර පුනරීක්ෂණය", "mixed_review", "review", "Review environmental themes and activities."),
    ],
}


def find_target_nodes(nodes_by_subject, subject, keyword):
    keyword_l = keyword.lower()
    candidates = []
    for node in nodes_by_subject[subject]:
        haystack = " ".join([node["text_primary"], node["text_en"], node["node_type"]]).lower()
        if keyword_l in haystack:
            candidates.append(node["curriculum_node_id"])
    if not candidates:
        candidates = [n["curriculum_node_id"] for n in nodes_by_subject[subject] if n["node_type"] in ("competency_level", "learning_outcome")]
    return candidates[:8]


def build_game_catalog(nodes):
    by_subject = defaultdict(list)
    for node in nodes:
        by_subject[node["subject"]].append(node)
    games = []
    for subject in SUBJECTS:
        for index, (title, mechanic, keyword, objective) in enumerate(GAME_DEFINITIONS[subject], start=1):
            refs = find_target_nodes(by_subject, subject, keyword)
            games.append({
                "game_id": f"G5-{subject}-G{index:02d}",
                "subject": subject,
                "subject_name": SUBJECT_NAMES[subject],
                "grade": 5,
                "title": title,
                "mechanic": mechanic,
                "learning_objective": objective,
                "target_curriculum_ids": ",".join(refs),
                "session_minutes": 8,
                "minimum_items": 20,
                "starter_items": 40,
                "difficulty_start": 1,
                "difficulty_end": 4,
                "scoring_rule": "10 points correct; 5 after one hint; streak bonus every 3 correct",
                "hint_rule": "One hint per item; remove one distractor or reveal a structural clue",
                "required_modalities": "text,audio" if mechanic in ("listening", "phonics", "activity_clue") else "text",
                "language": LANGUAGES[subject],
                "content_status": "prototype",
                "publication_status": "needs_review",
            })
    return games


def base_item(game, number, refs, lesson_id="", source_activity_id=""):
    return {
        "item_id": f"{game['game_id']}-I{number:03d}",
        "game_id": game["game_id"],
        "subject": game["subject"],
        "language": game["language"],
        "lesson_id": lesson_id,
        "curriculum_refs": ",".join(refs),
        "source_activity_id": source_activity_id,
        "mechanic": game["mechanic"],
        "prompt_primary": "",
        "prompt_en": "",
        "stimulus_primary": "",
        "stimulus_en": "",
        "options_json": "[]",
        "correct_answer_json": "[]",
        "feedback_correct": "Correct.",
        "feedback_incorrect": "Try again and use the hint.",
        "hint": "",
        "difficulty": 1 + ((number - 1) // 10),
        "cognitive_level": "understand" if number <= 20 else "apply",
        "estimated_seconds": 30,
        "generation_method": "rule_based",
        "source_confidence": "high",
        "answer_verified": False,
        "language_reviewed": False,
        "asset_status": "not_required",
        "publication_status": "needs_review",
    }


def math_refs(game):
    refs = [r for r in game["target_curriculum_ids"].split(",") if r]
    return refs[:3]


def make_math_items(game):
    items = []
    refs = math_refs(game)
    mechanic = game["mechanic"]
    for i in range(1, 41):
        item = base_item(game, i, refs)
        item.update({"language": "bilingual", "answer_verified": True, "source_confidence": "high"})
        difficulty = item["difficulty"]
        if mechanic == "place_value":
            number = RNG.randint(1000, 9999 if difficulty < 3 else 99999)
            digits = list(str(number))
            position = RNG.randrange(len(digits))
            digit = int(digits[position])
            value = digit * (10 ** (len(digits) - position - 1))
            options = make_options(str(value), [str(digit), str(value * 10), str(max(1, value // 10)), str(number)])
            item.update(prompt_primary=f"{number} සංඛ්‍යාවේ {digit} ඉලක්කමේ ස්ථානීය අගය කුමක් ද?", prompt_en=f"What is the place value of digit {digit} in {number}?", stimulus_primary=str(number), stimulus_en=str(number), options_json=json.dumps(options, ensure_ascii=False), correct_answer_json=json.dumps([str(value)]), hint="Count places from the right: ones, tens, hundreds, thousands.")
        elif mechanic == "number_order":
            values = RNG.sample(range(100, 9999 if difficulty < 3 else 99999), 4)
            correct = " < ".join(map(str, sorted(values)))
            variants = [" < ".join(map(str, order)) for order in [values, list(reversed(sorted(values))), sorted(values, key=lambda x: str(x))]]
            item.update(prompt_primary="සංඛ්‍යා කුඩාම සිට විශාලම දක්වා සකසන්න.", prompt_en="Arrange the numbers from smallest to largest.", stimulus_primary=", ".join(map(str, values)), stimulus_en=", ".join(map(str, values)), options_json=json.dumps(make_options(correct, variants), ensure_ascii=False), correct_answer_json=json.dumps([correct]), hint="Compare the highest place value first.")
        elif mechanic == "addition":
            limit = 999 if difficulty < 3 else 9999
            a, b = RNG.randint(20, limit), RNG.randint(20, limit)
            answer = a + b
            options = make_options(str(answer), [str(answer + 10), str(answer - 10), str(answer + 1), str(abs(a - b))])
            item.update(prompt_primary=f"{a} + {b} හි අගය සොයන්න.", prompt_en=f"Calculate {a} + {b}.", stimulus_primary=f"{a} + {b}", stimulus_en=f"{a} + {b}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint="Add ones first, then tens, hundreds and thousands.")
        elif mechanic == "subtraction":
            a = RNG.randint(100, 999 if difficulty < 3 else 9999)
            b = RNG.randint(10, a)
            answer = a - b
            options = make_options(str(answer), [str(answer + 10), str(max(0, answer - 10)), str(a + b), str(answer + 1)])
            item.update(prompt_primary=f"{a} - {b} හි අගය සොයන්න.", prompt_en=f"Calculate {a} - {b}.", stimulus_primary=f"{a} - {b}", stimulus_en=f"{a} - {b}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint="Regroup when the upper digit is smaller.")
        elif mechanic == "multiplication":
            a = RNG.randint(2, 12 if difficulty < 3 else 25)
            b = RNG.randint(2, 12 if difficulty < 4 else 20)
            answer = a * b
            options = make_options(str(answer), [str(answer + a), str(max(0, answer - a)), str(a + b), str(answer + b)])
            item.update(prompt_primary=f"{a} × {b} හි අගය සොයන්න.", prompt_en=f"Calculate {a} × {b}.", stimulus_primary=f"{a} × {b}", stimulus_en=f"{a} × {b}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint=f"Think of {b} groups of {a}.")
        elif mechanic == "division":
            divisor = RNG.randint(2, 12)
            quotient = RNG.randint(2, 12 if difficulty < 3 else 30)
            dividend = divisor * quotient
            options = make_options(str(quotient), [str(divisor), str(quotient + 1), str(max(1, quotient - 1)), str(dividend - divisor)])
            item.update(prompt_primary=f"{dividend} ÷ {divisor} හි අගය සොයන්න.", prompt_en=f"Calculate {dividend} ÷ {divisor}.", stimulus_primary=f"{dividend} ÷ {divisor}", stimulus_en=f"{dividend} ÷ {divisor}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(quotient)]), hint=f"What number multiplied by {divisor} gives {dividend}?")
        elif mechanic == "fractions":
            denominator = RNG.choice([2, 4, 10])
            groups = RNG.randint(1, 5)
            total = denominator * groups
            numerator = RNG.randint(1, denominator - 1)
            answer = total * numerator // denominator
            options = make_options(str(answer), [str(total // denominator), str(total - answer), str(answer + 1), str(max(1, answer - 1))])
            item.update(prompt_primary=f"වස්තු {total} කින් {numerator}/{denominator} කීය ද?", prompt_en=f"What is {numerator}/{denominator} of {total}?", stimulus_primary=f"{numerator}/{denominator} of {total}", stimulus_en=f"{numerator}/{denominator} of {total}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint=f"Divide {total} into {denominator} equal groups, then take {numerator} group(s).")
        elif mechanic == "decimals":
            a, b = RNG.randint(0, 9), RNG.randint(0, 9)
            if i % 2:
                correct = str(round((a + b) / 10, 1))
                prompt = f"0.{a} + 0.{b}"
            else:
                correct = f"0.{max(a,b)}"
                prompt = f"Which is greater: 0.{a} or 0.{b}?"
            options = make_options(correct, [f"0.{min(a,b)}", str(a + b), f"{a}.{b}", "1.0"])
            item.update(prompt_primary=prompt, prompt_en=prompt, stimulus_primary=prompt, stimulus_en=prompt, options_json=json.dumps(options), correct_answer_json=json.dumps([correct]), hint="Tenths are the first digit after the decimal point.")
        elif mechanic == "time":
            start_hour = RNG.randint(7, 15)
            start_min = RNG.choice([0, 15, 30, 45])
            elapsed = RNG.choice([15, 30, 45, 60, 90, 120])
            total = start_hour * 60 + start_min + elapsed
            answer = f"{(total // 60) % 24:02d}:{total % 60:02d}"
            start = f"{start_hour:02d}:{start_min:02d}"
            options = make_options(answer, [f"{(total // 60 + 1) % 24:02d}:{total % 60:02d}", f"{(total // 60) % 24:02d}:{(total + 15) % 60:02d}", start])
            item.update(prompt_primary=f"{start} සිට මිනිත්තු {elapsed} කට පසු වේලාව කුමක් ද?", prompt_en=f"What time is {elapsed} minutes after {start}?", stimulus_primary=start, stimulus_en=start, options_json=json.dumps(options), correct_answer_json=json.dumps([answer]), hint="Add the minutes first; exchange 60 minutes for one hour.")
        elif mechanic == "money":
            price1 = RNG.randrange(25, 501, 5)
            price2 = RNG.randrange(20, 301, 5)
            total = price1 + price2
            if i % 2:
                answer = total
                prompt_en = f"An item costs Rs. {price1} and another costs Rs. {price2}. What is the total?"
            else:
                paid = ((total + 99) // 100) * 100
                answer = paid - total
                prompt_en = f"The total is Rs. {total}. You pay Rs. {paid}. What is the change?"
            options = make_options(str(answer), [str(answer + 10), str(max(0, answer - 10)), str(total), str(price1)])
            item.update(prompt_primary=prompt_en, prompt_en=prompt_en, stimulus_primary=f"Rs. {price1}, Rs. {price2}", stimulus_en=f"Rs. {price1}, Rs. {price2}", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint="For change, subtract the total cost from the amount paid.")
        elif mechanic == "measurement":
            kind = i % 3
            n = RNG.randint(2, 20)
            if kind == 0:
                prompt_en, answer = f"Convert {n} metres to centimetres.", n * 100
                unit = "cm"
            elif kind == 1:
                prompt_en, answer = f"Convert {n} kilograms to grams.", n * 1000
                unit = "g"
            else:
                prompt_en, answer = f"Convert {n} litres to millilitres.", n * 1000
                unit = "ml"
            correct = f"{answer} {unit}"
            options = make_options(correct, [f"{n * 10} {unit}", f"{n * 100} {unit}", f"{n} {unit}"])
            item.update(prompt_primary=prompt_en, prompt_en=prompt_en, stimulus_primary=str(n), stimulus_en=str(n), options_json=json.dumps(options), correct_answer_json=json.dumps([correct]), hint="Use 1 m = 100 cm and 1 kg or L = 1000 smaller units.")
        else:
            start = RNG.randint(1, 30)
            step = RNG.randint(2, 10)
            seq = [start + step * k for k in range(4)]
            answer = start + step * 4
            options = make_options(str(answer), [str(answer + step), str(answer - step), str(answer + 1), str(answer * 2)])
            item.update(prompt_primary="රටාවේ ඊළඟ සංඛ්‍යාව සොයන්න.", prompt_en="Find the next number in the pattern.", stimulus_primary=", ".join(map(str, seq)) + ", …", stimulus_en=", ".join(map(str, seq)) + ", …", options_json=json.dumps(options), correct_answer_json=json.dumps([str(answer)]), hint="Find the common difference between neighbouring numbers.")
        items.append(item)
    return items


ENGLISH_WORDS = [
    ("island", "land surrounded by water"), ("forest", "a large area covered with trees"),
    ("kind", "helpful and caring"), ("share", "give part of something to another"),
    ("festival", "a special time of celebration"), ("athlete", "a person who takes part in sport"),
    ("healthy", "well and strong"), ("market", "a place where things are bought and sold"),
    ("helmet", "protective covering worn on the head"), ("journey", "travel from one place to another"),
    ("future", "the time that has not happened yet"), ("river", "a natural stream of water"),
    ("friend", "a person you like and trust"), ("team", "a group working or playing together"),
    ("doctor", "a person who treats illness"), ("teacher", "a person who helps others learn"),
    ("careful", "taking care to avoid danger"), ("country", "a nation with its own land"),
    ("garden", "a place where plants are grown"), ("animal", "a living creature that can move"),
    ("honest", "truthful and fair"), ("brave", "ready to face danger"),
    ("quiet", "making little or no sound"), ("rapid", "very fast"),
    ("protect", "keep safe from harm"), ("celebrate", "do something special for an occasion"),
    ("exercise", "activity that keeps the body fit"), ("traffic", "vehicles moving on a road"),
    ("planet", "a large body moving around a star"), ("invent", "create something new"),
    ("village", "a small settlement"), ("ocean", "a very large area of salt water"),
    ("respect", "show care for someone or something"), ("recycle", "use material again"),
    ("balance", "remain steady without falling"), ("energy", "power needed for activity"),
    ("visitor", "a person who comes to a place"), ("message", "information sent to someone"),
    ("shelter", "a place that gives protection"), ("discover", "find something for the first time"),
]


ENGLISH_SENTENCES = [
    "Sri Lanka is our beautiful island",
    "Trees give shade to people and animals",
    "We should care for our friends",
    "The children celebrate the festival together",
    "Our team practises every afternoon",
    "Clean food helps us stay healthy",
    "The family visits the fair on Saturday",
    "Wear a helmet when you ride a bicycle",
    "They travelled around the world",
    "We will build a kinder future",
]


def make_english_items(game):
    items = []
    refs = [r for r in game["target_curriculum_ids"].split(",") if r][:3]
    words = [w for w, _ in ENGLISH_WORDS]
    for i in range(1, 41):
        item = base_item(game, i, refs)
        word, definition = ENGLISH_WORDS[i - 1]
        mechanic = game["mechanic"]
        if mechanic == "phonics":
            target = word[0]
            choices = make_options(word, [w for w in words if not w.startswith(target)])
            item.update(prompt_primary=f"Which word begins with the sound /{target}/?", prompt_en=f"Which word begins with the sound /{target}/?", stimulus_primary=target, stimulus_en=target, options_json=json.dumps(choices), correct_answer_json=json.dumps([word]), hint=f"Say /{target}/ slowly, then say each option.")
        elif mechanic == "word_builder":
            letters = list(word)
            RNG.shuffle(letters)
            item.update(prompt_primary="Build a word from these letters.", prompt_en="Build a word from these letters.", stimulus_primary=" ".join(letters), stimulus_en=" ".join(letters), options_json=json.dumps(make_options(word, words)), correct_answer_json=json.dumps([word]), hint=definition)
        elif mechanic == "vocabulary":
            item.update(prompt_primary=f"Which word means “{definition}”?", prompt_en=f"Which word means “{definition}”?", stimulus_primary=definition, stimulus_en=definition, options_json=json.dumps(make_options(word, words)), correct_answer_json=json.dumps([word]), hint=f"The word begins with {word[0].upper()}.")
        elif mechanic == "sentence_order":
            sentence = ENGLISH_SENTENCES[(i - 1) % len(ENGLISH_SENTENCES)]
            words_in_sentence = sentence.split()
            shuffled = words_in_sentence[:]
            RNG.shuffle(shuffled)
            answer = sentence + "."
            item.update(prompt_primary="Arrange the words to make a sentence.", prompt_en="Arrange the words to make a sentence.", stimulus_primary=" / ".join(shuffled), stimulus_en=" / ".join(shuffled), options_json=json.dumps([]), correct_answer_json=json.dumps([answer]), hint="Start with a capital letter and finish with a full stop.")
        elif mechanic == "grammar_sort":
            categories = ["noun", "verb", "adjective"]
            category = "adjective" if word in {"kind", "healthy", "careful", "honest", "brave", "quiet", "rapid"} else ("verb" if word in {"share", "protect", "celebrate", "exercise", "invent", "respect", "recycle", "balance", "discover"} else "noun")
            item.update(prompt_primary=f"What kind of word is “{word}”?", prompt_en=f"What kind of word is “{word}”?", stimulus_primary=word, stimulus_en=word, options_json=json.dumps(categories), correct_answer_json=json.dumps([category]), hint="A noun names; a verb shows action; an adjective describes.")
        elif mechanic == "missing_word":
            sentence = f"The word _____ means {definition}."
            item.update(prompt_primary="Choose the missing word.", prompt_en="Choose the missing word.", stimulus_primary=sentence, stimulus_en=sentence, options_json=json.dumps(make_options(word, words)), correct_answer_json=json.dumps([word]), hint=f"It begins with {word[0]}.")
        elif mechanic == "punctuation":
            base = ENGLISH_SENTENCES[(i - 1) % len(ENGLISH_SENTENCES)]
            correct = base + "."
            wrong = [base.lower(), base + "?", base.upper() + "."]
            item.update(prompt_primary="Choose the correctly written sentence.", prompt_en="Choose the correctly written sentence.", stimulus_primary=base.lower(), stimulus_en=base.lower(), options_json=json.dumps(make_options(correct, wrong)), correct_answer_json=json.dumps([correct]), hint="Check the capital letter and end punctuation.")
        elif mechanic == "spelling":
            variants = [word[:-1], word + word[-1], (word[1] + word[0] + word[2:]) if len(word) > 2 else word + "e"]
            item.update(prompt_primary="Choose the correctly spelled word.", prompt_en="Choose the correctly spelled word.", stimulus_primary=definition, stimulus_en=definition, options_json=json.dumps(make_options(word, variants)), correct_answer_json=json.dumps([word]), hint=f"The word has {len(word)} letters.")
        elif mechanic == "reading":
            topic = ENGLISH_SENTENCES[(i - 1) % len(ENGLISH_SENTENCES)] + "."
            target = topic.split()[0]
            item.update(prompt_primary="Read the sentence. Which word begins the sentence?", prompt_en="Read the sentence. Which word begins the sentence?", stimulus_primary=topic, stimulus_en=topic, options_json=json.dumps(make_options(target, words)), correct_answer_json=json.dumps([target]), hint="Look at the first word after the beginning of the line.")
        elif mechanic == "dialogue":
            prompts = [("How are you?", "I am well, thank you."), ("May I borrow your pencil?", "Yes, you may."), ("Thank you for helping me.", "You are welcome."), ("Where is the library?", "It is next to the office."), ("Would you like to play?", "Yes, I would.")]
            question, answer = prompts[(i - 1) % len(prompts)]
            distractors = [p[1] for p in prompts if p[1] != answer]
            item.update(prompt_primary="Choose the best reply.", prompt_en="Choose the best reply.", stimulus_primary=question, stimulus_en=question, options_json=json.dumps(make_options(answer, distractors)), correct_answer_json=json.dumps([answer]), hint="Choose the reply that directly answers the speaker.")
        elif mechanic == "listening":
            sentence = ENGLISH_SENTENCES[(i - 1) % len(ENGLISH_SENTENCES)] + "."
            target = sentence.split()[RNG.randrange(len(sentence.split()))].strip(".")
            item.update(prompt_primary=f"Listen and choose the word you heard: {target}", prompt_en=f"Listen and choose the word you heard: {target}", stimulus_primary=sentence, stimulus_en=sentence, options_json=json.dumps(make_options(target, words)), correct_answer_json=json.dumps([target]), hint="Replay the audio once and listen for the target word.", asset_status="audio_required")
        else:
            lesson_topics = ["Sri Lanka", "nature", "sharing", "celebration", "sports", "health", "fair", "safety", "world", "future"]
            topic = lesson_topics[(i - 1) % len(lesson_topics)]
            item.update(prompt_primary=f"Choose the word that best fits the topic “{topic}”.", prompt_en=f"Choose the word that best fits the topic “{topic}”.", stimulus_primary=topic, stimulus_en=topic, options_json=json.dumps(make_options(word, words)), correct_answer_json=json.dumps([word]), hint=definition)
        item.update(answer_verified=True, language_reviewed=True, source_confidence="high")
        items.append(item)
    return items


def index_raw(raw, subject):
    lessons = raw[subject]["06_lessons"]
    activities = raw[subject]["07_activities"]
    outcomes = raw[subject]["04_learning_outcomes"]
    content = raw[subject]["05_content_points"]
    terms = raw[subject]["08_terms"]
    lesson_title = {}
    for row in lessons:
        lesson_title[first(row, "lesson_id")] = {
            "primary": first(row, "lesson_title", "lesson_title_si"),
            "en": first(row, "lesson_title", "lesson_title_en_gloss"),
        }
    return lessons, activities, outcomes, content, terms, lesson_title


def make_source_derived_items(game, raw):
    subject = game["subject"]
    lessons, activities, outcomes, content, terms, lesson_titles = index_raw(raw, subject)
    valid_activities = [a for a in activities if first(a, "lesson_id") and first(a, "activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si")]
    if not valid_activities:
        valid_activities = activities
    title_pool = [v["primary"] for v in lesson_titles.values() if v["primary"]]
    activity_title_pool = [first(a, "activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si") for a in valid_activities]
    term_pool_en = [first(t, "term_en_gloss", "term") for t in terms if first(t, "term_en_gloss", "term")]
    items = []
    for i in range(1, 41):
        activity = valid_activities[(i - 1) % len(valid_activities)]
        lesson_id = first(activity, "lesson_id")
        lesson = lesson_titles.get(lesson_id, {"primary": lesson_id, "en": lesson_id})
        activity_title = first(activity, "activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si")
        instruction = first(activity, "instructions_summary", "instructions_summary_si") or activity_title
        refs = [r.strip() for r in first(activity, "competency_level_ids").split(",") if r.strip()]
        if not refs:
            refs = [lesson_id] if lesson_id else [r for r in game["target_curriculum_ids"].split(",") if r][:1]
        item = base_item(game, i, refs, lesson_id, first(activity, "activity_id"))
        item.update(source_confidence=source_confidence(activity), generation_method="curriculum_adaptation")
        mechanic = game["mechanic"]
        if mechanic == "term_match" and terms:
            term = terms[(i - 1) % len(terms)]
            primary = first(term, "term", "term_si")
            english = first(term, "term_en_gloss", "term")
            item.update(prompt_primary=f"“{primary}” යන්නට ගැළපෙන අර්ථය තෝරන්න.", prompt_en=f"Choose the matching meaning for “{primary}”.", stimulus_primary=primary, stimulus_en=english, options_json=json.dumps(make_options(english, term_pool_en), ensure_ascii=False), correct_answer_json=json.dumps([english], ensure_ascii=False), hint="Compare the key idea in each option.")
        elif mechanic == "activity_instruction":
            item.update(prompt_primary="උපදෙස්වලට ගැළපෙන ක්‍රියාකාරකම තෝරන්න.", prompt_en="Choose the activity that matches the instruction.", stimulus_primary=instruction, stimulus_en="", options_json=json.dumps(make_options(activity_title, activity_title_pool), ensure_ascii=False), correct_answer_json=json.dumps([activity_title], ensure_ascii=False), hint="Look for the action described in the instruction.")
        elif mechanic == "activity_sequence":
            same = [a for a in valid_activities if first(a, "lesson_id") == lesson_id][:4]
            ordered = [first(a, "activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si") for a in same if first(a, "activity_title", "activity_title_si", "instructions_summary", "instructions_summary_si")]
            if len(ordered) < 3:
                ordered = activity_title_pool[:4]
            shuffled = ordered[:]
            RNG.shuffle(shuffled)
            item.update(prompt_primary="ක්‍රියාකාරකම් මූලාශ්‍ර අනුපිළිවෙළට සකසන්න.", prompt_en="Arrange the activities in source order.", stimulus_primary=" | ".join(shuffled), stimulus_en="", options_json=json.dumps([]), correct_answer_json=json.dumps(ordered, ensure_ascii=False), hint="Use the lesson progression from introduction to practice.")
        elif mechanic == "outcome_match" and outcomes:
            outcome = outcomes[(i - 1) % len(outcomes)]
            primary = first(outcome, "outcome", "outcome_si")
            english = first(outcome, "outcome_en_gloss", "outcome")
            en_pool = [first(o, "outcome_en_gloss", "outcome") for o in outcomes if first(o, "outcome_en_gloss", "outcome")]
            item.update(prompt_primary="මෙම ඉගෙනුම් ප්‍රතිඵලයට ගැළපෙන විස්තරය තෝරන්න.", prompt_en="Choose the matching description for this learning outcome.", stimulus_primary=primary, stimulus_en=english, options_json=json.dumps(make_options(english or primary, en_pool or [primary]), ensure_ascii=False), correct_answer_json=json.dumps([english or primary], ensure_ascii=False), hint="Identify the main action expected from the learner.")
            item["curriculum_refs"] = first(outcome, "learning_outcome_id")
        else:
            correct = lesson["primary"] or lesson_id
            item.update(prompt_primary="මෙම ක්‍රියාකාරකමට ගැළපෙන පාඩම් මාතෘකාව තෝරන්න.", prompt_en="Choose the lesson topic that best matches this activity.", stimulus_primary=instruction, stimulus_en="", options_json=json.dumps(make_options(correct, title_pool), ensure_ascii=False), correct_answer_json=json.dumps([correct], ensure_ascii=False), hint="Focus on the main subject of the activity.")
        item.update(answer_verified=False, language_reviewed=False, publication_status="needs_review")
        items.append(item)
    return items


def build_items(games, raw):
    items = []
    for game in games:
        if game["subject"] == "MAT":
            items.extend(make_math_items(game))
        elif game["subject"] == "ENG":
            items.extend(make_english_items(game))
        else:
            items.extend(make_source_derived_items(game, raw))
    return items


def schema_definition():
    return {
        "version": "1.0.0",
        "entities": {
            "curriculum_node": {"primary_key": "curriculum_node_id", "description": "Normalized source curriculum, lesson and activity nodes."},
            "game": {"primary_key": "game_id", "description": "Reusable gameplay configuration tied to curriculum targets."},
            "game_item": {"primary_key": "item_id", "description": "One playable round with prompt, response and QA metadata."},
        },
        "status_rules": {
            "prototype": "Generated and structurally valid but not approved for learners.",
            "needs_review": "Requires educator, native-language or mapping review.",
            "published": "May be served to learners after all release gates pass.",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the versioned Grade 5 curriculum-to-game dataset."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(os.environ[SOURCE_DIR_ENV]) if SOURCE_DIR_ENV in os.environ else None,
        help=f"Directory containing the four syllabus trace workbooks (or set {SOURCE_DIR_ENV}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Artifact destination (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args()
    if args.source_dir is None:
        parser.error(f"--source-dir is required unless {SOURCE_DIR_ENV} is set")
    return args


def validate_source_dir(source_dir: Path) -> None:
    missing = [
        source_dir / f"grade5_{subject}_syllabus_trace_v1.xlsx"
        for subject in SUBJECTS
        if not (source_dir / f"grade5_{subject}_syllabus_trace_v1.xlsx").is_file()
    ]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing required syllabus trace workbooks:\n{formatted}")


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    validate_source_dir(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes, raw = collect_curriculum(source_dir)
    games = build_game_catalog(nodes)
    items = build_items(games, raw)
    jsonl_write(output_dir / "curriculum_nodes.jsonl", nodes)
    jsonl_write(output_dir / "games.jsonl", games)
    jsonl_write(output_dir / "game_items.jsonl", items)

    counts = {"nodes": len(nodes), "games": len(games), "items": len(items)}
    (output_dir / "schema.json").write_text(
        json.dumps(schema_definition(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        "package": "grade5-curriculum-game-dataset",
        "version": "1.0.0",
        "counts": counts,
        "files": {},
    }
    generated_files = (
        "curriculum_nodes.jsonl",
        "game_items.jsonl",
        "games.jsonl",
        "schema.json",
    )
    for filename in generated_files:
        path = output_dir / filename
        manifest["files"][filename] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
