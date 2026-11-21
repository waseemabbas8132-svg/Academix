from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Academix API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./academix.db"
    secret_key: str = "replace-this-with-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_allowed_origins: list[str] = Field(default_factory=list)
    upload_max_file_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    upload_storage_path: Path = Path(".academix_uploads")
    ai_ollama_base_url: str = "http://127.0.0.1:11434"
    ai_ollama_model: str = "qwen2.5:3b"
    ai_ocr_model: str = "microsoft/trocr-base-handwritten"
    ai_ocr_local_files_only: bool = True
    ai_processing_max_pages: int = Field(default=30, ge=1, le=200)
    ai_processing_max_bytes: int = Field(default=30 * 1024 * 1024, ge=1)
    ai_max_active_jobs: int = Field(default=20, ge=1)
    ai_max_concurrent_jobs: int = Field(default=2, ge=1, le=16)
    ai_max_job_attempts: int = Field(default=3, ge=1, le=10)
    ai_stale_job_timeout_minutes: int = Field(default=30, ge=1, le=1440)
    ai_model_timeout_seconds: int = Field(default=180, ge=1, le=3600)
    ai_ocr_low_confidence_threshold: float = Field(default=0.6, ge=0, le=1)
    ai_similarity_max_peers: int = Field(default=20, ge=1, le=200)
    ai_similarity_max_segments: int = Field(default=500, ge=1, le=10000)
    ai_similarity_max_tokens: int = Field(default=1200, ge=100, le=10000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
