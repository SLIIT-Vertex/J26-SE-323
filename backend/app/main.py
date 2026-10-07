from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.shared.learner.router import router as learner_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
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

