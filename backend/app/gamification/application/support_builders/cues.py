"""What the help says to the child, for each subject, in the game's own language (Sinhala).

The builders decide what each help type shows; this module only holds the words. Mathematics cues
talk about places, steps and quantities; English cues talk about words, pictures, headings and
order. No cue carries an answer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectCues:
    visual_opening: tuple[str, ...]
    guided_questions: tuple[str, ...]
    # One extra guided question, pointed at the kind of difficulty Model 1 named.
    guided_focus: dict[str, str]
    # The idea again from another angle, for each kind of difficulty.
    reexplanations: dict[str, tuple[str, ...]]
    simpler_start: tuple[str, ...]
    simpler_return: tuple[str, ...]
    prerequisite_start: tuple[str, ...]
    prerequisite_return: tuple[str, ...]
    worked_view: tuple[str, ...]
    worked_then_you: tuple[str, ...]

    def focus(self, family: str | None) -> str:
        return self.guided_focus.get(family or "unclear", self.guided_focus["unclear"])

    def reexplanation(self, family: str | None) -> tuple[str, ...]:
        return self.reexplanations.get(family or "unclear", self.reexplanations["unclear"])


MATHEMATICS = SubjectCues(
    visual_opening=("ඉස්මතු කළ කොටස හොඳින් බලන්න. පිළිතුර ඔබම හදන්න.",),
    guided_questions=(
        "මෙම ප්‍රශ්නය ඔබෙන් ඉල්ලන්නේ කුමක්ද?",
        "ඔබට දැනටමත් පෙනෙන අගයන් හෝ කොටස් මොනවාද?",
        "පළමුව කළ යුත්තේ කුමක්ද? එම එක් පියවර පමණක් කරන්න.",
        "ඊළඟ පියවර කලින් පියවරෙන් ලැබුණු දෙයින් පටන් ගන්නේ කෙසේද?",
        "ඔබේ පිළිතුර ප්‍රශ්නයට ගැළපේදැයි නැවත බලන්න.",
    ),
    guided_focus={
        "representation": "සෑම ඉලක්කමක්ම හෝ කොටසක්ම තිබෙන්නේ කුමන තැනේද?",
        "procedure": "ඔබ මඟ හැරිය හැකි පියවරක් තිබේද—ගෙන යාම, ණයට ගැනීම, හුවමාරුව?",
        "relation": "මෙහි ඒකක දෙක හෝ ක්‍රියා දෙක අතර සම්බන්ධය කුමක්ද?",
        "prerequisite": "මේ ගණනයට අවශ්‍ය කුඩා කරුණ කුමක්ද? එය මුලින් සිතන්න.",
        "unclear": "ප්‍රශ්නය ඔබේම වචනවලින් කියා බලන්න.",
    },
    reexplanations={
        "representation": (
            ("පන්තියේ හැම ළමයෙකුටම තමන්ගේම පුටුවක් තියෙනවා වගේ, හැම ඉලක්කමකටම හෝ කොටසකටම තමන්ගේම තැනක් තියෙනවා."),
            "තැන වෙනස් වුණොත් එහි අගයත් වෙනස් වෙනවා. තැන මුලින්ම හොයාගන්න.",
        ),
        "procedure": (
            "ගණනය කිරීම පඩිපෙළක් නගිනවා වගේ. එක පඩියක් මඟ හැරුණොත් උඩට යන්න බැහැ.",
            "පියවර එකින් එක, පිළිවෙළට කරන්න. එක් පියවරක ප්‍රතිඵලය ඊළඟ පියවරට ගෙනියන්න.",
        ),
        "relation": (
            ("රුපියල් සහ ශත වගේ, මෙහි දේවල් දෙකක් තියෙනවා. ඒවා එකම දේ නොවේ, නමුත් එකක් අනෙකෙන් හැදෙනවා."),
            "දෙක අතර සම්බන්ධය මතක තබාගෙන, ඒ සම්බන්ධයට අනුව වැඩේ කරන්න.",
        ),
        "prerequisite": (
            ("ලොකු ගොඩනැගිල්ලක් හදන්නේ කුඩා ගඩොල්වලින්. මේ ප්‍රශ්නයත් කුඩා කරුණු කිහිපයකින් හැදිලා තියෙන්නේ."),
            "ඔබ දන්නා කුඩා කරුණෙන් පටන් අරන්, එය මේ ප්‍රශ්නයට යොදන්න.",
        ),
        "unclear": (
            "මේ ක්‍රීඩාවේ අරමුණ නැවත සිතමු: ඔබට පෙනෙන දේවල් අතර සම්බන්ධය හොයාගන්න.",
            "කලබල නොවී, ඔබට විශ්වාස එක් දෙයකින් පටන් ගන්න.",
        ),
    },
    simpler_start=("මෙය එකම ක්‍රීඩාවයි, නමුත් පහසු අගයන් සමඟ. මුලින් මෙය කරන්න.",),
    simpler_return=("හොඳයි! දැන් ඔබේ මුල් ප්‍රශ්නයට නැවත යමු.",),
    prerequisite_start=("මෙයට පෙර ඉගෙනගත් කුසලතාවක් මුලින් කරමු.",),
    prerequisite_return=("දැන් ඔබේ මුල් ප්‍රශ්නයට නැවත යමු.",),
    worked_view=("මේ වෙනත් ප්‍රශ්නයක්. එය විසඳන ආකාරය පියවරෙන් පියවර බලන්න.",),
    worked_then_you=("දැන් ඔබේ ප්‍රශ්නය ඔබම විසඳන්න.",),
)

ENGLISH = SubjectCues(
    visual_opening=("ඉස්මතු කළ රූපය හෝ වචනය හොඳින් බලන්න. සම්බන්ධය ඔබම තබන්න.",),
    guided_questions=(
        "මෙම ක්‍රීඩාවේ ඔබ කළ යුත්තේ කුමක්ද?",
        "රූපයේ හෝ දර්ශනයේ ඔබට පෙනෙන්නේ කුමක්ද?",
        "එක් ඉංග්‍රීසි වචනයක් තෝරා එය හොඳින් කියවන්න.",
        "ඒ වචනයට ගැළපෙන රූපය, තැන හෝ කොටස කුමක්දැයි සිතන්න.",
        "ඔබ තැබූ සෑම සම්බන්ධයක්ම නැවත පරීක්ෂා කරන්න.",
    ),
    guided_focus={
        "representation": "රූප දෙකක් සමාන නම්, එකකට පමණක් ඇති කොටස කුමක්ද?",
        "procedure": "පළමුව එන්නේ කුමක්ද? ඊළඟට එන්නේ කුමක්ද?",
        "relation": "මෙම වචනය අයත් වන්නේ කුමන කාණ්ඩයට හෝ කාර්යයටද?",
        "prerequisite": "මෙම ඉංග්‍රීසි වචනයේ සිංහල තේරුම කුමක්ද?",
        "unclear": "ඔබ විශ්වාස කරන එක් වචනයකින් පටන් ගන්න.",
    },
    reexplanations={
        "representation": (
            "හැම ඉංග්‍රීසි වචනයක්ම එක් දෙයකට නමක්. රූපයේ හැඩය, පාට සහ කොටස් බලා නම හඳුනාගන්න.",
            "දේවල් දෙකක් සමාන පෙනුනොත්, එකකට පමණක් ඇති කොටස සොයන්න.",
        ),
        "procedure": (
            "වාක්‍යයක් හෝ සංවාදයක් පෝළිමක් වගේ. මුලින් එන කොටස මුලින්ම සිටිය යුතුයි.",
            "මුල සහ අග මුලින් හොයාගෙන, මැද කොටස් ඊට පසු තබන්න.",
        ),
        "relation": (
            ("පාසල් බෑගයේ පොත් එක තැනක, කෑම පෙට්ටිය තව තැනක තියෙනවා වගේ, වචනත් ඒවායේ කාණ්ඩවලට අයත්."),
            "වචනය කුමක් කරන්නද, කොහේ තිබෙන්නද කියා සිතා එහි කාණ්ඩය තෝරන්න.",
        ),
        "prerequisite": (
            "ඉංග්‍රීසි වචනයක් සිංහල වචනයක යාළුවෙක් වගේ. දෙකම එකම දේට කියන නම්.",
            "වචනය ශබ්ද නඟා කියවා, එයින් අදහස් වන දේ මතකයට ගන්න.",
        ),
        "unclear": (
            "මේ ක්‍රීඩාවේ අරමුණ නැවත සිතමු: ඉංග්‍රීසි වචනය සහ එහි අර්ථය එකට තබන්න.",
            "කලබල නොවී, ඔබට විශ්වාස එක් වචනයකින් පටන් ගන්න.",
        ),
    },
    simpler_start=("මෙය එකම ක්‍රීඩාවයි, නමුත් වචන අඩුවෙන්. මුලින් මෙය කරන්න.",),
    simpler_return=("හොඳයි! දැන් ඔබේ මුල් ක්‍රීඩාවට නැවත යමු.",),
    prerequisite_start=("මෙයට පෙර ඉගෙනගත් වචන කුසලතාවක් මුලින් කරමු.",),
    prerequisite_return=("දැන් ඔබේ මුල් ක්‍රීඩාවට නැවත යමු.",),
    worked_view=("මේ වෙනත් වචන කට්ටලයක්. ඒවා ගළපන ආකාරය පියවරෙන් පියවර බලන්න.",),
    worked_then_you=("දැන් ඔබේ ක්‍රීඩාව ඔබම කරන්න.",),
)

SUBJECT_CUES = {"MAT": MATHEMATICS, "ENG": ENGLISH}


def cues_for(subject: str) -> SubjectCues:
    return SUBJECT_CUES[subject]
