from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Media Indexer"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://media_indexer:change-me@localhost:5432/media_indexer"
    session_secret: str = "change-me"
    session_cookie_name: str = "media_indexer_session"
    admin_username: str = "admin"
    admin_password: str = "change-me"
    curator_username: str = "curator"
    curator_password: str = "change-me"
    guest_username: str = "guest"
    guest_password: str = "change-me"
    frontend_origin: str = "http://localhost:3000"
    allowed_source_roots: str = "/data/sources"
    upload_source_name: str = "upload"
    upload_source_root: str = "/data/sources/upload"
    preview_root: str = "/workspace/storage/previews"
    access_token_ttl_seconds: int = 60 * 60 * 24
    cookie_secure: bool = False
    worker_poll_interval_seconds: int = 5
    max_thumbnail_size: int = 512
    deepzoom_tile_size: int = 256
    deepzoom_tile_overlap: int = 0
    deepzoom_tile_quality: int = 88
    preview_cache_max_mb: int = 2048
    duplicate_phash_threshold: int = 8
    semantic_neighbor_limit: int = 24
    semantic_similarity_threshold: float = 0.22
    clip_enabled: bool = True
    clip_model_id: str = "openai/clip-vit-base-patch32"
    clip_device: str = "cpu"
    nsfw_detector_enabled: bool = True
    nsfw_model_id: str = "Falconsai/nsfw_image_detection"

    @property
    def allowed_source_root_paths(self) -> list[Path]:
        return [
            Path(root.strip()).resolve(strict=False)
            for root in self.allowed_source_roots.split(",")
            if root.strip()
        ]

    @property
    def preview_root_path(self) -> Path:
        return Path(self.preview_root).resolve(strict=False)

    @model_validator(mode="after")
    def reject_insecure_defaults(self) -> "Settings":
        if self.app_env != "development" and self.session_secret.strip() in {"", "change-me", "change-me-in-production"}:
            raise ValueError(
                "SESSION_SECRET must be changed before running outside development."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
