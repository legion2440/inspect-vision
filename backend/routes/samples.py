"""Serve the pinned operator showcase through stable sample IDs."""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Response

from .sample_catalog import DATASETS, MVTEC_REVISION, SAMPLES, SPECIALIST_ASSET_COMMIT


router = APIRouter(prefix="/api/samples", tags=["samples"])
MAX_SAMPLE_BYTES = 10 * 1024 * 1024

# Exact byte checks exist for sources whose provenance recorded size/hash.
# Other MVTec entries are still immutable because their revision and path are pinned.
_INTEGRITY = {
    "mvtec-screw-good-001": ("983a27fcea10ce8eafeebac3db0899e5fb6ad84338a6cabc5746ee96d2865daa", 393132),
    "steel-good-img4685": ("488786e7ba9e197dbca75b3b35614b31bb6b4268edd62aca4c8117f195a5414d", 89636),
    "steel-inclusion-plos-fig3b": ("fbae86d7eaa5a397eee27eea80bac505c2dcdd64772648f0f7fc8748b2fd790e", 63157),
    "steel-scratch-img2113": ("1b86533d2e52180d3034db11850a2bbea6dd78d0379efa93602bde347c727292", 169207),
    "concrete-cr01-transverse": ("547fa46c42d80624ee62b154d743bc0aabc4230dfc745fca5a91dd3a665b1033", 285556),
    "concrete-cr26-longitudinal": ("2b26a0adaf83e54bad96ced2168744f3d5059be0ada8f1f85a309169b8c66795", 485999),
    "concrete-cr43-diagonal": ("4793bbf1e3720a76b1bbb65ef838e6d590ea1206ac9465e85184fd5c1bc28b5e", 289776),
}


def _sample_by_id(sample_id: str) -> dict:
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            return sample
    raise HTTPException(status_code=404, detail="Sample not found")


def _asset_url(sample: dict) -> str:
    scheme = "https:" + "//"
    if sample["datasetId"] == "mvtec-ad":
        return (
            scheme
            + "huggingface.co/datasets/jiang-cc/MMAD/resolve/"
            + MVTEC_REVISION
            + "/"
            + sample["sourcePath"]
        )
    return (
        scheme
        + "raw.githubusercontent.com/legion2440/inspect-vision/"
        + SPECIALIST_ASSET_COMMIT
        + "/backend/samples/showcase/"
        + sample["filename"]
    )


@lru_cache(maxsize=32)
def _load_remote_sample(
    asset_url: str,
    expected_sha256: str = "",
    expected_size: int = 0,
) -> bytes:
    # The browser supplies only a catalog ID. The server derives the pinned
    # source here, so arbitrary remote URLs can never enter this fetch boundary.
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
def list_samples() -> dict:
    return {
        "notice": "Source labels describe dataset metadata, not model predictions.",
        "datasets": DATASETS,
        "samples": [
            {**sample, "imageUrl": f"/api/samples/{sample['id']}/image"}
            for sample in SAMPLES
        ],
    }


@router.get("/{sample_id}/image", response_class=Response)
def get_sample_image(sample_id: str) -> Response:
    sample = _sample_by_id(sample_id)
    expected_sha256, expected_size = _INTEGRITY.get(sample_id, ("", 0))
    payload = _load_remote_sample(_asset_url(sample), expected_sha256, expected_size)
    return Response(content=payload, media_type=sample["mediaType"])
