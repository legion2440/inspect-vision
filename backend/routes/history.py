"""Persisted inspection list, detail, delete, and clear endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.models.record import (
    ClearHistoryResponse,
    DeleteInspectionResponse,
    InspectionDetailRecord,
    InspectionSummaryRecord,
)
from backend.storage.repository import HistoryFilters
from backend.storage.service import InspectionStorage

from .dependencies import get_storage
from .filters import get_history_filters
from .serialization import to_detail, to_summary


router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[InspectionSummaryRecord])
def list_history(
    filters: HistoryFilters = Depends(get_history_filters),
    storage: InspectionStorage = Depends(get_storage),
) -> list[InspectionSummaryRecord]:
    return [to_summary(record) for record in storage.list(filters)]


@router.get("/{inspection_id}", response_model=InspectionDetailRecord)
def get_inspection(
    inspection_id: str,
    storage: InspectionStorage = Depends(get_storage),
) -> InspectionDetailRecord:
    stored = storage.get_with_media(inspection_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    record, original_bytes, annotated_bytes = stored
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
