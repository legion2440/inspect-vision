from __future__ import annotations

import cv2
import numpy as np
import pytest

from backend.utils.preprocessing import (
    InspectionPreprocessingConfig,
    apply_clahe,
    decode_image,
    grayscale_to_bgr,
    letterbox,
    preprocess_inspection_image,
    restore_boxes,
    to_grayscale,
    to_normalized_rgb_tensor,
    validate_bgr_image,
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


def test_decode_image_returns_valid_bgr_pixels() -> None:
    source = np.zeros((12, 18, 3), dtype=np.uint8)
    source[:, :] = [10, 80, 220]
    encoded, payload = cv2.imencode(".png", source)
    assert encoded

    decoded = decode_image(payload.tobytes())

    validate_bgr_image(decoded)
    assert decoded.shape == source.shape
    np.testing.assert_array_equal(decoded, source)


@pytest.mark.parametrize("payload", [b"", b"not-an-image"])
def test_decode_image_rejects_invalid_content(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode_image(payload)


def test_decode_image_rejects_other_decodable_formats() -> None:
    encoded, payload = cv2.imencode(".bmp", np.zeros((5, 5, 3), dtype=np.uint8))
    assert encoded

    with pytest.raises(ValueError, match="JPEG or PNG"):
        decode_image(payload.tobytes())


def test_grayscale_conversion_matches_opencv_bgr_semantics() -> None:
    image = np.array([[[10, 80, 220], [220, 80, 10]]], dtype=np.uint8)

    grayscale = to_grayscale(image)

    np.testing.assert_array_equal(grayscale, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    assert grayscale.shape == (1, 2)


def test_clahe_adjusts_local_contrast() -> None:
    grayscale = np.tile(np.arange(64, dtype=np.uint8), (64, 1)) + 80

    adjusted = apply_clahe(grayscale, clip_limit=2.0, tile_grid_size=(8, 8))

    assert adjusted.shape == grayscale.shape
    assert adjusted.dtype == np.uint8
    assert not np.array_equal(adjusted, grayscale)


def test_grayscale_to_bgr_repeats_the_adjusted_channel() -> None:
    grayscale = np.arange(12, dtype=np.uint8).reshape(3, 4)

    converted = grayscale_to_bgr(grayscale)

    assert converted.shape == (3, 4, 3)
    np.testing.assert_array_equal(converted[:, :, 0], grayscale)
    np.testing.assert_array_equal(converted[:, :, 1], grayscale)
    np.testing.assert_array_equal(converted[:, :, 2], grayscale)


def test_inspection_preprocessing_outputs_one_640_square_three_channel_image() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    image[:, :, 1] = np.arange(200, dtype=np.uint8)
    original = image.copy()

    result = preprocess_inspection_image(
        image,
        InspectionPreprocessingConfig(
            input_size=640,
            clahe_clip_limit=2.0,
            clahe_tile_grid_size=(8, 8),
        ),
    )

    assert result.model_input.shape == (640, 640, 3)
    assert result.grayscale.shape == (640, 640)
    assert result.contrast_adjusted.shape == (640, 640)
    assert result.letterbox_info.original_shape == (100, 200)
    assert result.letterbox_info.input_shape == (640, 640)
    np.testing.assert_array_equal(result.model_input[:, :, 0], result.contrast_adjusted)
    np.testing.assert_array_equal(result.model_input[:, :, 1], result.contrast_adjusted)
    np.testing.assert_array_equal(result.model_input[:, :, 2], result.contrast_adjusted)
    np.testing.assert_array_equal(image, original)
