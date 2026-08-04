"""Manifest-backed model registry, construction, and integrity checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from backend.detection.device import DeviceInfo, select_device
from backend.detection.ultralytics_backend import ModelFactory, UltralyticsBackend


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
DEFAULT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/model-manifest.schema.json"
DEFAULT_MODELS_DIRECTORY = REPOSITORY_ROOT / "backend/models"


class ModelNotFoundError(LookupError):
    """Raised when an API caller requests an unregistered model ID."""


class ModelNotInstalledError(RuntimeError):
    """Raised when a registered checkpoint is missing or fails integrity checks."""


@dataclass(frozen=True, slots=True)
class PreprocessingProfileSpec:
    profile_id: str
    mode: str
    padding_color: tuple[int, int, int]
    clahe_clip_limit: float | None = None
    clahe_tile_grid_size: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    display_name: str
    role: str
    domain: str
    description: str
    filename: str
    sha256: str
    size_bytes: int
    task: str
    image_size: int
    native_classes: tuple[str, ...]
    confidence: float
    iou: float
    preprocessing: PreprocessingProfileSpec
    quality_default_weight: float
    quality_class_weights: tuple[tuple[str, float], ...]
    download_url: str
    revision: str
    license: str

    @property
    def classes(self) -> tuple[str, ...]:
        """Compatibility alias for the detector backend contract."""

        return self.native_classes

    @property
    def class_weights(self) -> dict[str, float]:
        return dict(self.quality_class_weights)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def validate_model_manifest(
    manifest: dict[str, Any],
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "root"
        raise ValueError(f"Invalid model manifest at {location}: {error.message}")

    models = manifest["models"]
    model_ids = [model["id"] for model in models]
    filenames = [model["filename"] for model in models]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Model manifest IDs must be unique")
    if len(filenames) != len(set(filenames)):
        raise ValueError("Model manifest filenames must be unique")
    if manifest["defaultModelId"] not in model_ids:
        raise ValueError("defaultModelId must reference a registered model")

    profiles = manifest["preprocessingProfiles"]
    for profile_id, profile in profiles.items():
        if profile["mode"] != profile_id:
            raise ValueError(f"Preprocessing profile key/mode mismatch: {profile_id}")

    for model in models:
        model_id = model["id"]
        input_size = model["inputSize"]
        if input_size["width"] != input_size["height"]:
            raise ValueError(f"Model {model_id} requires a square input")
        profile_id = model["preprocessingProfile"]
        if profile_id not in profiles:
            raise ValueError(f"Unknown preprocessing profile for {model_id}: {profile_id}")
        native_classes = set(model["nativeClasses"])
        unknown_weights = set(model["quality"]["classWeights"]) - native_classes
        if unknown_weights:
            raise ValueError(
                f"Quality weights for {model_id} reference unknown classes: "
                f"{', '.join(sorted(unknown_weights))}"
            )
        source = model["source"]
        if source["revision"] not in source["downloadUrl"]:
            raise ValueError(f"Download URL for {model_id} must contain its pinned revision")


def load_model_manifest(
    path: Path = DEFAULT_MANIFEST_PATH,
    *,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    manifest = _load_json(path)
    validate_model_manifest(manifest, schema_path=schema_path)
    return manifest


def _profile_spec(profile_id: str, raw: dict[str, Any]) -> PreprocessingProfileSpec:
    clahe = raw.get("clahe")
    return PreprocessingProfileSpec(
        profile_id=profile_id,
        mode=raw["mode"],
        padding_color=tuple(int(value) for value in raw["paddingColor"]),
        clahe_clip_limit=float(clahe["clipLimit"]) if clahe else None,
        clahe_tile_grid_size=(
            tuple(int(value) for value in clahe["tileGridSize"]) if clahe else None
        ),
    )


def _model_spec(model: dict[str, Any], profiles: dict[str, Any]) -> ModelSpec:
    profile_id = model["preprocessingProfile"]
    return ModelSpec(
        model_id=model["id"],
        display_name=model["displayName"],
        role=model["role"],
        domain=model["domain"],
        description=model["description"],
        filename=model["filename"],
        sha256=model["sha256"],
        size_bytes=int(model["sizeBytes"]),
        task=model["task"],
        image_size=int(model["inputSize"]["width"]),
        native_classes=tuple(model["nativeClasses"]),
        confidence=float(model["confidence"]),
        iou=float(model["iou"]),
        preprocessing=_profile_spec(profile_id, profiles[profile_id]),
        quality_default_weight=float(model["quality"]["defaultWeight"]),
        quality_class_weights=tuple(
            (class_name, float(weight))
            for class_name, weight in model["quality"]["classWeights"].items()
        ),
        download_url=model["source"]["downloadUrl"],
        revision=model["source"]["revision"],
        license=model["source"]["license"],
    )


class ModelRegistry:
    """Validated immutable projection of the tracked model manifest."""

    def __init__(
        self,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        *,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        manifest = load_model_manifest(self.manifest_path, schema_path=schema_path)
        self.default_model_id = str(manifest["defaultModelId"])
        profiles = manifest["preprocessingProfiles"]
        self._models = tuple(_model_spec(model, profiles) for model in manifest["models"])
        self._by_id = {model.model_id: model for model in self._models}

    @property
    def models(self) -> tuple[ModelSpec, ...]:
        return self._models

    def get(self, model_id: str | None = None) -> ModelSpec:
        resolved_id = model_id or self.default_model_id
        try:
            return self._by_id[resolved_id]
        except KeyError as error:
            raise ModelNotFoundError(f"Model is not registered: {resolved_id}") from error

    def is_default(self, model_id: str) -> bool:
        return model_id == self.default_model_id


def get_model_spec(
    model_id: str | None = None,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> ModelSpec:
    return ModelRegistry(manifest_path).get(model_id)


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


def model_is_installed(models_directory: Path, spec: ModelSpec) -> bool:
    try:
        verify_model_weight(models_directory / spec.filename, spec)
    except (FileNotFoundError, ValueError):
        return False
    return True


def create_detector(
    model_id: str | None = None,
    *,
    model_path: Path | None = None,
    device: str = "auto",
    confidence: float | None = None,
    iou: float | None = None,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    models_directory: Path = DEFAULT_MODELS_DIRECTORY,
    registry: ModelRegistry | None = None,
    torch_module: Any | None = None,
    model_factory: ModelFactory | None = None,
) -> UltralyticsBackend:
    active_registry = registry or ModelRegistry(manifest_path)
    spec = active_registry.get(model_id)
    if spec.task != "detect":
        raise ValueError(f"Unsupported model task: {spec.task}")
    resolved_model_path = model_path or (models_directory / spec.filename)
    verify_model_weight(resolved_model_path, spec)
    device_info: DeviceInfo = select_device(device, torch_module=torch_module)
    return UltralyticsBackend(
        model_id=spec.model_id,
        model_path=resolved_model_path,
        device=device_info,
        image_size=spec.image_size,
        confidence=spec.confidence if confidence is None else confidence,
        iou=spec.iou if iou is None else iou,
        expected_class_names=spec.native_classes,
        model_factory=model_factory,
    )
