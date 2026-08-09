"""Ultralytics implementation of the normalized detection interface."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from .base import DetectorBackend
from .dto import Detection, InferenceResult


ModelFactory = Callable[..., Any]


def _normalize_names(names: object) -> dict[int, str]:
    if isinstance(names, dict):
        normalized = {int(class_id): str(name) for class_id, name in names.items()}
    elif isinstance(names, (list, tuple)):
        normalized = {class_id: str(name) for class_id, name in enumerate(names)}
    else:
        raise TypeError(f"Unsupported model.names value: {type(names).__name__}")
    if not normalized or sorted(normalized) != list(range(len(normalized))):
        raise ValueError("model.names must define contiguous class IDs starting at zero")
    if any(not name for name in normalized.values()):
        raise ValueError("model.names contains an empty class name")
    return normalized


class UltralyticsBackend(DetectorBackend):
    name = "ultralytics"

    def __init__(self, *args: Any, model_factory: ModelFactory | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._model_factory = model_factory
        self._model: Any | None = None
        self._names: dict[int, str] = {}

    def load(self) -> None:
        if self._model is not None:
            return
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Model weight is missing: {self.model_path}")
        factory = self._model_factory
        if factory is None:
            from ultralytics import YOLO

            factory = YOLO
        model = factory(str(self.model_path), task="detect")
        if getattr(model, "task", None) != "detect":
            raise ValueError(
                f"Model {self.model_id} has task={getattr(model, 'task', None)!r}, "
                "expected 'detect'"
            )
        names = _normalize_names(model.names)
        actual_names = tuple(names[index] for index in range(len(names)))
        if self.expected_class_names and actual_names != self.expected_class_names:
            raise ValueError(
                f"Class metadata mismatch for {self.model_id}: "
                f"expected {self.expected_class_names}, got {actual_names}"
            )
        self._model = model
        self._names = names

    @property
    def class_names(self) -> tuple[str, ...]:
        self.load()
        return tuple(self._names[index] for index in range(len(self._names)))

    def _actual_device(self) -> str:
        if self._model is not None:
            module = getattr(self._model, "model", None)
            if module is not None:
                try:
                    return str(next(module.parameters()).device)
                except (AttributeError, StopIteration, TypeError):
                    pass
        if self.device.kind == "cuda":
            return f"cuda:{self.device.torch_device}"
        if self.device.kind == "mps":
            return "mps"
        return "cpu"

    def _normalize_prediction(
        self,
        prediction: Any,
        *,
        width: int,
        height: int,
        latency_ms: float,
    ) -> InferenceResult:
        detections: list[Detection] = []
        boxes = prediction.boxes
        if boxes is not None and len(boxes) > 0:
            xyxy_values = boxes.xyxy.detach().cpu().numpy()
            confidence_values = boxes.conf.detach().cpu().numpy()
            class_values = boxes.cls.detach().cpu().numpy()
            for xyxy, confidence, raw_class_id in zip(
                xyxy_values, confidence_values, class_values, strict=True
            ):
                class_id = int(raw_class_id)
                if class_id not in self._names:
                    raise ValueError(f"Unknown class ID {class_id} from {self.model_id}")
                x1, y1, x2, y2 = (float(value) for value in xyxy)
                if x2 < x1 or y2 < y1:
                    raise ValueError(f"Unordered bbox from {self.model_id}: {xyxy.tolist()}")
                clamped = (
                    min(max(x1, 0.0), float(width)),
                    min(max(y1, 0.0), float(height)),
                    min(max(x2, 0.0), float(width)),
                    min(max(y2, 0.0), float(height)),
                )
                if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
                    continue
                detections.append(
                    Detection(
                        class_id=class_id,
                        class_name=self._names[class_id],
                        confidence=float(confidence),
                        xyxy=clamped,
                    )
                )
        return InferenceResult(
            detections=tuple(detections),
            image_width=width,
            image_height=height,
            latency_ms=latency_ms,
            backend=self.name,
            device=self._actual_device(),
            model_id=self.model_id,
        )

    def infer_batch(self, frames: Sequence[np.ndarray]) -> list[InferenceResult]:
        self.load()
        if not frames:
            return []
        for frame in frames:
            self.validate_frame(frame)

        started = time.perf_counter()
        predictions = self._model.predict(
            source=list(frames),
            imgsz=self.image_size,
            conf=self.confidence,
            iou=self.iou,
            device=self.device.torch_device,
            verbose=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if len(predictions) != len(frames):
            raise RuntimeError(
                f"Model returned {len(predictions)} predictions for {len(frames)} frames"
            )
        per_frame_ms = elapsed_ms / len(frames)
        return [
            self._normalize_prediction(
                prediction,
                width=frame.shape[1],
                height=frame.shape[0],
                latency_ms=per_frame_ms,
            )
            for frame, prediction in zip(frames, predictions, strict=True)
        ]
