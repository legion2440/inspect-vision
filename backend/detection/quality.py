"""Versioned backend-authoritative inspection quality scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .dto import InspectionDefect


QUALITY_SCORE_VERSION = "quality-v1"
QUALITY_CLASS_WEIGHTS: dict[str, float] = {
    "crazing": 1.25,
    "inclusion": 1.10,
    "patches": 0.90,
    "pitted_surface": 1.00,
    "rolled-in_scale": 1.20,
    "scratches": 0.85,
}


def calculate_quality_score(
    defects: Sequence[InspectionDefect],
    *,
    image_width: int,
    image_height: int,
    class_weights: Mapping[str, float] = QUALITY_CLASS_WEIGHTS,
) -> int:
    """Calculate the quality-v1 heuristic in original-image coordinates."""

    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if not defects:
        return 100

    image_area = float(image_width * image_height)
    penalty = 0.0
    for defect in defects:
        try:
            class_weight = float(class_weights[defect.type])
        except KeyError as error:
            raise ValueError(f"No quality weight for defect type: {defect.type}") from error
        if class_weight <= 0.0:
            raise ValueError(f"Quality weight must be positive: {defect.type}")
        area_ratio = min(1.0, max(0.0, defect.bounding_box.area / image_area))
        penalty += class_weight * defect.confidence * (10.0 + 90.0 * area_ratio)

    rounded_score = math.floor(100.0 - penalty + 0.5)
    return max(0, min(100, rounded_score))
