"""English lessons for every Grade 5 English game.

The correct answer of a board is turned into teaching: each English word with its Sinhala meaning
and picture, where it goes and why, a sentence that uses it, and the whole answer. A diagnosis
says which of the child's own placements went wrong.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.gamification.application.support_builders.lessons.common import (
    Diagnosis,
    Game,
    Lesson,
    Solution,
)
from app.gamification.application.support_builders.lessons.english_glossary import (
    meaning,
    taught,
)

_OPAQUE = re.compile(r"^[a-z]{1,4}-[0-9a-f]{8,}$")
_LABEL_KEYS = ("text_en", "display_en", "text_si", "label", "label_si", "command_text")
_LINK_KEYS = (
    "placements",
    "links",
    "labels",
    "mappings",
    "matches",
    "selections",
    "pairs",
    "actions",
)

# Each English area's theme, said simply in Sinhala: the idea, how to work it out, a reminder.
ENGLISH_THEORY: dict[str, tuple[tuple[str, str], ...]] = {
    "G5-AREA-ENG-01": (
        ("මූලික අදහස", "ඉංග්‍රීසි විධානයක් කියන්නේ කළ යුතු දෙයයි: Stand, Sit, Run, Come."),
        ("කරන ආකාරය", "විධානයේ පළමු වචනය (ක්‍රියාව) බලන්න: Sit = වාඩි වෙන්න, Run = දුවන්න. ඉන්පසු to the … කොහේදැයි බලන්න."),
        ("මතක තබාගන්න", "“Come back” යනු ආරම්භක තැනට ආපසු ඒමයි."),
    ),
    "G5-AREA-ENG-02": (
        ("මූලික අදහස", "ශ්‍රී ලංකාවේ ආගමික ස්ථාන, උත්සව භාණ්ඩ සහ ජාතික සංකේත ඉංග්‍රීසියෙන් හඳුනාගනිමු."),
        ("කරන ආකාරය", "ස්ථානයක් (Temple, Church) යනු අපි යන තැනක්; භාණ්ඩයක් (Vesak Lantern, Kolam) යනු අපි හදන හෝ සරසන දෙයක්."),
        ("මතක තබාගන්න", "ජාතික ගස නා ගස, ජාතික පක්ෂියා වළිකුකුළා, ජාතික මල නිල් මානෙල්, ජාතික ක්‍රීඩාව වොලිබෝල්."),
    ),
    "G5-AREA-ENG-03": (
        ("මූලික අදහස", "පැළයක කොටස්: Roots (මුල්), Stem (කඳ), Leaves (කොළ), Flowers (මල්), Fruits (ගෙඩි)."),
        ("කරන ආකාරය", "එකකට වචනය: leaf, bud, branch. බොහොමයකට: leaves, buds, branches — බොහෝ විට -s හෝ -es එකතු වේ; leaf → leaves (f → ves)."),
        ("මතක තබාගන්න", "මුල් පොළොව යට; කොළ කොළ පාටයි; මල් පසුව ගෙඩි වේ."),
    ),
    "G5-AREA-ENG-04": (
        ("මූලික අදහස", "සතුන් කණ්ඩායම් තුනකට: Animals (සතුන්), Birds (කුරුල්ලන්), Insects (කෘමීන්)."),
        ("කරන ආකාරය", "පියාපත් සහ පිහාටු නම් Bird; කකුල් හයක් නම් Insect; අනෙක් සතුන් Animal."),
        ("මතක තබාගන්න", "අලියාගේ දිගු නාසය Trunk (සොඬ); Tail වලිගය; Eyes ඇස්; Mouth කට."),
    ),
    "G5-AREA-ENG-05": (
        ("මූලික අදහස", "අපි දිනපතා භාවිතා කරන දේවල් ඉංග්‍රීසියෙන්: පාසලේ සහ නිවසේ."),
        ("කරන ආකාරය", "එම දේ භාවිතා කරන්නේ කොහේදැයි සිතන්න: Ruler, Pencil → Classroom; Bed, Spoon → Home."),
        ("මතක තබාගන්න", "නම් දෙකකින් සෑදෙන වචනවල විස්තර වචනය මුලින් එයි: Lunch box, Work book."),
    ),
    "G5-AREA-ENG-06": (
        ("මූලික අදහස", "ආහාර කණ්ඩායම්: Drinks (බීම), Fruits (පලතුරු), Vegetables (එළවළු), Bread, eggs & fish."),
        ("කරන ආකාරය", "බොන දෙයක් නම් Drinks; ගසෙන් ලැබෙන පැණිරස දෙයක් නම් Fruits; උයන කොළ/අල නම් Vegetables."),
        ("මතක තබාගන්න", "නම් දෙකකින් සෑදෙන ආහාර: Fruit Juice, Curry Leaves, Ice Cream."),
    ),
    "G5-AREA-ENG-07": (
        ("මූලික අදහස", "ඇඳුම් වල ඉංග්‍රීසි නම්: Shirt, Trousers, Shoes, Socks, Frock."),
        ("කරන ආකාරය", "ශරීරයේ කොතැනට අඳිනවාද සිතන්න: කකුලට Socks/Shoes, උඩ කොටසට Shirt/Blouse."),
        ("මතක තබාගන්න", "Shoes, Socks, Trousers, Shorts සෑම විටම බහු වචන ලෙස (-s) කියමු."),
    ),
    "G5-AREA-ENG-08": (
        ("මූලික අදහස", "වතුර භාවිතා කරන ක්‍රියා: Drink, Cook, Wash, Bathe, Water (the plants)."),
        ("කරන ආකාරය", "රූපයේ කෙනා කරන දේ බලන්න: බොනවා = Drink, උයනවා = Cook, නානවා = Bathe."),
        ("මතක තබාගන්න", "ක්‍රියා පද මගින් කියන්නේ කරන දෙයයි."),
    ),
    "G5-AREA-ENG-09": (
        ("මූලික අදහස", "ප්‍රවාහන ක්‍රම: පොළොවේ (Bus, Car, Train, Bicycle), අහසේ (Aeroplane, Helicopter)."),
        ("කරන ආකාරය", "රෝද තිබේද, පියාපත් තිබේද, පීලි මත යනවාද කියා බලන්න."),
        ("මතක තබාගන්න", "Train පීලි මත යයි; Helicopter උඩ පංකා කරකවමින් පියාසර කරයි."),
    ),
    "G5-AREA-ENG-10": (
        ("මූලික අදහස", "ගෙවත්තේ මල්: Rose, Sunflower, Jasmine, Marigold, Shoe flower."),
        ("කරන ආකාරය", "මලේ පාට සහ හැඩය බලන්න: Sunflower විශාල කහ; Rose රතු පෙති රාශිය; Jasmine කුඩා සුදු."),
        ("මතක තබාගන්න", "Sunflower = Sun + flower: ඉර වගේ මල."),
    ),
    "G5-AREA-ENG-11": (
        ("මූලික අදහස", "රැකියා සහ ඒවා කරන තැන්: Teacher → School, Doctor → Hospital, Farmer → Paddy Field."),
        ("කරන ආකාරය", "එම පුද්ගලයා කරන වැඩය සිතන්න; ඒ වැඩය කරන්නේ කොහේද?"),
        ("මතක තබාගන්න", "-er, -ian බොහෝ විට කෙනෙක් අදහස් කරයි: Teacher, Farmer, Electrician."),
    ),
    "G5-AREA-ENG-12": (
        ("මූලික අදහස", "පවුලේ අය ඉංග්‍රීසියෙන්: Mother, Father, Sister, Brother, Grandmother, Grandfather."),
        ("කරන ආකාරය", "Grand- යනු එක් පරම්පරාවක් ඉහළ: Grandmother = අම්මාගේ හෝ තාත්තාගේ අම්මා."),
        ("මතක තබාගන්න", "Sister ගැහැණු, Brother පිරිමි."),
    ),
    "G5-AREA-ENG-13": (
        ("මූලික අදහස", "අහසේ (Sun, Moon, Stars, Clouds, Rainbow) සහ පොළොවේ ජලය (River, Sea, Waterfall, Well, Pond)."),
        ("කරන ආකාරය", "රූපයේ උඩ අහසේද, පහළ පොළොවේද බලන්න; ජලය ගලනවාද (River), වැටෙනවාද (Waterfall), නිශ්චලද (Pond)."),
        ("මතක තබාගන්න", "Rain drops = වැහි බිංදු; Mist = මීදුම."),
    ),
    "G5-AREA-ENG-14": (
        ("මූලික අදහස", "පාසලේ ස්ථාන (Library, Canteen, Laboratory) සහ නිවසේ කොටස් (Door, Window, Roof, Wall)."),
        ("කරන ආකාරය", "ස්ථානයක් කාමරයක්ද (පාසලේ), නැතිනම් ගොඩනැගිල්ලේ කොටසක්ද (නිවසේ) කියා සිතන්න."),
        ("මතක තබාගන්න", "කාමර නාම: විස්තරය මුලින්, room පසුව — Staff room, Store room, Living Room."),
    ),
    "G5-AREA-ENG-15": (
        ("මූලික අදහස", "තොරතුරු යැවීමේ ක්‍රම: Letter, Post, Newspapers, Telephone."),
        ("කරන ආකාරය", "Telephone මගින් කතා කරයි; Newspapers මගින් පුවත් කියවයි; Letter ලියා Post කරයි."),
        ("මතක තබාගන්න", "Newspapers = News (පුවත්) + papers (කඩදාසි)."),
    ),
    "G5-AREA-ENG-16": (
        ("මූලික අදහස", "අපේ අතීතය: Palace, Throne, Crown, Timber carvings, Stone carvings."),
        ("කරන ආකාරය", "රජතුමා ඉන්නේ Palace හි, වාඩි වන්නේ Throne මත, හිසේ පළඳින්නේ Crown."),
        ("මතක තබාගන්න", "Timber = ලී; Stone = ගල්; carvings = කැටයම්."),
    ),
    "G5-AREA-ENG-17": (
        ("මූලික අදහස", "පන්තියේ භාෂාව: ආචාර (Good Morning), විධාන (Hands up), ඉල්ලීම් (May I…?), ප්‍රශංසා (Well done), ආචාරශීලී වචන (Thank You)."),
        ("කරන ආකාරය", "අවස්ථාව සිතන්න: යමක් ලැබුණාම Thank You; වැරැද්දක් වුණාම I'm sorry; ඇතුළට එන්න May I come in?"),
        ("මතක තබාගන්න", "ප්‍රශ්න What/Who වලින් පටන් ගෙන ? ලකුණෙන් අවසන් වේ."),
    ),
    "G5-AREA-ENG-18": (
        ("මූලික අදහස", "සංවාදයක ප්‍රශ්නයකට ගැළපෙන පිළිතුර ප්‍රශ්නයේ වචනම භාවිතා කරයි."),
        ("කරන ආකාරය", "“Can you…?” → “Yes, I can.” / “No, I can't.”  “Do you…?” → “Yes, I do.” / “No, I don't.”"),
        ("මතක තබාගන්න", "සංවාදය ප්‍රශ්නයකින් පටන් ගෙන, පිළිතුරෙන් පසු ඊළඟ ප්‍රශ්නය එයි."),
    ),
}


def theory_for_english(area_id: str) -> tuple[tuple[str, str], ...]:
    return ENGLISH_THEORY.get(area_id, ())


def _rows(game: Game) -> list[Mapping[str, object]]:
    rows: list[Mapping[str, object]] = []
    for value in game.values():
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, Mapping))
    return rows


def _row_label(row: Mapping[str, object]) -> str | None:
    for key in _LABEL_KEYS:
        text = row.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _labels(game: Game) -> dict[str, str]:
    """Every token on the board with its words. A picture target, which carries no words, is
    named by the word whose token shares its suffix (``w-…ab12`` and ``o-…ab12``)."""

    labels: dict[str, str] = {}
    unnamed: list[tuple[str, Mapping[str, object]]] = []
    for row in _rows(game):
        label = _row_label(row)
        for key, token in row.items():
            if not isinstance(token, str) or not key.endswith(("_token", "_id")):
                continue
            if label:
                labels.setdefault(token, label)
            else:
                unnamed.append((token, row))
    by_suffix = {token.split("-", 1)[-1]: label for token, label in labels.items()}
    for token, row in unnamed:
        suffix = token.split("-", 1)[-1]
        if suffix in by_suffix:
            labels.setdefault(token, f"PICTURE:{by_suffix[suffix]}")
        elif isinstance(row.get("visual_key"), str):
            part = str(row["visual_key"]).removeprefix("plant-").removesuffix("-slot")
            labels.setdefault(token, f"PICTURE:{part}")
        elif row.get("marker_index") is not None:
            labels.setdefault(token, f"MARKER:{row['marker_index']}")
        elif row.get("renderer_variant") is not None and "situation_token" in row:
            labels.setdefault(token, f"SITUATION:{row['renderer_variant']}")
    return labels


# Classroom moments a phrase is said in (Classroom Language situation pictures).
SITUATIONS = {
    0: "🌅🧑‍🏫 උදේ ගුරුතුමා පන්තියට එන විට",
    1: "🎂 යාළුවෙකුගේ උපන්දිනයට",
    2: "🏆 කෙනෙක් හොඳින් වැඩක් කළ විට",
    3: "🤕 අපෙන් කෙනෙකුට වැරැද්දක් වුණ විට",
    4: "🚪✊ පන්තියට ඇතුළු වීමට අවසර ඉල්ලන විට",
    5: "🎁 කෙනෙක් අපට යමක් දුන් විට",
}


def _is_place(label: str) -> bool:
    return label.split(":", 1)[0] in {"PICTURE", "MARKER", "SITUATION"}


def _shown(label: str) -> str:
    """How a target appears: its words, or for a picture, the picture and what it shows."""

    if label.startswith("PICTURE:"):
        word = label.removeprefix("PICTURE:")
        found = meaning(word)
        return f"{found[1]} ({found[0]})" if found else "ගැළපෙන රූපය"
    if label.startswith("MARKER:"):
        return f"අංක {label.removeprefix('MARKER:')} සලකුණ"
    if label.startswith("SITUATION:"):
        return SITUATIONS.get(int(label.removeprefix("SITUATION:")), "ගැළපෙන අවස්ථාව")
    return label


def _pairs(game: Game, solution: Solution) -> list[tuple[str, str]]:
    """The correct (English word, where it goes) pairs, read from the solution's links."""

    labels = _labels(game)
    pairs: list[tuple[str, str]] = []
    # Groups: {group_id, ordered_member_ids}.
    for group in solution.get("groups", []) or []:  # type: ignore[union-attr]
        if isinstance(group, Mapping):
            heading = labels.get(str(group.get("group_id")), "")
            for member in group.get("ordered_member_ids", []) or []:  # type: ignore[union-attr]
                pairs.append((labels.get(str(member), str(member)), heading))
    if pairs:
        return pairs
    for key in _LINK_KEYS:
        rows = solution.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            named = [
                labels[value]
                for name, value in row.items()
                if isinstance(value, str) and value in labels and name != "command_token"
            ]
            if len(named) >= 2:
                words = [label for label in named if not _is_place(label)]
                pictures = [label for label in named if _is_place(label)]
                if pictures and words:
                    pairs.append((words[0], pictures[0]))
                else:
                    pairs.append((named[0], named[1]))
        if pairs:
            break
    return pairs


