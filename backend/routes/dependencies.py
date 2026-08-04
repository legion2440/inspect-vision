"""FastAPI dependency boundaries backed by lifespan-created application state."""

from __future__ import annotations

import threading

from fastapi import Request

from backend.detection.runtime import DetectionRuntimeManager
from backend.storage.service import InspectionStorage
from backend.utils.model_loader import ModelRegistry


def get_detection_runtime(request: Request) -> DetectionRuntimeManager:
    return request.app.state.detection_runtime


def get_model_registry(request: Request) -> ModelRegistry:
    return request.app.state.detection_runtime.registry


def get_storage(request: Request) -> InspectionStorage:
    return request.app.state.storage


def get_inference_lock(request: Request) -> threading.Lock:
    return request.app.state.inference_lock
