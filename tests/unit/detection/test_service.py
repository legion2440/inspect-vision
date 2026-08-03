from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import numpy as np
import pytest

import backend.detection.service as service_module
from backend.detection.dto import Detection, InferenceResult
from backend.detection.device import DeviceInfo
from backend.detection.service import DetectionService
from backend.detection.ultralytics_backend import UltralyticsBackend


class DetectorStub:
    image_size = 640

    def __init__(
        self,
        detections: tuple[Detection, ...] = (),
        *,
        model_id: str = "neu-defect-yolov8",
    ) -> None:
        self.model_id = model_id
        self.detections = detections
        self.received: np.ndarray | None = None

    def infer(self, frame: np.ndarray) -> InferenceResult:
        self.received = frame
        return InferenceResult(
            detections=self.detections,
            image_width=640,
            image_height=640,
            latency_ms=1.0,
            backend="stub",
            device="cpu",
            model_id=self.model_id,
        )


class FailingDetectorStub(DetectorStub):
    def __init__(self, error: RuntimeError) -> None:
        super().__init__()
        self.error = error

    def infer(self, frame: np.ndarray) -> NoReturn:
        self.received = frame
        raise self.error


class EmptyBoxesStub:
    def __len__(self) -> int:
        return 0


class EmptyPredictionStub:
    boxes = EmptyBoxesStub()


class UltralyticsServiceModelStub:
    task = "detect"
    names = {
        0: "crazing",
        1: "inclusion",
        2: "patches",
        3: "pitted_surface",
        4: "rolled-in_scale",
        5: "scratches",
    }

    def __init__(self) -> None:
        self.received_shapes: list[tuple[int, ...]] = []
        self.received_imgsz: int | None = None

    def predict(
        self,
        *,
        source: list[np.ndarray],
        imgsz: int,
        **_: object,
    ) -> list[EmptyPredictionStub]:
        self.received_shapes.extend(frame.shape for frame in source)
        self.received_imgsz = imgsz
        return [EmptyPredictionStub() for _frame in source]


def test_service_runs_single_letterbox_and_restores_original_coordinates_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detection = Detection(0, "crazing", 0.8, (32.0, 192.0, 96.0, 256.0))
    detector = DetectorStub((detection,))
    service = DetectionService(detector)  # type: ignore[arg-type]
    restore_calls = 0
    real_restore = service_module.restore_boxes

    def counted_restore(boxes: np.ndarray, info: object) -> np.ndarray:
        nonlocal restore_calls
        restore_calls += 1
        return real_restore(boxes, info)  # type: ignore[arg-type]

    monkeypatch.setattr(service_module, "restore_boxes", counted_restore)
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    result = service.inspect(image)

    assert restore_calls == 1
    assert detector.received is not None
    assert detector.received.shape == (640, 640, 3)
    np.testing.assert_array_equal(detector.received[:, :, 0], detector.received[:, :, 1])
    np.testing.assert_array_equal(detector.received[:, :, 1], detector.received[:, :, 2])
    box = result.defects[0].bounding_box
    assert (box.x, box.y, box.width, box.height) == pytest.approx((10.0, 10.0, 20.0, 20.0))
    assert result.image_width == 200
    assert result.image_height == 100
    assert result.status == "failed"
    assert result.quality_score == 88


def test_service_drops_box_that_collapses_when_padding_is_removed() -> None:
    padding_only = Detection(0, "crazing", 0.9, (10.0, 10.0, 20.0, 20.0))
    detector = DetectorStub((padding_only,))

    result = DetectionService(detector).inspect(  # type: ignore[arg-type]
        np.zeros((100, 200, 3), dtype=np.uint8)
    )

    assert result.defects == ()
    assert result.total_defects == 0
    assert result.quality_score == 100
    assert result.status == "passed"


def test_service_maps_multiple_native_classes_and_preserves_source_image() -> None:
    detections = (
        Detection(1, "inclusion", 0.8, (32.0, 192.0, 96.0, 256.0)),
        Detection(5, "scratches", 0.7, (320.0, 320.0, 384.0, 384.0)),
    )
    image = np.full((100, 200, 3), 127, dtype=np.uint8)
    original = image.copy()

    result = DetectionService(DetectorStub(detections)).inspect(image)  # type: ignore[arg-type]

    assert [defect.type for defect in result.defects] == ["inclusion", "scratches"]
    assert result.total_defects == 2
    assert result.status == "failed"
    assert result.annotated_image.shape == image.shape
    np.testing.assert_array_equal(image, original)
    assert not np.array_equal(result.annotated_image, original)


def test_service_rejects_unknown_native_class() -> None:
    detector = DetectorStub((Detection(6, "pcb_short", 0.8, (10.0, 170.0, 30.0, 190.0)),))

    with pytest.raises(ValueError, match="Unknown service class"):
        DetectionService(detector).inspect(  # type: ignore[arg-type]
            np.zeros((100, 200, 3), dtype=np.uint8)
        )


def test_alternative_model_requires_an_explicit_service_mapping() -> None:
    detector = DetectorStub(model_id="factory-defect-guard-v6-mc")

    with pytest.raises(ValueError, match="No service class mapping"):
        DetectionService(detector)  # type: ignore[arg-type]


def test_clean_image_returns_authoritative_clean_result() -> None:
    image = np.zeros((60, 90, 3), dtype=np.uint8)

    result = DetectionService(DetectorStub()).inspect(image)  # type: ignore[arg-type]

    assert result.defects == ()
    assert result.total_defects == 0
    assert result.quality_score == 100
    assert result.status == "passed"


def test_model_exception_propagates_unchanged() -> None:
    model_error = RuntimeError("inference failed")
    service = DetectionService(FailingDetectorStub(model_error))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as captured:
        service.inspect(np.zeros((60, 90, 3), dtype=np.uint8))

    assert captured.value is model_error


def test_service_rejects_invalid_bgr_input() -> None:
    service = DetectionService(DetectorStub())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="HxWx3"):
        service.inspect(np.zeros((60, 90), dtype=np.uint8))


def test_ultralytics_service_path_receives_preprocessed_640_square(
    tmp_path: Path,
) -> None:
    weight = tmp_path / "model.pt"
    weight.write_bytes(b"test")
    model = UltralyticsServiceModelStub()
    detector = UltralyticsBackend(
        model_id="neu-defect-yolov8",
        model_path=weight,
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        expected_class_names=tuple(model.names.values()),
        model_factory=lambda *_args, **_kwargs: model,
    )

    result = DetectionService(detector).inspect(
        np.zeros((100, 200, 3), dtype=np.uint8)
    )

    assert model.received_shapes == [(640, 640, 3)]
    assert model.received_imgsz == 640
    assert result.image_width == 200
    assert result.image_height == 100
