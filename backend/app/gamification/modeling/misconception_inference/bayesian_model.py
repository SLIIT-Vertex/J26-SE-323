"""Expert-initialised Bayesian misconception update.

Likelihood weights, the abstention threshold, the staleness window, and the response-time and
attempt bands are provisional assumptions. Synthetic data can exercise this update; it is not an
empirical calibration of Grade 5 misconceptions.
"""

import math
from collections.abc import Mapping
from types import MappingProxyType

from app.gamification.application.records import FeatureSnapshotRecord
from app.gamification.modeling.misconception_inference.contracts import UNKNOWN_CODE
from app.gamification.modeling.misconception_inference.probabilistic_model import (
    build_distribution,
)
from app.gamification.modeling.shared.artifact_registry import ModelArtifactBundle
from app.gamification.modeling.shared.contracts import MisconceptionDistribution

BAYESIAN_MODEL_VERSION = "bayesian-misconception-v1"
LIKELIHOOD_TABLE_VERSION = "provisional-likelihood-tables-v1"
PROVISIONAL_ABSTAIN_THRESHOLD = 0.6
PROVISIONAL_STALENESS_THRESHOLD_MS = 7 * 24 * 60 * 60 * 1000
PROVISIONAL_FACTOR_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "option_evidence": 1.0,
        "structured_error": 1.0,
        "attempt_count": 0.25,
        "response_time_band": 0.25,
        "support_need": 0.25,
    }
)
UNSEEN_EVIDENCE = "__unseen__"
_CONTEXT_FIELDS = (
    ("prior_skill_accuracy", "PRIOR_SKILL_ACCURACY", "PRIOR_SKILL_ACCURACY_MISSING"),
    ("template_key", "TEMPLATE_PRESENT", "TEMPLATE_MISSING"),
    ("item_difficulty", "ITEM_DIFFICULTY_PRESENT", "ITEM_DIFFICULTY_MISSING"),
    ("previous_scaffold_types", "SCAFFOLD_HISTORY_PRESENT", "SCAFFOLD_HISTORY_MISSING"),
    ("previous_independence_gains", "INDEPENDENCE_HISTORY_PRESENT", "INDEPENDENCE_HISTORY_MISSING"),
    ("support_dependency_index", "SUPPORT_DEPENDENCY_PRESENT", "SUPPORT_DEPENDENCY_MISSING"),
)


def attempt_band(attempt_count: int) -> str:
    """Provisional attempt bands: one, two, or three-or-more."""

    if attempt_count <= 1:
        return "1"
    if attempt_count == 2:
        return "2"
    return "3_plus"


def response_time_band(ratio: float) -> str:
    """Provisional bands for response time divided by the item's expected time."""

    if ratio < 0.75:
        return "fast"
    if ratio <= 1.25:
        return "typical"
    return "slow"


def support_need_band(support_need: float) -> str:
    """Provisional split of the learner-state support-need score."""

    return "elevated" if support_need >= 0.5 else "low"


def _copy_table(table: Mapping[str, Mapping[str, float]] | None) -> dict[str, dict[str, float]]:
    return {evidence: dict(weights) for evidence, weights in (table or {}).items()}


def _softmax(log_probabilities: Mapping[str, float]) -> dict[str, float]:
    peak = max(log_probabilities.values())
    exponentials = {code: math.exp(value - peak) for code, value in log_probabilities.items()}
    total = sum(exponentials.values())
    return {code: value / total for code, value in exponentials.items()}


