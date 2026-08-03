"""Multipart image inspection endpoint."""

from __future__ import annotations

import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

import cv2
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from backend.detection.dto import InspectionResult
from backend.detection.service import DetectionService
from backend.models.record import InspectionDetailRecord
from backend.storage.service import InspectionDraft, InspectionStorage
from backend.utils.preprocessing import decode_image

from .dependencies import get_detection_service, get_inference_lock, get_storage
from .serialization import to_detail


router = APIRouter(prefix="/api", tags=["inspection"])


def detect_media_type(payload: bytes) -> tuple[str, str]:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if payload.startswith(b"\xff\xd8"):
        return "image/jpeg", "jpg"
    raise ValueError("unsupported image content")


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
    detection_service: DetectionService = Depends(get_detection_service),
    storage: InspectionStorage = Depends(get_storage),
    inference_lock: threading.Lock = Depends(get_inference_lock),
) -> InspectionDetailRecord:
    max_bytes: int = request.app.state.settings.max_upload_bytes
    payload = image.file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File size exceeds 10MB limit",
        )
    try:
        media_type, extension = detect_media_type(payload)
        decoded = decode_image(payload)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        ) from None

    try:
        with inference_lock:
            result = detection_service.inspect(decoded)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection model error",
        ) from None

    encoded, annotated_buffer = cv2.imencode(f".{extension}", result.annotated_image)
    if not encoded:
        raise HTTPException(status_code=500, detail="Internal server error")
    now = datetime.now(UTC)
    identifier = inspection_id(now)
    draft = InspectionDraft(
        inspection_id=identifier,
        timestamp=now,
        filename=sanitize_filename(image.filename, extension),
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
        original_bytes=payload,
        annotated_bytes=annotated_buffer.tobytes(),
        extension=extension,
        media_type=media_type,
    )
    original_bytes, annotated_bytes = storage.read_media(record)
    return to_detail(
        record,
        original_bytes=original_bytes,
        annotated_bytes=annotated_bytes,
    )
