"""Manifest-backed model registry, construction, and integrity checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from backend.detection.base import DetectorBackend
from backend.detection.device import DeviceInfo, select_device
from backend.detection.ultralytics_backend import ModelFactory, UltralyticsBackend


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
DEFAULT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/model-manifest.schema.json"
DEFAULT_MODELS_DIRECTORY = REPOSITORY_ROOT / "backend/models"


class ModelNotFoundError(LookupError):
    """Raised when an API caller requests an unknown or hidden model ID."""


class ModelNotInstalledError(RuntimeError):
    """Raised when a registered checkpoint is missing or fails integrity checks."""


class ProductNameRequiredError(ValueError):
    """Raised when a category-guided model is called without a product name."""


@dataclass(frozen=True, slots=True)
class PreprocessingProfileSpec:
    profile_id: str
    mode: str
    padding_color: tuple[int, int, int]
    clahe_clip_limit: float | None = None
    clahe_tile_grid_size: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class ArtifactSourceSpec:
    repository_url: str
    download_url: str
    revision: str
    source_filename: str
    license: str
    license_source_url: str
    license_scope: str


@dataclass(frozen=True, slots=True)
class ModelArtifactSpec:
    artifact_id: str
    filename: str
    sha256: str
    size_bytes: int
    source: ArtifactSourceSpec


@dataclass(frozen=True, slots=True)
class TrackedFileSpec:
    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class UltralyticsConfigSpec:
    task: str
    model_family: str
    tested_version: str
    confidence: float
    iou: float
    preprocessing: PreprocessingProfileSpec


@dataclass(frozen=True, slots=True)
class AnomalyClipConfigSpec:
    task: str
    source_commit: str
    profile_id: str
    normalization_mean: tuple[float, float, float]
    normalization_std: tuple[float, float, float]
    features_list: tuple[int, ...]
    feature_map_layers: tuple[int, ...]
    dpam_layer: int
    prompt_length: int
    prompt_depth: int
    prompt_embedding_length: int
    gaussian_sigma: float
    map_threshold: float
    morphology_kernel: str
    morphology_kernel_size: int
    open_iterations: int
    close_iterations: int
    min_component_area_ratio: float
    merge_distance_px: int
    score_calibration: TrackedFileSpec


@dataclass(frozen=True, slots=True)
class BayesPflConfigSpec:
    task: str
    source_commit: str
    profile_id: str
    normalization_mean: tuple[float, float, float]
    normalization_std: tuple[float, float, float]
    features_list: tuple[int, ...]
    num_flows: int
    prompt_context_len: int
    prompt_num: int
    prompt_state_len: int
    sample_num: int
    seed: int
    gaussian_sigma: float
    map_threshold: float
    min_component_area_ratio: float
    bbox_padding_ratio: float


BackendConfigSpec = UltralyticsConfigSpec | AnomalyClipConfigSpec | BayesPflConfigSpec


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    display_name: str
    role: str
    domain: str
    description: str
    backend: str
    exposed: bool
    artifacts: tuple[ModelArtifactSpec, ...]
    image_size: int
    native_classes: tuple[str, ...]
    quality_default_weight: float
    quality_class_weights: tuple[tuple[str, float], ...]
    backend_config: BackendConfigSpec

    @property
    def classes(self) -> tuple[str, ...]:
        return self.native_classes

    @property
    def class_weights(self) -> dict[str, float]:
        return dict(self.quality_class_weights)

    @property
    def task(self) -> str:
        return self.backend_config.task

    @property
    def preprocessing(self) -> PreprocessingProfileSpec:
        if isinstance(self.backend_config, UltralyticsConfigSpec):
            return self.backend_config.preprocessing
        return PreprocessingProfileSpec(
            profile_id=self.backend_config.profile_id,
            mode=self.backend_config.profile_id,
            padding_color=(0, 0, 0),
        )

    @property
    def confidence(self) -> float:
        if isinstance(self.backend_config, UltralyticsConfigSpec):
            return self.backend_config.confidence
        return self.backend_config.map_threshold

    @property
    def iou(self) -> float:
        if isinstance(self.backend_config, UltralyticsConfigSpec):
            return self.backend_config.iou
        return 0.0

    @property
    def requires_product_name(self) -> bool:
        return isinstance(self.backend_config, BayesPflConfigSpec)

    def artifact(self, artifact_id: str) -> ModelArtifactSpec:
        try:
            return next(item for item in self.artifacts if item.artifact_id == artifact_id)
        except StopIteration as error:
            raise ValueError(
                f"Model {self.model_id} has no artifact named {artifact_id}"
            ) from error

    @property
    def primary_artifact(self) -> ModelArtifactSpec:
        return self.artifacts[0]

    @property
    def filename(self) -> str:
        return self.primary_artifact.filename

    @property
    def sha256(self) -> str:
        return self.primary_artifact.sha256

    @property
    def size_bytes(self) -> int:
        return self.primary_artifact.size_bytes

    @property
    def download_url(self) -> str:
        return self.primary_artifact.source.download_url

    @property
    def revision(self) -> str:
        return self.primary_artifact.source.revision

    @property
    def license(self) -> str:
        return self.primary_artifact.source.license


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
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Model manifest IDs must be unique")
    default_id = manifest["defaultModelId"]
    if default_id not in model_ids:
        raise ValueError("defaultModelId must reference a registered model")
    default_model = next(model for model in models if model["id"] == default_id)
    if not default_model["exposed"]:
        raise ValueError("defaultModelId must reference an exposed model")

    artifact_filenames = [
        artifact["filename"] for model in models for artifact in model["artifacts"]
    ]
    if len(artifact_filenames) != len(set(artifact_filenames)):
        raise ValueError("Model artifact filenames must be globally unique")

    profiles = manifest["preprocessingProfiles"]
    for profile_id, profile in profiles.items():
        if profile["mode"] != profile_id:
            raise ValueError(f"Preprocessing profile key/mode mismatch: {profile_id}")

    for model in models:
        model_id = model["id"]
        input_size = model["inputSize"]
        if input_size["width"] != input_size["height"]:
            raise ValueError(f"Model {model_id} requires a square input")
        native_classes = set(model["nativeClasses"])
        unknown_weights = set(model["quality"]["classWeights"]) - native_classes
        if unknown_weights:
            raise ValueError(
                f"Quality weights for {model_id} reference unknown classes: "
                f"{', '.join(sorted(unknown_weights))}"
            )
        artifact_ids = [artifact["id"] for artifact in model["artifacts"]]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError(f"Artifact IDs must be unique within model {model_id}")
        for artifact in model["artifacts"]:
            source = artifact["source"]
            if source["revision"] not in source["downloadUrl"]:
                raise ValueError(
                    f"Download URL for {model_id}/{artifact['id']} must contain its pinned revision"
                )

        backend = model["backend"]
        backend_config = model["backendConfig"]
        if backend == "ultralytics":
            profile_id = backend_config["preprocessingProfile"]
            if profile_id not in profiles:
                raise ValueError(f"Unknown preprocessing profile for {model_id}: {profile_id}")
            if artifact_ids != ["checkpoint"]:
                raise ValueError(
                    f"Ultralytics model {model_id} must have exactly one checkpoint artifact"
                )
        elif backend == "anomalyclip":
            if tuple(model["nativeClasses"]) != ("anomaly",):
                raise ValueError("AnomalyCLIP models must expose exactly the native class 'anomaly'")
            if set(artifact_ids) != {"clip-backbone", "prompt-checkpoint"}:
                raise ValueError(
                    f"AnomalyCLIP model {model_id} requires backbone and prompt artifacts"
                )
            resize = backend_config["preprocessing"]["resize"]
            if resize["width"] != input_size["width"] or resize["height"] != input_size["height"]:
                raise ValueError(
                    f"AnomalyCLIP model {model_id} inputSize must match its stretch resize"
                )
        elif backend == "bayespfl":
            if tuple(model["nativeClasses"]) != ("anomaly",):
                raise ValueError("Bayes-PFL models must expose exactly the native class 'anomaly'")
            if set(artifact_ids) != {"clip-backbone", "bayes-checkpoint"}:
                raise ValueError(
                    f"Bayes-PFL model {model_id} requires backbone and Bayes checkpoint artifacts"
                )
            resize = backend_config["preprocessing"]["resize"]
            if resize["width"] != input_size["width"] or resize["height"] != input_size["height"]:
                raise ValueError(
                    f"Bayes-PFL model {model_id} inputSize must match its stretch resize"
                )
        else:
            raise ValueError(f"Unsupported model backend: {backend}")


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


def _artifact_spec(raw: dict[str, Any]) -> ModelArtifactSpec:
    source = raw["source"]
    return ModelArtifactSpec(
        artifact_id=raw["id"],
        filename=raw["filename"],
        sha256=raw["sha256"],
        size_bytes=int(raw["sizeBytes"]),
        source=ArtifactSourceSpec(
            repository_url=source["repositoryUrl"],
            download_url=source["downloadUrl"],
            revision=source["revision"],
            source_filename=source["sourceFilename"],
            license=source["license"],
            license_source_url=source["licenseSourceUrl"],
            license_scope=source["licenseScope"],
        ),
    )


def _backend_config(
    model: dict[str, Any],
    profiles: dict[str, Any],
    repository_root: Path,
) -> BackendConfigSpec:
    raw = model["backendConfig"]
    backend = model["backend"]
    if backend == "ultralytics":
        profile_id = raw["preprocessingProfile"]
        framework = raw["framework"]
        return UltralyticsConfigSpec(
            task=raw["task"],
            model_family=framework["modelFamily"],
            tested_version=framework["testedVersion"],
            confidence=float(raw["confidence"]),
            iou=float(raw["iou"]),
            preprocessing=_profile_spec(profile_id, profiles[profile_id]),
        )
    if backend == "anomalyclip":
        preprocessing = raw["preprocessing"]
        prompt = raw["prompt"]
        postprocessing = raw["postprocessing"]
        morphology = postprocessing["morphology"]
        calibration = raw["scoreCalibration"]
        return AnomalyClipConfigSpec(
            task=raw["task"],
            source_commit=raw["sourceCommit"],
            profile_id=preprocessing["profileId"],
            normalization_mean=tuple(float(value) for value in preprocessing["normalization"]["mean"]),
            normalization_std=tuple(float(value) for value in preprocessing["normalization"]["std"]),
            features_list=tuple(int(value) for value in raw["featuresList"]),
            feature_map_layers=tuple(int(value) for value in raw["featureMapLayers"]),
            dpam_layer=int(raw["dpamLayer"]),
            prompt_length=int(prompt["promptLength"]),
            prompt_depth=int(prompt["learnableTextEmbeddingDepth"]),
            prompt_embedding_length=int(prompt["learnableTextEmbeddingLength"]),
            gaussian_sigma=float(raw["gaussianSigma"]),
            map_threshold=float(postprocessing["mapThreshold"]),
            morphology_kernel=morphology["kernel"],
            morphology_kernel_size=int(morphology["kernelSize"]),
            open_iterations=int(morphology["openIterations"]),
            close_iterations=int(morphology["closeIterations"]),
            min_component_area_ratio=float(postprocessing["minComponentAreaRatio"]),
            merge_distance_px=int(postprocessing["mergeDistancePx"]),
            score_calibration=TrackedFileSpec(
                path=(repository_root / calibration["path"]).resolve(),
                sha256=calibration["sha256"],
                size_bytes=int(calibration["sizeBytes"]),
            ),
        )

    preprocessing = raw["preprocessing"]
    postprocessing = raw["postprocessing"]
    return BayesPflConfigSpec(
        task=raw["task"],
        source_commit=raw["sourceCommit"],
        profile_id=preprocessing["profileId"],
        normalization_mean=tuple(float(value) for value in preprocessing["normalization"]["mean"]),
        normalization_std=tuple(float(value) for value in preprocessing["normalization"]["std"]),
        features_list=tuple(int(value) for value in raw["featuresList"]),
        num_flows=int(raw["numFlows"]),
        prompt_context_len=int(raw["promptContextLen"]),
        prompt_num=int(raw["promptNum"]),
        prompt_state_len=int(raw["promptStateLen"]),
        sample_num=int(raw["sampleNum"]),
        seed=int(raw["seed"]),
        gaussian_sigma=float(raw["gaussianSigma"]),
        map_threshold=float(postprocessing["mapThreshold"]),
        min_component_area_ratio=float(postprocessing["minComponentAreaRatio"]),
        bbox_padding_ratio=float(postprocessing["bboxPaddingRatio"]),
    )


def _model_spec(
    model: dict[str, Any],
    profiles: dict[str, Any],
    repository_root: Path,
) -> ModelSpec:
    return ModelSpec(
        model_id=model["id"],
        display_name=model["displayName"],
        role=model["role"],
        domain=model["domain"],
        description=model["description"],
        backend=model["backend"],
        exposed=bool(model["exposed"]),
        artifacts=tuple(_artifact_spec(artifact) for artifact in model["artifacts"]),
        image_size=int(model["inputSize"]["width"]),
        native_classes=tuple(model["nativeClasses"]),
        quality_default_weight=float(model["quality"]["defaultWeight"]),
        quality_class_weights=tuple(
            (class_name, float(weight))
            for class_name, weight in model["quality"]["classWeights"].items()
        ),
        backend_config=_backend_config(model, profiles, repository_root),
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
        self.repository_root = (
            REPOSITORY_ROOT
            if self.manifest_path == DEFAULT_MANIFEST_PATH.resolve()
            else self.manifest_path.parent
        )
        manifest = load_model_manifest(self.manifest_path, schema_path=schema_path)
        self.default_model_id = str(manifest["defaultModelId"])
        profiles = manifest["preprocessingProfiles"]
        self._models = tuple(
            _model_spec(model, profiles, self.repository_root) for model in manifest["models"]
        )
        self._by_id = {model.model_id: model for model in self._models}

    @property
    def models(self) -> tuple[ModelSpec, ...]:
        return self._models

    @property
    def exposed_models(self) -> tuple[ModelSpec, ...]:
        return tuple(model for model in self._models if model.exposed)

    def get(self, model_id: str | None = None) -> ModelSpec:
        resolved_id = model_id or self.default_model_id
        try:
            return self._by_id[resolved_id]
        except KeyError as error:
            raise ModelNotFoundError(f"Model is not registered: {resolved_id}") from error

    def get_exposed(self, model_id: str | None = None) -> ModelSpec:
        spec = self.get(model_id)
        if not spec.exposed:
            raise ModelNotFoundError(f"Model is not publicly available: {spec.model_id}")
        return spec

    def is_default(self, model_id: str) -> bool:
        return model_id == self.default_model_id


def get_model_spec(
    model_id: str | None = None,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> ModelSpec:
    return ModelRegistry(manifest_path).get(model_id)


def verify_model_artifact(path: Path, artifact: ModelArtifactSpec) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Model artifact is missing: {path}")
    if path.stat().st_size != artifact.size_bytes:
        raise ValueError(f"Model artifact size mismatch for {artifact.artifact_id}")
    digest = hashlib.sha256()
    with path.open("rb") as binary_file:
        for chunk in iter(lambda: binary_file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = digest.hexdigest()
    if actual_hash != artifact.sha256:
        raise ValueError(
            f"Model artifact hash mismatch for {artifact.artifact_id}: "
            f"expected {artifact.sha256}, got {actual_hash}"
        )


def verify_model_weight(path: Path, spec: ModelSpec) -> None:
    verify_model_artifact(path, spec.primary_artifact)


def _verify_tracked_file(spec: TrackedFileSpec, label: str) -> None:
    if not spec.path.is_file():
        raise FileNotFoundError(f"{label} is missing: {spec.path}")
    if spec.path.stat().st_size != spec.size_bytes:
        raise ValueError(f"{label} size mismatch")
    digest = hashlib.sha256(spec.path.read_bytes()).hexdigest()
    if digest != spec.sha256:
        raise ValueError(f"{label} hash mismatch")


def model_artifact_paths(models_directory: Path, spec: ModelSpec) -> dict[str, Path]:
    return {
        artifact.artifact_id: models_directory / artifact.filename
        for artifact in spec.artifacts
    }


def model_is_installed(models_directory: Path, spec: ModelSpec) -> bool:
    try:
        paths = model_artifact_paths(models_directory, spec)
        for artifact in spec.artifacts:
            verify_model_artifact(paths[artifact.artifact_id], artifact)
        if isinstance(spec.backend_config, AnomalyClipConfigSpec):
            _verify_tracked_file(spec.backend_config.score_calibration, "Score calibration")
        elif isinstance(spec.backend_config, BayesPflConfigSpec):
            from backend.detection.bayespfl_runtime import verify_bayespfl_runtime

            verify_bayespfl_runtime()
    except (FileNotFoundError, ValueError):
        return False
    return True


def create_detector(
    model_id: str | None = None,
    *,
    model_path: Path | None = None,
    artifact_paths: dict[str, Path] | None = None,
    device: str = "auto",
    confidence: float | None = None,
    iou: float | None = None,
    product_name: str | None = None,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    models_directory: Path = DEFAULT_MODELS_DIRECTORY,
    registry: ModelRegistry | None = None,
    torch_module: Any | None = None,
    model_factory: ModelFactory | None = None,
    anomalyclip_runtime_loader: Any | None = None,
    bayespfl_source_dir: Path | None = None,
) -> DetectorBackend:
    active_registry = registry or ModelRegistry(manifest_path)
    spec = active_registry.get(model_id)
    resolved_paths = artifact_paths or model_artifact_paths(models_directory, spec)
    if model_path is not None:
        if spec.backend != "ultralytics":
            raise ValueError("model_path override is supported only for Ultralytics models")
        resolved_paths = dict(resolved_paths)
        resolved_paths[spec.primary_artifact.artifact_id] = model_path
    for artifact in spec.artifacts:
        try:
            path = resolved_paths[artifact.artifact_id]
        except KeyError as error:
            raise ValueError(f"Missing path for model artifact: {artifact.artifact_id}") from error
        verify_model_artifact(path, artifact)
    device_info: DeviceInfo = select_device(device, torch_module=torch_module)

    if isinstance(spec.backend_config, UltralyticsConfigSpec):
        config = spec.backend_config
        return UltralyticsBackend(
            model_id=spec.model_id,
            model_path=resolved_paths[spec.primary_artifact.artifact_id],
            device=device_info,
            image_size=spec.image_size,
            confidence=config.confidence if confidence is None else confidence,
            iou=config.iou if iou is None else iou,
            expected_class_names=spec.native_classes,
            model_factory=model_factory,
        )

    if isinstance(spec.backend_config, AnomalyClipConfigSpec):
        from backend.detection.anomalyclip_backend import (
            AnomalyClipBackend,
            AnomalyClipBackendConfig,
            FileIntegrity,
        )

        config = spec.backend_config
        calibration = config.score_calibration
        _verify_tracked_file(calibration, "AnomalyCLIP score calibration")
        backbone = spec.artifact("clip-backbone")
        prompt = spec.artifact("prompt-checkpoint")
        return AnomalyClipBackend(
            model_id=spec.model_id,
            backbone_path=resolved_paths[backbone.artifact_id],
            prompt_path=resolved_paths[prompt.artifact_id],
            calibration_path=calibration.path,
            backbone_integrity=FileIntegrity(backbone.size_bytes, backbone.sha256),
            prompt_integrity=FileIntegrity(prompt.size_bytes, prompt.sha256),
            calibration_integrity=FileIntegrity(calibration.size_bytes, calibration.sha256),
            config=AnomalyClipBackendConfig(
                resize_width=spec.image_size,
                resize_height=spec.image_size,
                normalization_mean=config.normalization_mean,
                normalization_std=config.normalization_std,
                features_list=config.features_list,
                feature_map_layers=config.feature_map_layers,
                dpam_layer=config.dpam_layer,
                prompt_length=config.prompt_length,
                prompt_depth=config.prompt_depth,
                prompt_embedding_length=config.prompt_embedding_length,
                gaussian_sigma=config.gaussian_sigma,
                map_threshold=config.map_threshold,
                morphology_kernel=config.morphology_kernel,
                morphology_kernel_size=config.morphology_kernel_size,
                open_iterations=config.open_iterations,
                close_iterations=config.close_iterations,
                min_component_area_ratio=config.min_component_area_ratio,
                merge_distance_px=config.merge_distance_px,
            ),
            device=device_info,
            expected_class_names=spec.native_classes,
            runtime_loader=anomalyclip_runtime_loader,
        )

    config = spec.backend_config
    assert isinstance(config, BayesPflConfigSpec)
    normalized_product = (product_name or "").strip()
    if not normalized_product:
        raise ProductNameRequiredError("Product name is required for this detection model")

    from backend.detection.bayespfl_backend import BayesPflBackend, BayesPflConfig
    from backend.detection.bayespfl_runtime import BAYESPFL_RUNTIME_DIR, verify_bayespfl_runtime

    source_dir = (bayespfl_source_dir or BAYESPFL_RUNTIME_DIR).resolve()
    verify_bayespfl_runtime(source_dir)
    backbone = spec.artifact("clip-backbone")
    checkpoint = spec.artifact("bayes-checkpoint")
    return BayesPflBackend(
        model_id=spec.model_id,
        source_dir=source_dir,
        backbone_path=resolved_paths[backbone.artifact_id],
        checkpoint_path=resolved_paths[checkpoint.artifact_id],
        product_name=normalized_product,
        device=device_info,
        config=BayesPflConfig(
            image_size=spec.image_size,
            features_list=config.features_list,
            num_flows=config.num_flows,
            prompt_context_len=config.prompt_context_len,
            prompt_num=config.prompt_num,
            prompt_state_len=config.prompt_state_len,
            sample_num=config.sample_num,
            seed=config.seed,
            gaussian_sigma=config.gaussian_sigma,
            map_threshold=(config.map_threshold if confidence is None else confidence),
            min_component_area_ratio=config.min_component_area_ratio,
            bbox_padding_ratio=config.bbox_padding_ratio,
        ),
    )
