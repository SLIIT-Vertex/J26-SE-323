from app.gamification.domain.types import SkillId
from app.gamification.modeling.misconception_inference import BayesianMisconceptionModel
from app.gamification.modeling.misconception_inference.contracts import UNKNOWN_CODE
from app.gamification.modeling.shared import FeatureBuilder
from app.gamification.modeling.synthetic import (
    SYNTHETIC_SKILL_CODES,
    generate_hidden_misconception_observations,
    generate_synthetic_episodes,
)
from tests.gamification.modeling.fixtures import feature_input


def test_synthetic_generator_is_seeded_and_covers_required_cases() -> None:
    first = generate_synthetic_episodes(seed=5)
    assert first == generate_synthetic_episodes(seed=5)
    assert all(episode.synthetic for episode in first)
    assert any(not episode.learner_state_available for episode in first)
    assert any(not episode.verification_valid for episode in first)
    assert any(episode.evidence_count == 0 for episode in first)


def _recovery_model() -> BayesianMisconceptionModel:
    skill_codes = {skill: (*codes, UNKNOWN_CODE) for skill, codes in SYNTHETIC_SKILL_CODES.items()}
    option_likelihoods = {}
    class_priors = {}
    for skill, codes in skill_codes.items():
        class_priors[skill] = {code: 0.3 if code != UNKNOWN_CODE else 0.1 for code in codes}
        option_likelihoods[skill] = {
            evidence: {code: 0.8 if code == evidence else 0.1 for code in codes}
            for evidence in codes
            if evidence != UNKNOWN_CODE
        }
    return BayesianMisconceptionModel(
        catalogue_version="synthetic-misconceptions-v1",
        skill_codes=skill_codes,
        class_priors=class_priors,
        option_likelihoods=option_likelihoods,
        factor_weights={
            "option_evidence": 1.0,
            "structured_error": 0.0,
            "attempt_count": 0.0,
            "response_time_band": 0.0,
            "support_need": 0.0,
        },
    )


def test_hidden_misconception_generator_is_synthetic_and_recoverable() -> None:
    first = generate_hidden_misconception_observations(seed=11, learner_count=4, evidence_count=2)
    assert first == generate_hidden_misconception_observations(
        seed=11, learner_count=4, evidence_count=2
    )
    assert all(observation.synthetic for observation in first)
    assert all(observation.learner_id.startswith("synthetic-hidden-") for observation in first)
    assert {observation.generator_version for observation in first} == {
        "synthetic-hidden-misconception-v1"
    }

    model = _recovery_model()
    builder = FeatureBuilder()
    mean_recall: list[float] = []
    for evidence_count in (1, 2, 4, 8):
        hits = 0
        total = 0
        for seed in range(1, 6):
            observations = generate_hidden_misconception_observations(
                seed=seed, learner_count=40, evidence_count=evidence_count
            )
            by_learner: dict[str, list] = {}
            for observation in observations:
                by_learner.setdefault(observation.learner_id, []).append(observation)
            for rows in by_learner.values():
                belief = None
                for observation in rows:
                    snapshot = builder.build(
                        feature_input(
                            skill_id=SkillId(observation.skill_id),
                            misconception_catalogue_version=observation.catalogue_version,
                            attempt_count=observation.attempt_count,
                            structured_error_code=None,
                            distractor_misconception_code=observation.distractor_misconception_code,
                            response_time_ratio=observation.response_time_ratio,
                            prior_beliefs=belief,
                            prior_belief_age_ms=0 if belief is not None else None,
                        )
                    )
                    belief = model.predict(snapshot).probabilities
                predicted = max(belief, key=belief.__getitem__)
                hits += predicted == rows[0].hidden_misconception
                total += 1
        mean_recall.append(hits / total)

    assert mean_recall == sorted(mean_recall)
    assert mean_recall[-1] > mean_recall[0]
