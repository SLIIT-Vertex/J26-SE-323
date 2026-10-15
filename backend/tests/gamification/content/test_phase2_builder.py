import importlib.util
from pathlib import Path

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


def test_pinned_official_source_is_present_and_unchanged() -> None:
    builder = load_builder()
    builder.verify_source(PHASE2_CONTENT_DIRECTORY)
