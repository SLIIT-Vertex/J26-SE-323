"""Parsers for the question bank's text files (pure: they take text, not paths).

    answers-<set>[-T].md       `4.48 - i. a, ii. b`   one answer key per question
    skillMap-<set>.md          `4.20 - LAN-CMP, LAN-ORT`
    difficult-time-<set>.md    `4.20 - LAN-CMP, LAN-ORT: Hard / Medium | 3.0 / 1.5 mins ...`
    skill_nodes.md             the 30 skills as a markdown table
"""

import re
from dataclasses import dataclass, field
from typing import Generic, TypeVar

ID = r"\d+\.\d+"
SKILL_CODE = r"[A-Z]{3}-[A-Z]{3}"
T = TypeVar("T")
AREAS = {"APT", "MAT", "LAN", "ENV"}
DIFFICULTIES = {"easy", "medium", "hard"}


@dataclass(frozen=True)
class FileIssue:
    line: int | None
    message: str


@dataclass(frozen=True)
class AnswerEntry:
    question_id: str
    raw_key: str
    line: int


@dataclass(frozen=True)
class SkillEntry:
    question_id: str
    skills: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class DifficultyEntry:
    question_id: str
    skills: tuple[str, ...]
    levels: tuple[str, ...]
    minutes: tuple[float, ...]
    line: int

    @property
    def difficulty(self) -> str:
        return self.levels[0]

    @property
    def est_seconds(self) -> int:
        return max(1, round(sum(self.minutes) * 60))


@dataclass(frozen=True)
class SkillNode:
    code: str
    area: str
    name_en: str
    name_si: str | None
    description: str | None


@dataclass
class Parsed(Generic[T]):
    entries: dict[str, T] = field(default_factory=dict)
    issues: list[FileIssue] = field(default_factory=list)


def _lines(text: str) -> list[str]:
    return text.lstrip("﻿").splitlines()


def parse_answers(text: str) -> Parsed[AnswerEntry]:
    result: Parsed[AnswerEntry] = Parsed()
    pattern = re.compile(rf"^\s*({ID})\s*-\s*(.*?)\s*$")
    for number, line in enumerate(_lines(text), start=1):
        if not line.strip():
            continue
        match = pattern.match(line)
        if not match:
            result.issues.append(
                FileIssue(number, f"not '<id> - <answer>': {line.strip()[:60]!r}")
            )
            continue
        question_id, raw_key = match.groups()
        if question_id in result.entries:
            result.issues.append(FileIssue(number, f"duplicate id {question_id}"))
            continue
        if not raw_key:
            result.issues.append(FileIssue(number, f"{question_id} has an empty answer"))
            continue
        result.entries[question_id] = AnswerEntry(question_id, raw_key, number)
    return result


def parse_skill_map(text: str) -> Parsed[SkillEntry]:
    result: Parsed[SkillEntry] = Parsed()
    pattern = re.compile(rf"^\s*({ID})\s*-?\s*(.+?)\s*$")
    for number, line in enumerate(_lines(text), start=1):
        if not line.strip():
            continue
        match = pattern.match(line)
        if not match:
            result.issues.append(FileIssue(number, f"not '<id> - <skill>': {line.strip()[:60]!r}"))
            continue
        question_id, rest = match.groups()
        skills = tuple(part.strip() for part in rest.split(","))
        bad = [s for s in skills if not re.fullmatch(SKILL_CODE, s)]
        if bad:
            result.issues.append(FileIssue(number, f"{question_id}: bad skill code {bad[0]!r}"))
            continue
        if question_id in result.entries:
            result.issues.append(FileIssue(number, f"duplicate id {question_id}"))
            continue
        result.entries[question_id] = SkillEntry(question_id, skills, number)
    return result


_DIFFICULTY_ENTRY = re.compile(
    rf"({ID})\s*-?\s*({SKILL_CODE}(?:\s*,\s*{SKILL_CODE})*)\s*:\s*"
    r"([A-Za-z]+(?:\s*/\s*[A-Za-z]+)*)\s*\|\s*"
    r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)*)\s*mins?\b"
)


def parse_difficulty(text: str) -> Parsed[DifficultyEntry]:
    result: Parsed[DifficultyEntry] = Parsed()
    cleaned = text.lstrip("﻿")
    covered: list[tuple[int, int]] = []
    for match in _DIFFICULTY_ENTRY.finditer(cleaned):
        covered.append(match.span())
        line = cleaned.count("\n", 0, match.start()) + 1
        question_id, skills_text, levels_text, minutes_text = match.groups()
        skills = tuple(s.strip() for s in skills_text.split(","))
        levels = tuple(level.strip().lower() for level in levels_text.split("/"))
        minutes = tuple(float(m) for m in minutes_text.split("/"))
        if any(level not in DIFFICULTIES for level in levels):
            result.issues.append(FileIssue(line, f"{question_id}: unknown difficulty {levels_text!r}"))
            continue
        if not (len(skills) == len(levels) == len(minutes)):
            result.issues.append(
                FileIssue(line, f"{question_id}: {len(skills)} skills but {len(levels)} "
                          f"difficulties and {len(minutes)} times")
            )
            continue
        if question_id in result.entries:
            result.issues.append(FileIssue(line, f"duplicate id {question_id}"))
            continue
        result.entries[question_id] = DifficultyEntry(question_id, skills, levels, minutes, line)

    leftover = _remove_spans(cleaned, covered)
    if leftover.strip():
        first = leftover.strip().split()[0]
        line = cleaned.find(first)
        line_no = cleaned.count("\n", 0, max(line, 0)) + 1
        result.issues.append(
            FileIssue(line_no, f"text that is not a difficulty entry: {leftover.strip()[:60]!r}")
        )
    return result


def _remove_spans(text: str, spans: list[tuple[int, int]]) -> str:
    pieces: list[str] = []
    position = 0
    for start, end in spans:
        pieces.append(text[position:start])
        position = end
    pieces.append(text[position:])
    return " ".join(pieces)


def parse_skill_nodes(text: str) -> tuple[list[SkillNode], list[FileIssue]]:
    """Rows of the markdown table: | Domain | Skill ID | English | Sinhala | Description |."""
    nodes: list[SkillNode] = []
    issues: list[FileIssue] = []
    seen: set[str] = set()
    for number, line in enumerate(_lines(text), start=1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] not in AREAS:
            continue
        area, code, name_en = cells[0], cells[1], cells[2]
        if not re.fullmatch(SKILL_CODE, code):
            issues.append(FileIssue(number, f"bad skill code {code!r}"))
            continue
        if not code.startswith(area + "-"):
            issues.append(FileIssue(number, f"{code} does not belong to area {area}"))
            continue
        if code in seen:
            issues.append(FileIssue(number, f"duplicate skill {code}"))
            continue
        seen.add(code)
        name_si = cells[3] if len(cells) > 3 and cells[3] else None
        description = cells[4] if len(cells) > 4 and cells[4] else None
        nodes.append(SkillNode(code, area, name_en, name_si, description))
    return nodes, issues
