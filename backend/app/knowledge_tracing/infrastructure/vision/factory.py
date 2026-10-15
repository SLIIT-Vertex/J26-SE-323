from functools import lru_cache

import httpx

from app.config import Settings, get_settings
from app.knowledge_tracing.application.grading.call_log import (
    CallLog,
    InMemoryReadingCache,
    ReadingCache,
)
from app.knowledge_tracing.application.grading.types import VisionProvider
from app.knowledge_tracing.infrastructure.vision.gemini import GeminiProvider
from app.knowledge_tracing.infrastructure.vision.mock import MockProvider


class VisionNotConfigured(Exception):
    """The reader named in the settings cannot be created (for example no API key)."""


def create_vision_provider(
    settings: Settings,
    name: str | None = None,
    *,
    call_log: CallLog | None = None,
    cache: ReadingCache | None = None,
    client: httpx.Client | None = None,
) -> VisionProvider:
    chosen = (name or settings.vision_provider).strip().lower()
    if chosen == "mock":
        return MockProvider()
    if chosen == "gemini":
        if not settings.gemini_api_key.strip():
            raise VisionNotConfigured("VISION_PROVIDER is gemini but GEMINI_API_KEY is empty")
        return GeminiProvider(
            settings.gemini_api_key.strip(),
            settings.gemini_model.strip(),
            base_url=settings.gemini_base_url,
            timeout=float(settings.vision_timeout_seconds),
            max_output_tokens=settings.gemini_max_output_tokens,
            call_log=call_log,
            cache=cache if cache is not None else InMemoryReadingCache(),
            client=client,
        )
    raise VisionNotConfigured(f"unknown vision provider {chosen!r} (use mock or gemini)")


@lru_cache
def get_vision_provider() -> VisionProvider:
    """The reader for the running app, logging its calls to the database."""
    from app.knowledge_tracing.infrastructure.db.vision_call_repository import (
        SqlAlchemyVisionCallLog,
    )
    from app.shared.database.session import SessionLocal

    return create_vision_provider(get_settings(), call_log=SqlAlchemyVisionCallLog(SessionLocal))


@lru_cache
def get_second_vision_provider() -> VisionProvider | None:
    """The optional second reader (VISION_SECOND_PROVIDER), or None when it is off."""
    from app.knowledge_tracing.infrastructure.db.vision_call_repository import (
        SqlAlchemyVisionCallLog,
    )
    from app.shared.database.session import SessionLocal

    settings = get_settings()
    if not settings.vision_second_provider.strip():
        return None
    return create_vision_provider(
        settings,
        settings.vision_second_provider,
        call_log=SqlAlchemyVisionCallLog(SessionLocal),
    )
