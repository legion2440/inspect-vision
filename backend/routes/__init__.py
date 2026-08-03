"""Implemented FastAPI routers; stream and CSV remain deferred."""

from .detect import router as detect_router
from .history import router as history_router

__all__ = ["detect_router", "history_router"]
