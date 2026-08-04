"""Inspection-specific orchestration over the reusable detection core."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from backend.utils.preprocessing import (
    InspectionPreprocessingConfig,
    preprocess_inspection_image,
    restore_boxes,
    validate_bgr_image,
)

from .annotation import annotate_image
from .base import DetectorBackend
from .dto import BoundingBox, InspectionDefect, InspectionResult
from .quality import calculate_quality_score


class DetectionService:
    """Run one registered model pipeline and return library-neutral results."""

    def __init__(
        self,
        detector: DetectorBackend,
        *,
        preprocessing: InspectionPreprocessingConfig,
        native_classes: Sequence[str],
        quality_class_weights: Mapping[str, float] | None = None,
        quality_default_weight: float = 1.0,
    ) -> None:
        if detector.image_size != preprocessing.input_size:
            raise ValueError("Detector image_size must match service preprocessing input_size")
        normalized_classes = tuple(native_classes)
        if not normalized_classes or len(set(normalized_classes)) != len(normalized_classes):
            raise ValueError("native_classes must contain unique non-empty class names")
        if any(not class_name for class_name in normalized_classes):
            raise ValueError("native_classes must contain unique non-empty class names")
        normalized_weights = dict(quality_class_weights or {})
        unknown_weights = set(normalized_weights) - set(normalized_classes)
        if unknown_weights:
            raise ValueError(
                "Quality weights reference unknown native classes: "
                + ", ".join(sorted(unknown_weights))
            )
        if quality_default_weight <= 0.0:
            raise ValueError("quality_default_weight must be positive")
        self.detector = detector
        self.preprocessing = preprocessing
        self.native_classes = normalized_classes
        self.quality_class_weights = normalized_weights
        self.quality_default_weight = float(quality_default_weight)

    def inspect(self, image: np.ndarray) -> InspectionResult:
        validate_bgr_image(image)
        image_height, image_width = image.shape[:2]
        prepared = preprocess_inspection_image(image, self.preprocessing)
        model_input = prepared.model_input
        expected_shape = (
            self.preprocessing.input_size,
            self.preprocessing.input_size,
            3,
        )
        if model_input.shape != expected_shape:
            raise RuntimeError(
                f"Inspection preprocessing returned {model_input.shape}, expected {expected_shape}"
            )

        inference = self.detector.infer(model_input)
        if (
            inference.image_width != self.preprocessing.input_size
            or inference.image_height != self.preprocessing.input_size
        ):
            raise RuntimeError("Detector must return coordinates in the service input dimensions")

        if inference.detections:
            model_boxes = np.asarray(
                [detection.xyxy for detection in inference.detections],
                dtype=np.float32,
            )
            original_boxes = restore_boxes(model_boxes, prepared.letterbox_info)
        else:
            original_boxes = np.empty((0, 4), dtype=np.float32)

        defects: list[InspectionDefect] = []
        allowed_classes = set(self.native_classes)
        for detection, restored in zip(
            inference.detections,
            original_boxes,
            strict=True,
        ):
            if detection.class_name not in allowed_classes:
                raise ValueError(
                    f"Unknown native class for {self.detector.model_id}: "
                    f"{detection.class_name}"
                )
            x1, y1, x2, y2 = (float(value) for value in restored)
            if x2 <= x1 or y2 <= y1:
                continue
            defects.append(
                InspectionDefect(
                    type=detection.class_name,
                    confidence=detection.confidence,
                    bounding_box=BoundingBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    ),
                )
            )

        normalized_defects = tuple(defects)
        quality_score = calculate_quality_score(
            normalized_defects,
            image_width=image_width,
            image_height=image_height,
            class_weights=self.quality_class_weights,
            default_weight=self.quality_default_weight,
        )
        status = "passed" if not normalized_defects else "failed"
        annotated = annotate_image(image, normalized_defects)
        return InspectionResult(
            image_width=image_width,
            image_height=image_height,
            defects=normalized_defects,
            status=status,
            quality_score=quality_score,
            annotated_image=annotated,
            model_id=inference.model_id,
        )
