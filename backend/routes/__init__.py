"""Implemented inspection, history, stream, and export FastAPI routers."""

from .detect import router as detect_router
from .export import router as export_router
from .history import router as history_router
from .models import router as models_router
from .samples import router as samples_router
from .stream import router as stream_router

models_router.routes.extend(samples_router.routes)

__all__ = [
    "detect_router",
    "export_router",
    "history_router",
    "models_router",
    "stream_router",
]
