"""OpenCV decoding, inspection preprocessing, and coordinate utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class LetterboxInfo:
    original_shape: tuple[int, int]
    input_shape: tuple[int, int]
    scale: float
    pad_x: float
    pad_y: float


@dataclass(frozen=True, slots=True)
class InspectionPreprocessingConfig:
    input_size: int = 640
    profile: Literal["standard-color", "steel-enhanced"] = "steel-enhanced"
    padding_color: tuple[int, int, int] = (114, 114, 114)
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple[int, int] = (8, 8)

    def __post_init__(self) -> None:
        if self.input_size <= 0:
            raise ValueError("input_size must be positive")
        if self.profile not in {"standard-color", "steel-enhanced"}:
            raise ValueError(f"Unsupported preprocessing profile: {self.profile}")
        if len(self.padding_color) != 3 or any(
            value < 0 or value > 255 for value in self.padding_color
        ):
            raise ValueError("padding_color must contain three uint8 values")
        if self.clahe_clip_limit <= 0.0:
            raise ValueError("clahe_clip_limit must be positive")
        if (
            len(self.clahe_tile_grid_size) != 2
            or self.clahe_tile_grid_size[0] <= 0
            or self.clahe_tile_grid_size[1] <= 0
        ):
            raise ValueError("clahe_tile_grid_size must contain two positive integers")


@dataclass(frozen=True, slots=True)
class InspectionPreprocessingResult:
    model_input: np.ndarray
    grayscale: np.ndarray | None
    contrast_adjusted: np.ndarray | None
    letterbox_info: LetterboxInfo


def validate_bgr_image(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a numpy.ndarray")
    if image.dtype != np.uint8:
        raise ValueError("image must use uint8 pixels")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must have shape HxWx3 in BGR order")
    if image.shape[0] <= 0 or image.shape[1] <= 0:
        raise ValueError("image must not be empty")


def decode_image(encoded: bytes | bytearray | memoryview) -> np.ndarray:
    """Decode image bytes into a validated three-channel BGR array."""

    if not isinstance(encoded, (bytes, bytearray, memoryview)):
        raise TypeError("encoded image must be bytes-like")
    payload = bytes(encoded)
    if not payload:
        raise ValueError("encoded image must not be empty")
    is_png = payload.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = payload.startswith(b"\xff\xd8")
    if not (is_png or is_jpeg):
        raise ValueError("encoded image must be JPEG or PNG content")
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("encoded image could not be decoded")
    validate_bgr_image(image)
    return image


def letterbox(
    image: np.ndarray,
    size: int | tuple[int, int] = 640,
    color: tuple[int, int, int] = (114, 114, 114),
) -> tuple[np.ndarray, LetterboxInfo]:
    validate_bgr_image(image)
    target_h, target_w = (size, size) if isinstance(size, int) else size
    if target_h <= 0 or target_w <= 0:
        raise ValueError("letterbox size must be positive")
    height, width = image.shape[:2]
    scale = min(target_w / width, target_h / height)
    resized_w = int(round(width * scale))
    resized_h = int(round(height * scale))
    resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    pad_w = target_w - resized_w
    pad_h = target_h - resized_h
    left = pad_w // 2
    right = pad_w - left
    top = pad_h // 2
    bottom = pad_h - top
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=color,
    )
    return padded, LetterboxInfo(
        original_shape=(height, width),
        input_shape=(target_h, target_w),
        scale=scale,
        pad_x=float(left),
        pad_y=float(top),
    )


def to_grayscale(image: np.ndarray) -> np.ndarray:
    validate_bgr_image(image)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def apply_clahe(
    grayscale: np.ndarray,
    *,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    if not isinstance(grayscale, np.ndarray):
        raise TypeError("grayscale image must be a numpy.ndarray")
    if grayscale.dtype != np.uint8 or grayscale.ndim != 2:
        raise ValueError("grayscale image must have shape HxW with uint8 pixels")
    if grayscale.shape[0] <= 0 or grayscale.shape[1] <= 0:
        raise ValueError("grayscale image must not be empty")
    if clip_limit <= 0.0:
        raise ValueError("clip_limit must be positive")
    if len(tile_grid_size) != 2 or tile_grid_size[0] <= 0 or tile_grid_size[1] <= 0:
        raise ValueError("tile_grid_size must contain two positive integers")
    clahe = cv2.createCLAHE(
        clipLimit=float(clip_limit),
        tileGridSize=(int(tile_grid_size[0]), int(tile_grid_size[1])),
    )
    return clahe.apply(grayscale)


def grayscale_to_bgr(grayscale: np.ndarray) -> np.ndarray:
    if not isinstance(grayscale, np.ndarray):
        raise TypeError("grayscale image must be a numpy.ndarray")
    if grayscale.dtype != np.uint8 or grayscale.ndim != 2:
        raise ValueError("grayscale image must have shape HxW with uint8 pixels")
    if grayscale.shape[0] <= 0 or grayscale.shape[1] <= 0:
        raise ValueError("grayscale image must not be empty")
    return cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)


def preprocess_inspection_image(
    image: np.ndarray,
    config: InspectionPreprocessingConfig = InspectionPreprocessingConfig(),
) -> InspectionPreprocessingResult:
    """Build the single 640-square geometry used by the inspection service."""

    validate_bgr_image(image)
    padded, info = letterbox(image, config.input_size, config.padding_color)
    if config.profile == "standard-color":
        return InspectionPreprocessingResult(
            model_input=np.ascontiguousarray(padded),
            grayscale=None,
            contrast_adjusted=None,
            letterbox_info=info,
        )

    grayscale = to_grayscale(padded)
    contrast_adjusted = apply_clahe(
        grayscale,
        clip_limit=config.clahe_clip_limit,
        tile_grid_size=config.clahe_tile_grid_size,
    )
    model_input = grayscale_to_bgr(contrast_adjusted)
    return InspectionPreprocessingResult(
        model_input=model_input,
        grayscale=grayscale,
        contrast_adjusted=contrast_adjusted,
        letterbox_info=info,
    )


def to_normalized_rgb_tensor(
    image: np.ndarray,
    image_size: int = 640,
) -> tuple[np.ndarray, LetterboxInfo]:
    padded, info = letterbox(image, image_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
    return np.ascontiguousarray(tensor), info


def restore_boxes(boxes: np.ndarray, info: LetterboxInfo) -> np.ndarray:
    restored = np.asarray(boxes, dtype=np.float32).copy().reshape(-1, 4)
    if len(restored) == 0:
        return restored
    restored[:, [0, 2]] -= info.pad_x
    restored[:, [1, 3]] -= info.pad_y
    restored /= info.scale
    height, width = info.original_shape
    restored[:, [0, 2]] = restored[:, [0, 2]].clip(0, width)
    restored[:, [1, 3]] = restored[:, [1, 3]].clip(0, height)
    return restored
