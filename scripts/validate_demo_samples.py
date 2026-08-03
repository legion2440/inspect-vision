"""Validate the tracked VisA sample inventory, provenance, hashes, and images."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import cv2


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "backend/samples/demo-samples.json"
MODEL_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
DEMO_ROOT = PurePosixPath("backend/samples/demo")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ARCHIVE_MEMBER_PATTERN = re.compile(
    r"^(?P<category>[^/]+)/Data/Images/Anomaly/[^/]+\.(?:jpe?g|png)$",
    re.IGNORECASE,
)
MAX_SAMPLE_BYTES = 10 * 1024 * 1024
EXPECTED_DATASET_FIELDS = {
    "name": "Visual Anomaly (VisA)",
    "authors": [
        "Yang Zou",
        "Jongheon Jeong",
        "Latha Pemula",
        "Dongqing Zhang",
        "Onkar Dabeer",
    ],
    "repositoryUrl": "https://github.com/amazon-science/spot-diff",
    "sourceRevision": "2a692ab575001cbde74d402d897a7286086c6199",
    "archiveUrl": (
        "https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar"
    ),
    "archiveEtag": "05c830591a1172938cb714895c9e0cfb-113",
    "archiveLastModified": "Thu, 22 Sep 2022 19:23:39 GMT",
    "license": "CC BY 4.0",
    "licenseUrl": (
        "https://raw.githubusercontent.com/amazon-science/spot-diff/"
        "2a692ab575001cbde74d402d897a7286086c6199/LICENSE-DATASET"
    ),
    "citation": (
        "SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection "
        "and Segmentation, ECCV 2022"
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _valid_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value == path.as_posix()


def validate_demo_samples() -> list[str]:
    errors: list[str] = []
    manifest = _load_json(MANIFEST_PATH)
    model_manifest = _load_json(MODEL_MANIFEST_PATH)
    selected_model_id = model_manifest.get("selectedModelId")
    selected_model = next(
        (
            model
            for model in model_manifest.get("models", [])
            if model.get("id") == selected_model_id
        ),
        None,
    )
    native_classes = set(selected_model.get("classes", [])) if selected_model else set()

    selection = manifest.get("selection", {})
    if selection != {
        "method": "unmodified VisA anomaly images with nonzero selected-model output",
        "modelId": selected_model_id,
        "confidence": 0.25,
        "syntheticImages": False,
        "fakeDetections": False,
    }:
        errors.append("Demo selection contract is invalid")

    dataset = manifest.get("dataset", {})
    if dataset != EXPECTED_DATASET_FIELDS:
        errors.append("Demo dataset provenance or license metadata differs from the pinned source")
    if not COMMIT_PATTERN.fullmatch(str(dataset.get("sourceRevision", ""))):
        errors.append("Demo dataset source revision must be a full commit SHA")

    files = manifest.get("files")
    if not isinstance(files, list) or len(files) < 10:
        errors.append("Demo dataset must contain at least ten files")
        return errors
    identifiers = [item.get("id") for item in files if isinstance(item, dict)]
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if len(set(identifiers)) != len(files) or None in identifiers:
        errors.append("Demo sample IDs must be present and unique")
    if len(set(paths)) != len(files) or None in paths:
        errors.append("Demo sample paths must be present and unique")

    tracked_paths: set[PurePosixPath] = set()
    for item in files:
        if not isinstance(item, dict):
            errors.append("Demo file entry must be an object")
            continue
        relative_value = item.get("path")
        if not _valid_relative_path(relative_value):
            errors.append(f"Demo sample has an invalid path: {relative_value!r}")
            continue
        relative_path = PurePosixPath(relative_value)
        if DEMO_ROOT not in relative_path.parents:
            errors.append(f"Demo sample is outside the demo directory: {relative_value}")
            continue
        tracked_paths.add(relative_path)
        path = REPOSITORY_ROOT / relative_path
        if not path.is_file():
            errors.append(f"Demo sample is missing: {relative_value}")
            continue
        payload = path.read_bytes()
        if len(payload) != item.get("byteSize") or not 0 < len(payload) <= MAX_SAMPLE_BYTES:
            errors.append(f"Demo sample byte size is invalid: {relative_value}")
        if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
            errors.append(f"Demo sample hash mismatch: {relative_value}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        dimensions = item.get("dimensions", {})
        if image is None or image.shape[:2] != (
            dimensions.get("height"),
            dimensions.get("width"),
        ):
            errors.append(f"Demo sample dimensions/decode mismatch: {relative_value}")
        expected_media_type = "image/png" if payload.startswith(b"\x89PNG\r\n\x1a\n") else (
            "image/jpeg" if payload.startswith(b"\xff\xd8") else None
        )
        if expected_media_type is None or item.get("mediaType") != expected_media_type:
            errors.append(f"Demo sample media type is invalid: {relative_value}")
        if item.get("modified") is not False:
            errors.append(f"Demo sample must record unmodified source bytes: {relative_value}")

        source = item.get("source", {})
        archive_match = ARCHIVE_MEMBER_PATTERN.fullmatch(str(source.get("archivePath", "")))
        if (
            source.get("dataset") != dataset.get("name")
            or source.get("archiveUrl") != dataset.get("archiveUrl")
            or source.get("license") != dataset.get("license")
            or source.get("licenseUrl") != dataset.get("licenseUrl")
            or source.get("anomalyLabel") != "anomaly"
            or archive_match is None
            or source.get("category") != archive_match.group("category")
        ):
            errors.append(f"Demo sample provenance is invalid: {relative_value}")

        expected_class = item.get("expectedNativeClass")
        expected_types = item.get("expectedNativeTypes")
        if (
            expected_class not in native_classes
            or not isinstance(expected_types, list)
            or not expected_types
            or expected_class not in expected_types
            or not set(expected_types).issubset(native_classes)
        ):
            errors.append(f"Demo sample native-class expectation is invalid: {relative_value}")

    actual_paths = {
        PurePosixPath(path.relative_to(REPOSITORY_ROOT).as_posix())
        for path in (REPOSITORY_ROOT / DEMO_ROOT).iterdir()
        if path.is_file()
    }
    if tracked_paths != actual_paths:
        errors.append("Demo directory files do not match the manifest exactly")
    if not (REPOSITORY_ROOT / "backend/samples/VISA-NOTICE.md").is_file():
        errors.append("Demo dataset attribution notice is missing")
    return errors


def main() -> int:
    try:
        errors = validate_demo_samples()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
        errors = [f"Cannot validate demo samples: {error}"]
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[FAIL] Demo sample validation found {len(errors)} issue(s).", file=sys.stderr)
        return 1
    manifest = _load_json(MANIFEST_PATH)
    print(
        f"[OK] Validated {len(manifest['files'])} decoded, hash-bound, "
        "CC BY 4.0 demo samples."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
