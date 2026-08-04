"""FastAPI application composition for Inspect-Vision."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.detection.runtime import DetectionRuntimeManager
from backend.routes import (
    detect_router,
    export_router,
    history_router,
    models_router,
    stream_router,
)
from backend.storage.media import MediaStore
from backend.storage.repository import SQLiteInspectionRepository
from backend.storage.service import InspectionStorage
from backend.utils.model_loader import ModelRegistry


DetectionRuntimeFactory = Callable[[Settings], DetectionRuntimeManager]
StorageFactory = Callable[[Settings], InspectionStorage]


def build_detection_runtime(settings: Settings) -> DetectionRuntimeManager:
    return DetectionRuntimeManager(
        ModelRegistry(),
        models_directory=settings.models_dir,
        device=settings.model_device,
    )


def build_storage(settings: Settings) -> InspectionStorage:
    return InspectionStorage(
        SQLiteInspectionRepository(settings.database_path),
        MediaStore(settings.media_dir),
    )


def create_app(
    settings: Settings | None = None,
    *,
    detection_runtime_factory: DetectionRuntimeFactory = build_detection_runtime,
    storage_factory: StorageFactory = build_storage,
) -> FastAPI:
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        storage = storage_factory(runtime_settings)
        storage.initialize()
        app.state.settings = runtime_settings
        app.state.storage = storage
        app.state.detection_runtime = detection_runtime_factory(runtime_settings)
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
    application.include_router(models_router)
    return application


app = create_app()
