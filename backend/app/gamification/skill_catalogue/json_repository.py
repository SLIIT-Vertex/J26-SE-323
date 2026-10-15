import json
from pathlib import Path

from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY
from app.gamification.domain.types import SupportActionType
from app.gamification.skill_catalogue.catalogue import SkillCatalogue
from app.gamification.skill_catalogue.contracts import (
    ReviewStatus,
    SkillBinding,
    SkillReview,
    SourceCitation,
    UniversalSkillLink,
)

SKILL_REVIEW_DATA_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "skill-catalogue-review" / "v1"
DEVELOPMENT_SKILL_REVIEWS = SKILL_REVIEW_DATA_DIRECTORY / "development-skill-reviews.jsonl"
GRADE5_CANDIDATE_SKILL_BINDINGS = (
    SKILL_REVIEW_DATA_DIRECTORY / "grade5-candidate-skill-bindings.jsonl"
)
UNIVERSAL_SKILL_CROSSWALK = SKILL_REVIEW_DATA_DIRECTORY / "universal-skill-crosswalk.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_skill_reviews(path: Path = DEVELOPMENT_SKILL_REVIEWS) -> list[SkillReview]:
    reviews: list[SkillReview] = []
    for record in _read_jsonl(path):
        reviews.append(
            SkillReview(
                skill_code=str(record["skill_code"]),
                stable_index=int(record["stable_index"]),
                taxonomy_version=str(record["taxonomy_version"]),
                domain=str(record["domain"]),
                grade=int(record["grade"]),
                status=ReviewStatus(str(record["status"])),
                development_only=bool(record["development_only"]),
                learner_medium=str(record["learner_medium"]),
                required_label_languages=tuple(record["required_label_languages"]),  # type: ignore[arg-type]
                deferred_languages=tuple(record["deferred_languages"]),  # type: ignore[arg-type]
                scope_note=str(record["scope_note"]),
                definition=str(record["definition"]),
                labels=dict(record["labels"]),  # type: ignore[arg-type]
                prerequisites=tuple(record["prerequisites"]),  # type: ignore[arg-type]
                observable_success=tuple(record["observable_success"]),  # type: ignore[arg-type]
                misconceptions=tuple(record["misconceptions"]),  # type: ignore[arg-type]
                distinguishing_evidence=tuple(
                    record["distinguishing_evidence"]  # type: ignore[arg-type]
                ),
                eligible_support_action_types=tuple(
                    SupportActionType(value)
                    for value in record["eligible_support_action_types"]  # type: ignore[union-attr]
                ),
                verification_pair_rules=dict(
                    record["verification_pair_rules"]  # type: ignore[arg-type]
                ),
                source_citations=tuple(
                    SourceCitation(
                        source_id=str(citation["source_id"]),
                        page_from=str(citation["page_from"]),
                        page_to=str(citation["page_to"]),
                        skill_candidate_ids=tuple(citation["skill_candidate_ids"]),
                    )
                    for citation in record["source_citations"]  # type: ignore[union-attr]
                ),
                reviewer_id=record.get("reviewer_id"),  # type: ignore[arg-type]
                reviewed_on=record.get("reviewed_on"),  # type: ignore[arg-type]
                superseded_by=record.get("superseded_by"),  # type: ignore[arg-type]
            )
        )
    return reviews


def load_skill_bindings(path: Path = GRADE5_CANDIDATE_SKILL_BINDINGS) -> list[SkillBinding]:
    return [
        SkillBinding(
            skill_candidate_id=str(record["skill_candidate_id"]),
            gamification_skill_id=str(record["gamification_skill_id"]),
            mapping_version=str(record["mapping_version"]),
            status=ReviewStatus(str(record["status"])),
            confidence=str(record["confidence"]),
            rationale=str(record["rationale"]),
            source_ids=tuple(record["source_ids"]),  # type: ignore[arg-type]
            reviewer_id=record.get("reviewer_id"),  # type: ignore[arg-type]
            reviewed_on=record.get("reviewed_on"),  # type: ignore[arg-type]
        )
        for record in _read_jsonl(path)
    ]


def load_universal_skill_crosswalk(
    path: Path = UNIVERSAL_SKILL_CROSSWALK,
) -> dict[str, UniversalSkillLink]:
    links: dict[str, UniversalSkillLink] = {}
    for record in _read_jsonl(path):
        link = UniversalSkillLink(
            gamification_skill_id=str(record["gamification_skill_id"]),
            universal_skill_id=str(record["universal_skill_id"]),
            crosswalk_version=str(record["crosswalk_version"]),
            confidence=str(record["confidence"]),
            status=ReviewStatus(str(record["status"])),
            reviewer_id=record.get("reviewer_id"),  # type: ignore[arg-type]
            reviewed_on=record.get("reviewed_on"),  # type: ignore[arg-type]
        )
        if link.gamification_skill_id in links:
            raise ValueError(f"{link.gamification_skill_id} has more than one Universal parent")
        links[link.gamification_skill_id] = link
    return links


def load_development_skill_catalogue() -> SkillCatalogue:
    reviews = load_skill_reviews()
    return SkillCatalogue.build(
        reviews,
        load_skill_bindings(),
        taxonomy_version=reviews[0].taxonomy_version,
    )
