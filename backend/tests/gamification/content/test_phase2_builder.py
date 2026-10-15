import importlib.util
from pathlib import Path

import pytest

from app.gamification.content.phase2_registry import PHASE2_CONTENT_DIRECTORY

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BUILDER_PATH = (
    PROJECT_ROOT / "tools/gamification/datasets/build_grade5_sinhala_phase2_slice.py"
)


def load_builder() -> object:
    spec = importlib.util.spec_from_file_location("phase2_builder", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_rebuild_is_deterministic_and_current() -> None:
    builder = load_builder()
    first = builder.build_manifest(PHASE2_CONTENT_DIRECTORY)
    second = builder.build_manifest(PHASE2_CONTENT_DIRECTORY)

    assert first == second
    assert (PHASE2_CONTENT_DIRECTORY / "manifest.json").read_text(encoding="utf-8") == first


def test_pinned_official_source_is_unchanged_when_available() -> None:
    builder = load_builder()
    package = builder.PublicPhase2Package.model_validate_json(
        (PHASE2_CONTENT_DIRECTORY / "public_content.json").read_text(encoding="utf-8")
    )
    source_path = PROJECT_ROOT / package.source.source_path
    if not source_path.is_file():
        pytest.skip("raw curriculum PDFs are intentionally not committed")
    builder.verify_source(PHASE2_CONTENT_DIRECTORY)
