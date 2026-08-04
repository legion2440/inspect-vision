"""Reusable multiclass detection core and inspection orchestration service."""

from .annotation import annotate_image
from .base import DetectorBackend
from .device import DeviceInfo, select_device
from .dto import (
    BoundingBox,
    Detection,
    InferenceResult,
    InspectionDefect,
    InspectionResult,
)
from .quality import QUALITY_SCORE_VERSION, calculate_quality_score
from .service import DetectionService
from .ultralytics_backend import UltralyticsBackend

__all__ = [
    "BoundingBox",
    "Detection",
    "DetectionService",
    "DetectorBackend",
    "DeviceInfo",
    "InferenceResult",
    "InspectionDefect",
    "InspectionResult",
    "QUALITY_SCORE_VERSION",
    "UltralyticsBackend",
    "annotate_image",
    "calculate_quality_score",
    "select_device",
]
