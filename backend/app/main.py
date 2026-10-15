import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.knowledge_tracing.api.attempts_router import router as attempts_router
from app.knowledge_tracing.api.mastery_router import router as mastery_router
from app.knowledge_tracing.api.papers_router import router as papers_router
from app.knowledge_tracing.api.photo_check_router import router as photo_check_router
from app.knowledge_tracing.api.submissions_router import router as submissions_router
from app.knowledge_tracing.api.vision_router import router as vision_router
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.learner_state.api.router import router as learner_state_router
from app.shared.learner.router import router as learner_router

logger = logging.getLogger("mindbridge")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load the trained knowledge model once, at startup. A missing file must not stop the
    # rest of the API, so it is logged and the mastery endpoints answer 503 instead.
    try:
        model = get_knowledge_model()
        logger.info("knowledge model loaded: %s", model.version)
    except Exception:
        logger.warning("knowledge model not loaded; mastery endpoints will return 503", exc_info=True)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_v1_prefix}/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(learner_router, prefix=settings.api_v1_prefix)
app.include_router(learner_state_router, prefix=settings.api_v1_prefix)
app.include_router(attempts_router, prefix=settings.api_v1_prefix)
app.include_router(mastery_router, prefix=settings.api_v1_prefix)
app.include_router(papers_router, prefix=settings.api_v1_prefix)
app.include_router(photo_check_router, prefix=settings.api_v1_prefix)
app.include_router(vision_router, prefix=settings.api_v1_prefix)
app.include_router(submissions_router, prefix=settings.api_v1_prefix)
