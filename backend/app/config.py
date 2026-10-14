from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MindBridge API"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    frontend_origin: str = "http://localhost:5173"

    # Knowledge tracing: storage for question images, papers and photos.
    storage_backend: str = "local"  # local | s3
    local_storage_dir: str = "./data/storage"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_question_prefix: str = ""
    signed_url_seconds: int = 600

    # Knowledge tracing: model and feature spec.
    model_weights_path: str = (
        "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
    )
    feature_spec_path: str = "../shared/feature_spec.json"

    # Knowledge tracing: vision provider used to read answered paper pages.
    vision_provider: str = "mock"  # mock | gemini
    gemini_api_key: str = ""
    gemini_model: str = ""
    vision_confidence_min: float = 0.70
    vision_concurrency: int = 3
    vision_timeout_seconds: int = 90

    # Adaptive Tutor: explicit Task 13B generation provider selection.
    tutor_llm_provider: str = ""  # fake | gemini; blank is intentionally invalid
    tutor_gemini_api_key: str = ""
    tutor_gemini_model: str = ""
    tutor_gemini_timeout_seconds: float = 30.0
    tutor_gemini_max_output_tokens: int = 512
    tutor_gemini_temperature: float = 0.2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
