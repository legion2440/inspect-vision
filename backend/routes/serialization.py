"""Convert persistence DTOs and media bytes to the public HTTP contract."""

from __future__ import annotations

import base64

from backend.models.record import (
    BoundingBoxRecord,
    DefectRecord,
    InspectionDetailRecord,
    InspectionSummaryRecord,
    ModelRecord,
)
from backend.storage.repository import InspectionRecord


def data_url(media_type: str, content: bytes) -> str:
    return f"data:{media_type};base64,{base64.b64encode(content).decode('ascii')}"


def to_summary(record: InspectionRecord) -> InspectionSummaryRecord:
    defects = tuple(
        DefectRecord(
            type=defect["type"],
            confidence=defect["confidence"],
            bounding_box=BoundingBoxRecord.model_validate(defect["boundingBox"]),
        )
        for defect in record.defects
    )
    return InspectionSummaryRecord(
        inspection_id=record.inspection_id,
        timestamp=record.timestamp,
        file_name=record.filename,
        image_width=record.image_width,
        image_height=record.image_height,
        defects=defects,
        total_defects=record.total_defects,
        quality_score=record.quality_score,
        status=record.status,
        model=ModelRecord(name=record.model_id, version="1"),
    )


def to_detail(
    record: InspectionRecord,
    *,
    original_bytes: bytes,
    annotated_bytes: bytes,
) -> InspectionDetailRecord:
    summary = to_summary(record)
    return InspectionDetailRecord(
        **summary.model_dump(),
        image_url=data_url(record.media_type, annotated_bytes),
        original_image_url=data_url(record.media_type, original_bytes),
    )
