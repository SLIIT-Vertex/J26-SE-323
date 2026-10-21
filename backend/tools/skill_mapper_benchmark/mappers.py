"""Benchmark mappers that keep the existing SkillMappingRequest/SkillMappingResult contract.

Scoring and deciding are separate so a decision policy can be fitted on development scores
without re-running models. A policy never selects a skill the scorer did not rank first.
"""

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.adaptive_tutor.application.skill_mapper import (
    SemanticSkillRetriever,
    _clarification_question,
    _looks_learning_related,
    _uses_conversation_context,
    classify_intent,
    prepare_mapping_query,
)
from app.adaptive_tutor.application.skill_mapper_contracts import (
    MAX_CANDIDATE_SKILLS,
    SkillCandidate,
    SkillMappingRequest,
    SkillMappingResult,
)
from app.adaptive_tutor.domain import (
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
    SkillNode,
)
from tools.skill_mapper_benchmark.evidence import contradicts_evidence, notation_evidence
from tools.skill_mapper_benchmark.normalization import normalize_math_text
from tools.skill_mapper_benchmark.rerankers import PairScorer, skill_passage


@dataclass(frozen=True, slots=True)
class ScoredCase:
    """Ranked skills (best first) plus the facts a decision policy may use."""

    intent: LearningIntent
    ranking: tuple[tuple[str, float], ...]
    decision_pool: int
    evidence: frozenset[str]
    uses_context: bool
    seconds: float
    score_kind: str = "cosine"

    def confidence(self, score: float) -> float:
        """Contract confidence in [0, 1]: cosine is clipped, a logit passes through a sigmoid."""

        if self.score_kind == "logit":
            return 1.0 / (1.0 + math.exp(-score))
        return min(1.0, max(0.0, score))

    @property
    def top(self) -> tuple[str, float]:
        return self.ranking[0]

    @property
    def margin(self) -> float:
        pool = self.ranking[: self.decision_pool]
        return pool[0][1] - pool[1][1] if len(pool) > 1 else 1.0


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    match_score: float
    minimum_margin: float
    candidate_score: float
    evidence_veto: bool = True

    def __post_init__(self) -> None:
        if self.candidate_score > self.match_score:
            raise ValueError("candidate_score must not exceed match_score")


def _normalized_request(request: SkillMappingRequest) -> SkillMappingRequest:
    return request.model_copy(
        update={"learner_message": normalize_math_text(request.learner_message)}
    )


def _query(request: SkillMappingRequest) -> tuple[LearningIntent, str, bool]:
    intent = classify_intent(request)
    normalized = _normalized_request(request)
    return (
        intent,
        prepare_mapping_query(normalized, intent),
        _uses_conversation_context(request, intent),
    )


class E5Scorer:
    """The existing E5 retriever with notation normalization; the decision policy is separate."""

    def __init__(self, retriever: SemanticSkillRetriever) -> None:
        self._retriever = retriever

    def score(self, request: SkillMappingRequest) -> ScoredCase:
        started = time.perf_counter()
        intent, query, uses_context = _query(request)
        ranked = self._retriever.rank(query)
        ranking = tuple((item.node.skill_id, item.score) for item in ranked)
        return ScoredCase(
            intent=intent,
            ranking=ranking,
            decision_pool=len(ranking),
            evidence=notation_evidence(request.learner_message),
            uses_context=uses_context,
            seconds=time.perf_counter() - started,
        )


