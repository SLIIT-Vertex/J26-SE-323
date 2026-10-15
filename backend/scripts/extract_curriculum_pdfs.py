"""Offline, font-aware PDF extraction for curriculum source review.

This utility intentionally does not guess conversions for legacy Sinhala font
encodings. It preserves each raw span and reports unsupported encodings until a
font-specific mapping has been independently validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import pymupdf

SCHEMA_VERSION = 1
HASH_CHUNK_SIZE = 1024 * 1024
EXTRACTION_METHOD = "pymupdf_font_aware"
MAX_REPORT_EXAMPLES = 10

# These names were observed in the Grade 5 Mathematics teacher guide. A name
# match identifies a span for review; it does not prove encoding compatibility.
OBSERVED_LEGACY_FONTS = frozenset(
    {
        "fmabhaya",
        "fmabhayax",
        "fmababldbold",
        "fmemaneex",
        "fmsamantha",
    }
)

REFERENCE_EXAMPLES = (
    (".Ks;h", "ගණිතය"),
    (".=re ud¾f.damfoaYh", "ගුරු මාර්ගෝපදේශය"),
    ("Y%S ,xldj", "ශ්‍රී ලංකාව"),
)

MAPPING_ASSESSMENT = {
    "conversion_enabled": False,
    "strategy": "preserve_raw_until_font_mapping_is_verified",
    "candidate": {
        "name": "Pandukabhaya 1.0.1",
        "source": "https://github.com/akuruAI/Pandukabhaya",
        "license": "MIT",
        "claimed_encoding": "FM Abhaya",
    },
    "observed_font_compatibility": {
        "FMEmaneex_and_FMAbabldBold": "unverified",
        "FMAbhayax_and_FMAbhaya": "unverified",
    },
    "decision": (
        "Not enabled: the candidate claims FM Abhaya, but the sample primarily uses "
        "FMEmaneex, FMAbabldBold, and FMAbhayax. The supplied three examples do not "
        "establish full encoding compatibility, and the sample's FMAbhaya Identity-H "
        "resource extracts control-like text."
    ),
}


@dataclass(frozen=True)
class SpanConversion:
    """A conservative conversion decision for one PDF text span."""

    text: str | None
    status: str
    strategy: str
    reason: str | None = None


def stream_sha256(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Hash a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_font_name(font_name: str) -> str:
    """Remove a PDF subset prefix and whitespace from a font name."""

    name = font_name.strip()
    if len(name) > 7 and name[6] == "+" and name[:6].isupper():
        name = name[7:]
    return name


def is_legacy_sinhala_font(font_name: str) -> bool:
    """Identify observed or likely FM-family legacy Sinhala fonts."""

    normalized = normalize_font_name(font_name).casefold().replace("-", "")
    return normalized in OBSERVED_LEGACY_FONTS or normalized.startswith("fm")


def contains_sinhala(text: str) -> bool:
    """Return whether text already contains Sinhala Unicode code points."""

    return any("\u0d80" <= character <= "\u0dff" for character in text)


def is_numeric_or_math_text(text: str) -> bool:
    """Recognize spans that contain only digits, whitespace, and common math marks."""

    allowed = frozenset("0123456789 \\t\\r\\n.,:+-*/=()%[]{}<>×÷°")
    return bool(text) and all(character in allowed for character in text)


def convert_span(text: str, font_name: str) -> SpanConversion:
    """Preserve safe text and refuse unverified legacy-font conversion.

    The original text is retained separately by the caller. Returning ``None``
    means no safe Unicode representation is available for this span.
    """

    if not text:
        return SpanConversion(text="", status="preserved", strategy="preserve_empty")

    normalized_text = unicodedata.normalize("NFC", text)
    if contains_sinhala(normalized_text):
        return SpanConversion(
            text=normalized_text,
            status="preserved",
            strategy="preserve_existing_unicode_sinhala",
        )

    if not is_legacy_sinhala_font(font_name):
        return SpanConversion(
            text=normalized_text,
            status="preserved",
            strategy="preserve_non_legacy_font",
        )

    if is_numeric_or_math_text(normalized_text):
        return SpanConversion(
            text=normalized_text,
            status="preserved",
            strategy="preserve_numeric_or_math",
        )

    return SpanConversion(
        text=None,
        status="conversion_unavailable",
        strategy="no_verified_font_mapping",
        reason="The font-specific legacy encoding has not been independently validated.",
    )


def _rounded_bbox(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    return [round(float(coordinate), 3) for coordinate in value]


def _join_blocks(blocks: list[list[str]]) -> str:
    return "\n\n".join("\n".join(lines) for lines in blocks)


def build_page_record(
    page_dict: dict[str, Any],
    *,
    page_number: int,
    source_id: str,
    source_file: str,
    source_sha256: str,
    extracted_at: str,
) -> dict[str, Any]:
    """Build an auditable page record from a PyMuPDF text dictionary."""

    audit_spans: list[dict[str, Any]] = []
    original_blocks: list[list[str]] = []
    safe_blocks: list[list[str]] = []
    fonts: set[str] = set()
    status_counts: Counter[str] = Counter()
    image_count = 0
    has_unsafe_span = False

    for block_index, block in enumerate(page_dict.get("blocks", [])):
        if block.get("type") == 1:
            image_count += 1
            continue
        if block.get("type") != 0:
            continue

        original_lines: list[str] = []
        safe_lines: list[str] = []
        for line_index, line in enumerate(block.get("lines", [])):
            original_parts: list[str] = []
            safe_parts: list[str] = []
            for span_index, span in enumerate(line.get("spans", [])):
                original = str(span.get("text", ""))
                font = normalize_font_name(str(span.get("font", "")))
                decision = convert_span(original, font)

                original_parts.append(original)
                fonts.add(font or "<unknown>")
                status_counts[decision.status] += 1
                if decision.text is None:
                    has_unsafe_span = True
                else:
                    safe_parts.append(decision.text)

                audit_span: dict[str, Any] = {
                    "block_index": block_index,
                    "line_index": line_index,
                    "span_index": span_index,
                    "original_text": original,
                    "text": decision.text,
                    "font": font or None,
                    "font_size": round(float(span.get("size", 0.0)), 3),
                    "bbox": _rounded_bbox(span.get("bbox")),
                    "conversion_strategy": decision.strategy,
                    "conversion_status": decision.status,
                }
                if decision.reason:
                    audit_span["conversion_reason"] = decision.reason
                audit_spans.append(audit_span)

            original_lines.append("".join(original_parts))
            safe_lines.append("".join(safe_parts))

        original_blocks.append(original_lines)
        safe_blocks.append(safe_lines)

    original_text = _join_blocks(original_blocks)
    has_extractable_text = bool(original_text.strip())
    unavailable_count = status_counts["conversion_unavailable"]
    failed_count = status_counts["conversion_failed"]
    converted_count = status_counts["converted"]

    if not has_extractable_text:
        page_status = "empty"
    elif failed_count:
        page_status = "conversion_failed"
    elif unavailable_count and converted_count:
        page_status = "partial_conversion"
    elif unavailable_count:
        page_status = "conversion_unavailable"
    elif converted_count:
        page_status = "converted_needs_review"
    else:
        page_status = "preserved_needs_review"

    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"{source_id}:page:{page_number:04d}",
        "source_id": source_id,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "page_number": page_number,
        "original_text": original_text,
        "text": None if has_unsafe_span else _join_blocks(safe_blocks),
        "detected_fonts": sorted(fonts),
        "conversion_status": page_status,
        "review_status": "pending",
        "rag_eligible": False,
        "extraction_method": EXTRACTION_METHOD,
        "extracted_at": extracted_at,
        "has_extractable_text": has_extractable_text,
        "likely_scanned": not has_extractable_text and image_count > 0,
        "image_count": image_count,
        "span_counts": {
            "converted": converted_count,
            "preserved": status_counts["preserved"],
            "unsupported": unavailable_count,
            "failed": failed_count,
        },
        "spans": audit_spans,
    }


def _font_resources(page: pymupdf.Page, document: pymupdf.Document) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for item in page.get_fonts(full=True):
        xref = int(item[0])
        to_unicode = False
        if xref > 0:
            try:
                value_type, value = document.xref_get_key(xref, "ToUnicode")
                to_unicode = value_type != "null" and value != "null"
            except RuntimeError:
                pass
        resources.append(
            {
                "xref": xref,
                "extension": item[1],
                "subtype": item[2],
                "base_font": normalize_font_name(item[3]),
                "resource_name": item[4],
                "encoding": item[5],
                "has_to_unicode": to_unicode,
            }
        )
    return resources


def _append_unique_example(examples: list[dict[str, Any]], candidate: dict[str, Any]) -> None:
    if len(examples) >= MAX_REPORT_EXAMPLES:
        return
    if candidate not in examples:
        examples.append(candidate)


def _atomic_text_writer(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    return tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )


def _replace_atomic(temporary_name: str, destination: Path) -> None:
    os.replace(temporary_name, destination)


def extract_pdf(
    pdf_path: Path,
    output_path: Path,
    *,
    source_file: str | None = None,
    max_pages: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Extract one PDF incrementally and return its quality report."""

    if not dry_run and output_path.exists() and not force:
        raise FileExistsError(f"Output exists; pass --force to replace it: {output_path}")

    source_file = source_file or pdf_path.name
    source_hash = stream_sha256(pdf_path)
    source_id = f"curriculum:{source_hash[:24]}"
    extracted_at = datetime.now(UTC).isoformat()

    font_counts: Counter[str] = Counter()
    span_counts: Counter[str] = Counter()
    raw_examples: list[dict[str, Any]] = []
    converted_examples: list[dict[str, Any]] = []
    suspicious_examples: list[dict[str, Any]] = []
    font_resources: dict[tuple[Any, ...], dict[str, Any]] = {}
    pages_with_text = 0
    empty_pages = 0
    likely_scanned_pages = 0
    partial_pages = 0

    temporary: TextIO | None = None
    temporary_name: str | None = None
    try:
        with pymupdf.open(pdf_path) as document:
            document_page_count = document.page_count
            processed_page_count = min(document_page_count, max_pages or document_page_count)
            writer_context = nullcontext(None) if dry_run else _atomic_text_writer(output_path)

            with writer_context as output:
                temporary = output
                if output is not None:
                    temporary_name = output.name

                for page_index in range(processed_page_count):
                    page = document.load_page(page_index)
                    page_number = page_index + 1
                    page_dict = page.get_text("dict", sort=True)
                    record = build_page_record(
                        page_dict,
                        page_number=page_number,
                        source_id=source_id,
                        source_file=source_file,
                        source_sha256=source_hash,
                        extracted_at=extracted_at,
                    )

                    if output is not None:
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")

                    font_counts.update(record["detected_fonts"])
                    span_counts["converted"] += record["span_counts"]["converted"]
                    span_counts["preserved"] += record["span_counts"]["preserved"]
                    span_counts["unsupported"] += record["span_counts"]["unsupported"]
                    span_counts["failed"] += record["span_counts"]["failed"]
                    if record["has_extractable_text"]:
                        pages_with_text += 1
                    else:
                        empty_pages += 1
                    if record["likely_scanned"]:
                        likely_scanned_pages += 1
                    if record["conversion_status"] == "partial_conversion":
                        partial_pages += 1

                    for resource in _font_resources(page, document):
                        key = (
                            resource["xref"],
                            resource["base_font"],
                            resource["encoding"],
                        )
                        font_resources[key] = resource

                    for span in record["spans"]:
                        if span["conversion_status"] == "conversion_unavailable":
                            example = {
                                "page_number": page_number,
                                "font": span["font"],
                                "text": span["original_text"],
                            }
                            _append_unique_example(raw_examples, example)
                            _append_unique_example(suspicious_examples, example)
                        elif span["conversion_status"] == "converted":
                            _append_unique_example(
                                converted_examples,
                                {
                                    "page_number": page_number,
                                    "font": span["font"],
                                    "original_text": span["original_text"],
                                    "text": span["text"],
                                },
                            )

                    if show_progress and (
                        page_number == 1
                        or page_number == processed_page_count
                        or page_number % 25 == 0
                    ):
                        print(
                            f"  {source_file}: page {page_number}/{processed_page_count}",
                            file=sys.stderr,
                        )

                if output is not None:
                    output.flush()
                    os.fsync(output.fileno())

            if temporary_name is not None:
                _replace_atomic(temporary_name, output_path)
                temporary_name = None

    except Exception:
        if temporary is not None and not temporary.closed:
            temporary.close()
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise

    warnings: list[str] = []
    if span_counts["unsupported"]:
        warnings.append(
            "Legacy-font spans remain unconverted because no compatible mapping is verified."
        )
    if max_pages is not None and processed_page_count < document_page_count:
        warnings.append(
            f"Pilot only: processed {processed_page_count} of {document_page_count} pages."
        )
    if likely_scanned_pages:
        warnings.append("Some pages have images but no extractable text; OCR was not attempted.")

    if span_counts["failed"]:
        readiness = "EXTRACTION_FAILED"
    elif span_counts["unsupported"] and span_counts["converted"]:
        readiness = "PARTIAL_CONVERSION"
    elif span_counts["unsupported"]:
        readiness = "BLOCKED_UNSUPPORTED_ENCODING"
    else:
        readiness = "NEEDS_REVIEW"

    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "source_file": source_file,
        "source_path": pdf_path.as_posix(),
        "source_sha256": source_hash,
        "output_path": None if dry_run else output_path.as_posix(),
        "extraction_method": EXTRACTION_METHOD,
        "extracted_at": extracted_at,
        "dry_run": dry_run,
        "document_page_count": document_page_count,
        "processed_page_count": processed_page_count,
        "pages_with_extractable_text": pages_with_text,
        "empty_pages": empty_pages,
        "likely_scanned_pages": likely_scanned_pages,
        "partial_conversion_pages": partial_pages,
        "font_counts": dict(sorted(font_counts.items())),
        "font_resources": sorted(
            font_resources.values(), key=lambda item: (item["base_font"], item["xref"])
        ),
        "span_counts": {
            "converted": span_counts["converted"],
            "preserved": span_counts["preserved"],
            "unsupported": span_counts["unsupported"],
            "failed": span_counts["failed"],
        },
        "examples": {
            "raw_legacy_text": raw_examples,
            "converted_unicode_text": converted_examples,
            "suspicious_remaining_text": suspicious_examples,
        },
        "mapping_assessment": MAPPING_ASSESSMENT,
        "reference_examples": [
            {
                "legacy_text": legacy,
                "expected_unicode": expected,
                "status": "unverified_reference",
                "provenance": "task_specification",
            }
            for legacy, expected in REFERENCE_EXAMPLES
        ],
        "errors": [],
        "warnings": warnings,
        "overall_readiness": readiness,
        "review_status": "pending",
        "rag_eligible": False,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a concise human-readable report."""

    font_lines = [
        f"- `{font}`: {count} page(s)" for font, count in report["font_counts"].items()
    ] or ["- None"]
    warning_lines = [f"- {warning}" for warning in report["warnings"]] or ["- None"]
    error_lines = [f"- `{error['type']}`: {error['message']}" for error in report["errors"]] or [
        "- None"
    ]
    raw_lines = [
        f"- Page {item['page_number']} / `{item['font']}`: `{item['text']}`"
        for item in report["examples"]["raw_legacy_text"]
    ] or ["- None"]
    converted_lines = [
        f"- Page {item['page_number']}: `{item['original_text']}` → `{item['text']}`"
        for item in report["examples"]["converted_unicode_text"]
    ] or ["- None"]

    counts = report["span_counts"]
    return "\n".join(
        [
            f"# Extraction report: {report['source_file']}",
            "",
            f"- Overall readiness: **{report['overall_readiness']}**",
            f"- Review status: **{report['review_status']}**",
            f"- Source SHA-256: `{report['source_sha256']}`",
            (
                f"- Processed pages: {report['processed_page_count']} / "
                f"{report['document_page_count']}"
            ),
            f"- Pages with text: {report['pages_with_extractable_text']}",
            f"- Empty pages: {report['empty_pages']}",
            f"- Likely scanned pages: {report['likely_scanned_pages']}",
            (
                f"- Spans: {counts['converted']} converted, "
                f"{counts['preserved']} preserved, {counts['unsupported']} unsupported, "
                f"{counts['failed']} failed"
            ),
            "- RAG eligible: no",
            "",
            "## Fonts encountered",
            "",
            *font_lines,
            "",
            "## Raw legacy examples",
            "",
            *raw_lines,
            "",
            "## Converted Unicode examples",
            "",
            *converted_lines,
            "",
            "## Mapping decision",
            "",
            report["mapping_assessment"]["decision"],
            "",
            "## Warnings",
            "",
            *warning_lines,
            "",
            "## Errors",
            "",
            *error_lines,
            "",
        ]
    )


def atomic_write_text(path: Path, content: str, *, force: bool) -> None:
    """Write a complete UTF-8 file and replace the destination atomically."""

    if path.exists() and not force:
        raise FileExistsError(f"Output exists; pass --force to replace it: {path}")
    temporary = _atomic_text_writer(path)
    temporary_name = temporary.name
    try:
        with temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        _replace_atomic(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def write_reports(
    report: dict[str, Any], json_path: Path, markdown_path: Path, *, force: bool
) -> None:
    atomic_write_text(
        json_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        force=force,
    )
    atomic_write_text(markdown_path, render_markdown_report(report), force=force)


def build_failure_report(pdf_path: Path, source_file: str, error: Exception) -> dict[str, Any]:
    """Build a report for a PDF that could not be extracted."""

    try:
        source_hash = stream_sha256(pdf_path)
    except OSError:
        source_hash = None
    source_id = f"curriculum:{source_hash[:24]}" if source_hash else None
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "source_file": source_file,
        "source_path": pdf_path.as_posix(),
        "source_sha256": source_hash,
        "output_path": None,
        "extraction_method": EXTRACTION_METHOD,
        "extracted_at": datetime.now(UTC).isoformat(),
        "dry_run": False,
        "document_page_count": None,
        "processed_page_count": 0,
        "pages_with_extractable_text": 0,
        "empty_pages": 0,
        "likely_scanned_pages": 0,
        "partial_conversion_pages": 0,
        "font_counts": {},
        "font_resources": [],
        "span_counts": {"converted": 0, "preserved": 0, "unsupported": 0, "failed": 0},
        "examples": {
            "raw_legacy_text": [],
            "converted_unicode_text": [],
            "suspicious_remaining_text": [],
        },
        "mapping_assessment": MAPPING_ASSESSMENT,
        "reference_examples": [
            {
                "legacy_text": legacy,
                "expected_unicode": expected,
                "status": "unverified_reference",
                "provenance": "task_specification",
            }
            for legacy, expected in REFERENCE_EXAMPLES
        ],
        "errors": [{"type": type(error).__name__, "message": str(error)}],
        "warnings": [],
        "overall_readiness": "EXTRACTION_FAILED",
        "review_status": "pending",
        "rag_eligible": False,
    }


def discover_pdfs(input_path: Path) -> tuple[Path, list[Path]]:
    """Return the relative-path root and sorted PDFs for a file or directory."""

    if input_path.is_file():
        if input_path.suffix.casefold() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {input_path}")
        return input_path.parent, [input_path]
    if input_path.is_dir():
        pdfs = sorted(
            path
            for path in input_path.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".pdf"
        )
        return input_path, pdfs
    raise FileNotFoundError(f"Input does not exist: {input_path}")


def output_paths(relative_pdf: Path, output_dir: Path, report_dir: Path) -> tuple[Path, Path, Path]:
    jsonl_path = (output_dir / relative_pdf).with_suffix(".jsonl")
    report_base = report_dir / relative_pdf
    json_report = report_base.with_suffix(".report.json")
    markdown_report = report_base.with_suffix(".report.md")
    return jsonl_path, json_report, markdown_report


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract auditable, page-level curriculum JSONL from PDF files."
    )
    parser.add_argument("--input", required=True, type=Path, help="PDF file or directory")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/curriculum/extracted"),
        help="JSONL output directory",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("data/curriculum/reports"),
        help="quality report directory",
    )
    parser.add_argument("--max-pages", type=positive_integer, help="process only the first N pages")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="inspect PDFs without writing JSONL or reports",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="atomically replace existing outputs",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    input_root, pdf_paths = discover_pdfs(args.input)
    if not pdf_paths:
        print(f"No PDF files found under {args.input}.", file=sys.stderr)
        return 0

    failures = 0
    for pdf_path in pdf_paths:
        relative_pdf = pdf_path.relative_to(input_root)
        jsonl_path, json_report, markdown_report = output_paths(
            relative_pdf, args.output, args.report_dir
        )
        try:
            if not args.dry_run and not args.force:
                existing = [
                    path for path in (jsonl_path, json_report, markdown_report) if path.exists()
                ]
                if existing:
                    raise FileExistsError(
                        "Output exists; pass --force to replace it: "
                        + ", ".join(str(path) for path in existing)
                    )

            report = extract_pdf(
                pdf_path,
                jsonl_path,
                source_file=relative_pdf.as_posix(),
                max_pages=args.max_pages,
                force=args.force,
                dry_run=args.dry_run,
                show_progress=True,
            )
            if not args.dry_run:
                write_reports(report, json_report, markdown_report, force=args.force)

            action = "INSPECTED" if args.dry_run else "EXTRACTED"
            print(
                f"{action}: {relative_pdf.as_posix()} | "
                f"{report['processed_page_count']}/{report['document_page_count']} pages | "
                f"{report['overall_readiness']}"
            )
            if args.dry_run:
                print(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception as exc:  # noqa: BLE001 - one failed PDF must not stop the batch
            failures += 1
            print(f"FAILED: {relative_pdf.as_posix()}: {exc}", file=sys.stderr)
            if (
                not args.dry_run
                and not isinstance(exc, FileExistsError)
                and not json_report.exists()
                and not markdown_report.exists()
            ):
                failure_report = build_failure_report(pdf_path, relative_pdf.as_posix(), exc)
                try:
                    write_reports(
                        failure_report,
                        json_report,
                        markdown_report,
                        force=False,
                    )
                except OSError as report_error:
                    print(
                        f"FAILED TO WRITE REPORT: {relative_pdf.as_posix()}: {report_error}",
                        file=sys.stderr,
                    )

    return 1 if failures else 0


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
