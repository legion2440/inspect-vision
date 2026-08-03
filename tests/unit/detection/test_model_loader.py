from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.utils.model_loader import create_detector, get_model_spec, verify_model_weight


class CudaUnavailable:
    @staticmethod
    def is_available() -> bool:
        return False


class TorchStub:
    cuda = CudaUnavailable()


def _manifest(tmp_path: Path, payload: bytes) -> tuple[Path, Path]:
    models_directory = tmp_path / "models"
    models_directory.mkdir()
    model_path = models_directory / "test.pt"
    model_path.write_bytes(payload)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "selectedModelId": "test-model",
                "models": [
                    {
                        "id": "test-model",
                        "filename": "test.pt",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "sizeBytes": len(payload),
                        "task": "detect",
                        "inputSize": {"width": 640, "height": 640},
                        "classes": ["scratch", "dent"],
                    }
                ],
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path, models_directory


def test_selected_model_is_loaded_from_manifest(tmp_path: Path) -> None:
    manifest_path, _ = _manifest(tmp_path, b"model")

    spec = get_model_spec(manifest_path=manifest_path)

    assert spec.model_id == "test-model"
    assert spec.classes == ("scratch", "dent")


def test_create_detector_verifies_weight_and_uses_cpu(tmp_path: Path) -> None:
    manifest_path, models_directory = _manifest(tmp_path, b"model")

    detector = create_detector(
        manifest_path=manifest_path,
        models_directory=models_directory,
        device="auto",
        torch_module=TorchStub(),
    )

    assert detector.model_id == "test-model"
    assert detector.device.kind == "cpu"


def test_weight_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest_path, models_directory = _manifest(tmp_path, b"model")
    spec = get_model_spec(manifest_path=manifest_path)
    model_path = models_directory / spec.filename
    model_path.write_bytes(b"other")

    with pytest.raises(ValueError, match="size mismatch|hash mismatch"):
        verify_model_weight(model_path, spec)
