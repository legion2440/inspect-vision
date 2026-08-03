"""Normalized detection values independent of model-library objects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    xyxy: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.class_id, int) or isinstance(self.class_id, bool) or self.class_id < 0:
            raise ValueError("class_id must be a non-negative integer")
        if not self.class_name:
            raise ValueError("class_name must not be empty")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if len(self.xyxy) != 4 or not all(math.isfinite(value) for value in self.xyxy):
            raise ValueError("xyxy must contain four finite coordinates")
        x1, y1, x2, y2 = self.xyxy
        if x1 < 0.0 or y1 < 0.0 or x2 <= x1 or y2 <= y1:
            raise ValueError("xyxy must have positive area and non-negative coordinates")

    def to_dict(self) -> dict[str, object]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "xyxy": list(self.xyxy),
        }


@dataclass(frozen=True, slots=True)
class InferenceResult:
    detections: tuple[Detection, ...]
    image_width: int
    image_height: int
    latency_ms: float
    backend: str
    device: str
    model_id: str

    def __post_init__(self) -> None:
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("Image dimensions must be positive")
        if not math.isfinite(self.latency_ms) or self.latency_ms < 0.0:
            raise ValueError("latency_ms must be finite and non-negative")
        if not self.backend or not self.device or not self.model_id:
            raise ValueError("backend, device, and model_id must not be empty")
        for detection in self.detections:
            _, _, x2, y2 = detection.xyxy
            if x2 > self.image_width or y2 > self.image_height:
                raise ValueError("Detection bbox exceeds original image dimensions")

    def to_dict(self) -> dict[str, object]:
        return {
            "detections": [detection.to_dict() for detection in self.detections],
            "image_width": self.image_width,
            "image_height": self.image_height,
            "latency_ms": self.latency_ms,
            "backend": self.backend,
            "device": self.device,
            "model_id": self.model_id,
        }


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("bounding box values must be finite")
        if self.x < 0.0 or self.y < 0.0:
            raise ValueError("bounding box origin must be non-negative")
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("bounding box width and height must be positive")

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True)
class InspectionDefect:
    type: str
    confidence: float
    bounding_box: BoundingBox

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("defect type must not be empty")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class InspectionResult:
    image_width: int
    image_height: int
    defects: tuple[InspectionDefect, ...]
    status: Literal["passed", "failed"]
    quality_score: int
    annotated_image: np.ndarray
    model_id: str

    def __post_init__(self) -> None:
        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")
        expected_status = "passed" if not self.defects else "failed"
        if self.status != expected_status:
            raise ValueError("status must be passed only when no defects exist")
        if (
            not isinstance(self.quality_score, int)
            or isinstance(self.quality_score, bool)
            or not 0 <= self.quality_score <= 100
        ):
            raise ValueError("quality_score must be an integer from zero to 100")
        if not self.model_id:
            raise ValueError("model_id must not be empty")
        if not isinstance(self.annotated_image, np.ndarray):
            raise TypeError("annotated_image must be a numpy.ndarray")
        if self.annotated_image.dtype != np.uint8:
            raise ValueError("annotated_image must use uint8 pixels")
        if self.annotated_image.shape != (self.image_height, self.image_width, 3):
            raise ValueError("annotated_image must preserve original HxWx3 dimensions")
        for defect in self.defects:
            box = defect.bounding_box
            if box.x + box.width > self.image_width or box.y + box.height > self.image_height:
                raise ValueError("defect bbox exceeds original image dimensions")

    @property
    def total_defects(self) -> int:
        return len(self.defects)

    def to_dict(self) -> dict[str, object]:
        """Return JSON-ready metadata; image encoding belongs to the future API."""

        return {
            "image_width": self.image_width,
            "image_height": self.image_height,
            "defects": [defect.to_dict() for defect in self.defects],
            "total_defects": self.total_defects,
            "status": self.status,
            "quality_score": self.quality_score,
            "model_id": self.model_id,
        }
