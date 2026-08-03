from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from backend.models.record import InspectionSummaryRecord
from backend.routes.export import render_history_csv


def test_csv_writer_escapes_cells_and_keeps_unique_type_order() -> None:
    record = InspectionSummaryRecord.model_validate(
        {
            "inspectionId": 'insp,"quoted"',
            "timestamp": datetime(2026, 8, 3, tzinfo=UTC),
            "fileName": "part.jpg",
            "imageWidth": 100,
            "imageHeight": 100,
            "defects": [
                {
                    "type": "scratches,deep",
                    "confidence": 0.9,
                    "boundingBox": {"x": 1, "y": 1, "width": 5, "height": 5},
                },
                {
                    "type": 'quote"type',
                    "confidence": 0.8,
                    "boundingBox": {"x": 10, "y": 10, "width": 5, "height": 5},
                },
                {
                    "type": "scratches,deep",
                    "confidence": 0.7,
                    "boundingBox": {"x": 20, "y": 20, "width": 5, "height": 5},
                },
            ],
            "totalDefects": 3,
            "qualityScore": 70,
            "status": "failed",
            "model": {"name": "neu-defect-yolov8", "version": "1"},
        }
    )

    content = render_history_csv([record])
    rows = list(csv.DictReader(io.StringIO(content)))

    assert content.endswith("\n")
    assert rows == [
        {
            "inspectionId": 'insp,"quoted"',
            "timestamp": "2026-08-03T00:00:00.000000Z",
            "defectCount": "3",
            "types": 'scratches,deep | quote"type',
            "qualityScore": "70",
            "status": "failed",
        }
    ]
