"""Turns the evidence the game publishes into answers the knowledge model learns from.

The gamified module writes one record per scored answer into its outbox table
(`learner_evidence_outbox`, event `gamification_item_scored`). This module reads those records and
saves each accepted one as a game answer (`source = 1`) with its own skill and difficulty, because
the game's questions are not in the paper question bank.

Nothing here changes the game's table, and reading is safe to repeat: every answer is saved under
the key `game:<attempt id>`, so a record that was already read is recognised and not counted again.

A record is used only when ALL of these hold; every other record is skipped, with a reason:

* the game itself says it may be used for models (`model_ingestion_eligible`), unless this run was
  explicitly told to include development records, which is for trying the flow locally only;
* its skill is one of our 30 AND agrees with the skill crosswalk for the game's own skill id. The
  game's publisher once put one fixed skill on every record; this check keeps a wrong label from
  ever reaching the model;
* its difficulty is easy, medium or hard, and the answer is plainly right or wrong;
* the learner exists and has a language we can use.
"""

import json
import os
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.knowledge_tracing.application.attempts import (
    DIFFICULTIES,
    AnsweredInFutureError,
    AttemptService,
    DigitalAttemptCommand,
    IdempotencyKeyReusedError,
    InvalidAttemptError,
    LearnerNotFoundError,
    SkillNotFoundError,
)
from app.knowledge_tracing.domain.feature_spec import FeatureSpec

EVENT_TYPE = "gamification_item_scored"
KEY_PREFIX = "game:"
LANGUAGES = ("si", "ta")
MAX_TIME_MS = 600_000  # the same ceiling as POST /attempts; longer times are clamped, not refused
DEVELOPMENT_ENVIRONMENTS = ("development", "test")

# Skip reasons, as they appear in the report.
OTHER_EVENT = "other_event"
BAD_PAYLOAD = "bad_payload"
NOT_ELIGIBLE = "not_eligible"
UNKNOWN_SKILL = "unknown_skill"
NOT_IN_CROSSWALK = "skill_not_in_crosswalk"
SKILL_MISMATCH = "skill_mismatch"
UNKNOWN_DIFFICULTY = "unknown_difficulty"
NO_LANGUAGE = "no_language"
UNKNOWN_LEARNER = "unknown_learner"
IN_FUTURE = "in_future"
KEY_REUSED = "key_reused"


class CrosswalkUnavailable(Exception):
    """The skill crosswalk is missing or empty, so no record can be checked: nothing is read."""


@dataclass(frozen=True, slots=True)
class GameEvidence:
    """One record from the game's outbox."""

    key: str
    learner_id: UUID
    game_skill_id: str
    universal_skill_id: str
    event_type: str
    payload: Mapping[str, object]
    contract_version: str
    created_at: datetime


class EvidenceSource(Protocol):
    def batches(self, size: int) -> Iterator[list[GameEvidence]]:
        """Every record, oldest first, a batch at a time."""
        ...


@dataclass(slots=True)
class IngestReport:
    scanned: int = 0
    ingested: int = 0  # saved now (with dry_run: the ones that would be saved)
    already_ingested: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    learners: set[UUID] = field(default_factory=set)

    def __str__(self) -> str:
        lines = [
            f"records scanned: {self.scanned}",
            f"answers saved: {self.ingested} (for {len(self.learners)} learners)",
            f"already saved earlier: {self.already_ingested}",
        ]
        if self.skipped:
            lines.append("skipped:")
            lines += [f"  {reason}: {count}" for reason, count in sorted(self.skipped.items())]
        else:
            lines.append("skipped: none")
        return "\n".join(lines)


# ---- the skill crosswalk --------------------------------------------------------------------------


def default_crosswalk_path() -> Path:
    """Where the gamified module keeps its crosswalk (the same data folder it uses)."""
    configured = os.environ.get("MINDBRIDGE_GAMIFICATION_DATA_DIR")
    root = Path(configured) if configured else Path(__file__).resolve().parents[4] / "data" / "gamification"
    return root / "skill-catalogue-review" / "v1" / "universal-skill-crosswalk.jsonl"


def load_crosswalk(path: Path | None = None) -> dict[str, str]:
    """The game's own skill id -> one of our 30 skills."""
    path = path or default_crosswalk_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CrosswalkUnavailable(f"cannot read the skill crosswalk at {path}") from error
    mapping: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        mapping[str(row["gamification_skill_id"])] = str(row["universal_skill_id"])
    if not mapping:
        raise CrosswalkUnavailable(f"the skill crosswalk at {path} is empty")
    return mapping


