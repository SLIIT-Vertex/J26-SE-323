import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, UnidentifiedImageError

from app.knowledge_tracing.application.question_import import ImageInfo, ImageUnreadable
from app.knowledge_tracing.infrastructure.storage.base import StorageBackend

ALLOWED_FORMATS = {"PNG", "JPEG"}
EXTENSIONS = (".png", ".jpg", ".jpeg")


class StorageImageSource:
    """Finds question images in storage: <prefix><set>[-T]/<id>.png, e.g. questions/3-T/3.41.png."""

    def __init__(self, storage: StorageBackend, prefix: str = "", workers: int = 8) -> None:
        self._storage = storage
        self._prefix = prefix
        self._workers = workers
        self._keys = set(storage.list(prefix))
        self._cache: dict[str, ImageInfo | ImageUnreadable] = {}

    def key_for(self, language: str, question_id: str) -> str | None:
        folder = question_id.split(".")[0] + ("" if language == "si" else "-T")
        for extension in EXTENSIONS:
            key = f"{self._prefix}{folder}/{question_id}{extension}"
            if key in self._keys:
                return key
        return None

    def prefetch(self, pairs: list[tuple[str, str]]) -> None:
        """Download and measure many images in parallel."""
        keys = sorted({k for language, qid in pairs if (k := self.key_for(language, qid))})
        keys = [k for k in keys if k not in self._cache]
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            for key, outcome in zip(keys, pool.map(self._measure, keys), strict=True):
                self._cache[key] = outcome

    def describe(self, language: str, question_id: str) -> ImageInfo | None:
        key = self.key_for(language, question_id)
        if key is None:
            return None
        if key not in self._cache:
            self._cache[key] = self._measure(key)
        outcome = self._cache[key]
        if isinstance(outcome, ImageUnreadable):
            raise outcome
        return outcome

    def _measure(self, key: str) -> ImageInfo | ImageUnreadable:
        data = self._storage.get(key)
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ALLOWED_FORMATS:
                    return ImageUnreadable(f"{key}: {image.format} is not PNG or JPEG")
                width, height = image.size
        except (UnidentifiedImageError, OSError) as problem:
            return ImageUnreadable(f"{key}: {problem}")
        return ImageInfo(key, width, height, hashlib.sha256(data).hexdigest())
