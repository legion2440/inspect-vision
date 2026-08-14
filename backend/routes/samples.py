"""Serve the local operator demo corpus through stable sample IDs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .sample_catalog import DATASETS, SAMPLES


router = APIRouter(prefix="/api/samples", tags=["samples"])
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = (REPOSITORY_ROOT / "backend" / "samples" / "demo").resolve()


def _sample_by_id(sample_id: str) -> dict:
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            return sample
    raise HTTPException(status_code=404, detail="Sample not found")


def _sample_path(sample: dict) -> Path:
    path = (DEMO_ROOT / sample["filename"]).resolve()
    if path.parent != DEMO_ROOT or not path.is_file():
        raise RuntimeError("Demo sample file is missing")
    return path


@router.get("")
def list_samples() -> dict:
    return {
        "notice": "Source labels describe dataset metadata, not model predictions.",
        "datasets": DATASETS,
        "samples": [
            {**sample, "imageUrl": f"/api/samples/{sample['id']}/image"}
            for sample in SAMPLES
        ],
    }


@router.get("/{sample_id}/image", response_class=FileResponse)
def get_sample_image(sample_id: str) -> FileResponse:
    sample = _sample_by_id(sample_id)
    return FileResponse(_sample_path(sample), media_type=sample["mediaType"])