# ---- one record -> one answer -----------------------------------------------------------------------


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _count(value: object) -> int | None:
    """A whole number of at least 0, or None (a bool is not a number here)."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value != int(value):
        return None
    return int(value) if value >= 0 else None


def evidence_to_command(
    evidence: GameEvidence,
    spec: FeatureSpec,
    crosswalk: Mapping[str, str] | None,
    learner_language: str | None,
    *,
    include_development: bool = False,
) -> DigitalAttemptCommand | str:
    """The answer to save, or the reason this record is not used."""
    if evidence.event_type != EVENT_TYPE:
        return OTHER_EVENT
    payload = evidence.payload

    attempt_id = payload.get("attempt_id")
    correct = payload.get("correct")
    if not isinstance(attempt_id, str) or not attempt_id.strip() or not isinstance(correct, bool):
        return BAD_PAYLOAD  # without an id, or without a plain right/wrong, it cannot be used

    eligible = payload.get("model_ingestion_eligible") is True
    development = payload.get("environment") in DEVELOPMENT_ENVIRONMENTS
    if not eligible and not (include_development and development):
        return NOT_ELIGIBLE

    skill = evidence.universal_skill_id
    if skill not in spec.skills:
        return UNKNOWN_SKILL
    if crosswalk is not None:
        expected = crosswalk.get(evidence.game_skill_id)
        if expected is None:
            return NOT_IN_CROSSWALK
        if expected != skill:
            return SKILL_MISMATCH  # the record's label disagrees with the crosswalk

    difficulty = payload.get("difficulty")
    if difficulty not in DIFFICULTIES:
        return UNKNOWN_DIFFICULTY

    language = payload.get("language") if payload.get("language") in LANGUAGES else learner_language
    if language not in LANGUAGES:
        return NO_LANGUAGE

    time_ms = _count(payload.get("response_time_ms"))
    hints = _count(payload.get("hint_count")) or 0
    if payload.get("supported") is True:
        hints = max(hints, 1)  # an answer given with help on screen counts as one hint

    return DigitalAttemptCommand(
        learner_id=evidence.learner_id,
        skill_code=skill,
        difficulty=str(difficulty),
        language=str(language),
        correct=correct,
        answered_at=_aware(evidence.created_at),
        time_ms=None if time_ms is None else min(time_ms, MAX_TIME_MS),
        hints=hints,
        idempotency_key=f"{KEY_PREFIX}{attempt_id.strip()}",
    )


# ---- reading everything -----------------------------------------------------------------------------


class GameEvidenceIngestor:
    def __init__(
        self,
        source: EvidenceSource,
        attempts: AttemptService,
        learner_language: Callable[[UUID], str | None],
        spec: FeatureSpec,
        crosswalk: Mapping[str, str] | None,
        *,
        include_development: bool = False,
        batch_size: int = 500,
    ) -> None:
        self.source = source
        self.attempts = attempts
        self.learner_language = learner_language
        self.spec = spec
        self.crosswalk = crosswalk
        self.include_development = include_development
        self.batch_size = batch_size

    def run(self, *, dry_run: bool = False) -> IngestReport:
        """Save every usable record that is not saved yet. With dry_run, only report."""
        report = IngestReport()
        for batch in self.source.batches(self.batch_size):
            for evidence in batch:
                report.scanned += 1
                self._one(evidence, report, dry_run)
        return report

    def _one(self, evidence: GameEvidence, report: IngestReport, dry_run: bool) -> None:
        language = self.learner_language(evidence.learner_id)  # None: no such learner
        outcome = evidence_to_command(
            evidence,
            self.spec,
            self.crosswalk,
            language,
            include_development=self.include_development,
        )
        if isinstance(outcome, str):
            report.skipped[UNKNOWN_LEARNER if outcome == NO_LANGUAGE and language is None else outcome] += 1
            return
        if dry_run:
            known = self.attempts.repository.find_by_idempotency_key(outcome.idempotency_key or "")
            if known is not None:
                report.already_ingested += 1
            else:
                report.ingested += 1
                report.learners.add(outcome.learner_id)
            return
        try:
            _, created = self.attempts.log_digital_attempt(outcome)
        except LearnerNotFoundError:
            report.skipped[UNKNOWN_LEARNER] += 1
        except AnsweredInFutureError:
            report.skipped[IN_FUTURE] += 1
        except IdempotencyKeyReusedError:
            report.skipped[KEY_REUSED] += 1  # the same attempt id arrived with different content
        except (SkillNotFoundError, InvalidAttemptError):
            report.skipped[BAD_PAYLOAD] += 1
        else:
            if created:
                report.ingested += 1
                report.learners.add(outcome.learner_id)
            else:
                report.already_ingested += 1
