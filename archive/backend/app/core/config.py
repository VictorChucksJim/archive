"""
Application configuration.

All configuration is loaded from environment variables. Nothing sensitive
is hardcoded. See .env.example at the repo root for the full list of
variables and sane local-development defaults.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://archive:archive@localhost:5432/archive"

    # JWT / sessions
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Object storage (S3-compatible: AWS S3, Backblaze B2, Cloudflare R2, Wasabi, MinIO)
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    # Optional: only needed when the browser cannot resolve the same
    # hostname the backend uses internally (e.g. local Docker Compose,
    # where the backend talks to "minio" but the browser needs
    # "localhost"). Presigned URLs are generated against this endpoint
    # while all other S3 calls use STORAGE_ENDPOINT. Leave unset in
    # production where a single public endpoint serves both.
    STORAGE_PUBLIC_ENDPOINT: str | None = None
    STORAGE_REGION: str = "us-east-1"
    STORAGE_BUCKET: str = "archive-dev"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_USE_PATH_STYLE: bool = True  # required for MinIO / most S3-compatible providers
    STORAGE_PRESIGNED_UPLOAD_EXPIRE_SECONDS: int = 60 * 10   # 10 minutes
    STORAGE_PRESIGNED_DOWNLOAD_EXPIRE_SECONDS: int = 60 * 5  # 5 minutes

    # Quota
    DEFAULT_QUOTA_BYTES: int = 1_099_511_627_776  # 1 TB

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate limiting (auth endpoints)
    AUTH_RATE_LIMIT: str = "10/minute"

    # Uploads
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB per-file ceiling for v0.1
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "application/pdf",
        "text/plain", "text/csv",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/json",
        "video/mp4",
        "audio/mpeg",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
