"""The shared feature spec: single source of truth for training and serving."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    version: int
    skills: tuple[str, ...]
    digital_source: int
    paper_source: int
    difficulty_values: dict[str, float]
    paper_penalty: float
    history_cap: int
    min_attempts_for_known_skill: int
    digital_formula: str

    def skill_index(self, code: str) -> int:
        return self.skills.index(code)


def parse_feature_spec(data: dict) -> FeatureSpec:
    coding = data["source_coding"]
    return FeatureSpec(
        version=int(data["version"]),
        skills=tuple(data["skills"]),
        digital_source=int(coding["digital"]),
        paper_source=int(coding["paper"]),
        difficulty_values={k: float(v) for k, v in data["difficulty_to_model_value"].items()},
        paper_penalty=float(data["penalty"]["paper_default"]),
        history_cap=int(data["history_cap_steps"]),
        min_attempts_for_known_skill=int(data["min_attempts_for_known_skill"]),
        digital_formula=str(data["penalty"]["digital_formula"]),
    )


def resolve_path(path: str) -> Path:
    """Find a file given relative to the working folder or to the backend folder."""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_file():
        return candidate
    for base in (Path.cwd(), BACKEND_DIR):
        resolved = (base / candidate).resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(f"file not found: {path} (check the path in .env)")


def load_feature_spec(path: str) -> FeatureSpec:
    return parse_feature_spec(json.loads(resolve_path(path).read_text(encoding="utf-8")))


@lru_cache
def get_feature_spec() -> FeatureSpec:
    from app.config import get_settings

    return load_feature_spec(get_settings().feature_spec_path)
