import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.adaptive_tutor.application.skill_mapper_contracts import (
    MAX_CANDIDATE_SKILLS,
    SkillCandidate,
    SkillMappingRequest,
    SkillMappingResult,
    validate_skill_ids_against_taxonomy,
)
from app.adaptive_tutor.domain import (
    LearningIntent,
    SkillMappingReasonCode,
    SkillMappingStatus,
    SkillNode,
)

Vector = Sequence[float]


class EmbeddingModel(Protocol):
    """Replaceable semantic embedding boundary."""

    def embed_queries(self, texts: Sequence[str]) -> Sequence[Vector]: ...

    def embed_passages(self, texts: Sequence[str]) -> Sequence[Vector]: ...


@dataclass(frozen=True, slots=True)
class RankedSkill:
    node: SkillNode
    score: float


@dataclass(frozen=True, slots=True)
class SkillMappingPolicy:
    """Provisional prototype parameters; none are validated educational findings."""

    match_threshold: float = 0.82
    candidate_threshold: float = 0.70
    minimum_margin: float = 0.03
    active_skill_bonus: float = 0.02

    def __post_init__(self) -> None:
        for field_name in (
            "match_threshold",
            "candidate_threshold",
            "minimum_margin",
            "active_skill_bonus",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        if self.candidate_threshold > self.match_threshold:
            raise ValueError("candidate_threshold must not exceed match_threshold")


class SemanticSkillRetriever:
    def __init__(self, nodes: Sequence[SkillNode], embeddings: EmbeddingModel) -> None:
        self.nodes = tuple(sorted(nodes, key=lambda node: node.skill_id))
        if not self.nodes:
            raise ValueError("at least one skill node is required")
        if len({node.skill_id for node in self.nodes}) != len(self.nodes):
            raise ValueError("skill node IDs must be unique")
        self._embeddings = embeddings
        self._passage_vectors: tuple[tuple[float, ...], ...] | None = None

    def rank(
        self,
        query: str,
        score_adjustments: Mapping[str, float] | None = None,
    ) -> tuple[RankedSkill, ...]:
        query_vectors = self._embeddings.embed_queries([prepare_text(query)])
        if len(query_vectors) != 1:
            raise ValueError("embedding model must return one vector per query")
        passage_vectors = self._get_passage_vectors()
        query_vector = _validated_vector(query_vectors[0])
        adjustments = score_adjustments or {}

        ranked = [
            RankedSkill(
                node=node,
                score=min(1.0, _cosine_similarity(query_vector, vector) + adjustments.get(node.skill_id, 0.0)),
            )
            for node, vector in zip(self.nodes, passage_vectors, strict=True)
        ]
        return tuple(sorted(ranked, key=lambda candidate: (-candidate.score, candidate.node.skill_id)))

    def _get_passage_vectors(self) -> tuple[tuple[float, ...], ...]:
        if self._passage_vectors is None:
            vectors = self._embeddings.embed_passages(
                [node.retrieval_text for node in self.nodes]
            )
            if len(vectors) != len(self.nodes):
                raise ValueError("embedding model must return one vector per taxonomy passage")
            self._passage_vectors = tuple(_validated_vector(vector) for vector in vectors)
        return self._passage_vectors


class ConversationalSkillMapper:
    def __init__(
        self,
        retriever: SemanticSkillRetriever,
        policy: SkillMappingPolicy | None = None,
    ) -> None:
        self._retriever = retriever
        self._policy = policy or SkillMappingPolicy()
        self._nodes_by_id = {node.skill_id: node for node in retriever.nodes}

    def map(self, request: SkillMappingRequest) -> SkillMappingResult:
        validate_skill_ids_against_taxonomy(request, self._nodes_by_id.keys())
        intent = classify_intent(request)

        if intent is LearningIntent.GREETING:
            return SkillMappingResult(
                status=SkillMappingStatus.NOT_SKILL_RELATED,
                intent=intent,
                clarification_needed=False,
                reason_codes=(SkillMappingReasonCode.NOT_SKILL_RELATED,),
            )

        ranked = self.rank(request, intent)
        top = ranked[0]
        second_score = ranked[1].score if len(ranked) > 1 else -1.0
        top_score = _contract_score(top.score)
        margin = top.score - second_score
        uses_context = _uses_conversation_context(request, intent)

        if top_score >= self._policy.match_threshold and margin >= self._policy.minimum_margin:
            reasons = [
                SkillMappingReasonCode.CONVERSATION_CONTEXT_USED
                if uses_context
                else SkillMappingReasonCode.DIRECT_SKILL_EVIDENCE
            ]
            if uses_context and request.active_skill_id == top.node.skill_id:
                reasons.append(SkillMappingReasonCode.ACTIVE_SKILL_USED)
            result = SkillMappingResult(
                status=SkillMappingStatus.MATCHED,
                intent=intent,
                skill_id=top.node.skill_id,
                confidence=top_score,
                clarification_needed=False,
                reason_codes=tuple(reasons),
            )
        elif top_score >= self._policy.candidate_threshold:
            candidates = tuple(
                SkillCandidate(
                    skill_id=candidate.node.skill_id,
                    confidence=_contract_score(candidate.score),
                )
                for candidate in ranked[:MAX_CANDIDATE_SKILLS]
                if _contract_score(candidate.score) >= self._policy.candidate_threshold
            )
            reasons = [SkillMappingReasonCode.LOW_CONFIDENCE]
            if len(candidates) > 1 and margin < self._policy.minimum_margin:
                reasons.append(SkillMappingReasonCode.MULTIPLE_CANDIDATES)
            result = SkillMappingResult(
                status=SkillMappingStatus.AMBIGUOUS,
                intent=intent,
                candidate_skills=candidates,
                clarification_needed=True,
                clarification_question=_clarification_question(candidates, self._nodes_by_id),
                reason_codes=tuple(reasons),
            )
        else:
            learning_related = _looks_learning_related(request, intent)
            result = SkillMappingResult(
                status=(
                    SkillMappingStatus.NO_MATCH
                    if learning_related
                    else SkillMappingStatus.NOT_SKILL_RELATED
                ),
                intent=intent if learning_related else LearningIntent.OFF_TOPIC,
                clarification_needed=False,
                reason_codes=(
                    SkillMappingReasonCode.OUTSIDE_SUPPORTED_TAXONOMY
                    if learning_related
                    else SkillMappingReasonCode.NOT_SKILL_RELATED,
                    SkillMappingReasonCode.INSUFFICIENT_EVIDENCE,
                ),
            )

        validate_skill_ids_against_taxonomy(result, self._nodes_by_id.keys())
        return result

    def rank(
        self,
        request: SkillMappingRequest,
        intent: LearningIntent | None = None,
    ) -> tuple[RankedSkill, ...]:
        validate_skill_ids_against_taxonomy(request, self._nodes_by_id.keys())
        resolved_intent = intent or classify_intent(request)
        uses_context = _uses_conversation_context(request, resolved_intent)
        adjustments = (
            {request.active_skill_id: self._policy.active_skill_bonus}
            if uses_context and request.active_skill_id
            else None
        )
        return self._retriever.rank(
            prepare_mapping_query(request, resolved_intent),
            adjustments,
        )


def prepare_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding symbols, fractions, or numbers."""

    return " ".join(unicodedata.normalize("NFC", text).split())


def prepare_mapping_query(request: SkillMappingRequest, intent: LearningIntent) -> str:
    message = prepare_text(request.learner_message)
    if not _uses_conversation_context(request, intent):
        return message

    turns = "\n".join(
        f"{turn.role}: {prepare_text(turn.message)}" for turn in request.conversation_context
    )
    return f"Recent conversation:\n{turns}\nCurrent learner message: {message}"


def classify_intent(request: SkillMappingRequest) -> LearningIntent:
    """Conservative prototype rules; semantic intent classification is future work."""

    text = prepare_text(request.learner_message).casefold()
    plain = text.strip(" .,!?")
    if plain in {
        "hi",
        "hello",
        "hey",
        "hello teacher",
        "ayubowan",
        "ayubowan teacher",
        "ආයුබෝවන්",
        "வணக்கம்",
    }:
        return LearningIntent.GREETING
    if re.fullmatch(r"[\d\s.,/\\+*×÷=:%()\-]+", text) and (
        request.active_skill_id or request.conversation_context
    ):
        return LearningIntent.ANSWER_SUBMISSION
    if text.startswith(("i got ", "my answer", "the answer is", "answer is")):
        return LearningIntent.ANSWER_SUBMISSION
    if any(marker in text for marker in ("hint", "clue")):
        return LearningIntent.HINT_REQUEST
    if "another" in text and any(marker in text for marker in ("example", "one", "question")):
        return LearningIntent.ANOTHER_EXAMPLE_REQUEST
    if request.conversation_context and text.startswith(
        ("why ", "how did ", "what about ", "can you explain this", "can you explain that")
    ):
        return LearningIntent.FOLLOW_UP_QUESTION
    return LearningIntent.EXPLANATION_REQUEST


def _uses_conversation_context(
    request: SkillMappingRequest,
    intent: LearningIntent,
) -> bool:
    return bool(request.conversation_context) and intent in {
        LearningIntent.FOLLOW_UP_QUESTION,
        LearningIntent.ANSWER_SUBMISSION,
        LearningIntent.ANOTHER_EXAMPLE_REQUEST,
    }


def _looks_learning_related(
    request: SkillMappingRequest,
    intent: LearningIntent,
) -> bool:
    if intent in {
        LearningIntent.HINT_REQUEST,
        LearningIntent.FOLLOW_UP_QUESTION,
        LearningIntent.ANSWER_SUBMISSION,
        LearningIntent.ANOTHER_EXAMPLE_REQUEST,
    }:
        return True
    text = prepare_text(request.learner_message).casefold()
    return bool(re.search(r"[\d/+*×÷=%]", text)) or text.startswith(
        ("teach ", "explain ", "help ", "how ", "why ", "what is ", "solve ", "calculate ")
    )


def _clarification_question(
    candidates: Sequence[SkillCandidate],
    nodes_by_id: Mapping[str, SkillNode],
) -> str:
    names = [nodes_by_id[candidate.skill_id].name for candidate in candidates[:2]]
    if len(names) > 1:
        return f"Is your question about {names[0]} or {names[1]}?"
    return f"Is your question about {names[0]}?"


def _validated_vector(vector: Vector) -> tuple[float, ...]:
    values = tuple(float(value) for value in vector)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("embedding vectors must contain finite values")
    return values


def _cosine_similarity(left: Vector, right: Vector) -> float:
    if len(left) != len(right):
        raise ValueError("embedding vectors must have equal dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _contract_score(score: float) -> float:
    return max(0.0, min(1.0, float(score)))
