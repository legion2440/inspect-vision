"""FastAPI application composition for Inspect-Vision."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.detection.service import DetectionService
from backend.routes import detect_router, export_router, history_router, stream_router
from backend.storage.media import MediaStore
from backend.storage.repository import SQLiteInspectionRepository
from backend.storage.service import InspectionStorage
from backend.utils.model_loader import create_detector
from backend.utils.preprocessing import InspectionPreprocessingConfig


DetectionServiceFactory = Callable[[Settings], DetectionService]
StorageFactory = Callable[[Settings], InspectionStorage]


def build_detection_service(settings: Settings) -> DetectionService:
    detector = create_detector(
        settings.model_id,
        model_path=settings.model_path,
        device=settings.model_device,
        confidence=settings.model_confidence,
        iou=settings.model_iou,
    )
    if detector.image_size != settings.model_input_size:
        raise ValueError("configured model input size does not match the manifest")
    detector.load()
    return DetectionService(
        detector,
        preprocessing=InspectionPreprocessingConfig(
            input_size=settings.model_input_size,
            clahe_clip_limit=settings.clahe_clip_limit,
            clahe_tile_grid_size=(
                settings.clahe_tile_grid_size,
                settings.clahe_tile_grid_size,
            ),
        ),
    )


def build_storage(settings: Settings) -> InspectionStorage:
    return InspectionStorage(
        SQLiteInspectionRepository(settings.database_path),
        MediaStore(settings.media_dir),
    )


def create_app(
    settings: Settings | None = None,
    *,
    detection_service_factory: DetectionServiceFactory = build_detection_service,
    storage_factory: StorageFactory = build_storage,
) -> FastAPI:
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        storage = storage_factory(runtime_settings)
        storage.initialize()
        app.state.settings = runtime_settings
        app.state.storage = storage
        app.state.detection_service = detection_service_factory(runtime_settings)
        app.state.inference_lock = threading.Lock()
        yield

    application = FastAPI(title="Inspect-Vision API", version="1", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(detect_router)
    application.include_router(history_router)
    application.include_router(stream_router)
    application.include_router(export_router)
    return application


app = create_app()
