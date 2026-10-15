"""Shared curriculum chunking, version chunking-v1.

One chunker for both consumers. It tags page text and learning-outcome statements with the
trace hierarchy and writes only rows that already carry a Universal skill id. It does not
embed, approve, or read gamification item files.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.curriculum.application.retrieval import (
    CurriculumChunk,
    CurriculumReviewStatus,
    Grade,
    NonBlankText,
    PositivePage,
)

CHUNKING_VERSION = "chunking-v1"
# Fixed bound for this splitter version. It sits at the top of the 300–500 token planning
# range (about four characters per token). It is not fitted to a retrieval score.
CHUNKING_V1_MAX_CHARS = 2000
TranscriptionMethod = Literal["visual_read", "extracted_page"]
QuarantineReason = Literal[
    "unresolved_parent",
    "missing_universal_skill_id",
    "conversion_unavailable",
    "no_usable_text",
    "no_covering_outcome",
    "source_hash_mismatch",
    "source_not_in_registry",
    "extraction_missing",
]


class TraceNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    curriculum_node_id: NonBlankText
    node_type: NonBlankText
    parent_node_id: str = ""
    text_primary: str = ""
    source_id: NonBlankText
    source_page_from: int | None = None
    source_page_to: int | None = None
    skill_ids: tuple[NonBlankText, ...] = ()


class ChunkSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    source_version: NonBlankText
    subject: NonBlankText
    language: NonBlankText
    grade: Grade
    document_sha256: str | None = None


class ExtractedPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: NonBlankText
    page_number: PositivePage
    text: str | None = None
    conversion_status: str
    source_sha256: str | None = None


class ChunkFileRecord(BaseModel):
    """One `chunks.jsonl` row: a `CurriculumChunk` plus the chunk-file fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: NonBlankText
    source_id: NonBlankText
    source_version: NonBlankText
    content: NonBlankText
    grade: Grade
    subject: NonBlankText
    language: NonBlankText
    skill_ids: tuple[NonBlankText, ...] = Field(min_length=1)
    page_number: PositivePage | None = None
    section_locator: NonBlankText | None = None
    unit_id: NonBlankText | None = None
    learning_outcome_id: NonBlankText | None = None
    review_status: CurriculumReviewStatus = CurriculumReviewStatus.REVIEW_PENDING
    transcription_method: TranscriptionMethod
    chunking_version: Literal["chunking-v1"] = CHUNKING_VERSION

    def contract_chunk(self) -> CurriculumChunk:
        payload = self.model_dump(exclude={"transcription_method", "chunking_version"})
        return CurriculumChunk.model_validate(payload)


class QuarantineRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: QuarantineReason
    curriculum_node_id: NonBlankText | None = None
    parent_node_id: NonBlankText | None = None
    node_type: NonBlankText | None = None
    source_id: NonBlankText | None = None
    page_number: PositivePage | None = None


class ChunkingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunks: tuple[ChunkFileRecord, ...]
    quarantine: tuple[QuarantineRecord, ...]
    chunking_version: Literal["chunking-v1"] = CHUNKING_VERSION


def refuse_non_curriculum_path(path: Path) -> None:
    """Chunking reads `data/curriculum` only. Gamification item files are not inputs."""

    if "gamification" in path.as_posix().split("/"):
        raise ValueError("chunking reads data/curriculum only")


def read_curriculum_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    refuse_non_curriculum_path(path)
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return tuple(rows)


def load_trace_nodes(path: Path) -> tuple[TraceNode, ...]:
    nodes: list[TraceNode] = []
    for row in read_curriculum_jsonl(path):
        page_from = _page(row.get("source_page_from"))
        page_to = _page(row.get("source_page_to"))
        nodes.append(
            TraceNode(
                curriculum_node_id=str(row["curriculum_node_id"]),
                node_type=str(row["node_type"]),
                parent_node_id=str(row.get("parent_node_id") or ""),
                text_primary=str(row.get("text_primary") or ""),
                source_id=str(row["source_id"]),
                source_page_from=page_from,
                source_page_to=page_to if page_to is not None else page_from,
                skill_ids=_skill_ids(row),
            )
        )
    return tuple(nodes)


