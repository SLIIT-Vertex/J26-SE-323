"""Curriculum embedding port.

The adapter lives here so the shared index does not import Adaptive Tutor code.
The recorded pair matches the multilingual E5 model already named in this repository.
A new model name or revision is a new row, not an overwrite of an older revision.
"""

from collections.abc import Sequence
from typing import Any, Protocol

E5_MODEL_NAME = "intfloat/multilingual-e5-small"
E5_MODEL_REVISION = "d829207ab28e6a5fb3aafb5d4c44111b8146db32"
E5_DIMENSIONS = 384


class CurriculumProviderUnavailable(RuntimeError):
    """The embedding runtime is not installed."""


class CurriculumEmbedder(Protocol):
    model_name: str
    model_revision: str

    def embed_query(self, text: str) -> tuple[float, ...]: ...

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


class E5CurriculumEmbedder:
    """Lazy E5 adapter. Construction does not import or download the model."""

    def __init__(
        self,
        model_name: str = E5_MODEL_NAME,
        model_revision: str = E5_MODEL_REVISION,
        *,
        device: str | None = None,
        cache_folder: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.device = device
        self.cache_folder = cache_folder
        self.local_files_only = local_files_only
        self._model: Any | None = None

    def embed_query(self, text: str) -> tuple[float, ...]:
        vectors = self.embed_queries((text,))
        return vectors[0]

    def embed_queries(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return self._encode(texts, "query")

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return self._encode(texts, "passage")

    def _encode(self, texts: Sequence[str], prefix: str) -> tuple[tuple[float, ...], ...]:
        model = self._load_model()
        vectors = model.encode(
            [f"{prefix}: {text}" for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return tuple(tuple(float(value) for value in vector) for vector in vectors)

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ModuleNotFoundError as error:
                raise CurriculumProviderUnavailable(
                    "Install the backend 'skill-mapper' extra to embed curriculum chunks"
                ) from error
            self._model = SentenceTransformer(
                self.model_name,
                revision=self.model_revision,
                device=self.device,
                cache_folder=self.cache_folder,
                local_files_only=self.local_files_only,
                trust_remote_code=False,
            )
        return self._model
