import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.gamification.domain.types import SupportActionType

SKILL_CODE_PATTERN = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")
SUPPORTED_LANGUAGE_CODES = frozenset({"en", "si", "ta"})


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class SourceCitation:
    source_id: str
    page_from: str
    page_to: str
    skill_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_id or not self.page_from or not self.skill_candidate_ids:
            raise ValueError("source citations require a source, page, and skill candidate")


@dataclass(frozen=True, slots=True)
class SkillReview:
    skill_code: str
    stable_index: int
    taxonomy_version: str
    domain: str
    grade: int
    status: ReviewStatus
    development_only: bool
    learner_medium: str
    required_label_languages: tuple[str, ...]
    deferred_languages: tuple[str, ...]
    scope_note: str
    definition: str
    labels: Mapping[str, str | None]
    prerequisites: tuple[str, ...]
    observable_success: tuple[str, ...]
    misconceptions: tuple[str, ...]
    distinguishing_evidence: tuple[str, ...]
    eligible_support_action_types: tuple[SupportActionType, ...]
    verification_pair_rules: Mapping[str, object]
    source_citations: tuple[SourceCitation, ...]
    reviewer_id: str | None = None
    reviewed_on: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        labels = MappingProxyType(dict(self.labels))
        rules = MappingProxyType(dict(self.verification_pair_rules))
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "verification_pair_rules", rules)
        if not SKILL_CODE_PATTERN.fullmatch(self.skill_code):
            raise ValueError("skill_code must use the stable AAA-BBB format")
        if not 0 <= self.stable_index <= 29:
            raise ValueError("stable_index must remain between 0 and 29")
        if self.domain not in {"APT", "MAT", "LAN", "ENV"}:
            raise ValueError("unsupported skill domain")
        if self.grade not in {4, 5}:
            raise ValueError("skill grade must be 4 or 5")
        if self.learner_medium not in SUPPORTED_LANGUAGE_CODES:
            raise ValueError("learner_medium must be si, ta, or en")
        required_languages = set(self.required_label_languages)
        deferred_languages = set(self.deferred_languages)
        if len(required_languages) != len(self.required_label_languages) or len(
            deferred_languages
        ) != len(self.deferred_languages):
            raise ValueError("scope language lists cannot contain duplicates")
        if not required_languages or required_languages & deferred_languages:
            raise ValueError("required languages must be non-empty and disjoint from deferred ones")
        if not required_languages | deferred_languages <= SUPPORTED_LANGUAGE_CODES:
            raise ValueError("scope contains an unsupported language")
        if not self.scope_note:
            raise ValueError("skill review requires a scope note")
        if not self.taxonomy_version or not self.definition or not labels.get("en"):
            raise ValueError("skill review requires a version, definition, and English label")
        if any(language not in labels for language in required_languages | deferred_languages):
            raise ValueError("scope languages must exist in labels")
        if not self.source_citations:
            raise ValueError("skill review requires authoritative source citations")
        if self.status is ReviewStatus.APPROVED:
            if self.development_only:
                raise ValueError("development-only skills cannot be approved")
            if not self.reviewer_id or not self.reviewed_on:
                raise ValueError("approved skills require reviewer identity and date")
            if any(not labels.get(language) for language in required_languages):
                raise ValueError("approved skills require every in-scope language label")
        if self.status is ReviewStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError("superseded skills require a replacement skill code")


@dataclass(frozen=True, slots=True)
class SkillBinding:
    skill_candidate_id: str
    knowledge_tracing_skill_id: str
    mapping_version: str
    status: ReviewStatus
    confidence: str
    rationale: str
    source_ids: tuple[str, ...]
    reviewer_id: str | None = None
    reviewed_on: str | None = None

    def __post_init__(self) -> None:
        if not self.skill_candidate_id or not SKILL_CODE_PATTERN.fullmatch(
            self.knowledge_tracing_skill_id
        ):
            raise ValueError("binding requires valid candidate and knowledge-tracing IDs")
        if self.confidence not in {"low", "medium", "high"}:
            raise ValueError("binding confidence must be low, medium, or high")
        if not self.mapping_version or not self.rationale or not self.source_ids:
            raise ValueError("binding requires version, rationale, and sources")
        if self.status is ReviewStatus.APPROVED and (
            not self.reviewer_id or not self.reviewed_on
        ):
            raise ValueError("approved bindings require reviewer identity and date")
