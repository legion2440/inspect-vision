"""Persisted inspection list, detail, delete, and clear endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.models.record import (
    ClearHistoryResponse,
    DeleteInspectionResponse,
    InspectionDetailRecord,
    InspectionSummaryRecord,
)
from backend.storage.repository import HistoryFilters
from backend.storage.service import InspectionStorage

from .dependencies import get_storage
from .serialization import to_detail, to_summary


router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[InspectionSummaryRecord])
def list_history(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    defect_type: str | None = Query(default=None, alias="type"),
    query: str | None = Query(default=None, alias="q"),
    storage: InspectionStorage = Depends(get_storage),
) -> list[InspectionSummaryRecord]:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from must not be after to",
        )
    filters = HistoryFilters(
        from_date=from_date,
        to_date=to_date,
        defect_type=defect_type,
        query=query,
    )
    return [to_summary(record) for record in storage.list(filters)]


@router.get("/{inspection_id}", response_model=InspectionDetailRecord)
def get_inspection(
    inspection_id: str,
    storage: InspectionStorage = Depends(get_storage),
) -> InspectionDetailRecord:
    record = storage.get(inspection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    original_bytes, annotated_bytes = storage.read_media(record)
    return to_detail(
        record,
        original_bytes=original_bytes,
        annotated_bytes=annotated_bytes,
    )


@router.delete("/{inspection_id}", response_model=DeleteInspectionResponse)
def delete_inspection(
    inspection_id: str,
    storage: InspectionStorage = Depends(get_storage),
) -> DeleteInspectionResponse:
    record = storage.delete(inspection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return DeleteInspectionResponse(inspection_id=inspection_id)


@router.post("/clear", response_model=ClearHistoryResponse)
def clear_history(
    storage: InspectionStorage = Depends(get_storage),
) -> ClearHistoryResponse:
    return ClearHistoryResponse(cleared=storage.clear())
