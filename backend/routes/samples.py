"""Curated, redistributable inspection samples served from manifest IDs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(prefix="/api/samples", tags=["samples"])

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "samples"
MANIFEST_PATH = SAMPLES_ROOT / "showcase-samples.json"
IMAGE_DIRECTORY = (SAMPLES_ROOT / "showcase").resolve()


@lru_cache(maxsize=1)
def load_showcase_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest, dict):
        raise TypeError("Showcase manifest must contain a JSON object")
    return manifest


def _sample_by_id(sample_id: str) -> dict[str, Any]:
    for sample in load_showcase_manifest().get("samples", []):
        if sample.get("id") == sample_id:
            return sample
    raise HTTPException(status_code=404, detail="Sample not found")


def _sample_path(sample: dict[str, Any]) -> Path:
    filename = sample.get("filename")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise RuntimeError("Invalid showcase sample filename")
    path = (IMAGE_DIRECTORY / filename).resolve()
    if path.parent != IMAGE_DIRECTORY or not path.is_file():
        raise RuntimeError("Showcase sample file is missing")
    return path


@router.get("")
def list_samples() -> dict[str, Any]:
    manifest = load_showcase_manifest()
    return {
        "notice": manifest["notice"],
        "datasets": manifest["datasets"],
        "samples": [
            {
                **sample,
                "imageUrl": f"/api/samples/{sample['id']}/image",
            }
            for sample in manifest["samples"]
        ],
    }


@router.get("/{sample_id}/image", response_class=FileResponse)
def get_sample_image(sample_id: str) -> FileResponse:
    sample = _sample_by_id(sample_id)
    return FileResponse(
        _sample_path(sample),
        media_type=sample["mediaType"],
    )
