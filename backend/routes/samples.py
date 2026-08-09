"""Serve the tracked local demo corpus through stable sample IDs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(prefix="/api/samples", tags=["samples"])

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_ROOT = REPOSITORY_ROOT / "backend" / "samples"
DEMO_ROOT = (SAMPLES_ROOT / "demo").resolve()
MANIFEST_PATH = SAMPLES_ROOT / "demo-samples.json"

_PRODUCT_NAMES = {
    "candle": "Candle",
    "capsules": "Capsules",
    "cashew": "Cashew",
    "chewinggum": "Chewing gum",
}


@lru_cache(maxsize=1)
def load_demo_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest, dict):
        raise TypeError("Demo manifest must contain a JSON object")
    return manifest


def _sample_by_id(sample_id: str) -> dict[str, Any]:
    for sample in load_demo_manifest().get("files", []):
        if sample.get("id") == sample_id:
            return sample
    raise HTTPException(status_code=404, detail="Sample not found")


def _sample_path(sample: dict[str, Any]) -> Path:
    relative_path = sample.get("path")
    if not isinstance(relative_path, str):
        raise RuntimeError("Demo sample path is not configured")
    path = (REPOSITORY_ROOT / relative_path).resolve()
    if path.parent != DEMO_ROOT or not path.is_file():
        raise RuntimeError("Demo sample file is missing")
    return path


def _dataset_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    dataset = manifest.get("dataset", {})
    license_name = str(dataset.get("license", ""))
    return {
        "id": dataset.get("id", "visa"),
        "name": dataset.get("name", "Visual Anomaly (VisA)"),
        "authors": dataset.get("authors", []),
        "sourceUrl": dataset.get("repositoryUrl"),
        "sourceRevision": dataset.get("sourceRevision"),
        "license": {
            "name": license_name,
            "url": dataset.get("licenseUrl"),
        },
        "attribution": (
            f"{dataset.get('name', 'Visual Anomaly (VisA)')} demo images, "
            f"licensed {license_name}."
        ),
    }


def _sample_payload(sample: dict[str, Any]) -> dict[str, Any]:
    ground_truth = sample.get("sourceGroundTruth", {})
    category = str(ground_truth.get("category", "")).strip().casefold()
    product_name = _PRODUCT_NAMES.get(category, category.replace("_", " ").title())
    source_label = ground_truth.get("label")
    defect_labels = ground_truth.get("defectLabels")
    labels = defect_labels if isinstance(defect_labels, list) and defect_labels else ["normal"]
    dimensions = sample.get("dimensions", {})
    return {
        "id": sample["id"],
        "domain": product_name or "Other",
        "recommendedModelId": "bayespfl-general-v1",
        "datasetId": ground_truth.get("datasetId", "visa"),
        "productName": product_name,
        "condition": "good" if source_label == "normal" else "bad",
        "sourceLabels": labels,
        "sourcePath": ground_truth.get("imageArchivePath"),
        "filename": Path(str(sample["path"])).name,
        "mediaType": sample["mediaType"],
        "sha256": sample.get("sha256"),
        "sizeBytes": sample.get("byteSize"),
        "width": dimensions.get("width"),
        "height": dimensions.get("height"),
        "imageUrl": f"/api/samples/{sample['id']}/image",
    }


@router.get("")
def list_samples() -> dict[str, Any]:
    manifest = load_demo_manifest()
    return {
        "notice": "Source labels describe VisA dataset ground truth, not model predictions.",
        "datasets": [_dataset_payload(manifest)],
        "samples": [_sample_payload(sample) for sample in manifest.get("files", [])],
    }


@router.get("/{sample_id}/image", response_class=FileResponse)
def get_sample_image(sample_id: str) -> FileResponse:
    sample = _sample_by_id(sample_id)
    return FileResponse(
        _sample_path(sample),
        media_type=sample["mediaType"],
        filename=Path(str(sample["path"])).name,
    )
