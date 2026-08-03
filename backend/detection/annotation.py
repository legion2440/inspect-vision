"""Draw service-level defect annotations on original BGR images."""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from backend.utils.preprocessing import validate_bgr_image

from .dto import InspectionDefect


ANNOTATION_COLOR = (32, 32, 220)


def annotate_image(
    image: np.ndarray,
    defects: Sequence[InspectionDefect],
) -> np.ndarray:
    """Return an annotated copy while preserving the source image unchanged."""

    validate_bgr_image(image)
    annotated = image.copy()
    height, width = annotated.shape[:2]
    line_width = max(1, round(min(width, height) / 300))
    font_scale = max(0.4, min(width, height) / 900.0)

    for defect in defects:
        box = defect.bounding_box
        left = min(width - 1, max(0, int(round(box.x))))
        top = min(height - 1, max(0, int(round(box.y))))
        right_exclusive = min(width, max(left + 1, int(round(box.x + box.width))))
        bottom_exclusive = min(height, max(top + 1, int(round(box.y + box.height))))
        right = right_exclusive - 1
        bottom = bottom_exclusive - 1
        cv2.rectangle(
            annotated,
            (left, top),
            (right, bottom),
            ANNOTATION_COLOR,
            line_width,
            cv2.LINE_AA,
        )

        label = f"{defect.type} {defect.confidence:.2f}"
        (label_width, label_height), baseline = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            line_width,
        )
        label_box_width = min(width, label_width + 6)
        label_box_height = min(height, label_height + baseline + 4)
        label_left = min(left, width - label_box_width)
        if top >= label_box_height:
            label_top = top - label_box_height
        else:
            label_top = min(height - label_box_height, top + line_width)
        label_right = min(width - 1, label_left + label_box_width - 1)
        label_bottom = min(height - 1, label_top + label_box_height - 1)
        cv2.rectangle(
            annotated,
            (label_left, label_top),
            (label_right, label_bottom),
            ANNOTATION_COLOR,
            cv2.FILLED,
        )
        text_y = min(height - 1, label_top + label_height + 2)
        cv2.putText(
            annotated,
            label,
            (label_left + 3, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            line_width,
            cv2.LINE_AA,
        )

    return annotated
