import pytest

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.domain.types import (
    FeatureSnapshotId,
    ProtocolVersion,
    SkillId,
    TaxonomyVersion,
)
from app.gamification.modeling.misconception_inference import (
    UNKNOWN_CODE,
    BayesianMisconceptionModel,
)
from app.gamification.modeling.misconception_inference.bayesian_model import (
    PROVISIONAL_STALENESS_THRESHOLD_MS,
)
from app.gamification.modeling.offline import DatasetManifest, DatasetRow
from app.gamification.modeling.shared import FEATURE_DEFINITION_VERSION_V1, FeatureBuilder
from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle
from tests.gamification.modeling.fixtures import LEARNER, NOW, feature_input

CODES = ("m-a", "m-b", UNKNOWN_CODE)
CATALOGUE = "provisional-misconceptions-v1"


def _favour(code: str) -> dict[str, float]:
    return {candidate: 4.0 if candidate == code else 1.0 for candidate in CODES}


def _flat() -> dict[str, float]:
    return dict.fromkeys(CODES, 1.0)


def bayesian_model(**changes: object) -> BayesianMisconceptionModel:
    arguments: dict[str, object] = {
        "catalogue_version": CATALOGUE,
        "skill_codes": {"opaque-skill-1": CODES},
        "class_priors": {"opaque-skill-1": {"m-a": 0.4, "m-b": 0.4, UNKNOWN_CODE: 0.2}},
        "option_likelihoods": {"opaque-skill-1": {"m-a": _favour("m-a")}},
        "error_likelihoods": {"opaque-skill-1": {"error-a": _favour("m-a")}},
        "attempt_likelihoods": {
            "opaque-skill-1": {"1": _flat(), "2": _favour("m-a"), "3_plus": _favour("m-a")}
        },
        "response_time_likelihoods": {
            "opaque-skill-1": {"fast": _favour("m-a"), "typical": _flat(), "slow": _favour("m-b")}
        },
        "support_need_likelihoods": {
            "opaque-skill-1": {"low": _flat(), "elevated": _favour("m-a")}
        },
        "factor_weights": {
            "option_evidence": 1.0,
            "structured_error": 1.0,
            "attempt_count": 1.0,
            "response_time_band": 1.0,
            "support_need": 1.0,
        },
    }
    arguments.update(changes)
    return BayesianMisconceptionModel(**arguments)  # type: ignore[arg-type]


def test_posterior_is_normalised_and_names_missing_factors() -> None:
    prediction = bayesian_model().predict(
        FeatureBuilder().build(feature_input(structured_error_code=None, attempt_count=1))
    )

    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.abstained
    assert "OPTION_EVIDENCE_MISSING" in prediction.reason_codes
    assert "STRUCTURED_ERROR_MISSING" in prediction.reason_codes
    assert "RESPONSE_TIME_BAND_MISSING" in prediction.reason_codes
    assert "SUPPORT_NEED_MISSING" in prediction.reason_codes
    assert "PROVISIONAL_WEIGHTS" in prediction.reason_codes


def test_fresh_prior_is_carried_and_a_stale_or_undated_prior_is_not() -> None:
    model = bayesian_model()
    beliefs = {"m-b": 0.9, "m-a": 0.05, UNKNOWN_CODE: 0.05}
    carried = model.predict(
        FeatureBuilder().build(
            feature_input(
                structured_error_code=None,
                attempt_count=1,
                prior_beliefs=beliefs,
                prior_belief_age_ms=0,
            )
        )
    )
    stale = model.predict(
        FeatureBuilder().build(
            feature_input(
                structured_error_code=None,
                attempt_count=1,
                prior_beliefs=beliefs,
                prior_belief_age_ms=PROVISIONAL_STALENESS_THRESHOLD_MS + 1,
            )
        )
    )
    undated = model.predict(
        FeatureBuilder().build(
            feature_input(structured_error_code=None, attempt_count=1, prior_beliefs=beliefs)
        )
    )
    catalogue = model.predict(
        FeatureBuilder().build(feature_input(structured_error_code=None, attempt_count=1))
    )

    assert "PRIOR_CARRIED_OVER" in carried.reason_codes
    assert carried.probabilities["m-b"] == pytest.approx(0.9)
    assert "STALE_PRIOR" in stale.reason_codes
    assert "PRIOR_TIMESTAMP_MISSING" in undated.reason_codes
    assert stale.probabilities == catalogue.probabilities
    assert undated.probabilities == catalogue.probabilities


