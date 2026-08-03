"""CSV history projection with the canonical server-side filters."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from fastapi import APIRouter, Depends, Response

from backend.models.record import InspectionSummaryRecord
from backend.storage.repository import HistoryFilters
from backend.storage.service import InspectionStorage

from .dependencies import get_storage
from .filters import get_history_filters
from .serialization import to_summary


router = APIRouter(prefix="/api", tags=["export"])
CSV_COLUMNS = (
    "inspectionId",
    "timestamp",
    "defectCount",
    "types",
    "qualityScore",
    "status",
)


def _unique_types(record: InspectionSummaryRecord) -> str:
    return " | ".join(dict.fromkeys(defect.type for defect in record.defects))


def render_history_csv(records: Sequence[InspectionSummaryRecord]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for record in records:
        serialized = record.model_dump(mode="json", by_alias=True)
        writer.writerow(
            (
                serialized["inspectionId"],
                serialized["timestamp"],
                serialized["totalDefects"],
                _unique_types(record),
                serialized["qualityScore"],
                serialized["status"],
            )
        )
    return output.getvalue()


@router.get("/export")
def export_history(
    filters: HistoryFilters = Depends(get_history_filters),
    storage: InspectionStorage = Depends(get_storage),
) -> Response:
    summaries = [to_summary(record) for record in storage.list(filters)]
    return Response(
        content=render_history_csv(summaries).encode("utf-8"),
        headers={
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="inspection-history.csv"',
        },
    )
