from pathlib import Path

import numpy as np
import pytest

from backend.detection.bayespfl_backend import (
    BayesPflBackend,
    BayesPflConfig,
    _component_boxes,
    _load_checkpoint,
)
from backend.detection.device import DeviceInfo


def test_config_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        BayesPflConfig(map_threshold=1.1)


def test_config_rejects_invalid_bbox_padding() -> None:
    with pytest.raises(ValueError, match="padding"):
        BayesPflConfig(bbox_padding_ratio=1.1)


def test_component_boxes_filter_small_regions_and_score_mean_probability() -> None:
    anomaly_map = np.zeros((10, 10), dtype=np.float32)
    anomaly_map[2:5, 4:8] = 0.8
    anomaly_map[0, 0] = 0.9

    components = _component_boxes(
        anomaly_map,
        threshold=0.5,
        min_area_ratio=0.02,
    )

    assert len(components) == 1
    bbox, score = components[0]
    assert bbox == (4, 2, 8, 5)
    assert score == pytest.approx(0.8)


def test_checkpoint_uses_weights_only() -> None:
    calls = []

    class FakeTorch:
        @staticmethod
        def load(path, **kwargs):
            calls.append((path, kwargs))
            return {"MyModel": {"weight": object()}}

    checkpoint = _load_checkpoint(Path(__file__), FakeTorch)

    assert "MyModel" in checkpoint
    assert calls[0][1]["weights_only"] is True
    assert calls[0][1]["map_location"] == "cpu"


def test_backend_maps_mps_device_without_falling_back_to_cpu(tmp_path: Path) -> None:
    detector = BayesPflBackend(
        source_dir=tmp_path,
        backbone_path=tmp_path / "backbone.pt",
        checkpoint_path=tmp_path / "checkpoint.pth",
        product_name="capsule",
        device=DeviceInfo("mps", "mps", "Apple Metal GPU", "PyTorch MPS"),
    )

    assert detector._torch_device == "mps"


def test_backend_owned_geometry_restores_and_pads_boxes_once(tmp_path: Path) -> None:
    class FakeBackend(BayesPflBackend):
        def load(self) -> None:
            return None

        def _anomaly_map(self, frame: np.ndarray) -> np.ndarray:
            anomaly_map = np.zeros((10, 10), dtype=np.float32)
            anomaly_map[2:5, 4:8] = 0.9
            return anomaly_map

    detector = FakeBackend(
        source_dir=tmp_path,
        backbone_path=tmp_path / "backbone.pt",
        checkpoint_path=tmp_path / "checkpoint.pth",
        product_name="capsule",
        device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        config=BayesPflConfig(
            image_size=10,
            gaussian_sigma=0.0,
            map_threshold=0.5,
            min_component_area_ratio=0.02,
            bbox_padding_ratio=0.25,
        ),
    )
    frame = np.zeros((100, 200, 3), dtype=np.uint8)

    result = detector.infer(frame)

    assert result.image_width == 200
    assert result.image_height == 100
    assert len(result.detections) == 1
    assert result.detections[0].xyxy == pytest.approx((60.0, 12.5, 180.0, 57.5))
    assert result.detections[0].class_name == "anomaly"


def test_backend_requires_product_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="product/category"):
        BayesPflBackend(
            source_dir=tmp_path,
            backbone_path=tmp_path / "backbone.pt",
            checkpoint_path=tmp_path / "checkpoint.pth",
            product_name=" ",
            device=DeviceInfo("cpu", "cpu", "CPU", "PyTorch CPU"),
        )
