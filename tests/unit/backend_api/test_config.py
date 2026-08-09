from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import MAX_UPLOAD_BYTES, REPOSITORY_ROOT, Settings


def test_relative_runtime_paths_resolve_from_repository_root() -> None:
    settings = Settings(
        models_dir=Path("backend/models"),
        database_path=Path("runtime/test.sqlite3"),
        media_dir=Path("runtime/media"),
    )

    assert settings.models_dir == (REPOSITORY_ROOT / "backend/models")
    assert settings.database_path == (REPOSITORY_ROOT / "runtime/test.sqlite3")
    assert settings.media_dir == (REPOSITORY_ROOT / "runtime/media")


def test_cors_origins_are_trimmed() -> None:
    settings = Settings(cors_origins=" http://localhost:5173,https://example.test ")

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://example.test",
    ]


@pytest.mark.parametrize("value", ["gpu", "cuda:x", "", "cuda:-1"])
def test_invalid_model_device_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError, match="model_device"):
        Settings(model_device=value)


@pytest.mark.parametrize("value", ["auto", "cpu", "cuda", "cuda:1", "mps"])
def test_supported_model_devices_are_accepted(value: str) -> None:
    assert Settings(model_device=value).model_device == value


def test_upload_limit_may_be_lowered_but_not_raised() -> None:
    assert Settings(max_upload_bytes=1024).max_upload_bytes == 1024

    with pytest.raises(ValidationError):
        Settings(max_upload_bytes=MAX_UPLOAD_BYTES + 1)


def test_settings_load_integer_upload_limit_from_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INSPECT_VISION_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.delenv("INSPECT_VISION_MODEL_DEVICE", raising=False)
    env_file = tmp_path / "runtime.env"
    env_file.write_text(
        "INSPECT_VISION_MAX_UPLOAD_BYTES=10485760\n"
        "INSPECT_VISION_MODEL_DEVICE=cpu\n",
        encoding="utf-8",
        newline="\n",
    )

    settings = Settings(_env_file=env_file)

    assert settings.max_upload_bytes == MAX_UPLOAD_BYTES
    assert settings.model_device == "cpu"


def test_repository_env_example_loads_without_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INSPECT_VISION_MAX_UPLOAD_BYTES", raising=False)
    settings = Settings(_env_file=REPOSITORY_ROOT / ".env.example")

    assert settings.max_upload_bytes == MAX_UPLOAD_BYTES


@pytest.mark.parametrize(
    ("database_path", "media_dir"),
    [
        (Path("runtime"), Path("runtime/media")),
        (Path("runtime/media/inspection.sqlite3"), Path("runtime/media")),
    ],
)
def test_database_and_media_paths_must_not_overlap_in_either_direction(
    database_path: Path,
    media_dir: Path,
) -> None:
    with pytest.raises(ValidationError, match="must not overlap"):
        Settings(database_path=database_path, media_dir=media_dir)