def load_universal_skill_links(path: Path) -> dict[str, str]:
    """Map a curriculum node id to the Universal skill id already recorded for it."""

    refuse_non_curriculum_path(path)
    links: dict[str, str] = {}
    for row in read_curriculum_jsonl(path):
        node_id = str(row["curriculum_node_id"])
        skill_id = str(row["universal_skill_id"]).strip()
        if not skill_id:
            raise ValueError(f"{node_id} has no universal skill id")
        previous = links.get(node_id)
        if previous is not None and previous != skill_id:
            raise ValueError(f"{node_id} has two universal skill ids")
        links[node_id] = skill_id
    return links


def apply_universal_skill_links(
    nodes: Sequence[TraceNode],
    links: Mapping[str, str],
) -> tuple[TraceNode, ...]:
    """Copy a recorded Universal id onto a node that does not already have one."""

    applied: list[TraceNode] = []
    for node in nodes:
        skill_id = links.get(node.curriculum_node_id)
        if node.skill_ids or not skill_id:
            applied.append(node)
            continue
        applied.append(node.model_copy(update={"skill_ids": (skill_id,)}))
    return tuple(applied)


def load_chunk_sources(
    registry_path: Path,
    *,
    document_sha256: Mapping[str, str | None],
) -> tuple[ChunkSource, ...]:
    sources: list[ChunkSource] = []
    for row in read_curriculum_jsonl(registry_path):
        grade = row.get("grade")
        if grade not in (4, 5):
            continue
        version = row.get("source_version")
        subject = row.get("subject")
        language = row.get("language")
        if not version or not subject or not language:
            continue
        source_id = str(row["source_id"])
        sources.append(
            ChunkSource(
                source_id=source_id,
                source_version=str(version),
                subject=str(subject),
                language=str(language),
                grade=grade,
                document_sha256=document_sha256.get(source_id),
            )
        )
    return tuple(sources)


def load_extracted_pages(
    extracted_root: Path,
    sources_by_location: Mapping[str, str],
) -> tuple[ExtractedPage, ...]:
    """Join extractor JSONL to registry source ids by the PDF's relative path.

    `sources_by_location` maps a path relative to `data/curriculum/raw` (POSIX, `.pdf`)
    to the registry `source_id`. The extractor's own hash source id is not used.
    """

    refuse_non_curriculum_path(extracted_root)
    pages: list[ExtractedPage] = []
    if not extracted_root.is_dir():
        return ()
    for relative_pdf, source_id in sorted(sources_by_location.items()):
        jsonl_path = (extracted_root / relative_pdf).with_suffix(".jsonl")
        if not jsonl_path.is_file():
            continue
        for row in read_curriculum_jsonl(jsonl_path):
            page_number = row.get("page_number")
            if not isinstance(page_number, int) or page_number < 1:
                continue
            text = row.get("text")
            pages.append(
                ExtractedPage(
                    source_id=source_id,
                    page_number=page_number,
                    text=text if isinstance(text, str) else None,
                    conversion_status=str(row.get("conversion_status") or ""),
                    source_sha256=_optional_text(row.get("source_sha256")),
                )
            )
    return tuple(pages)


def chunk_curriculum(
    nodes: Sequence[TraceNode],
    sources: Sequence[ChunkSource],
    pages: Sequence[ExtractedPage] = (),
) -> ChunkingResult:
    by_id = {node.curriculum_node_id: node for node in nodes}
    by_source = {source.source_id: source for source in sources}
    chunks: list[ChunkFileRecord] = []
    quarantine: list[QuarantineRecord] = []
    resolved_outcomes: list[tuple[TraceNode, TraceNode | None]] = []

    for node in nodes:
        if not _parent_resolves(node, by_id):
            quarantine.append(
                QuarantineRecord(
                    reason="unresolved_parent",
                    curriculum_node_id=node.curriculum_node_id,
                    parent_node_id=node.parent_node_id or None,
                    node_type=node.node_type,
                    source_id=node.source_id,
                )
            )
            continue
        if node.node_type != "learning_outcome":
            continue
        source = by_source.get(node.source_id)
        if source is None:
            quarantine.append(
                QuarantineRecord(
                    reason="source_not_in_registry",
                    curriculum_node_id=node.curriculum_node_id,
                    node_type=node.node_type,
                    source_id=node.source_id,
                )
            )
            continue
        unit = _unit_ancestor(node, by_id)
        resolved_outcomes.append((node, unit))
        if not node.skill_ids:
            quarantine.append(
                QuarantineRecord(
                    reason="missing_universal_skill_id",
                    curriculum_node_id=node.curriculum_node_id,
                    node_type=node.node_type,
                    source_id=node.source_id,
                )
            )
            continue
        statement = node.text_primary.strip()
        if not statement:
            quarantine.append(
                QuarantineRecord(
                    reason="no_usable_text",
                    curriculum_node_id=node.curriculum_node_id,
                    node_type=node.node_type,
                    source_id=node.source_id,
                    page_number=node.source_page_from,
                )
            )
            continue
        chunks.append(_statement_chunk(node, source, unit.curriculum_node_id if unit else None))

    for page in pages:
        _chunk_page(page, by_source, resolved_outcomes, chunks, quarantine)

    return ChunkingResult(
        chunks=tuple(sorted(chunks, key=_chunk_sort_key)),
        quarantine=tuple(sorted(quarantine, key=_quarantine_sort_key)),
    )


