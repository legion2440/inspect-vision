from __future__ import annotations

import numpy as np

from backend.utils.preprocessing import (
    letterbox,
    restore_boxes,
    to_normalized_rgb_tensor,
)


def test_letterbox_preserves_aspect_ratio_and_records_padding() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    padded, info = letterbox(image, 640)

    assert padded.shape == (640, 640, 3)
    assert info.original_shape == (100, 200)
    assert info.input_shape == (640, 640)
    assert info.scale == 3.2
    assert info.pad_x == 0.0
    assert info.pad_y == 160.0


def test_restore_boxes_returns_original_coordinates_and_clamps() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    _, info = letterbox(image, 640)
    model_boxes = np.array([[-5.0, 160.0, 650.0, 480.0]], dtype=np.float32)

    restored = restore_boxes(model_boxes, info)

    np.testing.assert_allclose(restored, [[0.0, 0.0, 200.0, 100.0]])


def test_normalized_tensor_is_rgb_nchw_float32() -> None:
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    image[0, 0] = [0, 127, 255]

    tensor, _ = to_normalized_rgb_tensor(image, 2)

    assert tensor.shape == (1, 3, 2, 2)
    assert tensor.dtype == np.float32
    np.testing.assert_allclose(tensor[0, :, 0, 0], [1.0, 127 / 255, 0.0])
