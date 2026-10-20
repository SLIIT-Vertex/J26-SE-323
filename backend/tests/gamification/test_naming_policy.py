"""Repository-wide guard for stable implementation terminology."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALLOWED_RESEARCH = ROOT / "research" / "adaptive_gamified_learning_plan"
SKIPPED_DIRECTORY_NAMES = {
    ".git",
    ".next",
    ".playwright-mcp",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}
GENERATED_WEB_COPIES = {
    ROOT / "frontend" / "android" / "app" / "src" / "main" / "assets" / "public",
    ROOT / "frontend" / "ios" / "App" / "App" / "public",
}
NUMBERED_IMPLEMENTATION_TERM = re.compile(r"phase[\s_-]*\d+", re.IGNORECASE)


def _excluded(path: Path) -> bool:
    if path == ALLOWED_RESEARCH or ALLOWED_RESEARCH in path.parents:
        return True
    if any(
        part in SKIPPED_DIRECTORY_NAMES or part.startswith(".venv")  # e.g. .venv313 virtualenvs
        for part in path.relative_to(ROOT).parts
    ):
        return True
    return any(path == generated or generated in path.parents for generated in GENERATED_WEB_COPIES)


def test_repository_uses_stable_domain_names_outside_the_research_plan() -> None:
    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if _excluded(path):
            continue
        relative = path.relative_to(ROOT).as_posix()
        if NUMBERED_IMPLEMENTATION_TERM.search(relative):
            violations.append(f"path:{relative}")
        if not path.is_file() or path.suffix == ".tsbuildinfo":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if NUMBERED_IMPLEMENTATION_TERM.search(line):
                violations.append(f"text:{relative}:{line_number}")
    assert violations == []
