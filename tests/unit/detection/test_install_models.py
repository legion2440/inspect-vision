from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from backend.utils.model_loader import ModelRegistry
from scripts.install_models import install_models, requested_models


class DownloadResponse(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def model_entry(model_id: str, payload: bytes) -> dict[str, object]:
    revision = ("a" if model_id == "selected" else "b") * 40
    return {
        "id": model_id,
        "displayName": model_id.title(),
        "role": "general" if model_id == "selected" else "specialist",
        "domain": "Tests",
        "description": "Installer fixture.",
        "filename": f"{model_id}.pt",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sizeBytes": len(payload),
        "task": "detect",
        "framework": {
            "library": "ultralytics",
            "modelFamily": "YOLOv8",
            "testedVersion": "8.4.78",
        },
        "inputSize": {"width": 640, "height": 640},
        "nativeClasses": ["defect"],
        "confidence": 0.25,
        "iou": 0.5,
        "preprocessingProfile": "standard-color",
        "quality": {"defaultWeight": 1.0, "classWeights": {}},
        "source": {
            "repositoryUrl": "https://example.test/models",
            "downloadUrl": f"https://example.test/models/{revision}/{model_id}.pt",
            "revision": revision,
            "sourceFilename": f"{model_id}.pt",
            "license": "MIT",
            "licenseSourceUrl": "https://example.test/license",
        },
    }


def write_manifest(path: Path, payloads: dict[str, bytes]) -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
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

    assert [(spec.model_id, downloaded) for spec, _path, downloaded in results] == [("selected", True)]
    assert (destination / "selected.pt").read_bytes() == payloads["selected"]
    assert not (destination / "alternative.pt").exists()
    assert not list(destination.glob("*.part"))

    repeated = install_models(
        manifest_path,
        destination_dir=destination,
        opener=lambda _url: pytest.fail("verified checkpoint must not be downloaded"),
    )
    assert repeated[0][2] is False


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
    assert [spec.model_id for spec, _path, _downloaded in results] == ["selected", "alternative"]


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
