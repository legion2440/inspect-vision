from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.detection.dto import InferenceResult
from backend.detection.runtime import DetectionRuntimeManager
from backend.utils.model_loader import ModelNotFoundError, ModelNotInstalledError, ModelRegistry


class DetectorStub:
    def __init__(self, spec: object) -> None:
        self.model_id = spec.model_id
        self.image_size = spec.image_size
        self.load_calls = 0
        self.received: np.ndarray | None = None

    def load(self) -> None:
        self.load_calls += 1

    def infer(self, image: np.ndarray) -> InferenceResult:
        self.received = image
        return InferenceResult(
            detections=(),
            image_width=image.shape[1],
            image_height=image.shape[0],
            latency_ms=1.0,
            backend="stub",
            device="cpu",
            model_id=self.model_id,
        )


def test_runtime_uses_manifest_default_and_lazy_cache() -> None:
    registry = ModelRegistry()
    created: list[DetectorStub] = []

    def factory(spec: object) -> DetectorStub:
        detector = DetectorStub(spec)
        created.append(detector)
        return detector

    runtime = DetectionRuntimeManager(registry, detector_factory=factory)

    assert runtime.cached_model_ids == ()
    first = runtime.get_service()
    second = runtime.get_service("factory-defect-guard-v6-mc")

    assert first is second
    assert registry.default_model_id == "factory-defect-guard-v6-mc"
    assert runtime.cached_model_ids == ("factory-defect-guard-v6-mc",)
    assert len(created) == 1
    assert created[0].load_calls == 1


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

    runtime.inspect(image, "factory-defect-guard-v6-mc")
    runtime.inspect(image, "neu-defect-yolov8")

    broad_input = detectors["factory-defect-guard-v6-mc"].received
    steel_input = detectors["neu-defect-yolov8"].received
    assert broad_input is not None and steel_input is not None
    assert not np.array_equal(broad_input[:, :, 0], broad_input[:, :, 2])
    np.testing.assert_array_equal(steel_input[:, :, 0], steel_input[:, :, 2])


def test_runtime_rejects_unknown_and_missing_models(tmp_path: Path) -> None:
    runtime = DetectionRuntimeManager(ModelRegistry(), models_directory=tmp_path)

    with pytest.raises(ModelNotFoundError):
        runtime.get_service("unknown")
    with pytest.raises(ModelNotInstalledError, match="install_models.py --model"):
        runtime.get_service()