def _sentence(word: str) -> str | None:
    """A short sentence using a thing's name, for nouns only."""

    if word.lower() not in NOUNS:
        return None
    lower = word.lower()
    plural = lower.endswith("s") and not lower.endswith(("ss", "us"))
    if plural:
        return f"“These are {lower}.”"
    article = "an" if lower[0] in "aeiou" else "a"
    return f"“This is {article} {lower}.”"


# Words that name things, so a “This is a …” sentence makes sense.
NOUNS = frozenset(
    word
    for word in __import__(
        "app.gamification.application.support_builders.lessons.english_glossary",
        fromlist=["GLOSSARY"],
    ).GLOSSARY
    if not word.endswith(("?", "."))
    and word.split()[0]
    not in {
        "stand", "bend", "stretch", "put", "turn", "sit", "run", "come", "bathe", "cook",
        "wash", "drink", "water", "good", "happy", "merry", "hands", "jump", "start", "clap",
        "look", "form", "don't", "get", "may", "silence", "listen", "hurry", "be", "very",
        "that's", "well", "i", "i'm", "thank", "please", "who", "what's", "what", "are",
        "all", "greetings", "simple", "request", "praising", "polite", "places", "parts",
        "rooms", "cultural", "national", "animals", "birds", "insects", "drinks", "vegetables",
        "bread,", "yams",
    }
)


