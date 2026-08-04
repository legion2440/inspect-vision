"""Lazy multi-model runtime manager for production inspection services."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from backend.utils.model_loader import (
    DEFAULT_MODELS_DIRECTORY,
    ModelNotInstalledError,
    ModelRegistry,
    ModelSpec,
    create_detector,
    model_is_installed,
)
from backend.utils.preprocessing import InspectionPreprocessingConfig

from .base import DetectorBackend
from .dto import InspectionResult
from .service import DetectionService


DetectorFactory = Callable[[ModelSpec], DetectorBackend]


@dataclass(frozen=True, slots=True)
class RegisteredModel:
    spec: ModelSpec
    is_default: bool
    installed: bool


def preprocessing_config(spec: ModelSpec) -> InspectionPreprocessingConfig:
    profile = spec.preprocessing
    if profile.mode == "steel-enhanced":
        if profile.clahe_clip_limit is None or profile.clahe_tile_grid_size is None:
            raise ValueError(f"Incomplete steel-enhanced profile for {spec.model_id}")
        return InspectionPreprocessingConfig(
            input_size=spec.image_size,
            profile="steel-enhanced",
            padding_color=profile.padding_color,
            clahe_clip_limit=profile.clahe_clip_limit,
            clahe_tile_grid_size=profile.clahe_tile_grid_size,
        )
    if profile.mode == "standard-color":
        return InspectionPreprocessingConfig(
            input_size=spec.image_size,
            profile="standard-color",
            padding_color=profile.padding_color,
        )
    raise ValueError(f"Unsupported preprocessing profile: {profile.mode}")


class DetectionRuntimeManager:
    """Resolve, lazy-load, and cache one DetectionService per registered model."""

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        models_directory: Path = DEFAULT_MODELS_DIRECTORY,
        device: str = "auto",
        detector_factory: DetectorFactory | None = None,
    ) -> None:
        self.registry = registry
        self.models_directory = models_directory.resolve()
        self.device = device
        self._detector_factory = detector_factory
        self._services: dict[str, DetectionService] = {}
        self._cache_lock = threading.Lock()

    @property
    def cached_model_ids(self) -> tuple[str, ...]:
        with self._cache_lock:
            return tuple(self._services)

    def registered_models(self) -> tuple[RegisteredModel, ...]:
        return tuple(
            RegisteredModel(
                spec=spec,
                is_default=self.registry.is_default(spec.model_id),
                installed=model_is_installed(self.models_directory, spec),
            )
            for spec in self.registry.models
        )

    def _build_service(self, spec: ModelSpec) -> DetectionService:
        try:
            detector = (
                self._detector_factory(spec)
                if self._detector_factory is not None
                else create_detector(
                    spec.model_id,
                    device=self.device,
                    models_directory=self.models_directory,
                    registry=self.registry,
                )
            )
            detector.load()
        except (FileNotFoundError, ValueError) as error:
            command = f"python scripts/install_models.py --model {spec.model_id}"
            raise ModelNotInstalledError(
                f"Detection model is not installed or failed integrity checks. Run: {command}"
            ) from error

        return DetectionService(
            detector,
            preprocessing=preprocessing_config(spec),
            native_classes=spec.native_classes,
            quality_class_weights=spec.class_weights,
            quality_default_weight=spec.quality_default_weight,
        )

    def get_service(self, model_id: str | None = None) -> DetectionService:
        spec = self.registry.get(model_id)
        with self._cache_lock:
            cached = self._services.get(spec.model_id)
            if cached is not None:
                return cached
            service = self._build_service(spec)
            self._services[spec.model_id] = service
            return service

    def inspect(self, image: np.ndarray, model_id: str | None = None) -> InspectionResult:
        return self.get_service(model_id).inspect(image)
