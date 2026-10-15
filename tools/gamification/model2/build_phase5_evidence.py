"""Build deterministic synthetic-only Model 2 review evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "gamification" / "model2-phase5" / "v1"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.gamification.modeling.support_selection.phase5 import (
    ARTIFACT_SCHEMA_VERSION,
    BASELINE_POLICY_VERSION,
    CONTEXT_SCHEMA_VERSION,
    POLICY_VERSION,
    Model2Artifact,
    run_phase5_simulation,
)

OUTPUT_FILES = ("synthetic-evaluation.json", "model2-artifact.json", "manifest.json")


def _plain(value):
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _render(value: object) -> str:
    return json.dumps(_plain(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def build_outputs(*, seed: int = 31) -> dict[str, str]:
    simulation = _plain(run_phase5_simulation(seed=seed))
    evaluation = {
        "approval_status": "blocked_pending_human_approval",
        "evidence_status": "synthetic_engineering_only",
        "effectiveness_claim_authorized": False,
        "policy_version": POLICY_VERSION,
        "baseline_policy_version": BASELINE_POLICY_VERSION,
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "simulation": simulation,
        "limitations": [
            "No authorized real learner data was used.",
            "No educational-effectiveness, fairness, or child-safety claim is supported.",
            "Offline/shadow engineering evidence cannot authorize learned child control.",
        ],
    }
    evaluation_text = _render(evaluation)
    synthetic_manifest = {
        "generator_version": simulation["generator_version"],
        "seed": seed,
        "scenario_names": simulation["scenarios"],
        "synthetic": True,
        "evaluation_sha256": _digest(evaluation_text),
    }
    dataset_manifest_sha256 = _digest(_render(synthetic_manifest))
    artifact = Model2Artifact.create(
        artifact_version="model2-synthetic-engineering-v1",
        dataset_manifest_sha256=dataset_manifest_sha256,
        evaluation_sha256=_digest(evaluation_text),
        seed=seed,
        parameters={
            "candidate": "disjoint_linucb",
            "alpha": 0.1,
            "ridge": 1.0,
            "epsilon_min": 0.05,
            "action_types": simulation["known_best_actions"],
        },
        synthetic=True,
    )
    artifact_payload = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_version": artifact.artifact_version,
        "artifact_sha256": artifact.artifact_sha256,
        "policy_version": artifact.policy_version,
        "context_schema_version": artifact.context_schema_version,
        "catalogue_version": artifact.catalogue_version,
        "dataset_manifest_sha256": artifact.dataset_manifest_sha256,
        "evaluation_sha256": artifact.evaluation_sha256,
        "seed": artifact.seed,
        "parameters": dict(artifact.parameters),
        "evidence_status": artifact.evidence_status,
        "data_authorization_reference": artifact.data_authorization_reference,
        "lifecycle": artifact.lifecycle.value,
        "child_delivery_status": "blocked_pending_human_approval",
    }
    artifact_text = _render(artifact_payload)
    manifest = {
        "package_version": "phase5-model2-evidence-v1",
        "scope": "synthetic_offline_and_shadow_engineering_evidence",
        "files": {
            "model2-artifact.json": _digest(artifact_text),
            "synthetic-evaluation.json": _digest(evaluation_text),
        },
        "artifact_sha256": artifact.artifact_sha256,
        "approval_status": "blocked_pending_human_approval",
    }
    return {
        "synthetic-evaluation.json": evaluation_text,
        "model2-artifact.json": artifact_text,
        "manifest.json": _render(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIRECTORY)
    args = parser.parse_args()
    outputs = build_outputs()
    if args.check:
        for name in OUTPUT_FILES:
            path = args.output_dir / name
            if not path.is_file() or path.read_text(encoding="utf-8") != outputs[name]:
                raise SystemExit(f"Model 2 evidence is out of date: {path}")
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        (args.output_dir / name).write_text(outputs[name], encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
