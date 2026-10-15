from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Protocol

from app.gamification.modeling.misconception_inference.bayesian_model import (
    PROVISIONAL_ABSTAIN_THRESHOLD,
    PROVISIONAL_FACTOR_WEIGHTS,
    PROVISIONAL_STALENESS_THRESHOLD_MS,
    UNSEEN_EVIDENCE,
    attempt_band,
    response_time_band,
    support_need_band,
)
from app.gamification.modeling.misconception_inference.contracts import UNKNOWN_CODE
from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle


class LabelledRow(Protocol):
    learner_id: str
    label: str | None


class LikelihoodRow(LabelledRow, Protocol):
    features: Mapping[str, float | int | bool | str | None]


class TrainingManifest(Protocol):
    learner_splits: Mapping[str, tuple[str, ...]]

    @property
    def digest(self) -> str: ...

    @property
    def synthetic(self) -> bool: ...

    def assert_no_learner_leakage(self) -> None: ...


def train_frequency_candidate(
    rows: Sequence[LabelledRow],
    *,
    manifest: TrainingManifest,
    model_name: str,
    model_version: str,
    source_commit: str,
    feature_definition_version: str,
    seed: int,
) -> ModelArtifactBundle:
    """Create a reproducible baseline from only the manifest's training learners."""

    manifest.assert_no_learner_leakage()
    train_learners = set(manifest.learner_splits["train"])
    labels = [row.label for row in rows if row.learner_id in train_learners and row.label]
    if not labels:
        raise ValueError("training split contains no supplied labels")
    counts = {label: labels.count(label) for label in sorted(set(labels))}
    total = len(labels)
    return ModelArtifactBundle.create(
        model_name=model_name,
        model_version=model_version,
        source_commit=source_commit,
        feature_definition_version=feature_definition_version,
        manifest=manifest,
        seed=seed,
        parameters={"class_priors": {label: count / total for label, count in counts.items()}},
    )


# Provisional: a skill or code with fewer labelled rows than this borrows its family's counts.
SPARSE_OBSERVATION_THRESHOLD = 5
LAPLACE_ALPHA = 1.0


def train_likelihood_tables(
    rows: Sequence[LikelihoodRow],
    *,
    manifest: TrainingManifest,
    model_name: str,
    model_version: str,
    source_commit: str,
    feature_definition_version: str,
    seed: int,
    catalogue_version: str,
    skill_codes: Mapping[str, Sequence[str]] | None = None,
    skill_families: Mapping[str, str] | None = None,
    laplace_alpha: float = LAPLACE_ALPHA,
    sparse_observation_threshold: int = SPARSE_OBSERVATION_THRESHOLD,
) -> ModelArtifactBundle:
    """Estimate priors and likelihoods from the training split only.

    Counts are Laplace-smoothed. A skill with fewer than the provisional sparse threshold, and a
    code with fewer observations than that threshold, use the skill family's counts instead.
    """

    manifest.assert_no_learner_leakage()
    if laplace_alpha <= 0 or sparse_observation_threshold < 1:
        raise ValueError("smoothing strength and the sparse threshold must be positive")
    train_learners = set(manifest.learner_splits["train"])
    training = [
        row
        for row in rows
        if row.learner_id in train_learners and row.label and row.features.get("skill_id")
    ]
    if not training:
        raise ValueError("training split contains no labelled rows")
    codes_by_skill = _skill_codes(training, skill_codes)
    families: dict[str, str] = {}
    for row in training:
        skill = str(row.features["skill_id"])
        if skill not in families:
            families[skill] = (skill_families or {}).get(
                skill, str(row.features.get("skill_family") or skill)
            )
    grouped: dict[str, list[LikelihoodRow]] = defaultdict(list)
    for row in training:
        grouped[str(row.features["skill_id"])].append(row)
    family_rows: dict[str, list[LikelihoodRow]] = defaultdict(list)
    for skill, skill_rows in grouped.items():
        family_rows[families[skill]].extend(skill_rows)

    class_priors: dict[str, dict[str, float]] = {}
    option_likelihoods: dict[str, dict[str, dict[str, float]]] = {}
    error_likelihoods: dict[str, dict[str, dict[str, float]]] = {}
    attempt_likelihoods: dict[str, dict[str, dict[str, float]]] = {}
    response_time_likelihoods: dict[str, dict[str, dict[str, float]]] = {}
    support_need_likelihoods: dict[str, dict[str, dict[str, float]]] = {}
    class_prior_source: dict[str, str] = {}
    sparse_codes: dict[str, list[str]] = {}
    for skill in sorted(grouped):
        codes = codes_by_skill[skill]
        own = grouped[skill]
        pooled = family_rows[families[skill]]
        prior_rows = pooled if len(own) < sparse_observation_threshold else own
        class_prior_source[skill] = "skill_family" if prior_rows is pooled else "skill"
        class_priors[skill] = _class_prior(prior_rows, codes, laplace_alpha)
        borrowed = [
            code
            for code in codes
            if sum(row.label == code for row in own) < sparse_observation_threshold
        ]
        sparse_codes[skill] = borrowed
        option_likelihoods[skill] = _evidence_table(
            own, pooled, codes, borrowed, laplace_alpha, _option_key
        )
        error_likelihoods[skill] = _evidence_table(
            own, pooled, codes, borrowed, laplace_alpha, _error_key
        )
        attempt_likelihoods[skill] = _evidence_table(
            own, pooled, codes, borrowed, laplace_alpha, _attempt_key
        )
        response_time_likelihoods[skill] = _evidence_table(
            own, pooled, codes, borrowed, laplace_alpha, _time_key
        )
        support_need_likelihoods[skill] = _evidence_table(
            own, pooled, codes, borrowed, laplace_alpha, _support_key
        )
    return ModelArtifactBundle.create(
        model_name=model_name,
        model_version=model_version,
        source_commit=source_commit,
        feature_definition_version=feature_definition_version,
        manifest=manifest,
        seed=seed,
        parameters={
            "candidate": "bayesian",
            "catalogue_version": catalogue_version,
            "model_version": model_version,
            "table_version": "provisional-likelihood-tables-v1",
            "weights_status": "provisional_assumption",
            "abstain_threshold": PROVISIONAL_ABSTAIN_THRESHOLD,
            "abstain_threshold_status": "provisional_assumption",
            "staleness_threshold_ms": PROVISIONAL_STALENESS_THRESHOLD_MS,
            "staleness_threshold_status": "provisional_assumption",
            "band_cutoffs_status": "provisional_assumption",
            "factor_weights": dict(sorted(PROVISIONAL_FACTOR_WEIGHTS.items())),
            "smoothing": "laplace",
            "laplace_alpha": laplace_alpha,
            "laplace_status": "provisional_assumption",
            "sparse_observation_threshold": sparse_observation_threshold,
            "pooling_status": "provisional_assumption",
            "class_prior_source": class_prior_source,
            "sparse_codes": sparse_codes,
            "skill_codes": {skill: list(codes_by_skill[skill]) for skill in sorted(grouped)},
            "skill_families": dict(sorted(families.items())),
            "class_priors": class_priors,
            "option_likelihoods": option_likelihoods,
            "error_likelihoods": error_likelihoods,
            "attempt_likelihoods": attempt_likelihoods,
            "response_time_likelihoods": response_time_likelihoods,
            "support_need_likelihoods": support_need_likelihoods,
        },
    )


