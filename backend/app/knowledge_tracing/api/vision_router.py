"""Shows the owner which reader is in use and whether it needs attention.

Separate from /health on purpose: the health endpoint is shared with the other modules.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.knowledge_tracing.infrastructure.vision.factory import (
    VisionNotConfigured,
    get_second_vision_provider,
    get_vision_provider,
)

router = APIRouter(tags=["vision"])


class VisionStatus(BaseModel):
    configured: bool
    provider: str
    model: str | None = None
    second_provider: str | None = None
    # vision_model_not_pinned | vision_model_auto_switched | vision_quota_exhausted
    warnings: list[str] = []
    problem: str | None = None


@router.get("/vision/status", response_model=VisionStatus)
def vision_status() -> VisionStatus:
    settings = get_settings()
    try:
        provider = get_vision_provider()
    except VisionNotConfigured as error:
        return VisionStatus(
            configured=False, provider=settings.vision_provider, problem=str(error)
        )

    warnings = sorted(getattr(provider, "warnings", set()))
    configured_model = {"gemini": settings.gemini_model, "openai": settings.openai_model}.get(
        settings.vision_provider.strip().lower(), ""
    )
    model = getattr(provider, "model", None) or configured_model or None
    if settings.vision_provider == "gemini" and not settings.gemini_model.strip():
        warnings = sorted({*warnings, "vision_model_not_pinned"})

    second = None
    try:
        other = get_second_vision_provider()
        if other is not None:
            second = other.name
            warnings = sorted({*warnings, *getattr(other, "warnings", set())})
    except VisionNotConfigured as error:
        return VisionStatus(
            configured=False,
            provider=provider.name,
            model=model,
            problem=f"second reader: {error}",
            warnings=warnings,
        )
    return VisionStatus(
        configured=True, provider=provider.name, model=model, second_provider=second, warnings=warnings
    )
