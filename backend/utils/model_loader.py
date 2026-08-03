"""Manifest-backed construction and integrity checks for detection models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.detection.device import DeviceInfo, select_device
from backend.detection.ultralytics_backend import ModelFactory, UltralyticsBackend


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
DEFAULT_MODELS_DIRECTORY = REPOSITORY_ROOT / "backend/models"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    filename: str
    sha256: str
    size_bytes: int
    task: str
    image_size: int
    classes: tuple[str, ...]


def load_model_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        manifest = json.load(json_file)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("models"), list):
        raise ValueError("Model manifest must contain a models array")
    return manifest


def get_model_spec(
    model_id: str | None = None,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> ModelSpec:
    manifest = load_model_manifest(manifest_path)
    selected_id = model_id or manifest.get("selectedModelId")
    for model in manifest["models"]:
        if model.get("id") == selected_id:
            input_size = model["inputSize"]
            if input_size["width"] != input_size["height"]:
                raise ValueError(f"Model {selected_id} requires a non-square input")
            return ModelSpec(
                model_id=model["id"],
                filename=model["filename"],
                sha256=model["sha256"],
                size_bytes=int(model["sizeBytes"]),
                task=model["task"],
                image_size=int(input_size["width"]),
                classes=tuple(model["classes"]),
            )
    raise KeyError(f"Model is not registered: {selected_id}")


def verify_model_weight(path: Path, spec: ModelSpec) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Model weight is missing: {path}")
    if path.stat().st_size != spec.size_bytes:
        raise ValueError(f"Model size mismatch for {spec.model_id}")
    digest = hashlib.sha256()
    with path.open("rb") as binary_file:
        for chunk in iter(lambda: binary_file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = digest.hexdigest()
    if actual_hash != spec.sha256:
        raise ValueError(
            f"Model hash mismatch for {spec.model_id}: "
            f"expected {spec.sha256}, got {actual_hash}"
        )


def create_detector(
    model_id: str | None = None,
    *,
    device: str = "auto",
    confidence: float = 0.25,
    iou: float = 0.5,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    models_directory: Path = DEFAULT_MODELS_DIRECTORY,
    torch_module: Any | None = None,
    model_factory: ModelFactory | None = None,
) -> UltralyticsBackend:
    spec = get_model_spec(model_id, manifest_path=manifest_path)
    if spec.task != "detect":
        raise ValueError(f"Unsupported model task: {spec.task}")
    model_path = models_directory / spec.filename
    verify_model_weight(model_path, spec)
    device_info: DeviceInfo = select_device(device, torch_module=torch_module)
    return UltralyticsBackend(
        model_id=spec.model_id,
        model_path=model_path,
        device=device_info,
        image_size=spec.image_size,
        confidence=confidence,
        iou=iou,
        expected_class_names=spec.classes,
        model_factory=model_factory,
    )
