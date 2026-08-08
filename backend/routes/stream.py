"""Non-persisted live-frame inspection endpoint."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from backend.detection.runtime import DetectionRuntimeManager, ProductNameValidationError
from backend.models.record import (
    BoundingBoxRecord,
    DefectRecord,
    ModelRecord,
    StreamInspectionRecord,
)
from backend.utils.model_loader import (
    ModelNotFoundError,
    ModelNotInstalledError,
    ProductNameRequiredError,
)

from .dependencies import get_detection_runtime, get_inference_lock
from .images import decode_upload


router = APIRouter(prefix="/api", tags=["stream"])


@router.post("/stream", response_model=StreamInspectionRecord)
def inspect_stream_frame(
    request: Request,
    frame: UploadFile,
    model_id: str | None = Form(default=None, alias="modelId"),
    product_name: str | None = Form(default=None, alias="productName"),
    detection_runtime: DetectionRuntimeManager = Depends(get_detection_runtime),
    inference_lock: threading.Lock = Depends(get_inference_lock),
) -> StreamInspectionRecord:
    decoded = decode_upload(
        frame,
        max_bytes=request.app.state.settings.max_upload_bytes,
        allowed_media_types=frozenset({"image/jpeg"}),
    )
    try:
        with inference_lock:
            result = detection_runtime.inspect(
                decoded.image,
                model_id,
                product_name=product_name,
            )
    except (ProductNameRequiredError, ProductNameValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except ModelNotFoundError:
        raise HTTPException(status_code=404, detail="Detection model not found") from None
    except ModelNotInstalledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection model error",
        ) from None
    model_spec = detection_runtime.registry.get(result.model_id)
    return StreamInspectionRecord(
        frame_width=result.image_width,
        frame_height=result.image_height,
        defects=tuple(
            DefectRecord(
                type=defect.type,
                confidence=defect.confidence,
                bounding_box=BoundingBoxRecord(**defect.bounding_box.to_dict()),
            )
            for defect in result.defects
        ),
        total_defects=result.total_defects,
        quality_score=result.quality_score,
        status=result.status,
        model=ModelRecord(id=model_spec.model_id, display_name=model_spec.display_name),
    )