class CrossEncoderScorer:
    """Cross-encoder over E5's top-k candidates (hybrid) or over every skill (top_k=None)."""

    def __init__(
        self,
        nodes: Sequence[SkillNode],
        cross_encoder: PairScorer,
        *,
        retriever: SemanticSkillRetriever | None = None,
        top_k: int | None = None,
        passage_format: str = "scope",
    ) -> None:
        if (retriever is None) != (top_k is None):
            raise ValueError("a hybrid scorer needs both an E5 retriever and top_k")
        self._nodes = {node.skill_id: node for node in nodes}
        self._cross_encoder = cross_encoder
        self._retriever = retriever
        self._top_k = top_k
        self._passages = {
            skill_id: skill_passage(node, passage_format) for skill_id, node in self._nodes.items()
        }

    def score(self, request: SkillMappingRequest) -> ScoredCase:
        started = time.perf_counter()
        intent, query, uses_context = _query(request)
        if self._retriever is not None and self._top_k is not None:
            retrieved = [item.node.skill_id for item in self._retriever.rank(query)]
            candidates, remainder = retrieved[: self._top_k], retrieved[self._top_k :]
        else:
            candidates, remainder = sorted(self._nodes), []
        scores = self._cross_encoder.score([(query, self._passages[skill]) for skill in candidates])
        reranked = sorted(
            zip(candidates, scores, strict=True), key=lambda item: (-item[1], item[0])
        )
        ranking = (*reranked, *((skill, float("-inf")) for skill in remainder))
        return ScoredCase(
            intent=intent,
            ranking=tuple(ranking),
            decision_pool=len(candidates),
            evidence=notation_evidence(request.learner_message),
            uses_context=uses_context,
            seconds=time.perf_counter() - started,
            score_kind="logit",
        )


def decide(
    request: SkillMappingRequest,
    scored: ScoredCase,
    policy: DecisionPolicy,
    nodes_by_id: Mapping[str, SkillNode],
) -> tuple[SkillMappingResult, bool]:
    """Apply a fitted policy. Returns the contract result and whether evidence vetoed a match."""

    if scored.intent is LearningIntent.GREETING:
        return (
            SkillMappingResult(
                status=SkillMappingStatus.NOT_SKILL_RELATED,
                intent=scored.intent,
                clarification_needed=False,
                reason_codes=(SkillMappingReasonCode.NOT_SKILL_RELATED,),
            ),
            False,
        )

    top_id, top_score = scored.top
    confident = top_score >= policy.match_score and scored.margin >= policy.minimum_margin
    vetoed = confident and policy.evidence_veto and contradicts_evidence(top_id, scored.evidence)
    if confident and not vetoed:
        reasons = [
            SkillMappingReasonCode.CONVERSATION_CONTEXT_USED
            if scored.uses_context
            else SkillMappingReasonCode.DIRECT_SKILL_EVIDENCE
        ]
        if scored.uses_context and request.active_skill_id == top_id:
            reasons.append(SkillMappingReasonCode.ACTIVE_SKILL_USED)
        return (
            SkillMappingResult(
                status=SkillMappingStatus.MATCHED,
                intent=scored.intent,
                skill_id=top_id,
                confidence=scored.confidence(top_score),
                clarification_needed=False,
                reason_codes=tuple(reasons),
            ),
            False,
        )

    if top_score >= policy.candidate_score:
        candidates = tuple(
            SkillCandidate(skill_id=skill, confidence=scored.confidence(score))
            for skill, score in scored.ranking[: min(MAX_CANDIDATE_SKILLS, scored.decision_pool)]
            if score >= policy.candidate_score
        )
        reasons = [SkillMappingReasonCode.LOW_CONFIDENCE]
        if len(candidates) > 1:
            reasons.append(SkillMappingReasonCode.MULTIPLE_CANDIDATES)
        return (
            SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=scored.intent,
                candidate_skills=candidates,
                clarification_needed=True,
                clarification_question=_clarification_question(candidates, nodes_by_id),
                reason_codes=tuple(reasons),
            ),
            vetoed,
        )

    learning_related = _looks_learning_related(request, scored.intent)
    return (
        SkillMappingResult(
            status=SkillMappingStatus.NO_MATCH
            if learning_related
            else SkillMappingStatus.NOT_SKILL_RELATED,
            intent=scored.intent if learning_related else LearningIntent.OFF_TOPIC,
            clarification_needed=False,
            reason_codes=(
                SkillMappingReasonCode.OUTSIDE_SUPPORTED_TAXONOMY
                if learning_related
                else SkillMappingReasonCode.NOT_SKILL_RELATED,
                SkillMappingReasonCode.INSUFFICIENT_EVIDENCE,
            ),
        ),
        vetoed,
    )
