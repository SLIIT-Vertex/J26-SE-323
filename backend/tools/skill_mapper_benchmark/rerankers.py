"""Pinned, offline cross-encoder adapter and skill passage formats."""

from collections.abc import Sequence
from typing import Any, Protocol

from app.adaptive_tutor.domain import SkillNode

BGE_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
BGE_RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
BGE_RERANKER_LICENSE = "apache-2.0"


class PairScorer(Protocol):
    name: str

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]: ...


class SentenceTransformerCrossEncoder:
    """Lazy cross-encoder returning raw relevance logits (ranking signals, not probabilities)."""

    def __init__(
        self,
        model_name: str = BGE_RERANKER_MODEL,
        revision: str = BGE_RERANKER_REVISION,
        *,
        device: str | None = None,
        max_length: int = 256,
        batch_size: int = 32,
        local_files_only: bool = True,
    ) -> None:
        self.name = f"{model_name}@{revision[:8]}"
        self.model_name = model_name
        self.revision = revision
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.local_files_only = local_files_only
        self._model: Any | None = None

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        scores = self._load().predict(
            list(pairs),
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(value) for value in scores]

    def _load(self) -> Any:
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name,
                revision=self.revision,
                device=self.device,
                max_length=self.max_length,
                local_files_only=self.local_files_only,
                trust_remote_code=False,
                activation_fn=torch.nn.Identity(),
            )
        return self._model


def skill_passage(node: SkillNode, passage_format: str) -> str:
    """Text a cross-encoder compares a learner message against."""

    if passage_format == "taxonomy":
        return node.retrieval_text
    if passage_format == "scope":
        return f"{node.name} ({node.sinhala_designation}): {node.description}"
    raise ValueError(f"unknown passage format: {passage_format}")
