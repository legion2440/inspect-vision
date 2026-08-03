"""Abstract interface implemented by detection runtimes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

import numpy as np

from .device import DeviceInfo
from .dto import InferenceResult


class DetectorBackend(ABC):
    name: str

    def __init__(
        self,
        *,
        model_id: str,
        model_path: str | Path,
        device: DeviceInfo,
        image_size: int = 640,
        confidence: float = 0.25,
        iou: float = 0.5,
        expected_class_names: Sequence[str] = (),
    ) -> None:
        if not model_id:
            raise ValueError("model_id must not be empty")
        if image_size <= 0:
            raise ValueError("image_size must be positive")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if not 0.0 <= iou <= 1.0:
            raise ValueError("iou must be between zero and one")
        self.model_id = model_id
        self.model_path = Path(model_path)
        self.device = device
        self.image_size = int(image_size)
        self.confidence = float(confidence)
        self.iou = float(iou)
        self.expected_class_names = tuple(expected_class_names)

    @staticmethod
    def validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame must be a numpy.ndarray")
        if frame.dtype != np.uint8:
            raise ValueError("frame must use uint8 pixels")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must have shape HxWx3 in BGR order")
        if frame.shape[0] <= 0 or frame.shape[1] <= 0:
            raise ValueError("frame must not be empty")

    @property
    @abstractmethod
    def class_names(self) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def load(self) -> None:
        raise NotImplementedError

    def warmup(self) -> None:
        frame = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        self.infer(frame)

    def infer(self, frame: np.ndarray) -> InferenceResult:
        return self.infer_batch([frame])[0]

    @abstractmethod
    def infer_batch(self, frames: Sequence[np.ndarray]) -> list[InferenceResult]:
        raise NotImplementedError
