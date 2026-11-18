"""Read the expert model data package, checking every file against its manifest.

``expert-model-data/v1`` holds the provisional expert assumptions both research models start
from. They were taken from the rule-based games and no teacher has reviewed them yet.
"""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from app.gamification.data_paths import GAMIFICATION_DATA_DIRECTORY

EXPERT_MODEL_DATA_DIRECTORY = GAMIFICATION_DATA_DIRECTORY / "expert-model-data" / "v1"
EXPERT_MODEL_DATA_VERSION = "expert-model-data-v1"
EXPERT_EVIDENCE_STATUS = "provisional_expert_assumption"


def read_expert_manifest(directory: Path = EXPERT_MODEL_DATA_DIRECTORY) -> Mapping[str, object]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("package_version") != EXPERT_MODEL_DATA_VERSION
        or manifest.get("evidence_status") != EXPERT_EVIDENCE_STATUS
    ):
        raise ValueError("expert model data must be the provisional expert package")
    return manifest


def read_verified_expert_file(
    directory: Path, manifest: Mapping[str, object], path: str
) -> tuple[object, str]:
    """One package file's content and SHA-256, refused unless it matches the manifest."""

    expected = manifest["files"].get(path)  # type: ignore[union-attr]
    if expected is None:
        raise KeyError(f"{path} is not in the expert model data manifest")
    content = (directory / path).read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise ValueError(f"{path} does not match its manifest hash")
    return json.loads(content), actual
