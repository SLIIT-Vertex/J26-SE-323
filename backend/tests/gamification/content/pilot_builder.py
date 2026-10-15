import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from app.gamification.content import PILOT_CONTENT_DIRECTORY

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BUILDER_PATH = PROJECT_ROOT / "tools/gamification/datasets/build_grade5_pilot_slice.py"
_SPEC = importlib.util.spec_from_file_location("grade5_pilot_slice_builder", BUILDER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = BUILDER
_SPEC.loader.exec_module(BUILDER)

STATUS_FIELDS = {
    "skills.jsonl": "status",
    "misconception_catalogue.jsonl": "approval_status",
    "items.jsonl": "review_status",
    "parallel_groups.jsonl": "review_status",
    "scaffolds.jsonl": "approval_status",
    "content_assets.jsonl": "approval_status",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(BUILDER.render_jsonl(rows), encoding="utf-8")


def copy_package(destination: Path) -> Path:
    target = destination / "pilot"
    shutil.copytree(PILOT_CONTENT_DIRECTORY, target)
    return target


def rebuild(package_dir: Path) -> None:
    for name, text in BUILDER.build_outputs(package_dir, BUILDER.load_context()).items():
        (package_dir / name).write_text(text, encoding="utf-8")
