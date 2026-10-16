"""Copy Universal skill ids from the draft crosswalk onto learning-outcome rows.

The crosswalk is draft and has no reviewer. This script copies those ids. It does not review
them, and it does not read gamification items, answer keys, or scaffolds.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent

DEFAULT_NODES = (
    REPOSITORY_ROOT / "data/curriculum/grade5-curriculum-trace/v1/curriculum_nodes.jsonl"
)
DEFAULT_CROSSWALK = (
    REPOSITORY_ROOT / "data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data/curriculum/skill-links/v1/outcome-universal-skills.jsonl"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_links(
    nodes_path: Path, crosswalk_path: Path
) -> tuple[list[dict[str, object]], dict[str, int]]:
    outcomes = {
        str(row["curriculum_node_id"])
        for row in read_jsonl(nodes_path)
        if row.get("node_type") == "learning_outcome"
    }
    links: list[dict[str, object]] = []
    seen: dict[str, str] = {}
    for row in read_jsonl(crosswalk_path):
        node_id = str(row["gamification_skill_id"])
        if node_id not in outcomes:
            continue
        skill_id = str(row["universal_skill_id"])
        previous = seen.get(node_id)
        if previous is not None and previous != skill_id:
            raise ValueError(f"{node_id} has two universal skill ids")
        seen[node_id] = skill_id
        links.append(
            {
                "confidence": row.get("confidence"),
                "crosswalk_version": row.get("crosswalk_version"),
                "curriculum_node_id": node_id,
                "reviewer_id": row.get("reviewer_id"),
                "status": row.get("status"),
                "universal_skill_id": skill_id,
            }
        )
    links.sort(key=lambda item: str(item["curriculum_node_id"]))
    missing = sorted(outcomes - set(seen))
    if missing:
        raise ValueError(f"{len(missing)} learning outcomes have no crosswalk row")
    counts = Counter(str(item["status"]) for item in links)
    return links, dict(counts)


def write_links(path: Path, links: list[dict[str, object]], status_counts: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in links
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "confidence_counts": dict(Counter(str(row["confidence"]) for row in links)),
        "learning_outcome_rows": len(links),
        "reviewer_id": None,
        "source": "data/gamification/skill-catalogue-review/v1/universal-skill-crosswalk.jsonl",
        "status": "draft",
        "status_counts": status_counts,
        "note": "Copied from the draft crosswalk. No reviewer has signed these ids.",
    }
    path.with_name("manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy draft Universal skill ids for learning outcomes."
    )
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    links, status_counts = build_links(args.nodes, args.crosswalk)
    write_links(args.output, links, status_counts)
    print(f"wrote {len(links)} draft learning-outcome skill links to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
