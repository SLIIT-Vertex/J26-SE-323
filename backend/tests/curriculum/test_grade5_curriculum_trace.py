import hashlib
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TRACE_DIR = REPOSITORY_ROOT / "data/curriculum/grade5-curriculum-trace/v1"
TRACE_FILES = ("curriculum_sources.jsonl", "curriculum_nodes.jsonl", "curriculum_terms.jsonl")


def load_jsonl(filename: str) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in (TRACE_DIR / filename).read_text(encoding="utf-8").splitlines()
    ]


def test_manifest_hashes_every_trace_file() -> None:
    manifest = json.loads((TRACE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["package"] == "grade5-curriculum-trace"
    assert manifest["version"] == "1.0.0"
    assert manifest["review_status"] == "draft trace; not reviewed or approved"
    assert set(manifest["files"]) == {*TRACE_FILES, "schema.json", "README.md"}
    assert len(manifest["source_workbooks"]) == 4
    for filename, metadata in manifest["files"].items():
        payload = (TRACE_DIR / filename).read_bytes()
        assert len(payload) == metadata["bytes"]
        assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]


def test_trace_counts_and_references_resolve() -> None:
    sources = load_jsonl("curriculum_sources.jsonl")
    nodes = load_jsonl("curriculum_nodes.jsonl")
    terms = load_jsonl("curriculum_terms.jsonl")
    source_ids = {source["source_id"] for source in sources}

    assert (len(sources), len(nodes), len(terms)) == (17, 1_884, 250)
    assert len(source_ids) == len(sources)
    assert len({node["curriculum_node_id"] for node in nodes}) == len(nodes)
    assert all(node["source_id"] in source_ids for node in nodes)
    assert all(term["source_id"] in source_ids for term in terms)
    assert all(node["grade"] == 5 for node in nodes)


def test_trace_records_remain_unreviewed_drafts() -> None:
    sources = load_jsonl("curriculum_sources.jsonl")
    nodes = load_jsonl("curriculum_nodes.jsonl")
    terms = load_jsonl("curriculum_terms.jsonl")

    assert {source["approval_status"] for source in sources} == {"needs_review"}
    assert {node["trace_status"] for node in nodes} == {"draft"}
    assert {node["verification_status"] for node in nodes} == {"needs_review"}
    assert not any(node["reviewed_by"] for node in nodes)
    assert {term["trace_status"] for term in terms} == {"draft"}
