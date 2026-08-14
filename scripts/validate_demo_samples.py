"""Validate the single local operator/demo sample corpus."""

from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

import cv2

from backend.routes.sample_catalog import SAMPLES


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = (REPOSITORY_ROOT / "backend" / "samples" / "demo").resolve()
MAX_SAMPLE_BYTES = 10 * 1024 * 1024
EXPECTED_MODEL_COUNTS = {
    "bayespfl-general-v1": 8,
    "neu-defect-yolov8": 3,
    "concrete-crack-yolov8": 3,
}
VERIFIED_HASHES = {
    "mvtec-screw-good-001": "983a27fcea10ce8eafeebac3db0899e5fb6ad84338a6cabc5746ee96d2865daa",
    "steel-good-img4685": "488786e7ba9e197dbca75b3b35614b31bb6b4268edd62aca4c8117f195a5414d",
    "steel-inclusion-plos-fig3b": "fbae86d7eaa5a397eee27eea80bac505c2dcdd64772648f0f7fc8748b2fd790e",
    "steel-scratch-img2113": "1b86533d2e52180d3034db11850a2bbea6dd78d0379efa93602bde347c727292",
    "concrete-cr01-transverse": "547fa46c42d80624ee62b154d743bc0aabc4230dfc745fca5a91dd3a665b1033",
    "concrete-cr26-longitudinal": "2b26a0adaf83e54bad96ced2168744f3d5059be0ada8f1f85a309169b8c66795",
    "concrete-cr43-diagonal": "4793bbf1e3720a76b1bbb65ef838e6d590ea1206ac9465e85184fd5c1bc28b5e",
}


def validate_demo_samples() -> list[str]:
    errors: list[str] = []
    if len(SAMPLES) != 14:
        errors.append(f"Expected 14 demo samples, found {len(SAMPLES)}")

    ids = [sample.get("id") for sample in SAMPLES]
    filenames = [sample.get("filename") for sample in SAMPLES]
    if None in ids or len(set(ids)) != len(ids):
        errors.append("Demo sample IDs must be present and unique")
    if None in filenames or len(set(filenames)) != len(filenames):
        errors.append("Demo sample filenames must be present and unique")

    model_counts = Counter(sample.get("recommendedModelId") for sample in SAMPLES)
    if dict(model_counts) != EXPECTED_MODEL_COUNTS:
        errors.append(f"Demo model coverage differs from {EXPECTED_MODEL_COUNTS}: {dict(model_counts)}")

    conditions = Counter(sample.get("condition") for sample in SAMPLES)
    if not conditions.get("good") or not conditions.get("bad"):
        errors.append("Demo corpus must include both clean and defective examples")

    expected_files = set(filenames)
    actual_files = {path.name for path in DEMO_ROOT.iterdir() if path.is_file()}
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        if missing:
            errors.append(f"Missing demo files: {missing}")
        if extra:
            errors.append(f"Untracked demo files: {extra}")

    for sample in SAMPLES:
        filename = sample.get("filename")
        if not isinstance(filename, str):
            continue
        path = (DEMO_ROOT / filename).resolve()
        if path.parent != DEMO_ROOT or not path.is_file():
            continue
        payload = path.read_bytes()
        if not 0 < len(payload) <= MAX_SAMPLE_BYTES:
            errors.append(f"Demo sample byte size is invalid: {filename}")
            continue
        expected_media = sample.get("mediaType")
        actual_media = (
            "image/png" if payload.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg" if payload.startswith(b"\xff\xd8")
            else None
        )
        if actual_media != expected_media:
            errors.append(f"Demo sample media type mismatch: {filename}")
        if cv2.imread(str(path), cv2.IMREAD_COLOR) is None:
            errors.append(f"Demo sample cannot be decoded by OpenCV: {filename}")
        expected_hash = VERIFIED_HASHES.get(str(sample.get("id")))
        if expected_hash and hashlib.sha256(payload).hexdigest() != expected_hash:
            errors.append(f"Demo sample hash mismatch: {filename}")

    return errors


def main() -> int:
    errors = validate_demo_samples()
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[FAIL] Demo sample validation found {len(errors)} issue(s).", file=sys.stderr)
        return 1
    print("[OK] 14 local operator/demo images are valid and cover general, steel, and concrete cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
