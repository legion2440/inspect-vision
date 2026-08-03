"""Reusable multiclass defect-detection core."""

from .base import DetectorBackend
from .device import DeviceInfo, select_device
from .dto import Detection, InferenceResult
from .ultralytics_backend import UltralyticsBackend

__all__ = [
    "Detection",
    "DetectorBackend",
    "DeviceInfo",
    "InferenceResult",
    "UltralyticsBackend",
    "select_device",
]
