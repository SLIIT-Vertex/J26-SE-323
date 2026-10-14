import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class SkillRetrievalEnrichment:
    skill_id: str
    language: str
    text: str
    provenance: str
    review_status: str


class JsonSkillTaxonomyEnrichmentCatalog:
    """Load optional retrieval text while keeping skill identity in the XLSX taxonomy."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self, valid_skill_ids: set[str]) -> tuple[SkillRetrievalEnrichment, ...]:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        records = document.get("records")
        if not isinstance(records, list):
            raise TypeError("enrichment resource must contain a records list")

        enrichments: list[SkillRetrievalEnrichment] = []
        seen_skill_ids: set[str] = set()
        seen_entries: set[tuple[str, str, str]] = set()
        for record in records:
            if not isinstance(record, dict):
                raise TypeError("enrichment records must be objects")
            skill_id = _non_blank(record.get("skill_id"), "skill_id")
            if skill_id in seen_skill_ids:
                raise ValueError(f"duplicate enrichment record for {skill_id}")
            if skill_id not in valid_skill_ids:
                raise ValueError(f"unknown enrichment skill ID: {skill_id}")
            seen_skill_ids.add(skill_id)

            entries = record.get("entries")
            if not isinstance(entries, list) or not entries:
                raise ValueError(f"enrichment record {skill_id} must contain entries")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise TypeError(f"enrichment entries for {skill_id} must be objects")
                enrichment = SkillRetrievalEnrichment(
                    skill_id=skill_id,
                    language=_non_blank(entry.get("language"), "language"),
                    text=_non_blank(entry.get("text"), "text"),
                    provenance=_non_blank(entry.get("provenance"), "provenance"),
                    review_status=_non_blank(entry.get("review_status"), "review_status"),
                )
                identity = (skill_id, enrichment.language.casefold(), enrichment.text.casefold())
                if identity in seen_entries:
                    raise ValueError(f"duplicate enrichment entry for {skill_id}")
                seen_entries.add(identity)
                enrichments.append(enrichment)

        return tuple(
            sorted(
                enrichments,
                key=lambda item: (item.skill_id, item.language, item.text),
            )
        )


class JsonSkillRelevanceCatalog:
    """Load the small semantic counter-example set used by the optional relevance gate."""

    _CATEGORIES: ClassVar[frozenset[str]] = frozenset(
        {"unsupported_learning", "off_topic"}
    )

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, tuple[str, ...]]:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        categories = document.get("categories")
        if not isinstance(categories, dict) or set(categories) != self._CATEGORIES:
            raise ValueError("relevance resource must define unsupported_learning and off_topic")

        loaded: dict[str, tuple[str, ...]] = {}
        for category in sorted(self._CATEGORIES):
            examples = categories[category]
            if not isinstance(examples, list) or not examples:
                raise ValueError(f"relevance category {category} must contain examples")
            texts = tuple(_non_blank(example, category) for example in examples)
            if len({text.casefold() for text in texts}) != len(texts):
                raise ValueError(f"relevance category {category} contains duplicate examples")
            loaded[category] = texts
        return loaded


def _non_blank(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-blank text")
    return value.strip()
