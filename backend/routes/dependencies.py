"""FastAPI dependency boundaries backed by lifespan-created application state."""

from __future__ import annotations

import threading

from fastapi import Request

from backend.detection.service import DetectionService
from backend.storage.service import InspectionStorage


def get_detection_service(request: Request) -> DetectionService:
    return request.app.state.detection_service


def get_storage(request: Request) -> InspectionStorage:
    return request.app.state.storage


def get_inference_lock(request: Request) -> threading.Lock:
    return request.app.state.inference_lock
