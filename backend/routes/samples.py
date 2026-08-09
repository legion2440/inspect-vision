"""Curated inspection showcase served through stable manifest IDs."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response


router = APIRouter(prefix="/api/samples", tags=["samples"])

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "samples"
MANIFEST_PATH = SAMPLES_ROOT / "showcase-samples.json"
MAX_SAMPLE_BYTES = 10 * 1024 * 1024


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


@lru_cache(maxsize=32)
def _load_remote_sample(
    asset_url: str,
    expected_sha256: str = "",
    expected_size: int = 0,
) -> bytes:
    request = urllib.request.Request(asset_url, headers={"User-Agent": "Inspect-Vision/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as source:
            payload = source.read(MAX_SAMPLE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise HTTPException(status_code=502, detail="Could not load the pinned sample source") from error
    if not payload or len(payload) > MAX_SAMPLE_BYTES:
        raise HTTPException(status_code=502, detail="Pinned sample source returned invalid image bytes")
    if expected_size and len(payload) != expected_size:
        raise HTTPException(status_code=502, detail="Pinned sample source size changed")
    if expected_sha256 and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise HTTPException(status_code=502, detail="Pinned sample source hash changed")
    return payload


@router.get("")
def list_samples() -> dict[str, Any]:
    manifest = load_showcase_manifest()
    return {
        "notice": manifest["notice"],
        "datasets": manifest["datasets"],
        "samples": [
            {
                **{key: value for key, value in sample.items() if key != "assetUrl"},
                "imageUrl": f"/api/samples/{sample['id']}/image",
            }
            for sample in manifest["samples"]
        ],
    }


@router.get("/{sample_id}/image", response_class=Response)
def get_sample_image(sample_id: str) -> Response:
    sample = _sample_by_id(sample_id)
    asset_url = sample.get("assetUrl")
    if not isinstance(asset_url, str):
        raise HTTPException(status_code=500, detail="Pinned sample source is not configured")
    payload = _load_remote_sample(
        asset_url,
        str(sample.get("sha256", "")),
        int(sample.get("sizeBytes", 0)),
    )
    return Response(content=payload, media_type=sample["mediaType"])