def render_jsonl(rows: Sequence[BaseModel]) -> str:
    lines = [
        json.dumps(
            row.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    ]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    chunks_text: str,
    quarantine_text: str,
    written_count: int,
    quarantined_count: int,
    reason_counts: Mapping[str, int],
    source_document_sha256: Mapping[str, str | None],
) -> dict[str, object]:
    unpinned = sorted(
        source_id for source_id, digest in source_document_sha256.items() if not digest
    )
    return {
        "chunking_version": CHUNKING_VERSION,
        "review_status": CurriculumReviewStatus.REVIEW_PENDING.value,
        "ingestion_status": "NOT_INGESTED",
        "written_count": written_count,
        "quarantined_count": quarantined_count,
        "quarantine_reasons": dict(sorted(reason_counts.items())),
        "files": {
            "chunks.jsonl": {
                "sha256": sha256_text(chunks_text),
                "bytes": len(chunks_text.encode()),
            },
            "quarantine.jsonl": {
                "sha256": sha256_text(quarantine_text),
                "bytes": len(quarantine_text.encode()),
            },
        },
        "source_document_sha256": dict(sorted(source_document_sha256.items())),
        "unpinned_source_ids": unpinned,
    }


def split_page_paragraphs(text: str, *, max_chars: int = CHUNKING_V1_MAX_CHARS) -> tuple[str, ...]:
    """Split one page into paragraph pieces. Pieces never include another page."""

    pieces: list[str] = []
    for paragraph in text.split("\n\n"):
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        if len(cleaned) <= max_chars:
            pieces.append(cleaned)
            continue
        pieces.extend(_split_long_paragraph(cleaned, max_chars))
    return tuple(pieces)