def _pair_line(word: str, target: str) -> str:
    """``“Rose” 🌹 = රෝස → 🌹 (රෝස)``, or with a heading, why it belongs there."""

    shown = _shown(target)
    found = meaning(target)
    word_meaning = meaning(word)
    if word_meaning and target == word_meaning[0]:
        # A bilingual pair: the target is the word's own meaning.
        return taught(word)
    if target.startswith("PICTURE:"):
        # A picture target: say where to drag the word, not the meaning again.
        picture = meaning(target.removeprefix("PICTURE:"))
        return f"{taught(word)} → {picture[1] if picture else ''} පින්තූරයට".replace("  ", " ")
    heading = f"{target} ({found[0]})" if found and not _is_place(target) else shown
    return f"{taught(word)} → {heading}"


def lesson(area_id: str, game: Game, solution: Solution) -> Lesson | None:
    kind = str(solution.get("kind", ""))
    if area_id == "G5-AREA-ENG-01":
        return _action_lesson(game, solution)
    if kind == "classroom_command_action":
        command = str(game.get("command_text", ""))
        return Lesson(
            steps=(
                f"විධානය කියවන්න: {taught(command)}.",
                "චරිතය එම ක්‍රියාව කරන ආකාරය පෙන්වන පින්තූරය තෝරන්න.",
            ),
            answer=f"{command} → {meaning(command)[1] if meaning(command) else ''} {meaning(command)[0] if meaning(command) else ''}".strip(),
            hints=(f"“{command}” හි පළමු වචනය බලන්න; එය කළ යුතු ක්‍රියාවයි.",),
            another_view=(f"ගුරුතුමා “{command}” කීවොත්, ඔබ කරන්නේ: {meaning(command)[0] if meaning(command) else command}.",),
        )
    if kind == "singular_plural_pairing":
        return _plural_lesson(game, solution)
    if kind == "conversation_scene_reply":
        return _scene_reply_lesson(game, solution)
    if "ordered_chunk_tokens" in solution or "ordered_turn_tokens" in solution:
        return _sequence_lesson(game, solution)
    pairs = _pairs(game, solution)
    if not pairs:
        return None
    steps = tuple(_pair_line(word, target).rstrip(".") + "." for word, target in pairs)
    sentences = tuple(s for s in (_sentence(word) for word, _ in pairs) if s)
    answer = "; ".join(f"{word} → {_shown(target)}" for word, target in pairs)
    return Lesson(
        steps=(*steps, *(f"වාක්‍යයකින්: {s}" for s in sentences[:2])),
        answer=answer,
        hints=(
            "වචනය ශබ්ද නඟා කියවන්න, ඉන්පසු එහි තේරුම සිතන්න.",
            steps[0],
        ),
        another_view=tuple(
            f"{taught(word)} — {s}" for (word, _), s in zip(pairs, (_sentence(w) for w, _ in pairs), strict=False) if s
        )[:3]
        or tuple(f"{taught(word)}" for word, _ in pairs[:3]),
    )


