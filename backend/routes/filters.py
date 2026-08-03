"""One canonical FastAPI dependency for history and export filters."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Query, status

from backend.storage.repository import HistoryFilters


def get_history_filters(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    defect_type: str | None = Query(default=None, alias="type"),
    query: str | None = Query(default=None, alias="q"),
) -> HistoryFilters:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from must not be after to",
        )
    return HistoryFilters(
        from_date=from_date,
        to_date=to_date,
        defect_type=defect_type,
        query=query,
    )
