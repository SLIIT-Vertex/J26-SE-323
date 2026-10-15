"""Shared curriculum adapters."""

from app.curriculum.infrastructure.embeddings import (
    E5_MODEL_NAME,
    E5_MODEL_REVISION,
    E5CurriculumEmbedder,
)
from app.curriculum.infrastructure.hybrid_retriever import HybridCurriculumRetriever
from app.curriculum.infrastructure.pgvector_index import CurriculumVectorIndex
from app.curriculum.infrastructure.source_registry_jsonl import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    JsonlCurriculumSourceRegistry,
)

__all__ = [
    "DEFAULT_SOURCE_REGISTRY_PATH",
    "E5_MODEL_NAME",
    "E5_MODEL_REVISION",
    "CurriculumVectorIndex",
    "E5CurriculumEmbedder",
    "HybridCurriculumRetriever",
    "JsonlCurriculumSourceRegistry",
]
