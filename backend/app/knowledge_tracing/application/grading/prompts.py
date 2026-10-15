"""The instructions given to the reader, and parsing of what it returns.

Prompt `item-blind-v2`. "Blind" means the reader is never told the answer: it transcribes what
the child wrote or marked, and our code decides right or wrong. Changing the wording means a new
PROMPT_VERSION and a benchmark run.
"""

import json
import re
from collections.abc import Sequence

from pydantic import ValidationError

from app.knowledge_tracing.application.grading.types import ItemRead, PartSpec, VisionError

PROMPT_VERSION = "item-blind-v2"

_LANGUAGE_NAMES = {"si": "Sinhala", "ta": "Tamil"}


def blind_prompt(parts: Sequence[PartSpec], language: str, has_reference: bool = False) -> str:
    """The text sent with the cropped question picture. Contains no answer, by construction."""
    language_name = _LANGUAGE_NAMES.get(language, language)
    lines = [
        ("You are checking a Sri Lankan Grade 5 scholarship practice paper that a child answered "
        "by hand and a parent photographed. The image shows ONE question (printed text and "
        "pictures in black, the child's pencil or pen writing or marks on top). The question is "
        f"in {language_name}. Handwriting may be Sinhala, Tamil, English letters, digits or "
        "Roman numerals. Ignore any partial lines of neighbouring questions at the very top or "
        "bottom edge of the image."),
    ]
    if has_reference:
        lines.append(
            "A SECOND image is provided: it is the same question BLANK, as printed. Use it only "
            "to tell printed content from the child's additions. The FIRST image is the child's "
            "answered version."
        )
    count = len(parts)
    lines.append("")
    lines.append(f"This question has {count} answer part{'s' if count != 1 else ''}:")
    for part in parts:
        description = f"- Part {part.index}"
        if part.label:
            description += f" (labelled '{part.label}.')"
        if part.kind == "choice" and part.option_labels:
            description += f". A multiple-choice part; the options are {', '.join(part.option_labels)}."
        elif part.kind == "number":
            description += ". The child writes a number."
        elif part.kind == "text":
            description += ". The child writes a word or a sentence."
        elif part.kind == "instruction":
            description += ". Something to look for on the page."
        if part.instruction:
            description += f' Extra instruction: "{part.instruction}".'
        lines.append(description)

    lines += [
        "",
        "Task: transcribe the child's answer for every part.",
        "Rules:",
        ("- Transcribe exactly what the child wrote; do NOT solve the question and do NOT "
        "correct spelling."),
        ("- For a multiple-choice part, report the option label the child circled, ticked, "
        'underlined or wrote (for example "ii" or "2", exactly as printed beside the option).'),
        '- If a part has nothing written or marked, set "blank": true and leave the text empty.',
        ("- Write numbers with digits (Sinhala or Tamil digits become 0-9). Keep units and extra "
        'words the child wrote (for example "31 kg 400 g", "6 more").'),
        ("- Read word answers LETTER BY LETTER exactly as written. Children misspell: keep wrong, "
        'missing or extra letters (for example "rabite", not "rabbit"). Never auto-correct and '
        'never guess what they "meant".'),
        ("- Only pencil or pen marks made by the child count as an answer. Printed pictures, lines "
        "and option labels do not. If a part has no such mark, it is blank."),
        '- If you really cannot read it, give your best guess and lower "confidence" (0 to 1).',
    ]
    if any(part.instruction for part in parts):
        lines.append(
            'For a part with an "Extra instruction", ALSO set "instruction_met" to true or false '
            "by looking at the image (the answer then describes what you see)."
        )
    lines += [
        "Return ONLY JSON, one entry per part, in this shape:",
        ('{"parts":[{"part":1,"answer":"<what the child wrote or marked>","blank":false,'
        '"confidence":0.9,"instruction_met":null}],"notes":"<short, optional>"}'),
    ]
    return "\n".join(lines)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_item_read(text: str) -> ItemRead:
    """Turn a model's reply into an ItemRead, or raise VisionError('invalid_json').

    Strips <think> blocks and code fences, then takes the outermost JSON object.
    """
    cleaned = _THINK.sub("", text or "").strip()
    cleaned = _FENCE.sub("", cleaned).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise VisionError("invalid_json", "no JSON object in the reply")
    try:
        return ItemRead.model_validate(json.loads(cleaned[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as error:
        raise VisionError("invalid_json", str(error)[:200]) from error
