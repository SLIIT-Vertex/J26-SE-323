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
    # Generated papers (PDFs) are written here. Kept apart from the question images because
    # the question bank is only read, while papers need write access.
    paper_storage_backend: str = "local"  # local | s3
    # A child can ask for the weekly paper only this many days after joining, so that there is
    # some play history to build it from. 0 turns the rule off (useful when testing).
    paper_min_days_after_joining: int = 7

    # Photos of answered pages (and the question crops) are deleted this many days after upload
    # by scripts/delete_old_photos.py. A page's photos go sooner (7 days) once the parent has
    # opened its report.
    photo_retention_days: int = 30

    # Knowledge tracing: model and feature spec.
    model_weights_path: str = (
        "app/knowledge_tracing/infrastructure/ml/weights/mindbridge_dkt_v2_best.pt"
    )
    feature_spec_path: str = "../shared/feature_spec.json"

    # Knowledge tracing: vision provider used to read answered paper pages.
    vision_provider: str = "mock"  # mock | gemini | openai
    gemini_api_key: str = ""
    gemini_model: str = ""
    vision_second_provider: str = ""  # optional second opinion: mock | gemini | openai (empty = off)
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_max_output_tokens: int = 1024
    # The OpenAI reader (VISION_PROVIDER=openai). There is no default model: name the one you chose.
    openai_api_key: str = ""
    openai_model: str = ""
    openai_base_url: str = "https://api.openai.com/v1"  # or any server with the same protocol
    openai_max_output_tokens: int = 4096  # a thinking model spends part of this before it answers
    openai_image_detail: str = "high"  # low | high | auto: handwriting needs high
    openai_reasoning_effort: str = ""  # empty = not sent; only some models accept it (low, medium...)
    openai_temperature: str = ""  # empty = not sent, the model's own default is used
    # reader_unsure: the parent only sees what the reader could not make sense of.
    # strict: every doubt of the rules also goes to the parent.
    grading_review_policy: str = "reader_unsure"
    # Read a question again when a part came back blank, so one missed pencil mark is not marked
    # as "left blank". Costs one more reader call per blank question.
    grading_recheck_blanks: bool = True
    vision_confidence_min: float = 0.60
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
