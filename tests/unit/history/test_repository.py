from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from backend.storage.repository import (
    HistoryFilters,
    InspectionRecord,
    SQLiteInspectionRepository,
)


def make_record(
    inspection_id: str,
    *,
    timestamp: datetime,
    filename: str = "coil.png",
    defect_type: str | None = "scratches",
) -> InspectionRecord:
    defects = (
        (
            {
                "type": defect_type,
                "confidence": 0.91,
                "boundingBox": {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
            },
        )
        if defect_type
        else ()
    )
    return InspectionRecord(
        inspection_id=inspection_id,
        timestamp=timestamp,
        filename=filename,
        image_width=64,
        image_height=32,
        defects=defects,
        total_defects=len(defects),
        quality_score=82 if defects else 100,
        status="failed" if defects else "passed",
        model_id="neu-defect-yolov8",
        media_type="image/png",
        original_media_path=f"original/{inspection_id}.png",
        annotated_media_path=f"annotated/{inspection_id}.png",
    )


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteInspectionRepository:
    value = SQLiteInspectionRepository(tmp_path / "inspection.sqlite3")
    value.initialize()
    return value


def test_crud_survives_repository_reopen(
    repository: SQLiteInspectionRepository,
) -> None:
    record = make_record(
        "insp_first",
        timestamp=datetime(2026, 8, 3, 10, 20, tzinfo=UTC),
    )
    repository.create(record)

    reopened = SQLiteInspectionRepository(repository.database_path)
    reopened.initialize()

    assert reopened.get(record.inspection_id) == record
    assert reopened.list() == [record]
    assert reopened.media_paths() == {
        "original/insp_first.png",
        "annotated/insp_first.png",
    }
    assert reopened.delete(record.inspection_id)
    assert reopened.get(record.inspection_id) is None
    assert not reopened.delete(record.inspection_id)


def test_list_is_newest_first(repository: SQLiteInspectionRepository) -> None:
    older = make_record("insp_older", timestamp=datetime(2026, 8, 2, tzinfo=UTC))
    newer = make_record("insp_newer", timestamp=datetime(2026, 8, 3, tzinfo=UTC))
    repository.create(older)
    repository.create(newer)

    assert [record.inspection_id for record in repository.list()] == [
        "insp_newer",
        "insp_older",
    ]


def test_server_filters_are_combined_in_sql(
    repository: SQLiteInspectionRepository,
) -> None:
    records = (
        make_record(
            "insp_target",
            timestamp=datetime(2026, 8, 3, 12, tzinfo=UTC),
            filename="Line-A-Coil.PNG",
            defect_type="crazing",
        ),
        make_record(
            "insp_wrong_type",
            timestamp=datetime(2026, 8, 3, 13, tzinfo=UTC),
            filename="Line-A-Coil.PNG",
            defect_type="inclusion",
        ),
        make_record(
            "insp_wrong_day",
            timestamp=datetime(2026, 8, 4, 12, tzinfo=UTC),
            filename="Line-A-Coil.PNG",
            defect_type="crazing",
        ),
        make_record(
            "insp_wrong_query",
            timestamp=datetime(2026, 8, 3, 11, tzinfo=UTC),
            filename="other.png",
            defect_type="crazing",
        ),
    )
    for record in records:
        repository.create(record)

    result = repository.list(
        HistoryFilters(
            from_date=date(2026, 8, 3),
            to_date=date(2026, 8, 3),
            defect_type="crazing",
            query="line-a",
        )
    )

    assert [record.inspection_id for record in result] == ["insp_target"]


def test_query_matches_id_case_insensitively(
    repository: SQLiteInspectionRepository,
) -> None:
    record = make_record(
        "INSP_Special_42",
        timestamp=datetime(2026, 8, 3, tzinfo=UTC),
    )
    repository.create(record)

    assert repository.list(HistoryFilters(query="special_42")) == [record]


def test_all_type_disables_type_filter(repository: SQLiteInspectionRepository) -> None:
    record = make_record(
        "insp_any",
        timestamp=datetime(2026, 8, 3, tzinfo=UTC),
        defect_type=None,
    )
    repository.create(record)

    assert repository.list(HistoryFilters(defect_type="all")) == [record]


def test_clear_returns_deleted_count(repository: SQLiteInspectionRepository) -> None:
    repository.create(make_record("insp_a", timestamp=datetime(2026, 8, 3, tzinfo=UTC)))
    repository.create(make_record("insp_b", timestamp=datetime(2026, 8, 4, tzinfo=UTC)))

    assert repository.clear() == 2
    assert repository.list() == []


def test_invalid_filter_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="from_date"):
        HistoryFilters(from_date=date(2026, 8, 4), to_date=date(2026, 8, 3))


def test_record_invariants_are_enforced() -> None:
    with pytest.raises(ValueError, match="total_defects"):
        InspectionRecord(
            inspection_id="insp_bad",
            timestamp=datetime(2026, 8, 3, tzinfo=UTC),
            filename="bad.png",
            image_width=1,
            image_height=1,
            defects=(),
            total_defects=1,
            quality_score=100,
            status="passed",
            model_id="model",
            media_type="image/png",
            original_media_path="original/insp_bad.png",
            annotated_media_path="annotated/insp_bad.png",
        )
