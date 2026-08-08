from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from backend.utils.model_loader import ModelRegistry, model_is_installed
from scripts.install_models import install_models, requested_models


class DownloadResponse(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def model_entry(
    model_id: str,
    payload: bytes,
    *,
    exposed: bool = True,
) -> dict[str, object]:
    revision = ("a" if model_id == "selected" else "b") * 40
    return {
        "id": model_id,
        "displayName": model_id.title(),
        "role": "general" if model_id == "selected" else "specialist",
        "domain": "Tests",
        "description": "Installer fixture.",
        "backend": "ultralytics",
        "exposed": exposed,
        "artifacts": [
            {
                "id": "checkpoint",
                "filename": f"{model_id}.pt",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "sizeBytes": len(payload),
                "source": {
                    "repositoryUrl": "https://example.test/models",
                    "downloadUrl": f"https://example.test/models/{revision}/{model_id}.pt",
                    "revision": revision,
                    "sourceFilename": f"{model_id}.pt",
                    "license": "MIT",
                    "licenseSourceUrl": "https://example.test/license",
                    "licenseScope": "checkpoint",
                },
            }
        ],
        "inputSize": {"width": 640, "height": 640},
        "nativeClasses": ["defect"],
        "quality": {"defaultWeight": 1.0, "classWeights": {}},
        "backendConfig": {
            "task": "detect",
            "framework": {
                "library": "ultralytics",
                "modelFamily": "YOLOv8",
                "testedVersion": "8.4.78",
            },
            "confidence": 0.25,
            "iou": 0.5,
            "preprocessingProfile": "standard-color",
        },
    }


def anomalyclip_entry(
    payloads: dict[str, bytes],
    calibration: bytes,
) -> dict[str, object]:
    artifact_inputs = (
        ("clip-backbone", "backbone.pt", payloads["clip-backbone"], "a" * 40),
        (
            "prompt-checkpoint",
            "prompt.pth",
            payloads["prompt-checkpoint"],
            "b" * 40,
        ),
    )
    return {
        "id": "anomalyclip",
        "displayName": "AnomalyCLIP",
        "role": "general",
        "domain": "Tests",
        "description": "Two-artifact installer fixture.",
        "backend": "anomalyclip",
        "exposed": True,
        "artifacts": [
            {
                "id": artifact_id,
                "filename": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "sizeBytes": len(payload),
                "source": {
                    "repositoryUrl": "https://example.test/anomalyclip",
                    "downloadUrl": (
                        f"https://example.test/anomalyclip/{revision}/{filename}"
                    ),
                    "revision": revision,
                    "sourceFilename": filename,
                    "license": "MIT",
                    "licenseSourceUrl": "https://example.test/license",
                    "licenseScope": "checkpoint",
                },
            }
            for artifact_id, filename, payload, revision in artifact_inputs
        ],
        "inputSize": {"width": 518, "height": 518},
        "nativeClasses": ["anomaly"],
        "quality": {"defaultWeight": 1.0, "classWeights": {}},
        "backendConfig": {
            "task": "anomaly-localization",
            "sourceCommit": "c" * 40,
            "preprocessing": {
                "profileId": "anomalyclip-stretch",
                "resize": {
                    "mode": "stretch",
                    "width": 518,
                    "height": 518,
                    "interpolation": "bicubic",
                },
                "normalization": {
                    "mean": [0.1, 0.2, 0.3],
                    "std": [0.4, 0.5, 0.6],
                },
            },
            "featuresList": [6, 12, 18, 24],
            "featureMapLayers": [0, 1, 2, 3],
            "dpamLayer": 20,
            "prompt": {
                "className": "object",
                "promptLength": 12,
                "learnableTextEmbeddingDepth": 9,
                "learnableTextEmbeddingLength": 4,
            },
            "gaussianSigma": 4,
            "postprocessing": {
                "mapThreshold": 0.1,
                "morphology": {
                    "kernel": "ellipse",
                    "kernelSize": 3,
                    "openIterations": 1,
                    "closeIterations": 1,
                },
                "minComponentAreaRatio": 0.0005,
                "mergeDistancePx": 6,
            },
            "scoreCalibration": {
                "path": "backend/models/config/calibration.json",
                "sha256": hashlib.sha256(calibration).hexdigest(),
                "sizeBytes": len(calibration),
                "semanticMeaning": (
                    "anomaly confidence score relative to clean calibration artifacts; "
                    "not a class probability"
                ),
            },
        },
    }


def write_manifest(path: Path, payloads: dict[str, bytes]) -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 3,
                "defaultModelId": "selected",
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
                "models": [model_entry(model_id, payload) for model_id, payload in payloads.items()],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_manifest_with_hidden(path: Path, payloads: dict[str, bytes]) -> None:
    manifest = {
        "schemaVersion": 3,
        "defaultModelId": "selected",
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
            model_entry("selected", payloads["selected"]),
            model_entry("hidden", payloads["hidden"], exposed=False),
        ],
    }
    path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")


def write_multi_artifact_manifest(
    path: Path,
    payloads: dict[str, bytes],
    calibration: bytes,
) -> None:
    calibration_path = path.parent / "backend/models/config/calibration.json"
    calibration_path.parent.mkdir(parents=True)
    calibration_path.write_bytes(calibration)
    manifest = {
        "schemaVersion": 3,
        "defaultModelId": "anomalyclip",
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
        "models": [anomalyclip_entry(payloads, calibration)],
    }
    path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
        newline="\n",
    )


