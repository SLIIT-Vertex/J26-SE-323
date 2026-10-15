# Check the RAG from the terminal

This Mac has no `python` command. Every command below uses
`/tmp/j26-phase2-venv/bin/python`. `backend/.venv` is not present.

These checks ask the retriever. They do not start the play screen. A play response of
`CURRICULUM_RETRIEVAL_UNAVAILABLE` is a separate route and does not mean the retriever failed.

## 1. Tests

```bash
cd backend
/tmp/j26-phase2-venv/bin/python -m pytest tests/curriculum tests/gamification/test_curriculum_pilot_retrieval.py -q
```

Exit code 0 means the contracts, the index, the hybrid retriever, and the gamification
adapter agree. The adapter test loads the four `MAT-FRC` chunks and expects status `FOUND`.

## 2. Ask the retriever for one skill

From `backend/`:

```bash
/tmp/j26-phase2-venv/bin/python - <<'PY'
from pathlib import Path

from app.curriculum.application.retrieval import CurriculumRetrievalRequest
from app.curriculum.infrastructure.skill_index import open_skill_retriever

root = Path("..")
chunks = root / "data/curriculum/chunks/v1/chunks.jsonl"
registry = root / "data/curriculum/registry/v1/sources.jsonl"

for skill in ("MAT-FRC", "LAN-BIL", "LAN-WRT", "ENV-CIV"):
    engine, session, retriever, loaded = open_skill_retriever(
        f"sqlite:////tmp/j26-curriculum-check-{skill}.sqlite",
        chunks,
        registry,
        skill,
    )
    try:
        result = retriever.retrieve(
            CurriculumRetrievalRequest(
                learner_question="Grade 5",
                skill_id=skill,
                grade=5,
                purpose="CONTENT_AUTHORING",
                limit=4,
            )
        )
    finally:
        session.close()
        engine.dispose()
    print(
        skill,
        "loaded",
        loaded,
        "status",
        result.status.value,
        "returned",
        len(result.passages),
    )
PY
```

A working index prints:

```text
MAT-FRC loaded 4 status FOUND returned 4
LAN-BIL loaded 40 status FOUND returned 4
LAN-WRT loaded 23 status FOUND returned 4
ENV-CIV loaded 0 status NO_APPROVED_SOURCE returned 0
```

`loaded` is how many chunks of that skill were written into the database. `returned` is
how many of those came back, capped at 4. `LAN-BIL` has 40 English chunks, so `returned 4`
means the limit cut the list, not that English only has four chunks. `ENV-CIV` loads
nothing, so the status is `NO_APPROVED_SOURCE` and `returned` is 0. That is the current
Environmental Studies result.

The script prints counts and statuses. It does not print passage text.

Each skill uses its own SQLite file under `/tmp`. Opening a skill replaces that file.
The files are local indexes, not the gamification session store.

## 3. Score the fractions query

From `backend/`, the same directory as the other checks:

```bash
/tmp/j26-phase2-venv/bin/python scripts/evaluate_curriculum_retrieval.py
```

A working run prints a line of this shape:

```text
loaded 4 MAT-FRC chunks
wrote data/curriculum/evaluation/v1/reports/retrieval-evaluation.json reviewed=False filter_check_passed=True CONTENT_AUTHORING recall=1.0
```

`recall=1.0` means the four chunk ids listed in
`data/curriculum/evaluation/v1/gamification-queries.jsonl` came back for `MAT-FRC-PILOT`.
`reviewed=False` means no reviewer signed that query. The report is not an
educational-effectiveness claim. Exit code 0 also means the filter-violation rate was 0.
