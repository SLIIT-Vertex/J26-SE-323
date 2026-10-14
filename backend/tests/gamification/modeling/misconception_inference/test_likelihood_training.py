from dataclasses import replace

import pytest

from app.gamification.content import load_pilot_content_package
from app.gamification.modeling.misconception_inference import BayesianMisconceptionModel
from app.gamification.modeling.misconception_inference.training import train_likelihood_tables
from app.gamification.modeling.offline import DatasetManifest, DatasetRow

CATALOGUE = "synthetic-misconceptions-v1"


def _row(learner: str, label: str, skill: str = "synthetic-skill") -> DatasetRow:
    return DatasetRow(
        episode_id=f"{learner}-{label}-{skill}",
        learner_id=learner,
        features={
            "skill_id": skill,
            "skill_family": "synthetic-family",
            "selected_option_id": f"{label}-option",
            "distractor_misconception_code": label,
            "structured_error_code": f"{label}-error",
            "attempt_count": 2,
            "response_time_ratio": 1.0,
            "learner_support_need": 0.2,
        },
        action_id="synthetic-action",
        reward=None,
        propensity=None,
        valid_outcome=False,
        label=label,
    )


def _manifest(*train: str, test: tuple[str, ...] = ()) -> DatasetManifest:
    return DatasetManifest(
        dataset_id="synthetic-likelihood",
        schema_version="offline-dataset-v1",
        source_sha256="0" * 64,
        exclusion_rules=("invalid_outcome",),
        split_seed=1,
        learner_splits={"train": train, "validation": (), "test": test},
        synthetic=True,
    )


def test_likelihood_training_uses_only_the_train_split_and_is_reproducible() -> None:
    rows = [_row("train-learner", "m-a") for _ in range(6)] + [_row("test-learner", "m-b")]
    manifest = _manifest("train-learner", test=("test-learner",))
    arguments = {
        "manifest": manifest,
        "model_name": "misconception-bayesian",
        "model_version": "bayesian-misconception-v1",
        "source_commit": "test-fixture-commit",
        "feature_definition_version": "gamification-features-v2",
        "seed": 3,
        "catalogue_version": CATALOGUE,
    }

    first = train_likelihood_tables(rows, **arguments)
    second = train_likelihood_tables(rows, **arguments)
    changed_test = train_likelihood_tables(
        [_row("train-learner", "m-a") for _ in range(6)] + [_row("test-learner", "m-a")],
        **arguments,
    )
    changed_train = train_likelihood_tables(
        [_row("train-learner", "m-b") for _ in range(6)] + [_row("test-learner", "m-b")],
        **arguments,
    )

    assert first == second
    assert first == changed_test
    assert first != changed_train
    prior = first.parameters["class_priors"]["synthetic-skill"]
    assert "m-b" not in prior
    assert prior["m-a"] > prior["unknown/other"]
    trained_prior = changed_train.parameters["class_priors"]["synthetic-skill"]
    assert trained_prior["m-b"] == max(trained_prior.values())
    restored = BayesianMisconceptionModel.from_artifact(first)
    assert restored.catalogue_version == CATALOGUE


def test_likelihood_training_rejects_a_leaking_split() -> None:
    manifest = replace(
        _manifest("train-learner", test=("train-learner",)),
    )
    with pytest.raises(ValueError, match="multiple"):
        train_likelihood_tables(
            [_row("train-learner", "m-a")],
            manifest=manifest,
            model_name="misconception-bayesian",
            model_version="bayesian-misconception-v1",
            source_commit="test-fixture-commit",
            feature_definition_version="gamification-features-v2",
            seed=1,
            catalogue_version=CATALOGUE,
        )


def test_pilot_catalogue_codes_can_train_a_draft_artifact() -> None:
    package = load_pilot_content_package(allow_draft=True)
    rows: list[DatasetRow] = []
    learners: list[str] = []
    skill_codes: dict[str, list[str]] = {}
    for index, (skill_id, skill) in enumerate(sorted(package.skills.items())):
        codes = [
            code
            for code, misconception in package.misconceptions.items()
            if skill_id in misconception.skill_ids and not misconception.reserved
        ]
        skill_codes[skill_id] = codes
        learner = f"synthetic-pilot-{index}"
        learners.append(learner)
        rows.append(_row(learner, codes[0], skill_id))

    artifact = train_likelihood_tables(
        rows,
        manifest=_manifest(*learners),
        model_name="misconception-bayesian",
        model_version="bayesian-misconception-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v2",
        seed=1,
        catalogue_version=package.versions["catalogue_version"],
        skill_codes=skill_codes,
        skill_families={
            skill_id: skill.universal_skill_id for skill_id, skill in package.skills.items()
        },
    )

    model = BayesianMisconceptionModel.from_artifact(artifact)
    assert model.catalogue_version == "grade5-pilot-misconceptions-v1"
    assert set(model.skill_codes) == set(package.skills)
    assert artifact.parameters["weights_status"] == "provisional_assumption"
    assert artifact.parameters["pooling_status"] == "provisional_assumption"
