"""Read the expert model data package, checking every file against its manifest.

``expert-model-data/v1`` holds the provisional expert assumptions both research models start
from. They were taken from the rule-based games and no teacher has reviewed them yet.
"""

import hashlib
import json
from collections.abc import Mapping
from functools import cache
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


@cache
def _reason_families() -> Mapping[str, object]:
    manifest = read_expert_manifest(EXPERT_MODEL_DATA_DIRECTORY)
    families, _sha256 = read_verified_expert_file(
        EXPERT_MODEL_DATA_DIRECTORY, manifest, "reason_families.json"
    )
    assert isinstance(families, Mapping)
    return families


def expert_reason_family(label: str | None, subject: str) -> str:
    """A Model 1 label's reason family, from the checked expert data both models read."""

    table = _reason_families()["subjects"][subject]  # type: ignore[index]
    row = table["labels"].get(label or "")
    return str((row or table["missing_label"])["reason_family"])
