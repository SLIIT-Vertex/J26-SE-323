"""Fit a decision policy on development data under a zero-observed-false-confirmation target.

Selection rule (fixed before any benchmark run):
1. Keep only policies with zero false confident matches on the development cases supplied.
2. Maximize correct confirmed matches.
3. Break ties toward the most conservative policy (largest margin, then largest match score).
4. Then choose the candidate (clarification) threshold that maximizes development status
   accuracy, breaking ties toward the larger threshold.
Zero observed errors on development data is a target, not a guarantee for unseen inputs.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.adaptive_tutor.application.skill_mapper import _looks_learning_related
from app.adaptive_tutor.application.skill_mapper_contracts import SkillMappingRequest
from app.adaptive_tutor.domain import LearningIntent
from tools.skill_mapper_benchmark.evidence import contradicts_evidence
from tools.skill_mapper_benchmark.mappers import DecisionPolicy, ScoredCase


@dataclass(frozen=True, slots=True)
class LabelledScore:
    gold_status: str
    gold_skill_id: str | None
    scored: ScoredCase
    learning_related: bool


def labelled(
    request: SkillMappingRequest, gold_status: str, gold_skill_id: str | None, scored: ScoredCase
) -> LabelledScore:
    return LabelledScore(
        gold_status=gold_status,
        gold_skill_id=gold_skill_id,
        scored=scored,
        learning_related=_looks_learning_related(request, scored.intent),
    )


def predicted_status(case: LabelledScore, policy: DecisionPolicy) -> tuple[str, str | None]:
    """Mirror of mappers.decide() on plain values; tests keep the two in step."""

    scored = case.scored
    if scored.intent is LearningIntent.GREETING:
        return "NOT_SKILL_RELATED", None
    top_id, top_score = scored.top
    confident = top_score >= policy.match_score and scored.margin >= policy.minimum_margin
    if confident and not (policy.evidence_veto and contradicts_evidence(top_id, scored.evidence)):
        return "MATCHED", top_id
    if top_score >= policy.candidate_score:
        return "AMBIGUOUS", None
    return ("NO_MATCH" if case.learning_related else "NOT_SKILL_RELATED"), None


def fit_policy(
    cases: Sequence[LabelledScore], *, evidence_veto: bool = True
) -> tuple[DecisionPolicy, dict[str, object]]:
    if not cases:
        raise ValueError("calibration needs development cases")
    tops = sorted({case.scored.top[1] for case in cases if case.scored.top[1] != float("-inf")})
    margins = sorted(
        {0.0, *(case.scored.margin for case in cases if case.gold_status == "MATCHED")}
    )
    never = (tops[-1] if tops else 1.0) + 1.0

    best_key: tuple[int, float, float] | None = None
    best: tuple[float, float] = (never, 0.0)
    for match_score in (*tops, never):
        for margin in margins:
            policy = DecisionPolicy(match_score, margin, match_score, evidence_veto)
            correct = false_confident = 0
            for case in cases:
                status, skill = predicted_status(case, policy)
                if status != "MATCHED":
                    continue
                if case.gold_status == "MATCHED" and skill == case.gold_skill_id:
                    correct += 1
                else:
                    false_confident += 1
                    break
            if false_confident:
                continue
            key = (correct, margin, match_score)
            if best_key is None or key > best_key:
                best_key, best = key, (match_score, margin)

    match_score, margin = best
    best_candidate, best_accuracy = match_score, -1.0
    for candidate in sorted({*(value for value in tops if value <= match_score), match_score}):
        policy = DecisionPolicy(match_score, margin, candidate, evidence_veto)
        accuracy = sum(
            predicted_status(case, policy)[0] == case.gold_status for case in cases
        ) / len(cases)
        if accuracy >= best_accuracy:
            best_candidate, best_accuracy = candidate, accuracy

    policy = DecisionPolicy(match_score, margin, best_candidate, evidence_veto)
    return policy, {
        "development_cases": len(cases),
        "development_correct_matches": best_key[0] if best_key else 0,
        "development_status_accuracy": best_accuracy,
        "selection_rule": __doc__.split("Selection rule", 1)[1].strip(),
    }
