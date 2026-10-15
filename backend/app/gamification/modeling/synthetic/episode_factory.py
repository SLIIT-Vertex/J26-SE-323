from dataclasses import dataclass
from random import Random

GENERATOR_VERSION = "synthetic-hidden-misconception-v1"
SYNTHETIC_SKILL_CODES = {
    "synthetic-skill-a": ("syn-m1", "syn-m2", "syn-m3"),
    "synthetic-skill-b": ("syn-m4", "syn-m5", "syn-m6"),
}
_TIME_MEANS = (0.5, 1.0, 1.6)
_ATTEMPT_RANGES = ((1, 1), (1, 2), (2, 4))


@dataclass(frozen=True, slots=True)
class SyntheticEpisode:
    synthetic: bool
    learner_id: str
    episode_id: str
    baseline_score: float
    verification_score: float
    structured_error_code: str | None
    learner_state_available: bool
    support_delivered: bool
    verification_valid: bool
    evidence_count: int


def generate_synthetic_episodes(*, seed: int) -> tuple[SyntheticEpisode, ...]:
    """Generate deterministic engineering cases explicitly marked as synthetic."""

    rng = Random(seed)
    cases = (
        ("success", 0.0, 1.0, "error-a", True, True, True, 30),
        ("failure", 0.5, 0.0, "error-b", True, True, True, 30),
        ("missing-data", 0.0, 0.5, None, False, True, True, 30),
        ("invalid-verification", 0.0, 1.0, "error-a", True, True, False, 30),
        ("cold-start", 0.0, 0.5, "error-a", True, True, True, 0),
    )
    return tuple(
        SyntheticEpisode(
            synthetic=True,
            learner_id=f"synthetic-learner-{index}",
            episode_id=f"synthetic-{name}-{rng.randrange(1_000_000):06d}",
            baseline_score=baseline,
            verification_score=verification,
            structured_error_code=error,
            learner_state_available=state,
            support_delivered=delivered,
            verification_valid=valid,
            evidence_count=count,
        )
        for index, (
            name,
            baseline,
            verification,
            error,
            state,
            delivered,
            valid,
            count,
        ) in enumerate(cases, start=1)
    )


@dataclass(frozen=True, slots=True)
class SyntheticMisconceptionObservation:
    """One synthetic observation drawn from a hidden misconception. Not learner evidence."""

    synthetic: bool
    generator_version: str
    seed: int
    learner_id: str
    skill_id: str
    skill_family: str
    hidden_misconception: str
    evidence_index: int
    selected_option_id: str
    structured_error_code: str
    distractor_misconception_code: str
    response_time_ratio: float
    attempt_count: int
    catalogue_version: str


def generate_hidden_misconception_observations(
    *,
    seed: int,
    learner_count: int = 40,
    evidence_count: int = 8,
    catalogue_version: str = "synthetic-misconceptions-v1",
    match_probability: float = 0.8,
) -> tuple[SyntheticMisconceptionObservation, ...]:
    """Sample option choices, response times, and attempts from a hidden misconception.

    With `match_probability` the chosen option and error code name the hidden misconception;
    otherwise they name one of the other codes for that skill. Response-time means and attempt
    ranges differ by code. Every record is synthetic.
    """

    if learner_count < 1 or evidence_count < 1:
        raise ValueError("learner_count and evidence_count must be positive")
    if not 0 < match_probability < 1:
        raise ValueError("match_probability must be between zero and one")
    rng = Random(seed)
    skills = tuple(SYNTHETIC_SKILL_CODES)
    observations: list[SyntheticMisconceptionObservation] = []
    for learner_index in range(learner_count):
        skill_id = skills[learner_index % len(skills)]
        codes = SYNTHETIC_SKILL_CODES[skill_id]
        hidden = codes[rng.randrange(len(codes))]
        for evidence_index in range(1, evidence_count + 1):
            if rng.random() < match_probability:
                chosen = hidden
            else:
                alternatives = [code for code in codes if code != hidden]
                chosen = alternatives[rng.randrange(len(alternatives))]
            code_index = codes.index(chosen)
            low, high = _ATTEMPT_RANGES[code_index]
            ratio = max(0.05, _TIME_MEANS[code_index] + (rng.random() - 0.5) * 0.2)
            observations.append(
                SyntheticMisconceptionObservation(
                    synthetic=True,
                    generator_version=GENERATOR_VERSION,
                    seed=seed,
                    learner_id=f"synthetic-hidden-{seed}-{learner_index}",
                    skill_id=skill_id,
                    skill_family="synthetic-family",
                    hidden_misconception=hidden,
                    evidence_index=evidence_index,
                    selected_option_id=f"{chosen}-option",
                    structured_error_code=f"{chosen}-error",
                    distractor_misconception_code=chosen,
                    response_time_ratio=ratio,
                    attempt_count=rng.randint(low, high),
                    catalogue_version=catalogue_version,
                )
            )
    return tuple(observations)
