from __future__ import annotations

import pytest

from backend.detection.dto import BoundingBox, Detection, InferenceResult


def test_detection_exposes_normalized_fields() -> None:
    detection = Detection(2, "scratch", 0.75, (1.0, 2.0, 30.0, 40.0))

    assert detection.to_dict() == {
        "class_id": 2,
        "class_name": "scratch",
        "confidence": 0.75,
        "xyxy": [1.0, 2.0, 30.0, 40.0],
    }


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan")])
def test_detection_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        Detection(0, "scratch", confidence, (0.0, 0.0, 1.0, 1.0))


def test_inference_result_rejects_bbox_outside_original_image() -> None:
    detection = Detection(0, "scratch", 0.9, (0.0, 0.0, 101.0, 50.0))

    with pytest.raises(ValueError, match="exceeds"):
        InferenceResult((detection,), 100, 100, 1.0, "test", "cpu", "model")


@pytest.mark.parametrize(
    "xyxy",
    [(1.0, 1.0, 1.0, 2.0), (1.0, 1.0, 2.0, 1.0)],
)
def test_detection_rejects_zero_area_bbox(
    xyxy: tuple[float, float, float, float],
) -> None:
    with pytest.raises(ValueError, match="positive area"):
        Detection(0, "crazing", 0.8, xyxy)


@pytest.mark.parametrize(
    "width,height",
    [(0.0, 1.0), (1.0, 0.0), (-1.0, 1.0), (1.0, -1.0)],
)
def test_service_bbox_requires_positive_dimensions(width: float, height: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        BoundingBox(0.0, 0.0, width, height)