class BayesianMisconceptionModel:
    """Carry a learner-skill belief forward and multiply it by named likelihood factors."""

    def __init__(
        self,
        *,
        catalogue_version: str,
        skill_codes: Mapping[str, tuple[str, ...] | list[str]],
        class_priors: Mapping[str, Mapping[str, float]],
        option_likelihoods: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        error_likelihoods: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        attempt_likelihoods: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        response_time_likelihoods: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        support_need_likelihoods: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
        factor_weights: Mapping[str, float] | None = None,
        abstain_threshold: float = PROVISIONAL_ABSTAIN_THRESHOLD,
        staleness_threshold_ms: int = PROVISIONAL_STALENESS_THRESHOLD_MS,
        table_version: str = LIKELIHOOD_TABLE_VERSION,
        model_version: str = BAYESIAN_MODEL_VERSION,
    ) -> None:
        if not catalogue_version:
            raise ValueError("catalogue_version is required")
        if not 0 < abstain_threshold <= 1:
            raise ValueError("abstain_threshold must be in (0, 1]")
        if staleness_threshold_ms < 0:
            raise ValueError("staleness_threshold_ms must be non-negative")
        weights = dict(PROVISIONAL_FACTOR_WEIGHTS if factor_weights is None else factor_weights)
        if any(weight < 0 for weight in weights.values()):
            raise ValueError("factor weights must be non-negative")
        self.catalogue_version = catalogue_version
        self.model_version = model_version
        self.table_version = table_version
        self.abstain_threshold = abstain_threshold
        self.staleness_threshold_ms = staleness_threshold_ms
        self.factor_weights = weights
        self.skill_codes = {
            skill: tuple(dict.fromkeys((*codes, UNKNOWN_CODE)))
            for skill, codes in skill_codes.items()
        }
        self.class_priors = {skill: dict(prior) for skill, prior in class_priors.items()}
        self.option_likelihoods = {
            skill: _copy_table(table) for skill, table in (option_likelihoods or {}).items()
        }
        self.error_likelihoods = {
            skill: _copy_table(table) for skill, table in (error_likelihoods or {}).items()
        }
        self.attempt_likelihoods = {
            skill: _copy_table(table) for skill, table in (attempt_likelihoods or {}).items()
        }
        self.response_time_likelihoods = {
            skill: _copy_table(table) for skill, table in (response_time_likelihoods or {}).items()
        }
        self.support_need_likelihoods = {
            skill: _copy_table(table) for skill, table in (support_need_likelihoods or {}).items()
        }
        for skill, codes in self.skill_codes.items():
            prior = self.class_priors.get(skill)
            if prior is None or any(prior.get(code, 0.0) <= 0 for code in codes):
                raise ValueError(f"{skill} needs a positive class prior for every code")

    def predict(self, snapshot: FeatureSnapshotRecord) -> MisconceptionDistribution:
        reasons: list[str] = ["PROVISIONAL_WEIGHTS"]
        if snapshot.values.get("misconception_catalogue_version") != self.catalogue_version:
            return self._fallback("CATALOGUE_VERSION_MISMATCH")
        skill_id = str(snapshot.values.get("skill_id") or snapshot.skill_id)
        codes = self.skill_codes.get(skill_id)
        if codes is None:
            return self._fallback("SPARSE_OR_UNSEEN_SKILL")
        prior, prior_reason = self._prior(snapshot, skill_id, codes)
        reasons.append(prior_reason)
        log_probabilities = {code: math.log(prior[code]) for code in codes}
        for name, table, evidence in self._factor_evidence(snapshot, skill_id):
            self._apply_factor(name, table, evidence, codes, log_probabilities, reasons)
        for present, missing in (
            self._context_reason(snapshot, field, present_code, missing_code)
            for field, present_code, missing_code in _CONTEXT_FIELDS
        ):
            reasons.append(present or missing)
        return build_distribution(
            _softmax(log_probabilities),
            model_version=self.model_version,
            catalogue_version=self.catalogue_version,
            abstain_threshold=self.abstain_threshold,
            reasons=tuple(reasons),
        )

    def to_parameters(self) -> dict[str, object]:
        return {
            "candidate": "bayesian",
            "catalogue_version": self.catalogue_version,
            "model_version": self.model_version,
            "table_version": self.table_version,
            "weights_status": "provisional_assumption",
            "abstain_threshold": self.abstain_threshold,
            "abstain_threshold_status": "provisional_assumption",
            "staleness_threshold_ms": self.staleness_threshold_ms,
            "staleness_threshold_status": "provisional_assumption",
            "band_cutoffs_status": "provisional_assumption",
            "factor_weights": dict(sorted(self.factor_weights.items())),
            "skill_codes": {
                skill: list(codes) for skill, codes in sorted(self.skill_codes.items())
            },
            "class_priors": self.class_priors,
            "option_likelihoods": self.option_likelihoods,
            "error_likelihoods": self.error_likelihoods,
            "attempt_likelihoods": self.attempt_likelihoods,
            "response_time_likelihoods": self.response_time_likelihoods,
            "support_need_likelihoods": self.support_need_likelihoods,
        }

    @classmethod
    def from_artifact(cls, artifact: ModelArtifactBundle) -> "BayesianMisconceptionModel":
        artifact.verify()
        parameters = artifact.parameters
        if parameters.get("candidate") not in (None, "bayesian"):
            raise ValueError("artifact is not a Bayesian misconception candidate")
        catalogue_version = parameters.get("catalogue_version")
        skill_codes = parameters.get("skill_codes")
        class_priors = parameters.get("class_priors")
        if not isinstance(catalogue_version, str) or not isinstance(skill_codes, Mapping):
            raise TypeError("Bayesian artifact requires a catalogue version and skill codes")
        if not isinstance(class_priors, Mapping):
            raise TypeError("Bayesian artifact requires class priors")
        return cls(
            catalogue_version=catalogue_version,
            skill_codes=skill_codes,
            class_priors=class_priors,
            option_likelihoods=_mapping(parameters.get("option_likelihoods")),
            error_likelihoods=_mapping(parameters.get("error_likelihoods")),
            attempt_likelihoods=_mapping(parameters.get("attempt_likelihoods")),
            response_time_likelihoods=_mapping(parameters.get("response_time_likelihoods")),
            support_need_likelihoods=_mapping(parameters.get("support_need_likelihoods")),
            factor_weights=_flat_mapping(parameters.get("factor_weights")),
            abstain_threshold=float(
                parameters.get("abstain_threshold", PROVISIONAL_ABSTAIN_THRESHOLD)
            ),
            staleness_threshold_ms=int(
                parameters.get("staleness_threshold_ms", PROVISIONAL_STALENESS_THRESHOLD_MS)
            ),
            table_version=str(parameters.get("table_version", LIKELIHOOD_TABLE_VERSION)),
            model_version=str(parameters.get("model_version", artifact.model_version)),
        )

    def _fallback(self, reason: str) -> MisconceptionDistribution:
        return build_distribution(
            {UNKNOWN_CODE: 1.0},
            model_version=self.model_version,
            catalogue_version=self.catalogue_version,
            abstain_threshold=self.abstain_threshold,
            reasons=("PROVISIONAL_WEIGHTS", reason),
        )

    def _prior(
        self, snapshot: FeatureSnapshotRecord, skill_id: str, codes: tuple[str, ...]
    ) -> tuple[dict[str, float], str]:
        catalogue = self._catalogue_prior(skill_id, codes)
        beliefs = {
            key.removeprefix("prior_belief:"): float(value)
            for key, value in snapshot.values.items()
            if key.startswith("prior_belief:") and isinstance(value, (int, float))
        }
        if not beliefs:
            return (
                catalogue,
                "CATALOGUE_PRIOR" if skill_id in self.class_priors else "UNIFORM_PRIOR",
            )
        age_missing = snapshot.missingness.get("prior_belief_age_ms", True)
        age = snapshot.values.get("prior_belief_age_ms")
        if age_missing or not isinstance(age, (int, float)):
            return catalogue, "PRIOR_TIMESTAMP_MISSING"
        if age > self.staleness_threshold_ms:
            return catalogue, "STALE_PRIOR"
        usable = {code: beliefs[code] for code in codes if beliefs.get(code, 0) > 0}
        if not usable:
            return catalogue, "PRIOR_CODES_UNUSABLE"
        floor = min(usable.values()) * 1e-6
        filled = {code: usable.get(code, floor) for code in codes}
        total = sum(filled.values())
        return {code: value / total for code, value in filled.items()}, "PRIOR_CARRIED_OVER"

    def _catalogue_prior(self, skill_id: str, codes: tuple[str, ...]) -> dict[str, float]:
        supplied = self.class_priors.get(skill_id, {})
        if not supplied:
            share = 1 / len(codes)
            return dict.fromkeys(codes, share)
        total = sum(supplied.get(code, 0.0) for code in codes)
        return {code: supplied.get(code, 0.0) / total for code in codes}

    def _factor_evidence(
        self, snapshot: FeatureSnapshotRecord, skill_id: str
    ) -> tuple[tuple[str, Mapping[str, Mapping[str, float]], str | None], ...]:
        return (
            (
                "option_evidence",
                self.option_likelihoods.get(skill_id, {}),
                _option_evidence(snapshot),
            ),
            (
                "structured_error",
                self.error_likelihoods.get(skill_id, {}),
                _present(snapshot, "structured_error_code"),
            ),
            (
                "attempt_count",
                self.attempt_likelihoods.get(skill_id, {}),
                _attempt_evidence(snapshot),
            ),
            (
                "response_time_band",
                self.response_time_likelihoods.get(skill_id, {}),
                _time_evidence(snapshot),
            ),
            (
                "support_need",
                self.support_need_likelihoods.get(skill_id, {}),
                _support_evidence(snapshot),
            ),
        )

    def _apply_factor(
        self,
        name: str,
        table: Mapping[str, Mapping[str, float]],
        evidence: str | None,
        codes: tuple[str, ...],
        log_probabilities: dict[str, float],
        reasons: list[str],
    ) -> None:
        weight = self.factor_weights.get(name, 0.0)
        if weight == 0:
            return
        if evidence is None:
            reasons.append(f"{name.upper()}_MISSING")
            return
        row = table.get(evidence)
        fired = evidence
        if row is None and UNSEEN_EVIDENCE in table:
            row = table[UNSEEN_EVIDENCE]
            fired = UNSEEN_EVIDENCE
        if not row:
            reasons.append(f"{name.upper()}_UNSEEN")
            return
        fallback = sum(row.values()) / len(row)
        for code in codes:
            likelihood = row.get(code, fallback)
            if likelihood <= 0:
                raise ValueError(f"{name} likelihood for {code} must be positive")
            log_probabilities[code] += weight * math.log(likelihood)
        reasons.append(
            f"{name.upper()}_UNSEEN" if fired == UNSEEN_EVIDENCE else f"{name.upper()}_MATCHED"
        )

    def _context_reason(
        self, snapshot: FeatureSnapshotRecord, field: str, present: str, missing: str
    ) -> tuple[str, str]:
        absent = snapshot.missingness.get(field, field not in snapshot.values)
        return ("", missing) if absent else (present, "")


