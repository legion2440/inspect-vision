from __future__ import annotations

import numpy as np

from backend.detection.annotation import annotate_image
from backend.detection.dto import BoundingBox, InspectionDefect


def test_annotation_draws_on_copy_at_original_dimensions() -> None:
    image = np.full((80, 120, 3), 180, dtype=np.uint8)
    original = image.copy()
    defect = InspectionDefect(
        "pitted_surface",
        0.91,
        BoundingBox(20.0, 25.0, 40.0, 30.0),
    )

    annotated = annotate_image(image, (defect,))

    assert annotated.shape == image.shape
    assert annotated.dtype == np.uint8
    assert annotated is not image
    np.testing.assert_array_equal(image, original)
    assert not np.array_equal(annotated, original)


def test_clean_annotation_is_an_unmodified_copy() -> None:
    image = np.full((20, 30, 3), 100, dtype=np.uint8)

    annotated = annotate_image(image, ())

    assert annotated is not image
    np.testing.assert_array_equal(annotated, image)
