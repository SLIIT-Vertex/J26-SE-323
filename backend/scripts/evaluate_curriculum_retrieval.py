"""Score the shared curriculum query set and write the retrieval report.

A missing tutor query file is skipped. This script loads the manifest skill's chunks
into the database it scores. It does not call Adaptive Tutor code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.curriculum.application.retrieval_evaluation import (
    evaluate_queries,
    load_evaluation_manifest,
    load_evaluation_queries,
    load_optional_query_file,
    report_without_signed_queries,
    sha256_file,
    write_evaluation_report,
)
from app.curriculum.infrastructure.hybrid_retriever import retriever_version_for
from app.curriculum.infrastructure.skill_index import (
    PILOT_EMBEDDING_REVISION,
    open_skill_retriever,
)

DEFAULT_MANIFEST = REPOSITORY_ROOT / "data/curriculum/evaluation/v1/manifest.json"
DEFAULT_GAMIFICATION = REPOSITORY_ROOT / "data/curriculum/evaluation/v1/gamification-queries.jsonl"
DEFAULT_TUTOR = REPOSITORY_ROOT / "data/curriculum/evaluation/v1/tutor-queries.jsonl"
DEFAULT_CHUNK_MANIFEST = REPOSITORY_ROOT / "data/curriculum/chunks/v1/manifest.json"
DEFAULT_CHUNKS = REPOSITORY_ROOT / "data/curriculum/chunks/v1/chunks.jsonl"
DEFAULT_REGISTRY = REPOSITORY_ROOT / "data/curriculum/registry/v1/sources.jsonl"
DEFAULT_REPORT = REPOSITORY_ROOT / "data/curriculum/evaluation/v1/reports/retrieval-evaluation.json"
DEFAULT_DATABASE = "sqlite:////tmp/j26-curriculum-mat-frc.sqlite"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score the shared curriculum retrieval set.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gamification-queries", type=Path, default=DEFAULT_GAMIFICATION)
    parser.add_argument("--tutor-queries", type=Path, default=DEFAULT_TUTOR)
    parser.add_argument("--chunk-manifest", type=Path, default=DEFAULT_CHUNK_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DATABASE,
        help="SQLite or Postgres URL. The manifest skill's chunks are loaded into it.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = load_evaluation_manifest(args.manifest)
    gamification = load_evaluation_queries(
        args.gamification_queries,
        expected_purpose="CONTENT_AUTHORING",
    )
    tutor = load_optional_query_file(args.tutor_queries, expected_purpose="TUTOR_ANSWER")
    queries = gamification + (tutor or ())
    chunk_hash = sha256_file(args.chunk_manifest)
    version = retriever_version_for(PILOT_EMBEDDING_REVISION)
    if not queries:
        report = report_without_signed_queries(
            manifest=manifest,
            retriever_version=version,
            chunk_manifest_sha256=chunk_hash,
            tutor_queries_present=tutor is not None,
        )
    else:
        engine, session, retriever, loaded = open_skill_retriever(
            args.database_url,
            args.chunks,
            args.registry,
            manifest.skill_id,
        )
        if loaded == 0:
            print(f"No {manifest.skill_id} chunks to load.", file=sys.stderr)
            session.close()
            engine.dispose()
            return 1
        print(f"loaded {loaded} {manifest.skill_id} chunks")
        try:
            report = evaluate_queries(
                queries,
                retriever,
                manifest=manifest,
                retriever_version=version,
                chunk_manifest_sha256=chunk_hash,
                tutor_queries_present=tutor is not None,
            )
        finally:
            session.close()
            engine.dispose()
    write_evaluation_report(args.report, report)
    print(
        f"wrote {args.report} reviewed={report.reviewed} "
        f"filter_check_passed={report.filter_check_passed} "
        f"CONTENT_AUTHORING recall={report.by_purpose['CONTENT_AUTHORING'].recall_at_k}"
    )
    if report.filter_check_passed is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
