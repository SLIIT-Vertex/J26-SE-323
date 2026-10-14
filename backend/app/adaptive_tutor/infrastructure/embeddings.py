from collections.abc import Sequence
from typing import Any

DEFAULT_E5_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_E5_REVISION = "d829207ab28e6a5fb3aafb5d4c44111b8146db32"


class SentenceTransformerE5EmbeddingModel:
    """Lazy multilingual E5 adapter; construction performs no import or download."""

    def __init__(
        self,
        model_name: str = DEFAULT_E5_MODEL,
        revision: str = DEFAULT_E5_REVISION,
        *,
        device: str | None = None,
        cache_folder: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.device = device
        self.cache_folder = cache_folder
        self.local_files_only = local_files_only
        self._model: Any | None = None

    def embed_queries(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return self._encode(texts, "query")

    def embed_passages(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return self._encode(texts, "passage")

    def _encode(
        self,
        texts: Sequence[str],
        prefix: str,
    ) -> tuple[tuple[float, ...], ...]:
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
                raise RuntimeError(
                    "Install the backend 'skill-mapper' extra to run semantic inference"
                ) from error
            self._model = SentenceTransformer(
                self.model_name,
                revision=self.revision,
                device=self.device,
                cache_folder=self.cache_folder,
                local_files_only=self.local_files_only,
                trust_remote_code=False,
            )
        return self._model
