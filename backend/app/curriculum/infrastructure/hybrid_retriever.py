"""Hybrid curriculum retriever: BM25, pgvector nearest neighbours, reciprocal rank fusion.

BM25 uses the fixed Okapi defaults and fusion uses the fixed RRF constant. Neither is fitted
to learner answers.
"""

import math
import re
from collections.abc import Sequence

from app.curriculum.application.chunking import CHUNKING_VERSION
from app.curriculum.application.retrieval import (
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumRetrievalStatus,
    RetrievedCurriculumPassage,
    validate_retrieval_result_for_request,
)
from app.curriculum.infrastructure.embeddings import (
    CurriculumEmbedder,
    CurriculumProviderUnavailable,
)
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex, IndexedChunk

FUSION_METHOD = "reciprocal-rank-fusion-k60"
RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75
_TOKEN = re.compile(r"\w+", re.UNICODE)


def retriever_version_for(embedding_revision: str) -> str:
    return f"{CHUNKING_VERSION};embedding-revision={embedding_revision};fusion={FUSION_METHOD}"


class HybridCurriculumRetriever:
    def __init__(self, index: CurriculumVectorIndex, embedder: CurriculumEmbedder) -> None:
        self._index = index
        self._embedder = embedder

    def retrieve(self, request: CurriculumRetrievalRequest) -> CurriculumRetrievalResult:
        version = retriever_version_for(self._embedder.model_revision)
        try:
            result = self._search(request, version)
        except CurriculumProviderUnavailable:
            return _empty(CurriculumRetrievalStatus.PROVIDER_UNAVAILABLE, version)
        except Exception:  # noqa: BLE001  # any provider failure becomes a recorded retrieval error
            return _empty(CurriculumRetrievalStatus.PROVIDER_ERROR, version)
        validate_retrieval_result_for_request(request, result)
        return result

    def _search(
        self,
        request: CurriculumRetrievalRequest,
        version: str,
    ) -> CurriculumRetrievalResult:
        if not self._index.has_approved_source(request):
            return _empty(CurriculumRetrievalStatus.NO_APPROVED_SOURCE, version)
        candidates = self._index.approved_chunks(request)
        if not candidates:
            return _empty(CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES, version)
        query_vector = self._embedder.embed_query(request.learner_question)
        keyword_rank = _bm25_rank(request.learner_question, candidates)
        vector_rank = self._index.rank_by_vector(
            query_vector,
            [candidate.chunk.chunk_id for candidate in candidates],
            model_name=self._embedder.model_name,
            model_revision=self._embedder.model_revision,
        )
        ordered = _fuse((keyword_rank, vector_rank))[: request.limit]
        by_id = {candidate.chunk.chunk_id: candidate for candidate in candidates}
        passages = tuple(
            RetrievedCurriculumPassage(
                chunk=by_id[chunk_id].chunk,
                source=by_id[chunk_id].source,
                score=_fusion_score(chunk_id, keyword_rank, vector_rank),
            )
            for chunk_id in ordered
            if chunk_id in by_id
        )
        if not passages:
            return _empty(CurriculumRetrievalStatus.NO_RELEVANT_PASSAGES, version)
        return CurriculumRetrievalResult(
            status=CurriculumRetrievalStatus.FOUND,
            passages=passages,
            retriever_version=version,
        )


def _empty(status: CurriculumRetrievalStatus, version: str) -> CurriculumRetrievalResult:
    return CurriculumRetrievalResult(status=status, retriever_version=version)


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).casefold() for match in _TOKEN.finditer(text))


def _bm25_rank(query: str, candidates: Sequence[IndexedChunk]) -> tuple[str, ...]:
    documents = [
        (candidate.chunk.chunk_id, _tokenize(candidate.chunk.content)) for candidate in candidates
    ]
    query_terms = _tokenize(query)
    scores = {chunk_id: _bm25(query_terms, tokens, documents) for chunk_id, tokens in documents}
    return tuple(sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id)))


def _bm25(
    query_terms: Sequence[str],
    tokens: Sequence[str],
    documents: Sequence[tuple[str, Sequence[str]]],
) -> float:
    if not query_terms or not tokens:
        return 0.0
    total = len(documents)
    average = sum(len(document) for _chunk_id, document in documents) / total
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    score = 0.0
    for term in set(query_terms):
        document_frequency = sum(1 for _chunk_id, document in documents if term in document)
        idf = math.log(1.0 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
        frequency = counts.get(term, 0)
        denominator = frequency + BM25_K1 * (1.0 - BM25_B + BM25_B * len(tokens) / average)
        score += idf * (frequency * (BM25_K1 + 1.0)) / denominator
    return score


def _fuse(rankings: Sequence[Sequence[str]]) -> tuple[str, ...]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for index, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + index)
    return tuple(sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id)))


def _fusion_score(chunk_id: str, keyword_rank: Sequence[str], vector_rank: Sequence[str]) -> float:
    score = 0.0
    if chunk_id in keyword_rank:
        score += 1.0 / (RRF_K + keyword_rank.index(chunk_id) + 1)
    if chunk_id in vector_rank:
        score += 1.0 / (RRF_K + vector_rank.index(chunk_id) + 1)
    return score
