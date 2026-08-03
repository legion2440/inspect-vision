"""Pydantic models for the stable frontend/backend inspection contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class BoundingBoxRecord(ContractModel):
    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)


class DefectRecord(ContractModel):
    type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBoxRecord


class ModelRecord(ContractModel):
    name: str = Field(min_length=1)
    version: str = "1"


class InspectionSummaryRecord(ContractModel):
    inspection_id: str = Field(min_length=1)
    timestamp: datetime
    file_name: str = Field(min_length=1)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    defects: tuple[DefectRecord, ...]
    total_defects: int = Field(ge=0)
    quality_score: int = Field(ge=0, le=100)
    status: Literal["passed", "failed"]
    model: ModelRecord

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @model_validator(mode="after")
    def validate_invariants(self) -> InspectionSummaryRecord:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.total_defects != len(self.defects):
            raise ValueError("totalDefects must equal defects length")
        expected_status = "passed" if self.total_defects == 0 else "failed"
        if self.status != expected_status:
            raise ValueError("status must be passed only when totalDefects is zero")
        for defect in self.defects:
            box = defect.bounding_box
            if box.x + box.width > self.image_width or box.y + box.height > self.image_height:
                raise ValueError("defect boundingBox exceeds original dimensions")
        return self


class InspectionDetailRecord(InspectionSummaryRecord):
    image_url: str = Field(pattern=r"^data:image/(jpeg|png);base64,")
    original_image_url: str = Field(pattern=r"^data:image/(jpeg|png);base64,")


class DeleteInspectionResponse(ContractModel):
    inspection_id: str
    deleted: Literal[True] = True


class ClearHistoryResponse(ContractModel):
    cleared: int = Field(ge=0)
