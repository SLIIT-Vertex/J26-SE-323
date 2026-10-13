"""Builds an import plan from the question bank files, or a list of every problem found.

The plan is all-or-nothing: if any error is reported, nothing may be written.
Pure logic: images are reached through an `ImageSource` so this module has no I/O of its own.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from app.knowledge_tracing.application.answer_key import (
    AnswerKeyError,
    ParsedPart,
    parse_answer_key,
)
from app.knowledge_tracing.application.question_files import (
    AnswerEntry,
    DifficultyEntry,
    SkillEntry,
    parse_answers,
    parse_difficulty,
    parse_skill_map,
    parse_skill_nodes,
)

LANGUAGES = ("si", "ta")
TALL_IMAGE_RATIO = 2.5  # a single-part question this much taller than wide may hold two questions


@dataclass(frozen=True)
class ImageInfo:
    key: str
    width: int
    height: int
    content_hash: str


class ImageUnreadable(Exception):
    """The image exists but cannot be used (wrong format, corrupt)."""


class ImageSource(Protocol):
    def describe(self, language: str, question_id: str) -> ImageInfo | None:
        """Details of the question image, or None if it does not exist."""
        ...


@dataclass(frozen=True)
class ImportIssue:
    severity: Literal["error", "warning"]
    source: str  # file name, or 'bank' for cross-file checks
    message: str
    line: int | None = None
    question_id: str | None = None

    def __str__(self) -> str:
        where = self.source + (f":{self.line}" if self.line else "")
        who = f" [{self.question_id}]" if self.question_id else ""
        return f"{self.severity.upper():7} {where}{who} {self.message}"


@dataclass(frozen=True)
class SkillPlan:
    code: str
    sort_index: int
    area: str
    name_en: str
    name_si: str | None
    description: str | None


@dataclass(frozen=True)
class VariantPlan:
    language: str
    image: ImageInfo
    answer_key_raw: str
    parts: tuple[ParsedPart, ...]


@dataclass(frozen=True)
class QuestionPlan:
    id: str
    skill_code: str
    secondary_skill_codes: tuple[str, ...]
    difficulty: str
    est_seconds: int
    variants: dict[str, VariantPlan]


@dataclass
class ImportPlan:
    skills: list[SkillPlan] = field(default_factory=list)
    questions: list[QuestionPlan] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class QuestionBankFiles:
    """The raw text of every file, keyed by file name."""

    skill_nodes: tuple[str, str] | None = None  # (file name, text)
    answers: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)  # (set, lang)
    skill_maps: dict[str, tuple[str, str]] = field(default_factory=dict)  # set
    difficulties: dict[str, tuple[str, str]] = field(default_factory=dict)  # set


def load_files(directory: Path) -> QuestionBankFiles:
    """Find the bank files in a folder. A .md file is preferred over a .txt of the same name."""
    files = QuestionBankFiles()

    def read(path: Path) -> tuple[str, str]:
        return path.name, path.read_text(encoding="utf-8-sig")

    def pick(stem: str) -> Path | None:
        for suffix in (".md", ".txt"):
            candidate = directory / f"{stem}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    nodes = pick("skill_nodes")
    if nodes:
        files.skill_nodes = read(nodes)

    sets: set[str] = set()
    for path in directory.iterdir():
        match = re.fullmatch(r"(answers|skillMap|difficult-time)-(\d+)(-T)?\.(md|txt)", path.name)
        if match:
            sets.add(match.group(2))
    for number in sorted(sets, key=int):
        for language, suffix in (("si", ""), ("ta", "-T")):
            path = pick(f"answers-{number}{suffix}")
            if path:
                files.answers[(number, language)] = read(path)
        skill_map = pick(f"skillMap-{number}")
        if skill_map:
            files.skill_maps[number] = read(skill_map)
        difficulty = pick(f"difficult-time-{number}")
        if difficulty:
            files.difficulties[number] = read(difficulty)
    return files


def build_plan(
    files: QuestionBankFiles,
    images: ImageSource,
    feature_spec_order: list[str] | None = None,
) -> ImportPlan:
    plan = ImportPlan()

    def error(source: str, message: str, line: int | None = None, qid: str | None = None) -> None:
        plan.issues.append(ImportIssue("error", source, message, line, qid))

    def warn(source: str, message: str, line: int | None = None, qid: str | None = None) -> None:
        plan.issues.append(ImportIssue("warning", source, message, line, qid))

    # --- skills ------------------------------------------------------------------------------
    if files.skill_nodes is None:
        error("bank", "skill_nodes.md is missing")
        return plan
    nodes_name, nodes_text = files.skill_nodes
    nodes, node_issues = parse_skill_nodes(nodes_text)
    for issue in node_issues:
        error(nodes_name, issue.message, issue.line)
    plan.skills = _order_skills(nodes, feature_spec_order, error, warn)
    skill_codes = {skill.code for skill in plan.skills}

    # --- per-set files -------------------------------------------------------------------------
    sets = sorted({s for s, _ in files.answers} | set(files.skill_maps) | set(files.difficulties),
                  key=int)
    if not sets:
        error("bank", "no answers-*, skillMap-* or difficult-time-* files were found")
        return plan

    for number in sets:
        _plan_set(number, files, images, skill_codes, plan, error, warn)

    _check_duplicate_images(plan, warn)
    plan.questions.sort(key=lambda q: [int(p) for p in q.id.split(".")])
    return plan


def _order_skills(nodes, feature_spec_order, error, warn) -> list[SkillPlan]:
    by_code = {node.code: node for node in nodes}
    if len(nodes) != 30:
        error("skill_nodes", f"expected 30 skills, found {len(nodes)}")
    if feature_spec_order is None:
        warn(
            "bank",
            "no feature_spec.json: skills are numbered in skill_nodes.md order. This must match "
            "the order the model was trained with before any model is served.",
        )
        order = [node.code for node in nodes]
    else:
        missing = [code for code in feature_spec_order if code not in by_code]
        extra = [code for code in by_code if code not in feature_spec_order]
        for code in missing:
            error("feature_spec", f"skill {code} is in the feature spec but not in skill_nodes.md")
        for code in extra:
            error("skill_nodes", f"skill {code} is not in the feature spec")
        order = [code for code in feature_spec_order if code in by_code]
    return [
        SkillPlan(
            code=code,
            sort_index=index,
            area=by_code[code].area,
            name_en=by_code[code].name_en,
            name_si=by_code[code].name_si,
            description=by_code[code].description,
        )
        for index, code in enumerate(order)
    ]


def _plan_set(number, files, images, skill_codes, plan, error, warn) -> None:
    skill_map_file = files.skill_maps.get(number)
    difficulty_file = files.difficulties.get(number)
    if skill_map_file is None:
        error("bank", f"set {number}: skillMap-{number} is missing")
    if difficulty_file is None:
        error("bank", f"set {number}: difficult-time-{number} is missing")
    for language in LANGUAGES:
        if (number, language) not in files.answers:
            suffix = "" if language == "si" else "-T"
            error("bank", f"set {number}: answers-{number}{suffix} is missing")
    if skill_map_file is None or difficulty_file is None or any(
        (number, language) not in files.answers for language in LANGUAGES
    ):
        return

    skill_map_name, skill_map_text = skill_map_file
    difficulty_name, difficulty_text = difficulty_file
    skill_map = parse_skill_map(skill_map_text)
    difficulty = parse_difficulty(difficulty_text)
    for issue in skill_map.issues:
        error(skill_map_name, issue.message, issue.line)
    for issue in difficulty.issues:
        error(difficulty_name, issue.message, issue.line)

    answers_by_language: dict[str, dict[str, AnswerEntry]] = {}
    names: dict[str, str] = {}
    for language in LANGUAGES:
        name, text = files.answers[(number, language)]
        parsed = parse_answers(text)
        names[language] = name
        for issue in parsed.issues:
            error(name, issue.message, issue.line)
        answers_by_language[language] = parsed.entries
        for entry in parsed.entries.values():
            if entry.question_id.split(".")[0] != number:
                error(name, f"id {entry.question_id} does not belong to set {number}",
                      entry.line, entry.question_id)

    si_ids = set(answers_by_language["si"])
    ta_ids = set(answers_by_language["ta"])
    for qid in sorted(si_ids - ta_ids, key=_id_key):
        si_entry = answers_by_language["si"][qid]
        error(names["si"], f"{qid} has a Sinhala answer but no Tamil answer in {names['ta']}",
              si_entry.line, qid)
    for qid in sorted(ta_ids - si_ids, key=_id_key):
        ta_entry = answers_by_language["ta"][qid]
        error(names["ta"], f"{qid} has a Tamil answer but no Sinhala answer in {names['si']}",
              ta_entry.line, qid)

    answered = si_ids & ta_ids
    for qid in sorted(set(skill_map.entries) - answered, key=_id_key):
        error(skill_map_name, f"{qid} has a skill but no answer", skill_map.entries[qid].line, qid)
    for qid in sorted(set(difficulty.entries) - answered, key=_id_key):
        error(difficulty_name, f"{qid} has a difficulty but no answer",
              difficulty.entries[qid].line, qid)

    for qid in sorted(answered, key=_id_key):
        _plan_question(
            qid, answers_by_language, skill_map.entries.get(qid), difficulty.entries.get(qid),
            names, skill_map_name, difficulty_name, images, skill_codes, plan, error, warn,
        )


def _plan_question(
    qid: str,
    answers: dict[str, dict[str, AnswerEntry]],
    skill: SkillEntry | None,
    level: DifficultyEntry | None,
    names: dict[str, str],
    skill_map_name: str,
    difficulty_name: str,
    images: ImageSource,
    skill_codes: set[str],
    plan: ImportPlan,
    error,
    warn,
) -> None:
    before = len(plan.errors)
    if skill is None:
        error(names["si"], f"{qid} has an answer but no skill in {skill_map_name}",
              answers["si"][qid].line, qid)
    if level is None:
        error(names["si"], f"{qid} has an answer but no difficulty/time in {difficulty_name}",
              answers["si"][qid].line, qid)
    if skill is None or level is None:
        return
    for code in skill.skills:
        if code not in skill_codes:
            error(skill_map_name, f"unknown skill {code}", skill.line, qid)
    if skill.skills != level.skills:
        error(difficulty_name,
              f"skills {', '.join(level.skills)} differ from the skill map ({', '.join(skill.skills)})",
              level.line, qid)

    variants: dict[str, VariantPlan] = {}
    for language in LANGUAGES:
        entry = answers[language][qid]
        try:
            parts = tuple(parse_answer_key(entry.raw_key))
        except AnswerKeyError as problem:
            error(names[language], str(problem), entry.line, qid)
            continue
        try:
            image = images.describe(language, qid)
        except ImageUnreadable as problem:
            error(names[language], f"{language} image is unusable: {problem}", entry.line, qid)
            continue
        if image is None:
            error(names[language], f"no {language} image found", entry.line, qid)
            continue
        variants[language] = VariantPlan(language, image, entry.raw_key, parts)
        if len(parts) == 1 and image.width and image.height / image.width > TALL_IMAGE_RATIO:
            warn("images", f"{language} image is very tall but has one answer part; it may "
                 "contain more than one question", qid=qid)

    if len(variants) == len(LANGUAGES):
        si_parts, ta_parts = variants["si"].parts, variants["ta"].parts
        if len(si_parts) != len(ta_parts):
            error(names["ta"], f"{len(ta_parts)} answer parts but the Sinhala key has {len(si_parts)}",
                  answers["ta"][qid].line, qid)
        elif [p.answer_kind for p in si_parts] != [p.answer_kind for p in ta_parts]:
            warn(names["ta"], "answer kinds differ from the Sinhala key "
                 f"({[p.answer_kind for p in si_parts]} vs {[p.answer_kind for p in ta_parts]})",
                 answers["ta"][qid].line, qid)

    if len(plan.errors) > before or len(variants) < len(LANGUAGES):
        return
    plan.questions.append(
        QuestionPlan(
            id=qid,
            skill_code=skill.skills[0],
            secondary_skill_codes=tuple(dict.fromkeys(s for s in skill.skills[1:] if s != skill.skills[0])),
            difficulty=level.difficulty,
            est_seconds=level.est_seconds,
            variants=variants,
        )
    )


def _check_duplicate_images(plan: ImportPlan, warn) -> None:
    """The same picture on two different questions is suspicious. Sinhala/Tamil twins are fine."""
    owners: dict[str, set[str]] = {}
    for question in plan.questions:
        for variant in question.variants.values():
            owners.setdefault(variant.image.content_hash, set()).add(question.id)
    for ids in owners.values():
        if len(ids) > 1:
            ordered = sorted(ids, key=_id_key)
            warn("images", f"questions {', '.join(ordered)} share an identical image",
                 qid=ordered[0])


def _id_key(question_id: str) -> list[int]:
    return [int(part) for part in question_id.split(".")]
