"""Normalized detection values independent of model-library objects."""

from __future__ import annotations

import math
from dataclasses import dataclass


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
        if x1 < 0.0 or y1 < 0.0 or x2 < x1 or y2 < y1:
            raise ValueError("xyxy must be ordered and non-negative")

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
