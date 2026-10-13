import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
)
from app.gamification.modeling.misconception_inference.training import (
    train_frequency_candidate,
)
from app.gamification.modeling.offline.dataset_manifest import DatasetManifest
from app.gamification.modeling.shared.artifact_registry import model_card
from app.gamification.modeling.synthetic.datasets import load_dataset_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline gamification model tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("dataset", type=Path)
    manifest_parser.add_argument("output", type=Path)
    manifest_parser.add_argument("--dataset-id", required=True)
    manifest_parser.add_argument("--seed", type=int, default=42)
    manifest_parser.add_argument("--synthetic", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate-classification")
    evaluate_parser.add_argument("predictions", type=Path)
    evaluate_parser.add_argument("output", type=Path)
    evaluate_parser.add_argument("--slice-field", default="skill_id")
    train_parser = subparsers.add_parser("train-candidate")
    train_parser.add_argument("dataset", type=Path)
    train_parser.add_argument("artifact", type=Path)
    train_parser.add_argument("model_card", type=Path)
    train_parser.add_argument("--dataset-id", required=True)
    train_parser.add_argument("--model-name", required=True)
    train_parser.add_argument("--model-version", required=True)
    train_parser.add_argument("--source-commit", required=True)
    train_parser.add_argument("--feature-version", required=True)
    train_parser.add_argument("--seed", type=int, default=42)
    train_parser.add_argument("--synthetic", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse offline commands and delegate all model behavior to its owning package."""

    args = build_parser().parse_args(argv)
    if args.command == "manifest":
        manifest = DatasetManifest.build(
            load_dataset_rows(args.dataset),
            dataset_id=args.dataset_id,
            split_seed=args.seed,
            synthetic=args.synthetic,
        )
        args.output.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    elif args.command == "evaluate-classification":
        records = json.loads(args.predictions.read_text())
        report = evaluate_classification(records, slice_field=args.slice_field)
        args.output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
    elif args.command == "train-candidate":
        rows = load_dataset_rows(args.dataset)
        manifest = DatasetManifest.build(
            rows,
            dataset_id=args.dataset_id,
            split_seed=args.seed,
            synthetic=args.synthetic,
        )
        artifact = train_frequency_candidate(
            rows,
            manifest=manifest,
            model_name=args.model_name,
            model_version=args.model_version,
            source_commit=args.source_commit,
            feature_definition_version=args.feature_version,
            seed=args.seed,
        )
        args.artifact.write_text(json.dumps(asdict(artifact), indent=2, sort_keys=True) + "\n")
        args.model_card.write_text(model_card(artifact, manifest) + "\n")
    return 0
