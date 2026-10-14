from typing import Protocol


class StorageError(Exception):
    """Base class for storage failures."""


class InvalidStorageKey(StorageError):
    """The key is empty, absolute, or tries to leave the storage root."""


class StorageKeyNotFound(StorageError):
    """No object exists under the key."""


def validate_key(key: str) -> str:
    """Return the key unchanged if it is a safe relative path with forward slashes."""
    if not key or key != key.strip():
        raise InvalidStorageKey(f"Invalid storage key: {key!r}")
    if key.startswith("/") or "\\" in key or "\x00" in key or ":" in key.split("/")[0]:
        raise InvalidStorageKey(f"Invalid storage key: {key!r}")
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise InvalidStorageKey(f"Invalid storage key: {key!r}")
    return key


class StorageBackend(Protocol):
    """Private object storage addressed by keys such as 'questions/3/3.41.png'.

    Keys are what the database stores. URLs are created per request and expire.
    """

    def get(self, key: str) -> bytes: ...

    def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...

    def exists(self, key: str) -> bool: ...

    def list(self, prefix: str = "") -> list[str]:
        """Keys that start with the prefix, sorted."""
        ...

    def delete(self, key: str) -> None: ...

    def signed_url(self, key: str, expires_seconds: int) -> str: ...
