"""Notation evidence that can only veto a confident decision; it never selects a skill."""

import re

from app.adaptive_tutor.application.skill_mapper import has_explicit_fraction_notation
from tools.skill_mapper_benchmark.normalization import normalize_math_text

_CLOCK_OR_DATE = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?!\d)|\d{1,4}/\d{1,2}/\d{2,4}|\d\s*[ap]\.?m\b")
_CURRENCY = re.compile(r"\b(?:rs\.?|rupees?|lkr)\s*\d|\d\s*(?:rs|rupees?)\b|රු\.?\s*\d|ரூ\.?\s*\d")
_MASS_OR_CAPACITY = re.compile(r"\d\s*(?:kg|g|mg|ml|l|litres?|liters?)\b")
_LENGTH = re.compile(r"\d\s*(?:mm|cm|km|m)\b")


def notation_evidence(text: str) -> frozenset[str]:
    """Skills whose curriculum scope explicitly owns notation present in the message."""

    normalized = normalize_math_text(text).casefold()
    skills: set[str] = set()
    if has_explicit_fraction_notation(normalized):
        skills.add("MAT-FRC")
    if _CLOCK_OR_DATE.search(normalized):
        skills.add("MAT-TIM")
    if _CURRENCY.search(normalized):
        skills.add("MAT-MON")
    if _MASS_OR_CAPACITY.search(normalized):
        skills.add("MAT-MAS")
    if _LENGTH.search(normalized):
        skills.add("MAT-LEN")
    return frozenset(skills)


def contradicts_evidence(top_skill_id: str, evidence: frozenset[str]) -> bool:
    """A confident pick outside every evidenced skill must become a clarification instead."""

    return bool(evidence) and top_skill_id not in evidence
