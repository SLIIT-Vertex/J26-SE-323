from app.config import Settings
from app.knowledge_tracing.infrastructure.storage.base import StorageBackend
from app.knowledge_tracing.infrastructure.storage.local import LocalStorage
from app.knowledge_tracing.infrastructure.storage.s3 import S3Storage


def create_storage(settings: Settings) -> StorageBackend:
    """Build the storage backend named by STORAGE_BACKEND."""
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.local_storage_dir)
    if backend == "s3":
        return S3Storage(settings.s3_bucket, settings.s3_region)
    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.storage_backend!r} (use local or s3)")


def create_paper_storage(settings: Settings) -> StorageBackend:
    """Where generated papers are written, named by PAPER_STORAGE_BACKEND."""
    backend = settings.paper_storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.local_storage_dir)
    if backend == "s3":
        return S3Storage(settings.s3_bucket, settings.s3_region)
    raise ValueError(
        f"Unknown PAPER_STORAGE_BACKEND: {settings.paper_storage_backend!r} (use local or s3)"
    )