def _skill_codes(
    rows: Sequence[LikelihoodRow], supplied: Mapping[str, Sequence[str]] | None
) -> dict[str, tuple[str, ...]]:
    observed: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        observed[str(row.features["skill_id"])].add(str(row.label))
    if supplied is None:
        return {
            skill: tuple(sorted(labels | {UNKNOWN_CODE}))
            for skill, labels in sorted(observed.items())
        }
    resolved: dict[str, tuple[str, ...]] = {}
    for skill, labels in observed.items():
        allowed = set(supplied.get(skill, ())) | {UNKNOWN_CODE}
        unknown_labels = labels - allowed
        if unknown_labels:
            raise ValueError(
                f"{skill} has training labels outside its catalogue: {sorted(unknown_labels)}"
            )
        resolved[skill] = tuple(sorted(allowed))
    return resolved


def _class_prior(
    rows: Sequence[LikelihoodRow], codes: tuple[str, ...], alpha: float
) -> dict[str, float]:
    counts = {code: sum(row.label == code for row in rows) for code in codes}
    total = sum(counts.values()) + alpha * len(codes)
    return {code: (count + alpha) / total for code, count in counts.items()}


def _evidence_table(
    own: Sequence[LikelihoodRow],
    pooled: Sequence[LikelihoodRow],
    codes: tuple[str, ...],
    borrowed_codes: Sequence[str],
    alpha: float,
    key_of,
) -> dict[str, dict[str, float]]:
    evidence = sorted({key for row in pooled if (key := key_of(row))})
    if not evidence:
        return {}
    counts = {code: {value: 0 for value in evidence} for code in codes}
    for code in codes:
        source = pooled if code in borrowed_codes else own
        for row in source:
            key = key_of(row)
            if row.label == code and key in counts[code]:
                counts[code][key] += 1
    vocabulary = len(evidence) + 1
    table = {value: {} for value in (*evidence, UNSEEN_EVIDENCE)}
    for code in codes:
        code_total = sum(counts[code].values()) + alpha * vocabulary
        for value in evidence:
            table[value][code] = (counts[code][value] + alpha) / code_total
        table[UNSEEN_EVIDENCE][code] = alpha / code_total
    return table


def _option_key(row: LikelihoodRow) -> str | None:
    value = row.features.get("distractor_misconception_code") or row.features.get(
        "selected_option_id"
    )
    return str(value) if isinstance(value, str) and value else None


def _error_key(row: LikelihoodRow) -> str | None:
    value = row.features.get("structured_error_code")
    return str(value) if isinstance(value, str) and value else None


def _attempt_key(row: LikelihoodRow) -> str | None:
    count = row.features.get("attempt_count")
    return attempt_band(int(count)) if isinstance(count, int) and count >= 1 else None


def _time_key(row: LikelihoodRow) -> str | None:
    ratio = row.features.get("response_time_ratio")
    return response_time_band(float(ratio)) if isinstance(ratio, (int, float)) else None


def _support_key(row: LikelihoodRow) -> str | None:
    need = row.features.get("learner_support_need")
    return support_need_band(float(need)) if isinstance(need, (int, float)) else None
