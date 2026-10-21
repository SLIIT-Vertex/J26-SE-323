"""Import one operator-reviewed Fractions pack; never creates approval metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adaptive_tutor.infrastructure.skill_taxonomy import XlsxSkillTaxonomyCatalog
from app.curriculum.application import (
    CurriculumSourceRecord,
    ResearchCurriculumApproval,
    ResearchCurriculumImporter,
)
from app.curriculum.application.chunking import ExtractedPage
from app.curriculum.infrastructure.embeddings import E5CurriculumEmbedder
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.shared.database.session import SessionLocal


def load_manifest(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("template_status"):
        raise ValueError(
            "unreviewed template cannot be imported; copy it and replace/remove template_status "
            "only after human ownership, rights and approval review"
        )
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Import an already reviewed Fractions pack.")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    document = load_manifest(manifest_path)

    source = CurriculumSourceRecord.model_validate(document["source"])
    approval = ResearchCurriculumApproval.model_validate(document["approval"])
    pages = tuple(
        ExtractedPage(
            source_id=source.source_id,
            page_number=page["page_number"],
            text=(manifest_path.parent / page["text_file"]).read_text(encoding="utf-8"),
            conversion_status=page.get("conversion_status", "preserved_needs_review"),
            source_sha256=page.get("source_sha256"),
        )
        for page in document["pages"]
    )
    skill_ids = {
        node.skill_id
        for node in XlsxSkillTaxonomyCatalog(REPOSITORY_ROOT / "docs/skill_nodes.xlsx").load()
    }
    if set(approval.skill_ids) != {"MAT-FRC"}:
        raise ValueError("the live Fractions importer accepts only reviewed MAT-FRC scope")

    with SessionLocal() as session:
        result = ResearchCurriculumImporter(
            CurriculumVectorIndex(session),
            E5CurriculumEmbedder(local_files_only=True),
            skill_ids,
        ).import_pages(source=source, pages=pages, approval=approval)
        session.commit()
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
