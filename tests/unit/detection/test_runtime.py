from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from backend.detection.base import GeometryOwnership
from backend.detection.dto import InferenceResult
from backend.detection.product_context import ProductNameValidationError
from backend.detection.runtime import DetectionRuntimeManager
from backend.utils.model_loader import (
    ModelNotFoundError,
    ModelNotInstalledError,
    ModelRegistry,
)


class DetectorStub:
    def __init__(self, spec: object) -> None:
        self.model_id = spec.model_id
        self.image_size = spec.image_size
        self.load_calls = 0
        self.received: np.ndarray | None = None
        self.product_name: str | None = None
        self.received_product_names: list[str | None] = []

    def load(self) -> None:
        self.load_calls += 1

    def infer(self, image: np.ndarray) -> InferenceResult:
        self.received = image
        self.received_product_names.append(self.product_name)
        return InferenceResult(
            detections=(),
            image_width=image.shape[1],
            image_height=image.shape[0],
            latency_ms=1.0,
            backend="stub",
            device="cpu",
            model_id=self.model_id,
        )


class BackendOwnedDetectorStub(DetectorStub):
    geometry_ownership = GeometryOwnership.BACKEND


class ConcurrentContextDetectorStub(BackendOwnedDetectorStub):
    def __init__(self, spec: object) -> None:
        super().__init__(spec)
        self.context_windows: list[tuple[str | None, str | None]] = []

    def infer(self, image: np.ndarray) -> InferenceResult:
        before = self.product_name
        time.sleep(0.02)
        after = self.product_name
        self.context_windows.append((before, after))
        return super().infer(image)


def test_runtime_uses_guided_manifest_default_and_lazy_cache() -> None:
    registry = ModelRegistry()
    created: list[DetectorStub] = []

    def factory(spec: object) -> DetectorStub:
        detector = BackendOwnedDetectorStub(spec)
        created.append(detector)
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)

    assert runtime.cached_model_ids == ()
    first = runtime.get_service(product_name="Capsule")
    second = runtime.get_service("bayespfl-general-v1", product_name="capsule")

    assert first is second
    assert registry.default_model_id == "bayespfl-general-v1"
    assert runtime.cached_model_ids == ("bayespfl-general-v1",)
    assert len(created) == 1
    assert created[0].load_calls == 1


def test_guided_model_requires_valid_product_name_before_loading() -> None:
    runtime = DetectionRuntimeManager(
        ModelRegistry(),
        detector_factory=lambda spec: BackendOwnedDetectorStub(spec),
    )

    with pytest.raises(ProductNameValidationError, match="required"):
        runtime.get_service("bayespfl-general-v1")
    with pytest.raises(ProductNameValidationError, match="Latin letters"):
        runtime.get_service("bayespfl-general-v1", product_name="хуй")
    with pytest.raises(ProductNameValidationError, match="at most 3 words"):
        runtime.get_service("bayespfl-general-v1", product_name="one two three four")


def test_guided_cache_reuses_one_loaded_service_across_categories() -> None:
    registry = ModelRegistry()
    created: list[DetectorStub] = []

    def factory(spec: object) -> DetectorStub:
        detector = BackendOwnedDetectorStub(spec)
        created.append(detector)
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)
    first = runtime.get_service("bayespfl-general-v1", product_name=" Metal_Nut ")
    second = runtime.get_service("bayespfl-general-v1", product_name="metal nut")
    screw = runtime.get_service("bayespfl-general-v1", product_name="Screw")
    capsule = runtime.get_service("bayespfl-general-v1", product_name="Capsule")

    assert first is second is screw is capsule
    assert len(created) == 1
    assert created[0].load_calls == 1
    assert runtime.cached_model_ids == ("bayespfl-general-v1",)


def test_guided_inspect_applies_each_category_to_the_shared_detector() -> None:
    registry = ModelRegistry()
    created: list[DetectorStub] = []

    def factory(spec: object) -> DetectorStub:
        detector = BackendOwnedDetectorStub(spec)
        created.append(detector)
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)
    image = np.zeros((20, 30, 3), dtype=np.uint8)

    for product_name in ("Bottle", "Capsule", "Screw", "Metal nut", "Other objects"):
        runtime.inspect(
            image,
            "bayespfl-general-v1",
            product_name=product_name,
        )

    assert len(created) == 1
    assert created[0].load_calls == 1
    assert created[0].received_product_names == [
        "bottle",
        "capsule",
        "screw",
        "metal nut",
        "other objects",
    ]


def test_guided_concurrent_requests_do_not_mix_product_context() -> None:
    registry = ModelRegistry()
    created: list[ConcurrentContextDetectorStub] = []

    def factory(spec: object) -> ConcurrentContextDetectorStub:
        detector = ConcurrentContextDetectorStub(spec)
        created.append(detector)
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)
    image = np.zeros((20, 30, 3), dtype=np.uint8)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                runtime.inspect,
                image,
                "bayespfl-general-v1",
                product_name=product_name,
            )
            for product_name in ("Bottle", "Capsule")
        ]
        for future in futures:
            future.result()

    assert len(created) == 1
    assert set(created[0].context_windows) == {
        ("bottle", "bottle"),
        ("capsule", "capsule"),
    }


def test_runtime_applies_per_model_preprocessing_profiles() -> None:
    registry = ModelRegistry()
    detectors: dict[str, DetectorStub] = {}

    def factory(spec: object) -> DetectorStub:
        detector = DetectorStub(spec)
        detectors[spec.model_id] = detector
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)
    image = np.zeros((20, 40, 3), dtype=np.uint8)
    image[:, :] = [10, 80, 220]

    runtime.inspect(image, "concrete-crack-yolov8")
    runtime.inspect(image, "neu-defect-yolov8")

    color_input = detectors["concrete-crack-yolov8"].received
    steel_input = detectors["neu-defect-yolov8"].received
    assert color_input is not None and steel_input is not None
    assert not np.array_equal(color_input[:, :, 0], color_input[:, :, 2])
    np.testing.assert_array_equal(steel_input[:, :, 0], steel_input[:, :, 2])


def test_runtime_rejects_unknown_and_missing_models(tmp_path: Path) -> None:
    runtime = DetectionRuntimeManager(ModelRegistry(), models_directory=tmp_path)

    with pytest.raises(ModelNotFoundError):
        runtime.get_service("unknown")
    with pytest.raises(ModelNotInstalledError, match="install_models.py --model"):
        runtime.get_service(product_name="capsule")


def test_bayespfl_is_available_through_public_inspect_with_backend_geometry() -> None:
    registry = ModelRegistry()
    runtime = DetectionRuntimeManager(
        registry,
        detector_factory=lambda spec: BackendOwnedDetectorStub(spec),
    )

    result = runtime.inspect(
        np.zeros((20, 30, 3), dtype=np.uint8),
        "bayespfl-general-v1",
        product_name="Capsule",
    )

    assert result.model_id == "bayespfl-general-v1"
    assert result.image_width == 30
    assert result.image_height == 20
    service = runtime.get_service(
        "bayespfl-general-v1",
        product_name="capsule",
    )
    assert service.detector.received.shape == (20, 30, 3)
    assert service.detector.received_product_names == ["capsule"]
