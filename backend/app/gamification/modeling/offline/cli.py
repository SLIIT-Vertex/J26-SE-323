import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from app.gamification.modeling.misconception_inference.evaluation import (
    evaluate_classification,
)
from app.gamification.modeling.misconception_inference.training import (
    train_frequency_candidate,
    train_likelihood_tables,
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
    evaluate_parser.add_argument("--ece-bins", type=int, default=10)
    evaluate_parser.add_argument("--top-k", type=int, default=3)
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
    bayes_parser = subparsers.add_parser("train-bayesian")
    bayes_parser.add_argument("dataset", type=Path)
    bayes_parser.add_argument("artifact", type=Path)
    bayes_parser.add_argument("model_card", type=Path)
    bayes_parser.add_argument("--dataset-id", required=True)
    bayes_parser.add_argument("--model-name", required=True)
    bayes_parser.add_argument("--model-version", required=True)
    bayes_parser.add_argument("--source-commit", required=True)
    bayes_parser.add_argument("--feature-version", required=True)
    bayes_parser.add_argument("--catalogue-version")
    bayes_parser.add_argument("--use-pilot-catalogue", action="store_true")
    bayes_parser.add_argument("--seed", type=int, default=42)
    bayes_parser.add_argument("--synthetic", action="store_true")
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
        args.output.write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    elif args.command == "evaluate-classification":
        records = json.loads(args.predictions.read_text(encoding="utf-8"))
        report = evaluate_classification(
            records, slice_field=args.slice_field, ece_bins=args.ece_bins, top_k=args.top_k
        )
        args.output.write_text(
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
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
        args.artifact.write_text(
            json.dumps(asdict(artifact), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.model_card.write_text(
            model_card(artifact, manifest) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    elif args.command == "train-bayesian":
        rows = load_dataset_rows(args.dataset)
        manifest = DatasetManifest.build(
            rows,
            dataset_id=args.dataset_id,
            split_seed=args.seed,
            synthetic=args.synthetic,
        )
        catalogue_version, skill_codes, skill_families = _catalogue_binding(args)
        artifact = train_likelihood_tables(
            rows,
            manifest=manifest,
            model_name=args.model_name,
            model_version=args.model_version,
            source_commit=args.source_commit,
            feature_definition_version=args.feature_version,
            seed=args.seed,
            catalogue_version=catalogue_version,
            skill_codes=skill_codes,
            skill_families=skill_families,
        )
        args.artifact.write_text(
            json.dumps(asdict(artifact), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        args.model_card.write_text(
            model_card(artifact, manifest) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0


def _catalogue_binding(
    args: argparse.Namespace,
) -> tuple[str, dict[str, list[str]] | None, dict[str, str] | None]:
    if args.use_pilot_catalogue:
        from app.gamification.content import load_pilot_content_package

        package = load_pilot_content_package(allow_draft=True)
        skill_codes = {
            skill_id: [
                code
                for code, misconception in package.misconceptions.items()
                if skill_id in misconception.skill_ids and code != "unknown/other"
            ]
            for skill_id in package.skills
        }
        families = {
            skill_id: skill.universal_skill_id for skill_id, skill in package.skills.items()
        }
        return package.versions["catalogue_version"], skill_codes, families
    if not args.catalogue_version:
        raise SystemExit("train-bayesian requires --catalogue-version or --use-pilot-catalogue")
    return args.catalogue_version, None, None
