"""Run the deterministic Task 16A Adaptive Tutor evaluation."""

import argparse
import json
from pathlib import Path

from app.adaptive_tutor.evaluation import (
    EvaluationManifest,
    evaluate_reference_policy,
    render_evaluation_summary,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = (
    REPOSITORY_ROOT / "backend/app/adaptive_tutor/application/reference_scenarios.json"
)
DEFAULT_MANIFEST = REPOSITORY_ROOT / "research/adaptive-tutor/evaluation-manifest-v1.json"
DEFAULT_JSON_OUTPUT = (
    REPOSITORY_ROOT / "research/adaptive-tutor/results/controller-reference-policy-v1.json"
)
DEFAULT_SUMMARY_OUTPUT = (
    REPOSITORY_ROOT / "research/adaptive-tutor/results/controller-reference-policy-v1.md"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    return parser


def run(args: argparse.Namespace) -> dict[str, object]:
    document = json.loads(args.dataset.read_text(encoding="utf-8"))
    manifest = EvaluationManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    report = evaluate_reference_policy(
        document,
        manifest,
        dataset_source=_relative_or_absolute(args.dataset),
    )
    summary = render_evaluation_summary(report)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.summary_output.write_text(summary, encoding="utf-8")
    return report


def main() -> int:
    args = build_parser().parse_args()
    report = run(args)
    print(render_evaluation_summary(report), end="")
    return 0


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPOSITORY_ROOT))
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
