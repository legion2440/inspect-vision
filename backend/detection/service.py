"""Inspection-specific orchestration over the reusable detection core."""

from __future__ import annotations

from collections.abc import Mapping

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


PRIMARY_MODEL_ID = "neu-defect-yolov8"
PRIMARY_CLASS_MAPPING: dict[str, str] = {
    "crazing": "crazing",
    "inclusion": "inclusion",
    "patches": "patches",
    "pitted_surface": "pitted_surface",
    "rolled-in_scale": "rolled-in_scale",
    "scratches": "scratches",
}


class DetectionService:
    """Run the selected inspection pipeline and return library-neutral results."""

    def __init__(
        self,
        detector: DetectorBackend,
        *,
        preprocessing: InspectionPreprocessingConfig = InspectionPreprocessingConfig(),
        class_mapping: Mapping[str, str] | None = None,
    ) -> None:
        if preprocessing.input_size != 640:
            raise ValueError("DetectionService requires a 640-square preprocessing input")
        if detector.image_size != preprocessing.input_size:
            raise ValueError("Detector image_size must match service preprocessing input_size")
        if class_mapping is None:
            if detector.model_id != PRIMARY_MODEL_ID:
                raise ValueError(
                    f"No service class mapping registered for model: {detector.model_id}"
                )
            class_mapping = PRIMARY_CLASS_MAPPING
        normalized_mapping = dict(class_mapping)
        if not normalized_mapping or any(
            not native_name or not service_name
            for native_name, service_name in normalized_mapping.items()
        ):
            raise ValueError("class_mapping must contain non-empty class names")
        self.detector = detector
        self.preprocessing = preprocessing
        self.class_mapping = normalized_mapping

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
            raise RuntimeError("Detector must return coordinates in the 640-square service input")

        if inference.detections:
            model_boxes = np.asarray(
                [detection.xyxy for detection in inference.detections],
                dtype=np.float32,
            )
            original_boxes = restore_boxes(model_boxes, prepared.letterbox_info)
        else:
            original_boxes = np.empty((0, 4), dtype=np.float32)

        defects: list[InspectionDefect] = []
        for detection, restored in zip(
            inference.detections,
            original_boxes,
            strict=True,
        ):
            x1, y1, x2, y2 = (float(value) for value in restored)
            if x2 <= x1 or y2 <= y1:
                continue
            try:
                service_type = self.class_mapping[detection.class_name]
            except KeyError as error:
                raise ValueError(
                    f"Unknown service class for {self.detector.model_id}: "
                    f"{detection.class_name}"
                ) from error
            defects.append(
                InspectionDefect(
                    type=service_type,
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