def test_installer_default_model_is_atomic_and_idempotent(tmp_path: Path) -> None:
    payloads = {"selected": b"selected checkpoint", "alternative": b"alternative checkpoint"}
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payloads)

    results = install_models(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: DownloadResponse(payloads["selected"]),
    )

    assert [(result.model.model_id, result.downloaded) for result in results] == [("selected", True)]
    assert (destination / "selected.pt").read_bytes() == payloads["selected"]
    assert not (destination / "alternative.pt").exists()
    assert not list(destination.glob("*.part"))

    repeated = install_models(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: pytest.fail("verified checkpoint must not be downloaded"),
    )
    assert repeated[0].downloaded is False


def test_installer_supports_model_and_all_selection(tmp_path: Path) -> None:
    payloads = {"selected": b"selected", "alternative": b"alternative"}
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payloads)
    registry = ModelRegistry(manifest_path)

    assert [spec.model_id for spec in requested_models(registry)] == ["selected"]
    assert [spec.model_id for spec in requested_models(registry, model_id="alternative")] == ["alternative"]
    assert [spec.model_id for spec in requested_models(registry, install_all=True)] == ["selected", "alternative"]

    results = install_models(
        manifest_path,
        destination_dir=destination,
        install_all=True,
        opener=lambda url: DownloadResponse(
            payloads["alternative"] if "alternative.pt" in url else payloads["selected"]
        ),
    )
    assert [result.model.model_id for result in results] == ["selected", "alternative"]


def test_installer_rejects_bad_hash_and_cleans_temporary_file(tmp_path: Path) -> None:
    payloads = {"selected": b"expected bytes", "alternative": b"alternative"}
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_manifest(manifest_path, payloads)

    with pytest.raises(ValueError, match="SHA-256"):
        install_models(
            manifest_path,
            destination_dir=destination,
            opener=lambda _url: DownloadResponse(b"wrong payload!"),
        )

    assert not (destination / "selected.pt").exists()
    assert not list(destination.glob("*.part"))


def test_all_excludes_hidden_model_but_explicit_model_installs_it(tmp_path: Path) -> None:
    payloads = {"selected": b"selected", "hidden": b"hidden"}
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_manifest_with_hidden(manifest_path, payloads)
    registry = ModelRegistry(manifest_path)

    assert [model.model_id for model in requested_models(registry, install_all=True)] == [
        "selected"
    ]
    assert [
        model.model_id for model in requested_models(registry, model_id="hidden")
    ] == ["hidden"]

    results = install_models(
        manifest_path,
        destination_dir=destination,
        model_id="hidden",
        opener=lambda _url: DownloadResponse(payloads["hidden"]),
    )

    assert results[0].model.model_id == "hidden"
    assert (destination / "hidden.pt").read_bytes() == payloads["hidden"]


def test_production_all_intentionally_includes_exposed_anomalyclip() -> None:
    selected = requested_models(ModelRegistry(), install_all=True)

    assert [model.model_id for model in selected] == [
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
        "anomalyclip-general-v1",
    ]


def test_two_artifact_installation_is_idempotent_and_detects_each_corruption(
    tmp_path: Path,
) -> None:
    payloads = {
        "clip-backbone": b"clip backbone bytes",
        "prompt-checkpoint": b"prompt checkpoint bytes",
    }
    calibration = b'{"referenceCount":1,"sortedReferenceComponentMeans":[0.1]}\n'
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_multi_artifact_manifest(manifest_path, payloads, calibration)
    opened_urls: list[str] = []

    def opener(url: str) -> DownloadResponse:
        opened_urls.append(url)
        artifact_id = "prompt-checkpoint" if url.endswith("prompt.pth") else "clip-backbone"
        return DownloadResponse(payloads[artifact_id])

    installed = install_models(
        manifest_path,
        destination_dir=destination,
        opener=opener,
    )
    registry = ModelRegistry(manifest_path)
    spec = registry.get()

    assert [(result.artifact.artifact_id, result.downloaded) for result in installed] == [
        ("clip-backbone", True),
        ("prompt-checkpoint", True),
    ]
    assert len(opened_urls) == 2
    assert model_is_installed(destination, spec) is True

    repeated = install_models(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: pytest.fail("verified artifacts must not be downloaded"),
    )
    assert [result.downloaded for result in repeated] == [False, False]

    for artifact in spec.artifacts:
        corrupt_path = destination / artifact.filename
        original = corrupt_path.read_bytes()
        corrupt_path.write_bytes(b"x" * len(original))
        assert model_is_installed(destination, spec) is False

        opened_urls.clear()
        repaired = install_models(
            manifest_path,
            destination_dir=destination,
            opener=opener,
        )
        assert [result.downloaded for result in repaired] == [
            item.artifact.artifact_id == artifact.artifact_id for item in repaired
        ]
        assert len(opened_urls) == 1
        assert model_is_installed(destination, spec) is True


def test_tracked_calibration_integrity_participates_in_installation_state(
    tmp_path: Path,
) -> None:
    payloads = {
        "clip-backbone": b"clip backbone bytes",
        "prompt-checkpoint": b"prompt checkpoint bytes",
    }
    calibration = b'{"referenceCount":1,"sortedReferenceComponentMeans":[0.1]}\n'
    manifest_path = tmp_path / "manifest.json"
    destination = tmp_path / "models"
    write_multi_artifact_manifest(manifest_path, payloads, calibration)
    install_models(
        manifest_path,
        destination_dir=destination,
        opener=lambda url: DownloadResponse(
            payloads["prompt-checkpoint"]
            if url.endswith("prompt.pth")
            else payloads["clip-backbone"]
        ),
    )
    spec = ModelRegistry(manifest_path).get()
    calibration_path = manifest_path.parent / "backend/models/config/calibration.json"

    assert model_is_installed(destination, spec) is True
    calibration_path.write_bytes(b"x" * len(calibration))
    assert model_is_installed(destination, spec) is False
