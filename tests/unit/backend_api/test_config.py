from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.config import REPOSITORY_ROOT, Settings


def test_relative_runtime_paths_resolve_from_repository_root() -> None:
    settings = Settings(
        model_path=Path("backend/models/defect_neu_yolov8.pt"),
        database_path=Path("runtime/test.sqlite3"),
        media_dir=Path("runtime/media"),
    )

    assert settings.model_path == (REPOSITORY_ROOT / "backend/models/defect_neu_yolov8.pt")
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


def test_upload_limit_is_the_exact_contract_value() -> None:
    with pytest.raises(ValidationError):
        Settings(max_upload_bytes=1024)
