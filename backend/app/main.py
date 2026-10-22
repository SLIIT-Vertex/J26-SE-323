import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware

from app.adaptive_tutor.api.router import router as adaptive_tutor_router
from app.config import get_settings
from app.gamification.api.learning_flow_router import (
    development_router as development_learning_flow_router,
)
from app.gamification.api.learning_flow_router import legacy_router as legacy_learning_flow_router
from app.gamification.api.learning_flow_router import router as learning_flow_router
from app.gamification.api.research_dashboard_router import router as research_dashboard_router
from app.gamification.api.router import register_play_errors
from app.gamification.api.router import router as gamification_router
from app.gamification.application.delivery import METRICS, privacy_log
from app.knowledge_tracing.api.attempts_router import router as attempts_router
from app.knowledge_tracing.api.mastery_router import router as mastery_router
from app.knowledge_tracing.api.papers_router import router as papers_router
from app.knowledge_tracing.api.photo_check_router import router as photo_check_router
from app.knowledge_tracing.api.report_router import router as report_router
from app.knowledge_tracing.api.submissions_router import router as submissions_router
from app.knowledge_tracing.api.vision_router import router as vision_router
from app.knowledge_tracing.infrastructure.ml.service import get_knowledge_model
from app.learner_state.api.router import router as learner_state_router
from app.shared.learner.router import router as learner_router

logger = logging.getLogger("mindbridge")
settings = get_settings()


def _regrade_interrupted_pages() -> None:
    """Pages left in "grading" by a restart are put back to "uploaded" and marked again."""
    try:
        from threading import Thread

        from app.knowledge_tracing.api.submissions_router import make_submission_service
        from app.knowledge_tracing.application.recovery import AT_STARTUP, recover_stuck_grading
        from app.knowledge_tracing.infrastructure.db.submission_repository import (
            SqlAlchemySubmissionRepository,
        )
        from app.knowledge_tracing.infrastructure.storage import create_paper_storage
        from app.shared.database.session import SessionLocal

        storage = create_paper_storage(get_settings())
        with SessionLocal() as session:
            ids = recover_stuck_grading(
                SqlAlchemySubmissionRepository(session), stuck_after=AT_STARTUP
            )

        def regrade() -> None:
            for submission_id in ids:
                with SessionLocal() as session:
                    make_submission_service(session, storage).grade(submission_id)

        if ids:
            Thread(target=regrade, name="regrade-interrupted", daemon=True).start()
    except Exception:
        logger.warning("could not recover interrupted marking", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load the trained knowledge model once, at startup. A missing file must not stop the
    # rest of the API, so it is logged and the mastery endpoints answer 503 instead.
    try:
        model = get_knowledge_model()
        logger.info("knowledge model loaded: %s", model.version)
    except Exception:
        logger.warning(
            "knowledge model not loaded; mastery endpoints will return 503",
            exc_info=True,
        )
    _regrade_interrupted_pages()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
_local_frontend = settings.frontend_origin.startswith(("http://localhost", "http://127.0.0.1"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    # Local web dev servers, plus the iOS/Android Capacitor shell (capacitor://localhost).
    allow_origin_regex=(
        r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|capacitor://localhost)$"
        if _local_frontend
        else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_v1_prefix}/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{settings.api_v1_prefix}/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    return {"status": "ok", "child_delivery": "blocked_pending_approved_content"}


@app.middleware("http")
async def observe_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith(f"{settings.api_v1_prefix}/"):
        elapsed_ms = (time.perf_counter() - started) * 1000
        METRICS.observe(
            status_code=response.status_code, latency_ms=elapsed_ms, span=request.url.path
        )
        privacy_log(
            "http",
            path=request.url.path,
            status_code=response.status_code,
            correlation_id=response.headers.get("x-correlation-id"),
        )
    return response


app.include_router(learner_router, prefix=settings.api_v1_prefix)
app.include_router(learner_state_router, prefix=settings.api_v1_prefix)
app.include_router(attempts_router, prefix=settings.api_v1_prefix)
app.include_router(mastery_router, prefix=settings.api_v1_prefix)
app.include_router(papers_router, prefix=settings.api_v1_prefix)
app.include_router(photo_check_router, prefix=settings.api_v1_prefix)
app.include_router(vision_router, prefix=settings.api_v1_prefix)
app.include_router(submissions_router, prefix=settings.api_v1_prefix)
app.include_router(report_router, prefix=settings.api_v1_prefix)
app.include_router(gamification_router, prefix=settings.api_v1_prefix)
app.include_router(learning_flow_router, prefix=settings.api_v1_prefix)
app.include_router(research_dashboard_router, prefix=settings.api_v1_prefix)
app.include_router(development_learning_flow_router, prefix=settings.api_v1_prefix)
app.include_router(legacy_learning_flow_router, prefix=settings.api_v1_prefix)
app.include_router(adaptive_tutor_router, prefix=settings.api_v1_prefix)
register_play_errors(app)
