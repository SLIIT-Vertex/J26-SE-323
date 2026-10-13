from pathlib import Path

from app.knowledge_tracing.infrastructure.storage.base import (
    StorageKeyNotFound,
    validate_key,
)


class LocalStorage:
    """Stores objects as files under one folder. For development and tests."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if not path.is_relative_to(self.root):  # defence in depth; validate_key already rejects
            raise StorageKeyNotFound(key)
        return path

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageKeyNotFound(key)
        return path.read_bytes()

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def list(self, prefix: str = "") -> list[str]:
        keys = (
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file()
        )
        return sorted(key for key in keys if key.startswith(prefix))

    def delete(self, key: str) -> None:
        path = self._path(key)
        if not path.is_file():
            raise StorageKeyNotFound(key)
        path.unlink()

    def signed_url(self, key: str, expires_seconds: int) -> str:
        """A file URI. Only meaningful on the machine that holds the files."""
        path = self._path(key)
        if not path.is_file():
            raise StorageKeyNotFound(key)
        return path.as_uri()