def _chunk_page(
    page: ExtractedPage,
    by_source: Mapping[str, ChunkSource],
    outcomes: Sequence[tuple[TraceNode, TraceNode | None]],
    chunks: list[ChunkFileRecord],
    quarantine: list[QuarantineRecord],
) -> None:
    source = by_source.get(page.source_id)
    if source is None:
        quarantine.append(
            QuarantineRecord(
                reason="source_not_in_registry",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    if (
        page.source_sha256
        and source.document_sha256
        and page.source_sha256 != source.document_sha256
    ):
        quarantine.append(
            QuarantineRecord(
                reason="source_hash_mismatch",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    if page.conversion_status == "conversion_unavailable":
        quarantine.append(
            QuarantineRecord(
                reason="conversion_unavailable",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    if page.text is None or not page.text.strip():
        quarantine.append(
            QuarantineRecord(
                reason="no_usable_text",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    covering = [
        (outcome, unit)
        for outcome, unit in outcomes
        if outcome.source_id == page.source_id and _covers(outcome, page.page_number)
    ]
    skilled = [(outcome, unit) for outcome, unit in covering if outcome.skill_ids]
    if not covering:
        quarantine.append(
            QuarantineRecord(
                reason="no_covering_outcome",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    if not skilled:
        quarantine.append(
            QuarantineRecord(
                reason="missing_universal_skill_id",
                source_id=page.source_id,
                page_number=page.page_number,
            )
        )
        return
    paragraphs = split_page_paragraphs(page.text)
    for outcome, unit in skilled:
        for index, paragraph in enumerate(paragraphs):
            chunks.append(
                _page_chunk(
                    paragraph,
                    index,
                    page,
                    outcome,
                    source,
                    unit.curriculum_node_id if unit else None,
                )
            )


def _statement_chunk(node: TraceNode, source: ChunkSource, unit_id: str | None) -> ChunkFileRecord:
    lesson_id = node.parent_node_id or None
    locator = f"outcome:{node.curriculum_node_id}"
    if lesson_id:
        locator = f"lesson:{lesson_id};{locator}"
    record = ChunkFileRecord(
        chunk_id=f"{node.source_id}:p{node.source_page_from or 0:04d}:{node.curriculum_node_id}:visual_read:0000",
        source_id=node.source_id,
        source_version=source.source_version,
        content=node.text_primary.strip(),
        grade=source.grade,
        subject=source.subject,
        language=source.language,
        skill_ids=node.skill_ids,
        page_number=node.source_page_from,
        section_locator=locator,
        unit_id=unit_id,
        learning_outcome_id=node.curriculum_node_id,
        review_status=CurriculumReviewStatus.REVIEW_PENDING,
        transcription_method="visual_read",
        chunking_version=CHUNKING_VERSION,
    )
    record.contract_chunk()
    return record


def _page_chunk(
    paragraph: str,
    index: int,
    page: ExtractedPage,
    outcome: TraceNode,
    source: ChunkSource,
    unit_id: str | None,
) -> ChunkFileRecord:
    record = ChunkFileRecord(
        chunk_id=(
            f"{page.source_id}:p{page.page_number:04d}:{outcome.curriculum_node_id}:"
            f"extracted_page:{index:04d}"
        ),
        source_id=page.source_id,
        source_version=source.source_version,
        content=paragraph,
        grade=source.grade,
        subject=source.subject,
        language=source.language,
        skill_ids=outcome.skill_ids,
        page_number=page.page_number,
        section_locator=f"page:{page.page_number};outcome:{outcome.curriculum_node_id}",
        unit_id=unit_id,
        learning_outcome_id=outcome.curriculum_node_id,
        review_status=CurriculumReviewStatus.REVIEW_PENDING,
        transcription_method="extracted_page",
        chunking_version=CHUNKING_VERSION,
    )
    record.contract_chunk()
    return record


def _parent_resolves(node: TraceNode, by_id: Mapping[str, TraceNode]) -> bool:
    seen = {node.curriculum_node_id}
    parent_id = node.parent_node_id
    while parent_id:
        if parent_id in seen or parent_id not in by_id:
            return False
        seen.add(parent_id)
        parent_id = by_id[parent_id].parent_node_id
    return True


def _unit_ancestor(node: TraceNode, by_id: Mapping[str, TraceNode]) -> TraceNode | None:
    parent_id = node.parent_node_id
    found: TraceNode | None = None
    seen = {node.curriculum_node_id}
    while parent_id and parent_id not in seen and parent_id in by_id:
        parent = by_id[parent_id]
        if parent.node_type == "competency":
            return parent
        if parent.node_type == "competency_level" and found is None:
            found = parent
        seen.add(parent_id)
        parent_id = parent.parent_node_id
    return found


def _covers(node: TraceNode, page_number: int) -> bool:
    start = node.source_page_from
    end = node.source_page_to if node.source_page_to is not None else start
    if start is None or end is None:
        return False
    return start <= page_number <= end


def _split_long_paragraph(paragraph: str, max_chars: int) -> tuple[str, ...]:
    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for word in paragraph.split():
        if len(word) > max_chars:
            if current:
                pieces.append(" ".join(current))
                current = []
                length = 0
            for start in range(0, len(word), max_chars):
                pieces.append(word[start : start + max_chars])
            continue
        extra = len(word) + (1 if current else 0)
        if current and length + extra > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        pieces.append(" ".join(current))
    return tuple(pieces)


def _skill_ids(row: Mapping[str, object]) -> tuple[str, ...]:
    raw = row.get("skill_ids", row.get("universal_skill_ids", ()))
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list | tuple):
        values = [str(item) for item in raw if str(item).strip()]
    else:
        values = []
    return tuple(sorted(set(values)))


def _page(value: object) -> int | None:
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed >= 1 else None
    return None


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _chunk_sort_key(record: ChunkFileRecord) -> tuple[str, int, str, str, str]:
    return (
        record.source_id,
        record.page_number or 0,
        record.learning_outcome_id or "",
        record.transcription_method,
        record.chunk_id,
    )


def _quarantine_sort_key(record: QuarantineRecord) -> tuple[str, str, int, str]:
    return (
        record.reason,
        record.source_id or "",
        record.page_number or 0,
        record.curriculum_node_id or "",
    )
