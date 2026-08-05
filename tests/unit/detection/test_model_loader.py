from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import backend.utils.model_loader as model_loader_module
from backend.detection.anomalyclip_backend import AnomalyClipBackend
from backend.utils.model_loader import (
    ModelNotFoundError,
    ModelRegistry,
    create_detector,
    get_model_spec,
    verify_model_weight,
)


class CudaUnavailable:
    @staticmethod
    def is_available() -> bool:
        return False


class TorchStub:
    cuda = CudaUnavailable()


def manifest_payload(payload: bytes) -> dict[str, object]:
    revision = "a" * 40
    return {
        "schemaVersion": 3,
        "defaultModelId": "test-model",
        "preprocessingProfiles": {
            "standard-color": {
                "mode": "standard-color",
                "paddingColor": [114, 114, 114],
            },
            "steel-enhanced": {
                "mode": "steel-enhanced",
                "paddingColor": [114, 114, 114],
                "clahe": {"clipLimit": 2.0, "tileGridSize": [8, 8]},
            },
        },
        "models": [
            {
                "id": "test-model",
                "displayName": "Test model",
                "role": "general",
                "domain": "Tests",
                "description": "Fixture model.",
                "backend": "ultralytics",
                "exposed": True,
                "artifacts": [
                    {
                        "id": "checkpoint",
                        "filename": "test.pt",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "sizeBytes": len(payload),
                        "source": {
                            "repositoryUrl": "https://example.com/model",
                            "downloadUrl": f"https://example.com/model/{revision}/test.pt",
                            "revision": revision,
                            "sourceFilename": "test.pt",
                            "license": "MIT",
                            "licenseSourceUrl": "https://example.com/model/license",
                            "licenseScope": "checkpoint",
                        },
                    }
                ],
                "inputSize": {"width": 640, "height": 640},
                "nativeClasses": ["scratch", "dent"],
                "quality": {"defaultWeight": 1.0, "classWeights": {"dent": 1.2}},
                "backendConfig": {
                    "task": "detect",
                    "framework": {
                        "library": "ultralytics",
                        "modelFamily": "YOLOv8",
                        "testedVersion": "8.4.78",
                    },
                    "confidence": 0.3,
                    "iou": 0.45,
                    "preprocessingProfile": "standard-color",
                },
            }
        ],
    }


def _manifest(tmp_path: Path, payload: bytes) -> tuple[Path, Path]:
    models_directory = tmp_path / "models"
    models_directory.mkdir()
    (models_directory / "test.pt").write_bytes(payload)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_payload(payload)),
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path, models_directory


def test_default_model_and_full_contract_are_loaded_from_manifest(tmp_path: Path) -> None:
    manifest_path, _ = _manifest(tmp_path, b"model")

    registry = ModelRegistry(manifest_path)
    spec = registry.get()

    assert registry.default_model_id == "test-model"
    assert spec.model_id == "test-model"
    assert spec.display_name == "Test model"
    assert spec.native_classes == ("scratch", "dent")
    assert spec.preprocessing.profile_id == "standard-color"
    assert spec.class_weights == {"dent": 1.2}


def test_production_registry_hides_anomalyclip_without_changing_public_default() -> None:
    registry = ModelRegistry()

    hidden = registry.get("anomalyclip-general-v1")

    assert registry.default_model_id == "factory-defect-guard-v6-mc"
    assert hidden.backend == "anomalyclip"
    assert hidden.native_classes == ("anomaly",)
    assert hidden.exposed is False
    assert [model.model_id for model in registry.exposed_models] == [
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
    ]
    with pytest.raises(ModelNotFoundError, match="publicly available"):
        registry.get_exposed("anomalyclip-general-v1")


def test_unknown_model_lookup_is_explicit(tmp_path: Path) -> None:
    manifest_path, _ = _manifest(tmp_path, b"model")

    with pytest.raises(ModelNotFoundError, match="not registered"):
        get_model_spec("missing", manifest_path=manifest_path)


def test_manifest_rejects_quality_weight_for_unknown_class(tmp_path: Path) -> None:
    manifest_path, _ = _manifest(tmp_path, b"model")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["models"][0]["quality"]["classWeights"] = {"unknown": 2.0}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")

    with pytest.raises(ValueError, match="unknown classes"):
        ModelRegistry(manifest_path)


def test_create_detector_verifies_weight_and_uses_manifest_tuning(tmp_path: Path) -> None:
    manifest_path, models_directory = _manifest(tmp_path, b"model")

    detector = create_detector(
        manifest_path=manifest_path,
        models_directory=models_directory,
        device="auto",
        torch_module=TorchStub(),
    )

    assert detector.model_id == "test-model"
    assert detector.device.kind == "cpu"
    assert detector.confidence == 0.3
    assert detector.iou == 0.45


def test_create_detector_honors_explicit_weight_path(tmp_path: Path) -> None:
    manifest_path, models_directory = _manifest(tmp_path, b"model")
    explicit_path = tmp_path / "deployment" / "selected.pt"
    explicit_path.parent.mkdir()
    explicit_path.write_bytes((models_directory / "test.pt").read_bytes())

    detector = create_detector(
        manifest_path=manifest_path,
        models_directory=tmp_path / "unused",
        model_path=explicit_path,
        device="cpu",
        torch_module=TorchStub(),
    )

    assert detector.model_path == explicit_path


def test_weight_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest_path, models_directory = _manifest(tmp_path, b"model")
    spec = get_model_spec(manifest_path=manifest_path)
    model_path = models_directory / spec.filename
    model_path.write_bytes(b"other")

    with pytest.raises(ValueError, match="size mismatch|hash mismatch"):
        verify_model_weight(model_path, spec)


def test_create_detector_dispatches_hidden_anomalyclip_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        model_loader_module,
        "verify_model_artifact",
        lambda _path, _artifact: None,
    )

    detector = create_detector(
        "anomalyclip-general-v1",
        artifact_paths={
            "clip-backbone": Path("backbone.pt"),
            "prompt-checkpoint": Path("prompt.pth"),
        },
        device="cpu",
        torch_module=TorchStub(),
        anomalyclip_runtime_loader=lambda _backend: object(),
    )

    assert isinstance(detector, AnomalyClipBackend)
    assert detector.class_names == ("anomaly",)
