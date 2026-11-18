"""Build the games' Bayesian misconception model for one area from the expert model data.

The tables in ``expert-model-data/v1`` are provisional expert assumptions taken from the rule-based
games. Each area has one table; every skill of the area uses it, because the model is keyed by
skill. Every file is checked against the package manifest before it is used.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path

from app.gamification.modeling.misconception_inference.bayesian_model import (
    GAME_FACTOR_WEIGHTS,
    GAME_MODEL_VERSION,
    BayesianMisconceptionModel,
    band_evidence_key,
)
from app.gamification.modeling.misconception_inference.game_belief import GameBeliefSettings
from app.gamification.modeling.shared.expert_data import (
    EXPERT_MODEL_DATA_DIRECTORY,
    EXPERT_MODEL_DATA_VERSION,
    read_expert_manifest,
    read_verified_expert_file,
)

__all__ = ["EXPERT_MODEL_DATA_DIRECTORY", "load_game_misconception_model"]


def load_game_misconception_model(
    area_id: str,
    skill_ids: Iterable[str],
    *,
    directory: Path = EXPERT_MODEL_DATA_DIRECTORY,
) -> BayesianMisconceptionModel:
    """The expert-initialised model for one game area, with every given skill on its table."""

    skills = tuple(dict.fromkeys(skill_ids))
    if not skills:
        raise ValueError(f"{area_id} needs at least one skill")
    manifest = read_expert_manifest(directory)
    table_path = f"misconception_tables/{area_id}.json"
    hashes = {}
    table, hashes[table_path] = read_verified_expert_file(directory, manifest, table_path)
    settings, hashes["misconception_settings.json"] = read_verified_expert_file(
        directory, manifest, "misconception_settings.json"
    )
    families, hashes["reason_families.json"] = read_verified_expert_file(
        directory, manifest, "reason_families.json"
    )
    assert isinstance(table, Mapping) and isinstance(settings, Mapping)
    assert isinstance(families, Mapping)
    if table["area_id"] != area_id:
        raise ValueError(f"{table_path} belongs to another area")
    rows = {
        band_evidence_key(band, code): dict(row)
        for band, by_code in table["error_likelihoods"].items()
        for code, row in by_code.items()
    }
    return BayesianMisconceptionModel(
        catalogue_version=str(table["catalogue_version"]),
        skill_codes={skill: list(table["codes"]) for skill in skills},
        class_priors={skill: dict(table["class_priors"]) for skill in skills},
        error_likelihoods={skill: rows for skill in skills},
        factor_weights=GAME_FACTOR_WEIGHTS,
        table_version=EXPERT_MODEL_DATA_VERSION,
        model_version=GAME_MODEL_VERSION,
        game=GameBeliefSettings.from_expert_data(table, settings, families, file_sha256=hashes),
    )