def _action_lesson(game: Game, solution: Solution) -> Lesson | None:
    command = str(game.get("command_text_en", ""))
    found = meaning(command)
    if solution.get("kind") == "body_state":
        what = found[0] if found else command
        return Lesson(
            steps=(
                f"විධානය කියවන්න: {taught(command)}.",
                f"චරිතය {what} ලෙස සකස් කරන බොත්තම තෝරන්න.",
            ),
            answer=f"{command} → {what}",
            hints=(f"“{command.split()[0]}” යනු ක්‍රියාවයි; එය කුමක් කරන්නදැයි සිතන්න.",),
            another_view=(f"ගුරුතුමා “{command}” කීවොත්, ඔබ {what}.",),
        )
    destination = str(solution.get("final_location_id", ""))
    place = {
        "wall-zone": "බිත්තිය (Wall)",
        "blackboard-zone": "කළු ලෑල්ල (Blackboard)",
        "start-a": "ආරම්භක තැන (Start)",
    }.get(destination, destination)
    return Lesson(
        steps=(
            f"විධානය කියවන්න: {taught(command)}.",
            f"“to the …” පසුව එන වචනය ගමනාන්තයයි: {place}.",
            f"දරුවා {place} වෙත ගෙන යන්න.",
        ),
        answer=f"{command} → {place}",
        hints=("විධානයේ අවසාන වචනය බලන්න; දරුවා යා යුත්තේ එතැනටයි.",),
        another_view=("Run = දුවන්න, to the wall = බිත්තිය වෙත, Come back = ආපසු ආරම්භක තැනට.",),
    )


