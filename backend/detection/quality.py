"""Versioned backend-authoritative inspection quality scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .dto import InspectionDefect


QUALITY_SCORE_VERSION = "quality-v1"


def calculate_quality_score(
    defects: Sequence[InspectionDefect],
    *,
    image_width: int,
    image_height: int,
    class_weights: Mapping[str, float] | None = None,
    default_weight: float = 1.0,
) -> int:
    """Calculate the quality-v1 heuristic in original-image coordinates."""

    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if default_weight <= 0.0:
        raise ValueError("default quality weight must be positive")
    if not defects:
        return 100

    weights = class_weights or {}
    image_area = float(image_width * image_height)
    penalty = 0.0
    for defect in defects:
        class_weight = float(weights.get(defect.type, default_weight))
        if class_weight <= 0.0:
            raise ValueError(f"Quality weight must be positive: {defect.type}")
        area_ratio = min(1.0, max(0.0, defect.bounding_box.area / image_area))
        penalty += class_weight * defect.confidence * (10.0 + 90.0 * area_ratio)

    rounded_score = math.floor(100.0 - penalty + 0.5)
    return max(0, min(100, rounded_score))
