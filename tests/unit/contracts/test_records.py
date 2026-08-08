from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.models.record import AvailableModelRecord, InspectionSummaryRecord


def valid_record() -> dict[str, object]:
    return {
        "inspectionId": "insp_contract",
        "timestamp": datetime(2026, 8, 3, tzinfo=UTC),
        "fileName": "part.png",
        "imageWidth": 100,
        "imageHeight": 50,
        "defects": [
            {
                "type": "scratches",
                "confidence": 0.9,
                "boundingBox": {"x": 10, "y": 5, "width": 20, "height": 10},
            }
        ],
        "totalDefects": 1,
        "qualityScore": 80,
        "status": "failed",
        "model": {"id": "neu-defect-yolov8", "displayName": "Steel Surface"},
    }


def test_contract_serializes_camel_case_and_utc() -> None:
    record = InspectionSummaryRecord.model_validate(valid_record())

    serialized = record.model_dump(mode="json", by_alias=True)

    assert serialized["inspectionId"] == "insp_contract"
    assert serialized["timestamp"] == "2026-08-03T00:00:00.000000Z"
    assert serialized["defects"][0]["boundingBox"]["width"] == 20.0


def test_contract_rejects_out_of_bounds_box() -> None:
    payload = valid_record()
    payload["defects"][0]["boundingBox"]["width"] = 100

    with pytest.raises(ValidationError, match="exceeds original dimensions"):
        InspectionSummaryRecord.model_validate(payload)


def test_contract_rejects_status_count_mismatch() -> None:
    payload = valid_record()
    payload["status"] = "passed"

    with pytest.raises(ValidationError, match="status must be passed"):
        InspectionSummaryRecord.model_validate(payload)


def test_public_model_contract_accepts_guided_bayespfl_profile() -> None:
    model = AvailableModelRecord.model_validate(
        {
            "id": "bayespfl-general-v1",
            "displayName": "General Manufacturing (Bayes-PFL)",
            "role": "general",
            "domain": "Cross-domain manufacturing anomaly localization",
            "description": "Category-guided anomaly localization.",
            "classes": ["anomaly"],
            "preprocessingProfile": "bayespfl-stretch",
            "requiresProductName": True,
            "isDefault": True,
            "installed": True,
        }
    )

    assert model.preprocessing_profile == "bayespfl-stretch"
    assert model.requires_product_name is True
