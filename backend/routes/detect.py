"""Multipart image inspection endpoint."""

from __future__ import annotations

import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

import cv2
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from backend.detection.dto import InspectionResult
from backend.detection.runtime import DetectionRuntimeManager
from backend.models.record import InspectionDetailRecord
from backend.storage.service import InspectionDraft, InspectionStorage
from backend.utils.model_loader import ModelNotFoundError, ModelNotInstalledError
from .dependencies import get_detection_runtime, get_inference_lock, get_storage
from .images import decode_upload
from .serialization import to_detail


router = APIRouter(prefix="/api", tags=["inspection"])


def sanitize_filename(filename: str | None, extension: str) -> str:
    basename = PurePath((filename or "").replace("\\", "/")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    if not safe:
        safe = f"upload.{extension}"
    if len(safe) > 240:
        stem = PurePath(safe).stem[: 235 - len(extension)] or "upload"
        safe = f"{stem}.{extension}"
    return safe


def inspection_id(timestamp: datetime) -> str:
    prefix = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"insp_{prefix}_{uuid.uuid4().hex[:8]}"


def defects_for_storage(result: InspectionResult) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "type": defect.type,
            "confidence": defect.confidence,
            "boundingBox": defect.bounding_box.to_dict(),
        }
        for defect in result.defects
    )


@router.post("/inspect", response_model=InspectionDetailRecord)
def inspect_image(
    request: Request,
    image: UploadFile,
    model_id: str | None = Form(default=None, alias="modelId"),
    detection_runtime: DetectionRuntimeManager = Depends(get_detection_runtime),
    storage: InspectionStorage = Depends(get_storage),
    inference_lock: threading.Lock = Depends(get_inference_lock),
) -> InspectionDetailRecord:
    decoded = decode_upload(
        image,
        max_bytes=request.app.state.settings.max_upload_bytes,
    )

    try:
        with inference_lock:
            result = detection_runtime.inspect(decoded.image, model_id)
    except ModelNotFoundError:
        raise HTTPException(status_code=404, detail="Detection model not found") from None
    except ModelNotInstalledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection model error",
        ) from None

    encoded, annotated_buffer = cv2.imencode(
        f".{decoded.extension}",
        result.annotated_image,
    )
    if not encoded:
        raise HTTPException(status_code=500, detail="Internal server error")
    now = datetime.now(UTC)
    identifier = inspection_id(now)
    draft = InspectionDraft(
        inspection_id=identifier,
        timestamp=now,
        filename=sanitize_filename(image.filename, decoded.extension),
        image_width=result.image_width,
        image_height=result.image_height,
        defects=defects_for_storage(result),
        total_defects=result.total_defects,
        quality_score=result.quality_score,
        status=result.status,
        model_id=result.model_id,
    )
    record = storage.create(
        draft,
        original_bytes=decoded.payload,
        annotated_bytes=annotated_buffer.tobytes(),
        extension=decoded.extension,
        media_type=decoded.media_type,
    )
    return to_detail(
        record,
        original_bytes=decoded.payload,
        annotated_bytes=annotated_buffer.tobytes(),
        registry=detection_runtime.registry,
    )
