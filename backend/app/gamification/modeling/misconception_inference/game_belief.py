"""How the games read evidence for the Bayesian misconception model.

The games observe an answer's error code, its response time and a short interaction summary. The
expert data turns those into an evidence band, may re-code an unexplained answer from interaction
counts, counts the learner's last unaided answers on the skill as a prior, and says when a reading
is too uncertain to name a reason. Every setting is a provisional expert assumption taken from the
rule-based games, not learned from children.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

UNAIDED_ROLES = frozenset({"unsupported_before", "unsupported_after"})
_SIGNAL_KINDS = frozenset({"missing", "empty", "any", "equals"})
_REWRITE_CONDITIONS = frozenset({"equals", "at_least"})


def learner_answer_window(history: Iterable[Mapping[str, object]], *, size: int) -> tuple[str, ...]:
    """The learner's last ``size`` completed, unaided answers on the skill, oldest first.

    The caller owns the scope (this learner, this skill) and the order. Supported answers never
    count. A correct answer keeps its place as an empty string, so it pushes older mistakes out of
    the window without counting as one.
    """

    answers: list[str] = []
    for episode in history:
        for attempt in episode.get("attempts") or []:  # type: ignore[union-attr]
            if (
                attempt.get("role") in UNAIDED_ROLES
                and attempt.get("assistance_state", "none") == "none"
            ):
                answers.append(
                    "" if attempt.get("correct") else str(attempt.get("structured_error_code"))
                )
    return tuple(answers[-size:]) if size > 0 else ()


def _matches(value: object, expected: object) -> bool:
    return value is expected if isinstance(expected, bool) else value == expected


@dataclass(frozen=True)
class GameBeliefSettings:
    """One game area's evidence reading, uncertainty rule and learner prior, from expert data."""

    area_id: str
    subject: str
    band_rule: str
    band_rules: Mapping[str, tuple[Mapping[str, object], ...]]
    signals: Mapping[str, Mapping[str, object]]
    default_band: str
    weak_bands: frozenset[str]
    interaction_rewrites: tuple[Mapping[str, object], ...]
    unknown_code: str
    unknown_top_is_uncertain: bool
    top_probability_below: float
    top_two_margin_below: float
    prior_window: int
    prior_pseudocount: int
    reason_families: Mapping[str, str]
    missing_label_family: str
    data_version: str
    evidence_status: str
    file_sha256: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.band_rule not in self.band_rules:
            raise ValueError(f"{self.area_id} names an unknown evidence band rule")
        for name, spec in self.signals.items():
            kinds = set(spec) & _SIGNAL_KINDS
            if len(kinds) != 1 or (kinds <= {"missing", "empty"} and "field" not in spec):
                raise ValueError(f"signal {name} is not understood")
        for rule in self.band_rules.values():
            for entry in rule:
                unknown = set(entry["when_all"]) - set(self.signals)  # type: ignore[arg-type]
                if unknown:
                    raise ValueError(f"band rule uses unknown signals {sorted(unknown)}")
        if any(r["condition"] not in _REWRITE_CONDITIONS for r in self.interaction_rewrites):
            raise ValueError(f"{self.area_id} has an interaction rewrite that is not understood")
        if self.prior_window < 0 or self.prior_pseudocount <= 0:
            raise ValueError(
                "the learner prior needs a window of at least 0 and a positive pseudocount"
            )

    @classmethod
    def from_expert_data(
        cls,
        table: Mapping[str, object],
        settings: Mapping[str, object],
        families: Mapping[str, object],
        *,
        file_sha256: Mapping[str, str],
    ) -> GameBeliefSettings:
        subject = str(table["subject"])
        labels = families["subjects"][subject]  # type: ignore[index]
        rule = settings["uncertainty_rule"]
        prior = settings["learner_prior"]
        return cls(
            area_id=str(table["area_id"]),
            subject=subject,
            band_rule=str(table["evidence_band_rule"]),
            band_rules={
                name: tuple(entries)  # type: ignore[arg-type]
                for name, entries in settings["band_rules"].items()  # type: ignore[union-attr]
            },
            signals=settings["signals"],  # type: ignore[arg-type]
            default_band=str(settings["default_band"]),
            weak_bands=frozenset(settings["weak_bands"]),  # type: ignore[arg-type]
            interaction_rewrites=tuple(table["interaction_rewrites"]),  # type: ignore[arg-type]
            unknown_code=str(rule["unknown_code"]),  # type: ignore[index]
            unknown_top_is_uncertain=bool(table["unknown_top_is_uncertain"]),
            top_probability_below=float(rule["top_probability_below"]),  # type: ignore[index]
            top_two_margin_below=float(rule["top_two_margin_below"]),  # type: ignore[index]
            prior_window=int(prior["window"]),  # type: ignore[index]
            prior_pseudocount=int(prior["pseudocount"]),  # type: ignore[index]
            reason_families={
                code: str(labels["labels"][code]["reason_family"])
                for code in table["codes"]  # type: ignore[union-attr]
            },
            missing_label_family=str(labels["missing_label"]["reason_family"]),
            data_version=str(settings["package_version"]),
            evidence_status=str(settings["evidence_status"]),
            file_sha256=dict(file_sha256),
        )

    def signal(
        self, name: str, response_time_ms: int | None, summary: Mapping[str, object]
    ) -> bool:
        spec = self.signals[name]
        observed: Mapping[str, object] = {
            "response_time_ms": response_time_ms,
            "interaction_summary": summary,
        }
        if spec.get("missing"):
            return observed.get(str(spec["field"])) is None
        if spec.get("empty"):
            return not observed.get(str(spec["field"]))
        if "any" in spec:
            limits: Mapping[str, int] = spec["any"]  # type: ignore[assignment]
            return any(int(summary.get(field, 0) or 0) >= limit for field, limit in limits.items())  # type: ignore[call-overload]
        expected: Mapping[str, object] = spec["equals"]  # type: ignore[assignment]
        return all(_matches(summary.get(field), value) for field, value in expected.items())

    def evidence_band(self, response_time_ms: int | None, summary: Mapping[str, object]) -> str:
        """The first band of this area's rule whose signals all fire, else the default band."""

        for entry in self.band_rules[self.band_rule]:
            if all(self.signal(str(name), response_time_ms, summary) for name in entry["when_all"]):  # type: ignore[union-attr]
                return str(entry["band"])
        return self.default_band

    def interpret_error_code(
        self, error_code: str, summary: Mapping[str, object]
    ) -> tuple[str, Mapping[str, object] | None]:
        """Re-code an unexplained answer from interaction counts; the first matching rewrite wins."""

        if error_code != self.unknown_code or not summary:
            return error_code, None
        for rewrite in self.interaction_rewrites:
            value = summary.get(str(rewrite["field"]))
            expected = rewrite["value"]
            if rewrite["condition"] == "equals":
                fired = _matches(value, expected)
            else:
                fired = type(value) is int and value >= expected  # type: ignore[operator]
            if fired:
                return str(rewrite["error_code"]), rewrite
        return error_code, None

    def uncertain_because(
        self, probabilities: Mapping[str, float], top: str, band: str
    ) -> tuple[bool, tuple[str, ...]]:
        """Whether the top two probabilities make a low-confidence reading, and every cause."""

        ordered = sorted(probabilities, key=probabilities.get, reverse=True)  # type: ignore[arg-type]
        confidence = probabilities[ordered[0]]
        low = confidence < self.top_probability_below or (
            len(ordered) > 1 and confidence - probabilities[ordered[1]] < self.top_two_margin_below
        )
        causes = []
        if low:
            causes.append("low_confidence_rule")
        if band in self.weak_bands:
            causes.append("weak_evidence")
        if self.unknown_top_is_uncertain and top == self.unknown_code:
            causes.append("unknown_top")
        return low, tuple(causes)

    def reason_family(self, label: str | None) -> str:
        return self.reason_families.get(label or "", self.missing_label_family)

    def to_parameters(self) -> dict[str, object]:
        return {
            "area_id": self.area_id,
            "subject": self.subject,
            "band_rule": self.band_rule,
            "band_rules": {name: list(entries) for name, entries in self.band_rules.items()},
            "signals": dict(self.signals),
            "default_band": self.default_band,
            "weak_bands": sorted(self.weak_bands),
            "interaction_rewrites": list(self.interaction_rewrites),
            "uncertainty_rule": {
                "top_probability_below": self.top_probability_below,
                "top_two_margin_below": self.top_two_margin_below,
                "weak_band": True,
                "unknown_top": self.unknown_top_is_uncertain,
                "unknown_code": self.unknown_code,
                "abstain_threshold_used": False,
            },
            "learner_prior": {"window": self.prior_window, "pseudocount": self.prior_pseudocount},
            "reason_families": dict(self.reason_families),
            "missing_label_family": self.missing_label_family,
            "data_version": self.data_version,
            "evidence_status": self.evidence_status,
            "file_sha256": dict(self.file_sha256),
        }

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, object]) -> GameBeliefSettings:
        rule = parameters["uncertainty_rule"]
        prior = parameters["learner_prior"]
        return cls(
            area_id=str(parameters["area_id"]),
            subject=str(parameters["subject"]),
            band_rule=str(parameters["band_rule"]),
            band_rules={
                name: tuple(entries)  # type: ignore[arg-type]
                for name, entries in parameters["band_rules"].items()  # type: ignore[union-attr]
            },
            signals=MappingProxyType(dict(parameters["signals"])),  # type: ignore[call-overload]
            default_band=str(parameters["default_band"]),
            weak_bands=frozenset(parameters["weak_bands"]),  # type: ignore[arg-type]
            interaction_rewrites=tuple(parameters["interaction_rewrites"]),  # type: ignore[arg-type]
            unknown_code=str(rule["unknown_code"]),  # type: ignore[index]
            unknown_top_is_uncertain=bool(rule["unknown_top"]),  # type: ignore[index]
            top_probability_below=float(rule["top_probability_below"]),  # type: ignore[index]
            top_two_margin_below=float(rule["top_two_margin_below"]),  # type: ignore[index]
            prior_window=int(prior["window"]),  # type: ignore[index]
            prior_pseudocount=int(prior["pseudocount"]),  # type: ignore[index]
            reason_families=dict(parameters["reason_families"]),  # type: ignore[call-overload]
            missing_label_family=str(parameters["missing_label_family"]),
            data_version=str(parameters["data_version"]),
            evidence_status=str(parameters["evidence_status"]),
            file_sha256=dict(parameters["file_sha256"]),  # type: ignore[call-overload]
        )
