import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar, Protocol

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
class RelevanceAssessment:
    status: SkillMappingStatus | None
    category: str | None
    negative_score: float
    supported_score: float


@dataclass(frozen=True, slots=True)
class SkillMappingPolicy:
    """Provisional prototype parameters; none are validated educational findings."""

    match_threshold: float = 0.82
    candidate_threshold: float = 0.70
    minimum_margin: float = 0.03
    active_skill_bonus: float = 0.02
    explicit_fraction_notation_bonus: float = 0.03

    def __post_init__(self) -> None:
        for field_name in (
            "match_threshold",
            "candidate_threshold",
            "minimum_margin",
            "active_skill_bonus",
            "explicit_fraction_notation_bonus",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0 and 1")
        if self.candidate_threshold > self.match_threshold:
            raise ValueError("candidate_threshold must not exceed match_threshold")


class SemanticSkillRetriever:
    def __init__(
        self,
        nodes: Sequence[SkillNode],
        embeddings: EmbeddingModel,
        retrieval_enrichments: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.nodes = tuple(sorted(nodes, key=lambda node: node.skill_id))
        if not self.nodes:
            raise ValueError("at least one skill node is required")
        if len({node.skill_id for node in self.nodes}) != len(self.nodes):
            raise ValueError("skill node IDs must be unique")
        self._embeddings = embeddings
        enrichments = retrieval_enrichments or {}
        unknown_ids = sorted(set(enrichments) - {node.skill_id for node in self.nodes})
        if unknown_ids:
            raise ValueError(f"unknown enrichment skill IDs: {', '.join(unknown_ids)}")
        self._passages = tuple(
            (node, passage)
            for node in self.nodes
            for passage in (
                node.retrieval_text,
                *sorted(
                    {
                        prepare_text(text)
                        for text in enrichments.get(node.skill_id, ())
                        if prepare_text(text)
                    }
                ),
            )
        )
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

        scores = {node.skill_id: -1.0 for node in self.nodes}
        for (node, _), vector in zip(self._passages, passage_vectors, strict=True):
            scores[node.skill_id] = max(
                scores[node.skill_id],
                _cosine_similarity(query_vector, vector),
            )
        ranked = [
            RankedSkill(
                node=node,
                score=min(1.0, scores[node.skill_id] + adjustments.get(node.skill_id, 0.0)),
            )
            for node in self.nodes
        ]
        return tuple(sorted(ranked, key=lambda candidate: (-candidate.score, candidate.node.skill_id)))

    def _get_passage_vectors(self) -> tuple[tuple[float, ...], ...]:
        if self._passage_vectors is None:
            vectors = self._embeddings.embed_passages(
                [passage for _, passage in self._passages]
            )
            if len(vectors) != len(self._passages):
                raise ValueError("embedding model must return one vector per taxonomy passage")
            self._passage_vectors = tuple(_validated_vector(vector) for vector in vectors)
        return self._passage_vectors


class SemanticRelevanceGate:
    """Compare the best supported skill with small unsupported/off-topic counter-examples."""

    _STATUSES: ClassVar[dict[str, SkillMappingStatus]] = {
        "unsupported_learning": SkillMappingStatus.NO_MATCH,
        "off_topic": SkillMappingStatus.NOT_SKILL_RELATED,
    }

    def __init__(
        self,
        embeddings: EmbeddingModel,
        examples: Mapping[str, Sequence[str]],
        minimum_advantage: float = 0.0,
    ) -> None:
        if set(examples) != set(self._STATUSES):
            raise ValueError("relevance examples must define unsupported_learning and off_topic")
        if not 0.0 <= minimum_advantage <= 1.0:
            raise ValueError("minimum_advantage must be between 0 and 1")
        self._embeddings = embeddings
        self._examples = tuple(
            (category, prepare_text(text))
            for category in sorted(examples)
            for text in examples[category]
            if prepare_text(text)
        )
        if not self._examples:
            raise ValueError("relevance examples must not be empty")
        self.minimum_advantage = minimum_advantage
        self._passage_vectors: tuple[tuple[float, ...], ...] | None = None

    def assess(self, query: str, supported_score: float) -> RelevanceAssessment:
        query_vectors = self._embeddings.embed_queries([prepare_text(query)])
        if len(query_vectors) != 1:
            raise ValueError("embedding model must return one vector per query")
        query_vector = _validated_vector(query_vectors[0])
        scores = {category: -1.0 for category in self._STATUSES}
        for (category, _), vector in zip(
            self._examples,
            self._get_passage_vectors(),
            strict=True,
        ):
            scores[category] = max(scores[category], _cosine_similarity(query_vector, vector))
        category, negative_score = min(scores.items(), key=lambda item: (-item[1], item[0]))
        status = (
            self._STATUSES[category]
            if negative_score >= supported_score + self.minimum_advantage
            else None
        )
        return RelevanceAssessment(
            status=status,
            category=category if status else None,
            negative_score=negative_score,
            supported_score=supported_score,
        )

    def _get_passage_vectors(self) -> tuple[tuple[float, ...], ...]:
        if self._passage_vectors is None:
            vectors = self._embeddings.embed_passages(
                [text for _, text in self._examples]
            )
            if len(vectors) != len(self._examples):
                raise ValueError("embedding model must return one vector per relevance example")
            self._passage_vectors = tuple(_validated_vector(vector) for vector in vectors)
        return self._passage_vectors


class ConversationalSkillMapper:
    def __init__(
        self,
        retriever: SemanticSkillRetriever,
        policy: SkillMappingPolicy | None = None,
        relevance_gate: SemanticRelevanceGate | None = None,
    ) -> None:
        self._retriever = retriever
        self._policy = policy or SkillMappingPolicy()
        self._relevance_gate = relevance_gate
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

        if self._relevance_gate is not None:
            relevance = self._relevance_gate.assess(request.learner_message, top.score)
            if relevance.status is not None:
                is_off_topic = relevance.status is SkillMappingStatus.NOT_SKILL_RELATED
                return SkillMappingResult(
                    status=relevance.status,
                    intent=LearningIntent.OFF_TOPIC if is_off_topic else intent,
                    clarification_needed=False,
                    reason_codes=(
                        SkillMappingReasonCode.NOT_SKILL_RELATED
                        if is_off_topic
                        else SkillMappingReasonCode.OUTSIDE_SUPPORTED_TAXONOMY,
                        SkillMappingReasonCode.INSUFFICIENT_EVIDENCE,
                    ),
                )

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
        adjustments: dict[str, float] = {}
        if uses_context and request.active_skill_id:
            adjustments[request.active_skill_id] = self._policy.active_skill_bonus
        if has_explicit_fraction_notation(request.learner_message):
            adjustments["MAT-FRC"] = (
                adjustments.get("MAT-FRC", 0.0) + self._policy.explicit_fraction_notation_bonus
            )
        return self._retriever.rank(
            prepare_mapping_query(request, resolved_intent),
            adjustments or None,
        )


def prepare_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding symbols, fractions, or numbers."""

    return " ".join(unicodedata.normalize("NFC", text).split())


# Deterministic notation evidence for MAT-FRC. A slash alone is not treated as a fraction:
# "3/4" can be a date, so any clock, date or calendar cue disables the signal entirely.
_SIMPLE_FRACTION = re.compile(r"(?<![\d/])\d+\s*/\s*[1-9]\d*(?![\d/])")
_TIME_OR_DATE_CUE = re.compile(
    r"\d\s*:\s*\d{2}"
    r"|\d+\s*/\s*\d+\s*/\s*\d+"
    r"|\d\s*(?:a\.?m|p\.?m)\b"
    r"|\b(?:time|clock|o'?clock|hours?|hrs?|minutes?|mins?|seconds?|noon|midnight"
    r"|date|dates|today|tomorrow|yesterday|days?|weeks?|months?|years?|calendar|birthday|leap"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|january|february|march|april|june|july|august|september|october|november|december"
    r"|welawa|paya|minithu\w*|dinaya|dawasa|sathiya|masaya|awurudda|oralosu\w*)\b"
    r"|වේලාව|වෙලාව|ඔරලෝසු|පැය|මිනිත්තු|තත්පර|දිනය|දවස|සතිය|මාස|අවුරුදු|දිනදර්ශන"
    r"|நேரம்|மணி|நிமிட|நாள்|தேதி|வாரம்|மாத"
)
_FRACTION_RELATION = re.compile(
    r"[+\-−*×÷=<>]"
    r"|\b(?:equal|equals|equivalent|same|compare|comparing|bigger|biggest|larger|largest"
    r"|smaller|smallest|greater|greatest|less|more|add|adding|plus|sum|total|minus"
    r"|subtract|take away|difference|multiply|times|divide|divided)\b"
    r"|\b(?:samana|ekathu|adu|loku|podi|wishala|kuda|guna|beda)\w*"
    r"|සමාන|එකතු|අඩු|ලොකු|විශාල|කුඩා|පොඩි|සසඳ|සංසන්දන|ගුණ|බෙද"
    r"|சமம|கூட்ட|கழி|பெரிய|சிறிய|ஒப்பிட"
)
_FRACTION_VOCABULARY = re.compile(
    r"\b(?:fractions?|numerator|denominator|bhaga\w*|haraya|lawaya)\b|භාග|හරය|ලවය|பின்ன"
)
_FRACTION_OF_QUANTITY = re.compile(
    r"(?<![\d/])\d+\s*/\s*[1-9]\d*\s+of\s+(?:an?\s+|the\s+)?\d"
    r"|\d+\s*න්\s*\d+\s*/\s*[1-9]"
)


def has_explicit_fraction_notation(text: str) -> bool:
    """True only for unambiguous written fractions; time and date wording always vetoes."""

    normalized = prepare_text(text).casefold()
    if _TIME_OR_DATE_CUE.search(normalized):
        return False
    fractions = _SIMPLE_FRACTION.findall(normalized)
    if not fractions:
        return False
    if len(fractions) >= 2 and _FRACTION_RELATION.search(normalized):
        return True
    return bool(_FRACTION_VOCABULARY.search(normalized) or _FRACTION_OF_QUANTITY.search(normalized))


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
