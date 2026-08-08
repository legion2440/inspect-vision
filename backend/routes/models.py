"""Public model registry endpoint for operator model selection."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.detection.runtime import DetectionRuntimeManager
from backend.models.record import AvailableModelRecord

from .dependencies import get_detection_runtime


router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models", response_model=list[AvailableModelRecord])
def list_models(
    detection_runtime: DetectionRuntimeManager = Depends(get_detection_runtime),
) -> list[AvailableModelRecord]:
    return [
        AvailableModelRecord(
            id=registered.spec.model_id,
            display_name=registered.spec.display_name,
            role=registered.spec.role,
            domain=registered.spec.domain,
            description=registered.spec.description,
            classes=registered.spec.native_classes,
            preprocessing_profile=registered.spec.preprocessing.profile_id,
            requires_product_name=registered.spec.requires_product_name,
            is_default=registered.is_default,
            installed=registered.installed,
        )
        for registered in detection_runtime.registered_models(exposed_only=True)
    ]
