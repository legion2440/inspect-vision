"""Environment-backed FastAPI, detection, and persistence settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class Settings(BaseSettings):
    """Single validated runtime contract loaded from INSPECT_VISION_* variables."""

    model_config = SettingsConfigDict(
        env_prefix="INSPECT_VISION_",
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = Field(default=MAX_UPLOAD_BYTES, gt=0, le=MAX_UPLOAD_BYTES)

    model_kind: Literal["ultralytics"] = "ultralytics"
    model_id: str | None = None
    model_path: Path = Path("backend/models/defect_neu_yolov8.pt")
    model_input_size: int = Field(default=640, gt=0)
    model_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    model_iou: float = Field(default=0.5, ge=0.0, le=1.0)
    model_device: str = "auto"
    clahe_clip_limit: float = Field(default=2.0, gt=0.0)
    clahe_tile_grid_size: int = Field(default=8, gt=0)

    database_path: Path = Path("backend/storage/inspections.sqlite3")
    media_dir: Path = Path("backend/storage/media")

    @field_validator("host")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value.strip()

    @field_validator("model_device")
    @classmethod
    def valid_model_device(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"auto", "cpu", "cuda"}:
            return normalized
        if normalized.startswith("cuda:") and normalized[5:].isdigit():
            return normalized
        raise ValueError("model_device must be auto, cpu, cuda, or cuda:N")

    @field_validator("model_id")
    @classmethod
    def valid_optional_model_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("model_id must not be empty")
        return normalized

    @model_validator(mode="after")
    def resolve_runtime_paths(self) -> Settings:
        for field_name in ("model_path", "database_path", "media_dir"):
            path = getattr(self, field_name)
            if not path.is_absolute():
                setattr(self, field_name, (REPOSITORY_ROOT / path).resolve())
            else:
                setattr(self, field_name, path.resolve())
        if (
            self.database_path == self.media_dir
            or self.media_dir in self.database_path.parents
            or self.database_path in self.media_dir.parents
        ):
            raise ValueError("database_path and media_dir must not overlap")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [value.strip() for value in self.cors_origins.split(",") if value.strip()]
        if not origins:
            raise ValueError("at least one CORS origin is required")
        return origins