def _mapping(value: object) -> Mapping[str, Mapping[str, Mapping[str, float]]]:
    return value if isinstance(value, Mapping) else {}


def _flat_mapping(value: object) -> Mapping[str, float] | None:
    return value if isinstance(value, Mapping) else None


def _flagged_missing(snapshot: FeatureSnapshotRecord, field: str) -> bool:
    """A missingness flag wins. A version-1 snapshot with no flag still exposes a present value."""

    return bool(snapshot.missingness.get(field, False))


def _present(snapshot: FeatureSnapshotRecord, field: str) -> str | None:
    if _flagged_missing(snapshot, field):
        return None
    value = snapshot.values.get(field)
    return str(value) if isinstance(value, str) and value else None


def _option_evidence(snapshot: FeatureSnapshotRecord) -> str | None:
    return _present(snapshot, "distractor_misconception_code") or _present(
        snapshot, "selected_option_id"
    )


def _attempt_evidence(snapshot: FeatureSnapshotRecord) -> str | None:
    count = snapshot.values.get("attempt_count")
    if not isinstance(count, int):
        return None
    return attempt_band(count)


def _time_evidence(snapshot: FeatureSnapshotRecord) -> str | None:
    if _flagged_missing(snapshot, "response_time_ratio"):
        return None
    ratio = snapshot.values.get("response_time_ratio")
    return response_time_band(float(ratio)) if isinstance(ratio, (int, float)) else None


def _support_evidence(snapshot: FeatureSnapshotRecord) -> str | None:
    if _flagged_missing(snapshot, "learner_support_need"):
        return None
    need = snapshot.values.get("learner_support_need")
    return support_need_band(float(need)) if isinstance(need, (int, float)) else None