def test_catalogue_mismatch_abstains_on_unknown() -> None:
    prediction = bayesian_model().predict(
        FeatureBuilder().build(feature_input(misconception_catalogue_version="other-catalogue"))
    )

    assert prediction.abstained
    assert prediction.probabilities == {UNKNOWN_CODE: 1.0}
    assert "CATALOGUE_VERSION_MISMATCH" in prediction.reason_codes


def test_evidence_that_favours_a_code_never_decreases_its_probability() -> None:
    model = bayesian_model()
    stages = [
        feature_input(structured_error_code=None, attempt_count=1),
        feature_input(
            structured_error_code=None, attempt_count=1, distractor_misconception_code="m-a"
        ),
        feature_input(attempt_count=1, distractor_misconception_code="m-a"),
        feature_input(
            attempt_count=1,
            distractor_misconception_code="m-a",
            response_time_ratio=0.4,
        ),
        feature_input(
            attempt_count=1,
            distractor_misconception_code="m-a",
            response_time_ratio=0.4,
            learner_support_need=0.8,
        ),
    ]
    probabilities = [
        model.predict(FeatureBuilder().build(stage)).probabilities["m-a"] for stage in stages
    ]

    assert probabilities == sorted(probabilities)
    assert probabilities[-1] > probabilities[0]


def test_version_one_snapshot_is_readable_as_missing_new_modalities() -> None:
    snapshot = FeatureSnapshotRecord(
        snapshot_id=FeatureSnapshotId(LEARNER),
        learner_id=LEARNER,
        skill_id=SkillId("opaque-skill-1"),
        captured_at=NOW,
        protocol_version=ProtocolVersion("adaptive-episode-v1"),
        taxonomy_version=TaxonomyVersion("provisional-v1"),
        feature_definition_version=FEATURE_DEFINITION_VERSION_V1,
        values={
            "skill_id": "opaque-skill-1",
            "misconception_catalogue_version": CATALOGUE,
            "attempt_count": 1,
            "structured_error_code": "error-a",
        },
        missingness={"learner_support_need": True},
    )

    prediction = bayesian_model().predict(snapshot)

    assert prediction.catalogue_version == CATALOGUE
    assert "OPTION_EVIDENCE_MISSING" in prediction.reason_codes
    assert "STRUCTURED_ERROR_MATCHED" in prediction.reason_codes
    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)


def test_artifact_round_trip_is_deterministic() -> None:
    model = bayesian_model()
    manifest = DatasetManifest.build(
        [
            DatasetRow(
                "episode", "learner", {"skill_id": "opaque-skill-1"}, "action", None, None, False
            )
        ],
        dataset_id="synthetic-bayes",
        split_seed=1,
        synthetic=True,
    )
    artifact = ModelArtifactBundle.create(
        model_name="misconception-bayesian",
        model_version="bayesian-misconception-v1",
        source_commit="test-fixture-commit",
        feature_definition_version="gamification-features-v2",
        manifest=manifest,
        seed=7,
        parameters=model.to_parameters(),
    )
    snapshot = FeatureBuilder().build(feature_input(distractor_misconception_code="m-a"))
    restored = BayesianMisconceptionModel.from_artifact(artifact)

    assert restored.predict(snapshot) == restored.predict(snapshot)
    assert restored.predict(snapshot) == model.predict(snapshot)
