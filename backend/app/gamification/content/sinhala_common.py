"""Pieces shared by the Sinhala game packages: opaque ids, Model 1 and Model 2 references.

Each package owns its source, items, rubric and copy. What is identical across packages, and
must stay identical so the research can compare them, lives here.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from collections.abc import Iterable, Mapping

UNKNOWN = "unknown_or_other"
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")
DONE_LINE = "දැන් ඔයාම කරලා බලන්න! 💪"
UNKNOWN_CODE_MAPPING = {
    "mapping_version": "g5-sin-unknown-reconciliation-v1",
    "package_code": UNKNOWN,
    "shared_code": "unknown_or_other",
}
_MOTOR_CORRECTIONS = 3
_MOTOR_CANCELS = 2


class SinhalaResponseError(ValueError):
    """A response the server refuses to score. ``code`` is machine-readable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def digest(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def token(prefix: str, value: object, salt: str) -> str:
    """An opaque presentation-local id: it never encodes position or correctness."""

    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def infer_belief(
    error_code: str,
    hypotheses: Iterable[str],
    *,
    catalogue_version: str,
    sparse: bool = False,
    interaction_summary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """A full normalized distribution with a safe unknown fallback.

    Motor difficulty, a reported rendering problem or sparse evidence are not linguistic
    evidence: they move mass to ``unknown_or_other`` and are recorded as flags. Reading time
    and selection counts never raise a hypothesis on their own.
    """

    summary = interaction_summary or {}
    codes = tuple(hypotheses)
    motor = (
        int(summary.get("correction_count", 0) or 0) >= _MOTOR_CORRECTIONS
        or int(summary.get("cancelled_drag_count", 0) or 0) >= _MOTOR_CANCELS
    )
    rendering = bool(summary.get("rendering_issue_reported", False))
    primary = error_code if error_code in codes else UNKNOWN
    weights = dict.fromkeys(codes, 1.0)
    if sparse or rendering:
        weights[UNKNOWN] = 8.0
    elif primary != UNKNOWN:
        weights[primary] = 3.0 if motor else 9.0
        weights[UNKNOWN] = 3.0 if motor else 1.5
    else:
        weights[UNKNOWN] = 6.0
    total = sum(weights.values())
    probabilities = {code: weight / total for code, weight in weights.items()}
    top = max(probabilities, key=probabilities.__getitem__)
    confidence = probabilities[top]
    return {
        "probabilities": probabilities,
        "unknown_probability": probabilities[UNKNOWN],
        "top_hypothesis": top,
        "confidence": confidence,
        "entropy": -sum(p * math.log(p) for p in probabilities.values() if p > 0),
        "abstained": top == UNKNOWN,
        "low_confidence": sparse or rendering or motor or confidence < 0.5,
        "motor_difficulty_suspected": motor,
        "rendering_failure_suspected": rendering,
        "evidence_window": "unsupported_before_only",
        "unknown_code_mapping": dict(UNKNOWN_CODE_MAPPING),
        "catalogue_version": catalogue_version,
    }


def scaffold_decision(
    skill_id: str,
    condition: str,
    belief: Mapping[str, object],
    *,
    seed: int,
    policy_version: str,
    affinity: Mapping[str, set[str]],
) -> dict[str, object]:
    """Predicted raw IG and uncertainty for every candidate; selection is fixed in baseline."""

    top = str(belief.get("top_hypothesis"))
    abstained = bool(belief.get("abstained"))
    candidates = [
        {
            "scaffold_type": scaffold,
            "eligible": True,
            "exclusion_reasons": [],
            "predicted_raw_ig": round(0.06 + (0.08 if top in affinity.get(scaffold, set()) else 0.0), 6),
            "uncertainty": 0.2 if abstained else 0.1,
            "propensity": 1.0 if condition == "baseline" and scaffold == "visual_guidance" else None,
        }
        for scaffold in SCAFFOLDS
    ]
    if condition == "baseline":
        selected, mode = "visual_guidance", "deterministic_baseline"
    elif abstained:
        selected, mode = "visual_guidance", "proposed_shadow_conservative_fallback"
    else:
        selected = str(max(candidates, key=lambda c: float(c["predicted_raw_ig"]))["scaffold_type"])
        mode = "proposed_shadow"
    return {
        "policy_version": policy_version,
        "skill_id": skill_id,
        "condition": condition,
        "mode": mode,
        "objective": "predicted_raw_independence_gain",
        "uses_complete_model1_distribution": condition != "baseline",
        "seed": seed,
        "exploration": None,
        "selected_action": selected,
        "candidates": candidates,
    }
