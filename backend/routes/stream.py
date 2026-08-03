"""Non-persisted live-frame inspection endpoint."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from backend.detection.service import DetectionService
from backend.models.record import BoundingBoxRecord, DefectRecord, StreamInspectionRecord

from .dependencies import get_detection_service, get_inference_lock
from .images import decode_upload


router = APIRouter(prefix="/api", tags=["stream"])


@router.post("/stream", response_model=StreamInspectionRecord)
def inspect_stream_frame(
    request: Request,
    frame: UploadFile,
    detection_service: DetectionService = Depends(get_detection_service),
    inference_lock: threading.Lock = Depends(get_inference_lock),
) -> StreamInspectionRecord:
    decoded = decode_upload(
        frame,
        max_bytes=request.app.state.settings.max_upload_bytes,
        allowed_media_types=frozenset({"image/jpeg"}),
    )
    try:
        with inference_lock:
            result = detection_service.inspect(decoded.image)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection model error",
        ) from None
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
    )