def _plural_lesson(game: Game, solution: Solution) -> Lesson | None:
    labels = _labels(game)
    lines = []
    for pair in solution.get("pairs", []) or []:  # type: ignore[union-attr]
        if not isinstance(pair, Mapping):
            continue
        one = labels.get(str(pair.get("singular_form_token")), "")
        many = labels.get(str(pair.get("plural_form_token")), "")
        rule = "f → ves" if one.lower().endswith("f") else "-es" if one.lower().endswith(("ch", "sh", "s", "x")) else "-s"
        lines.append(f"එකක් = {taught(one)}; බොහොමයක් = {taught(many)} ({rule}).")
    if not lines:
        return None
    return Lesson(
        steps=tuple(lines),
        answer="; ".join(line.split(" (")[0] for line in lines),
        hints=("එක දෙයක් පෙන්වන රූපයට එකවචනය; බොහෝ දේ පෙන්වන රූපයට බහුවචනය.",),
        another_view=("“This is a leaf.” — “These are leaves.”", "“This is a bud.” — “These are buds.”"),
    )


def _sequence_lesson(game: Game, solution: Solution) -> Lesson | None:
    labels = _labels(game)
    tokens = solution.get("ordered_chunk_tokens") or solution.get("ordered_turn_tokens") or []
    words = [labels.get(str(token), "") for token in tokens]  # type: ignore[union-attr]
    if not any(words):
        return None
    if "ordered_turn_tokens" in solution:
        speakers = {
            str(row.get("turn_token")): labels.get(str(row.get("speaker_token")), "")
            for row in solution.get("speaker_assignments", []) or []  # type: ignore[union-attr]
            if isinstance(row, Mapping)
        }
        lines = tuple(
            f"{index + 1}. {speakers.get(str(token), '')}: “{word}”"
            for index, (token, word) in enumerate(zip(tokens, words, strict=False))  # type: ignore[arg-type]
        )
        return Lesson(
            steps=("ප්‍රශ්නය මුලින්, එහි පිළිතුර ඊළඟට:", *lines),
            answer=" → ".join(f"“{word}”" for word in words),
            hints=("? ලකුණ ඇති වාක්‍යය ප්‍රශ්නයයි; එය මුලින් එයි.",),
            another_view=("සංවාදයක් ප්‍රශ්නය → පිළිතුර → ඊළඟ ප්‍රශ්නය → පිළිතුර ලෙස යයි.",),
        )
    joined = " ".join(words).replace(" ?", "?").replace(" .", ".")
    # A question with a blank (Is that a … ?) is shown in its printed form.
    if isinstance(game.get("source_form"), str) and "…" not in joined and "." * 3 in str(game["source_form"]):
        joined = str(game["source_form"]).replace(".................", "……")
    return Lesson(
        steps=(
            *(f"{index + 1} වන තැන: “{word}”" for index, word in enumerate(words)),
            f"එකට කියවන්න: “{joined}”" + (f" = {meaning(joined)[0]}" if meaning(joined) else ""),
        ),
        answer=f"“{joined}”",
        hints=(f"පළමු වචනය “{words[0]}”.",),
        another_view=(
            "ප්‍රශ්නයක් What / Who / Is / Do වලින් පටන් ගෙන ? වලින් අවසන් වේ."
            if joined.endswith("?")
            else "නම් දෙකක: විස්තර කරන වචනය මුලින්, දෙයේ නම පසුව (Lunch box, Staff room).",
        ),
    )


