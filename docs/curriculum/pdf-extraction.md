# Curriculum PDF extraction

`backend/scripts/extract_curriculum_pdfs.py` is an offline, page-by-page extraction tool for
preparing curriculum PDFs for human quality review. It uses PyMuPDF span metadata, preserves raw
text and positions, writes UTF-8 JSONL atomically, and creates JSON and Markdown quality reports.
Generated records are always `review_status: pending` and `rag_eligible: false`.

## Conversion safety

The Grade 5 Mathematics sample contains ordinary Latin fonts and several FM-family legacy Sinhala
fonts. The principal observed legacy fonts are `FMEmaneex`, `FMAbabldBold`, and `FMAbhayax`; the
document also contains `FMAbhaya` and `FMSamantha` resources with different extraction behavior.
Font names identify text for review but do not prove that the encodings are interchangeable.

An external candidate was investigated:

- Pandukabhaya 1.0.1: <https://github.com/akuruAI/Pandukabhaya>
- License: MIT
- Claimed encoding: FM Abhaya ASCII to Unicode

It is not enabled. The candidate does not claim the sample's principal font variants, the three
known phrases are insufficient to validate a complete mapping, and the sample's exact `FMAbhaya`
Identity-H resource extracts control-like text. Until a qualified review validates the encoding,
legacy spans retain `original_text`, receive `conversion_unavailable`, and have `text: null`. A page
containing any such span also has `text: null`, preventing incomplete text from silently entering a
later RAG pipeline.

The supplied phrases remain reference cases only:

| Raw legacy text | Expected after future validated conversion |
|---|---|
| `.Ks;h` | `ගණිතය` |
| `.=re ud¾f.damfoaYh` | `ගුරු මාර්ගෝපදේශය` |
| `Y%S ,xldj` | `ශ්‍රී ලංකාව` |

## Setup

From the repository root:

```bash
cd backend
python -m pip install -e '.[dev,curriculum-extraction]'
cd ..
```

## Commands

Inspect the sample without writing extraction outputs or reports:

```bash
backend/.venv/bin/python backend/scripts/extract_curriculum_pdfs.py \
  --input data/curriculum/raw/grade5/mathematics/grade-5-mathematics-teacher-guide-61923d6dbce3d.pdf \
  --max-pages 5 \
  --dry-run
```

Extract the first five pages and generate reports:

```bash
backend/.venv/bin/python backend/scripts/extract_curriculum_pdfs.py \
  --input data/curriculum/raw/grade5/mathematics/grade-5-mathematics-teacher-guide-61923d6dbce3d.pdf \
  --output data/curriculum/extracted \
  --report-dir data/curriculum/reports \
  --max-pages 5
```

Inspect the resulting JSONL and reports:

```bash
sed -n '1,5p' \
  data/curriculum/extracted/grade-5-mathematics-teacher-guide-61923d6dbce3d.jsonl
sed -n '1,220p' \
  data/curriculum/reports/grade-5-mathematics-teacher-guide-61923d6dbce3d.report.md
```

After approval, atomically replace the pilot with all 189 pages:

```bash
backend/.venv/bin/python backend/scripts/extract_curriculum_pdfs.py \
  --input data/curriculum/raw/grade5/mathematics/grade-5-mathematics-teacher-guide-61923d6dbce3d.pdf \
  --output data/curriculum/extracted \
  --report-dir data/curriculum/reports \
  --force
```

Process a directory later while preserving relative subpaths:

```bash
backend/.venv/bin/python backend/scripts/extract_curriculum_pdfs.py \
  --input data/curriculum/raw \
  --output data/curriculum/extracted \
  --report-dir data/curriculum/reports
```

Without `--force`, any existing JSONL or report causes that PDF to fail safely instead of appending
or overwriting. Each other PDF in a directory run continues independently. PDFs and generated
extraction/report directories are ignored by Git.
