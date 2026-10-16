import hashlib
import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "backend/scripts/extract_curriculum_pdfs.py"
SCRIPT_SPEC = importlib.util.spec_from_file_location("curriculum_pdf_extractor", SCRIPT_PATH)
assert SCRIPT_SPEC and SCRIPT_SPEC.loader
SCRIPT = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = SCRIPT
SCRIPT_SPEC.loader.exec_module(SCRIPT)

REFERENCE_EXAMPLES = SCRIPT.REFERENCE_EXAMPLES
atomic_write_text = SCRIPT.atomic_write_text
build_page_record = SCRIPT.build_page_record
convert_span = SCRIPT.convert_span
extract_pdf = SCRIPT.extract_pdf
run = SCRIPT.run
stream_sha256 = SCRIPT.stream_sha256


def _span(text: str, font: str, x: float = 0.0) -> dict:
    return {
        "text": text,
        "font": font,
        "size": 12.0,
        "bbox": (x, 0.0, x + 10.0, 12.0),
    }


def _page_dict(*spans: dict) -> dict:
    return {
        "blocks": [
            {
                "type": 0,
                "lines": [{"spans": list(spans)}],
            }
        ]
    }


def _record(page_dict: dict, page_number: int = 1) -> dict:
    return build_page_record(
        page_dict,
        page_number=page_number,
        source_id="curriculum:test",
        source_file="guide.pdf",
        source_sha256="0" * 64,
        extracted_at="2026-01-01T00:00:00+00:00",
    )


def _make_two_page_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "English 123 + 4")
    document.new_page()
    document.save(path)
    document.close()


@pytest.mark.parametrize(("legacy", "expected_unicode"), REFERENCE_EXAMPLES)
def test_reference_examples_are_preserved_but_not_fabricated(
    legacy: str, expected_unicode: str
) -> None:
    decision = convert_span(legacy, "FMEmaneex")

    assert decision.status == "conversion_unavailable"
    assert decision.text is None
    assert decision.text != expected_unicode


def test_preserves_english_text() -> None:
    decision = convert_span("Mathematics guide", "TimesNewRomanPS-BoldMT")

    assert decision.status == "preserved"
    assert decision.text == "Mathematics guide"


def test_preserves_existing_unicode_sinhala() -> None:
    decision = convert_span("ගණිතය", "FMEmaneex")

    assert decision.status == "preserved"
    assert decision.strategy == "preserve_existing_unicode_sinhala"
    assert decision.text == "ගණිතය"


def test_mixed_font_page_is_auditable_and_not_partially_emitted() -> None:
    record = _record(
        _page_dict(
            _span("Mathematics ", "TimesNewRomanPSMT"),
            _span(".Ks;h", "FMEmaneex", 10.0),
            _span(" 123 + 4", "FMEmaneex", 20.0),
            _span(" ගණිතය", "NotoSansSinhala", 30.0),
        )
    )

    assert record["original_text"] == "Mathematics .Ks;h 123 + 4 ගණිතය"
    assert record["text"] is None
    assert record["conversion_status"] == "conversion_unavailable"
    assert record["span_counts"] == {
        "converted": 0,
        "preserved": 3,
        "unsupported": 1,
        "failed": 0,
    }
    assert record["spans"][1]["original_text"] == ".Ks;h"
    assert record["spans"][1]["bbox"] == [10.0, 0.0, 20.0, 12.0]


def test_unknown_fm_font_is_treated_as_unverified_legacy() -> None:
    decision = convert_span("legacy", "FMUnknownFamily")

    assert decision.status == "conversion_unavailable"
    assert decision.strategy == "no_verified_font_mapping"


def test_digits_and_math_in_legacy_font_are_preserved() -> None:
    decision = convert_span("12 + 3 = 15", "FMAbabldBold")

    assert decision.status == "preserved"
    assert decision.strategy == "preserve_numeric_or_math"


def test_json_output_is_utf8_and_not_ascii_escaped(tmp_path: Path) -> None:
    record = _record(_page_dict(_span("ගණිතය", "NotoSansSinhala")))
    destination = tmp_path / "page.jsonl"

    atomic_write_text(
        destination,
        json.dumps(record, ensure_ascii=False) + "\n",
        force=False,
    )

    raw = destination.read_bytes()
    assert "ගණිතය".encode() in raw
    assert b"\\u0d9c" not in raw


def test_page_numbers_and_empty_pages_are_preserved(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two-pages.pdf"
    output_path = tmp_path / "two-pages.jsonl"
    _make_two_page_pdf(pdf_path)

    report = extract_pdf(pdf_path, output_path)
    records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert [record["page_number"] for record in records] == [1, 2]
    assert records[1]["conversion_status"] == "empty"
    assert records[1]["original_text"] == ""
    assert report["document_page_count"] == 2
    assert report["empty_pages"] == 1


def test_repeated_run_requires_force_and_never_appends(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two-pages.pdf"
    output_path = tmp_path / "two-pages.jsonl"
    _make_two_page_pdf(pdf_path)

    extract_pdf(pdf_path, output_path)
    with pytest.raises(FileExistsError, match="--force"):
        extract_pdf(pdf_path, output_path)

    extract_pdf(pdf_path, output_path, force=True)
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 2


def test_hashing_is_streamed_without_path_read_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "large.bin"
    content = b"mindbridge" * 1000
    source.write_bytes(content)

    def fail_read_bytes(_path: Path) -> bytes:
        raise AssertionError("Path.read_bytes() must not be used")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    assert stream_sha256(source, chunk_size=17) == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("kind", ["missing", "malformed"])
def test_bad_pdf_does_not_leave_partial_output(tmp_path: Path, kind: str) -> None:
    pdf_path = tmp_path / f"{kind}.pdf"
    if kind == "malformed":
        pdf_path.write_bytes(b"not a PDF")
    output_path = tmp_path / "result.jsonl"

    with pytest.raises((FileNotFoundError, pymupdf.FileDataError)):
        extract_pdf(pdf_path, output_path)

    assert not output_path.exists()


def test_dry_run_does_not_create_output(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two-pages.pdf"
    output_path = tmp_path / "two-pages.jsonl"
    _make_two_page_pdf(pdf_path)

    report = extract_pdf(pdf_path, output_path, max_pages=1, dry_run=True)

    assert report["dry_run"] is True
    assert report["processed_page_count"] == 1
    assert not output_path.exists()
    assert not output_path.parent.joinpath(f".{output_path.name}.tmp").exists()


def test_batch_continues_and_reports_an_individual_pdf_failure(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw"
    input_dir.mkdir()
    (input_dir / "a-malformed.pdf").write_bytes(b"not a PDF")
    _make_two_page_pdf(input_dir / "b-valid.pdf")
    output_dir = tmp_path / "extracted"
    report_dir = tmp_path / "reports"

    exit_code = run(
        Namespace(
            input=input_dir,
            output=output_dir,
            report_dir=report_dir,
            max_pages=None,
            dry_run=False,
            force=False,
        )
    )

    failure_report = json.loads(
        (report_dir / "a-malformed.report.json").read_text(encoding="utf-8")
    )
    assert exit_code == 1
    assert failure_report["overall_readiness"] == "EXTRACTION_FAILED"
    assert failure_report["errors"][0]["type"] == "FileDataError"
    assert (output_dir / "b-valid.jsonl").exists()