def _scene_reply_lesson(game: Game, solution: Solution) -> Lesson | None:
    labels = _labels(game)
    reply = labels.get(str(solution.get("response_token")), "")
    question = str(game.get("prompt_text", ""))
    scene = game.get("scene_renderer") if isinstance(game.get("scene_renderer"), Mapping) else {}
    if not reply:
        return None
    return Lesson(
        steps=(
            f"ප්‍රශ්නය: “{question}”" + (f" = {meaning(question)[0]}" if meaning(question) else ""),
            f"දර්ශනයේ ඇත්තේ {scene.get('emoji', '')} ({scene.get('non_colour_cue', '')}).",  # type: ignore[union-attr]
            f"එය කියන පිළිතුර: “{reply}”",
        ),
        answer=f"“{reply}”",
        hints=("දර්ශනයේ ඇති දේ මුලින්ම හඳුනාගන්න.",),
        another_view=(f"“{question}” — “{reply}”",),
    )


def diagnose(area_id: str, game: Game, solution: Solution, response: Mapping[str, object]) -> Diagnosis | None:
    """Which of the child's own placements did not match the right answer."""

    right = dict(_pairs(game, solution))
    given = _pairs(game, response)
    for word, target in given:
        if word in right and right[word] != target:
            return Diagnosis(
                you_did=f"ඔබ “{word}” → {_shown(target)} ලෙස තැබුවා",
                went_wrong=f"{taught(word)}; එය යා යුත්තේ {_shown(right[word])} වෙතටයි.",
            )
    return None
