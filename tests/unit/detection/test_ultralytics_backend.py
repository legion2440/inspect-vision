from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.detection.device import DeviceInfo
from backend.detection.ultralytics_backend import UltralyticsBackend


class TensorStub:
    def __init__(self, values: object) -> None:
        self._values = np.asarray(values)

    def detach(self) -> "TensorStub":
        return self

    def cpu(self) -> "TensorStub":
        return self

    def numpy(self) -> np.ndarray:
        return self._values


class BoxesStub:
    def __init__(self) -> None:
        self.xyxy = TensorStub([[-5.0, 2.0, 205.0, 120.0], [10.0, 11.0, 20.0, 21.0]])
        self.conf = TensorStub([0.9, 0.8])
        self.cls = TensorStub([0, 1])

    def __len__(self) -> int:
        return 2


class PredictionStub:
    boxes = BoxesStub()


class ModelStub:
    task = "detect"
    names = {0: "scratch", 1: "dent"}

    def predict(self, *, source: list[np.ndarray], **_: object) -> list[PredictionStub]:
        return [PredictionStub() for _frame in source]


def _weight(tmp_path: Path) -> Path:
    weight = tmp_path / "model.pt"
    weight.write_bytes(b"test")
    return weight


def test_adapter_returns_all_native_classes_and_clamped_original_boxes(
    tmp_path: Path,
) -> None:
    backend = UltralyticsBackend(
        model_id="test-model",
        model_path=_weight(tmp_path),
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        expected_class_names=("scratch", "dent"),
        model_factory=lambda *_args, **_kwargs: ModelStub(),
    )

    result = backend.infer(np.zeros((100, 200, 3), dtype=np.uint8))

    assert [detection.class_name for detection in result.detections] == ["scratch", "dent"]
    assert result.detections[0].xyxy == (0.0, 2.0, 200.0, 100.0)
    assert result.image_width == 200
    assert result.image_height == 100
    assert result.device == "cpu"


def test_adapter_rejects_manifest_class_mismatch(tmp_path: Path) -> None:
    backend = UltralyticsBackend(
        model_id="test-model",
        model_path=_weight(tmp_path),
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        expected_class_names=("person",),
        model_factory=lambda *_args, **_kwargs: ModelStub(),
    )

    with pytest.raises(ValueError, match="Class metadata mismatch"):
        backend.load()


def test_adapter_rejects_non_bgr_frame(tmp_path: Path) -> None:
    backend = UltralyticsBackend(
        model_id="test-model",
        model_path=_weight(tmp_path),
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        expected_class_names=("scratch", "dent"),
        model_factory=lambda *_args, **_kwargs: ModelStub(),
    )

    with pytest.raises(ValueError, match="HxWx3"):
        backend.infer(np.zeros((100, 200), dtype=np.uint8))
