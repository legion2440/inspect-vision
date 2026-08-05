"""Validate demo source truth, model observations, provenance, hashes, and images."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import cv2


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "backend/samples/demo-samples.json"
MODEL_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
DEMO_ROOT = PurePosixPath("backend/samples/demo")
PROVENANCE_ROOT = PurePosixPath("backend/samples/provenance")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ARCHIVE_PATTERN = re.compile(
    r"^(?P<category>[^/]+)/Data/Images/(?P<label>Normal|Anomaly)/"
    r"[^/]+\.(?:jpe?g|png)$",
    re.IGNORECASE,
)
MASK_ARCHIVE_PATTERN = re.compile(
    r"^(?P<category>[^/]+)/Data/Masks/Anomaly/[^/]+\.png$",
    re.IGNORECASE,
)
MAX_SAMPLE_BYTES = 10 * 1024 * 1024
EXPECTED_DATASET_FIELDS = {
    "id": "visa",
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


def _read_annotation_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != ["image", "label", "mask"]:
            raise ValueError(f"Unexpected VisA annotation columns in {path}")
        return {row["image"].strip(): row for row in reader}


def _defect_labels(raw_label: str) -> list[str]:
    if raw_label.strip().casefold() == "normal":
        return []
    return [value.strip() for value in raw_label.split(",") if value.strip()]


def _validate_model_observation(
    item: dict[str, Any],
    *,
    model_contract: dict[str, Any],
    dimensions: dict[str, Any],
    errors: list[str],
) -> None:
    identifier = item.get("id", "<unknown>")
    observation = item.get("modelObservation")
    if not isinstance(observation, dict):
        errors.append(f"Demo sample is missing modelObservation: {identifier}")
        return
    if (
        observation.get("modelId") != model_contract.get("modelId")
        or observation.get("modelSha256") != model_contract.get("modelSha256")
        or observation.get("confidenceThreshold")
        != model_contract.get("confidenceThreshold")
    ):
        errors.append(f"Demo model observation contract mismatch: {identifier}")
    detections = observation.get("detections")
    if not isinstance(detections, list):
        errors.append(f"Demo model observation detections are invalid: {identifier}")
        return
    if observation.get("totalDetections") != len(detections):
        errors.append(f"Demo model observation count is invalid: {identifier}")
    expected_status = "passed" if not detections else "failed"
    if observation.get("status") != expected_status:
        errors.append(f"Demo model observation status is invalid: {identifier}")
    score = observation.get("qualityScore")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        errors.append(f"Demo model observation quality score is invalid: {identifier}")
    native_classes = set(model_contract.get("nativeClasses", []))
    observed_types: list[str] = []
    width, height = dimensions.get("width"), dimensions.get("height")
    for detection in detections:
        defect_type = detection.get("type") if isinstance(detection, dict) else None
        if defect_type not in native_classes:
            errors.append(f"Demo model observation has unknown native class: {identifier}")
            continue
        if defect_type not in observed_types:
            observed_types.append(defect_type)
        confidence = detection.get("confidence")
        box = detection.get("boundingBox", {})
        x, y = box.get("x"), box.get("y")
        box_width, box_height = box.get("width"), box.get("height")
        values = (confidence, x, y, box_width, box_height)
        if (
            not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in values
            )
            or not 0.0 <= confidence <= 1.0
            or not isinstance(width, int)
            or not isinstance(height, int)
            or not (0.0 <= x < x + box_width <= width)
            or not (0.0 <= y < y + box_height <= height)
        ):
            errors.append(f"Demo model observation has invalid detection: {identifier}")
    if observation.get("observedNativeClasses") != observed_types:
        errors.append(f"Demo observed native class summary is invalid: {identifier}")


def validate_demo_samples() -> list[str]:
    errors: list[str] = []
    manifest = _load_json(MANIFEST_PATH)
    model_manifest = _load_json(MODEL_MANIFEST_PATH)
    if manifest.get("schemaVersion") != 2:
        errors.append("Demo manifest must use schemaVersion 2")
    selection = manifest.get("selection", {})
    if selection != {
        "method": "source-ground-truth quotas applied before model inference",
        "modelIndependent": True,
        "categoryCount": 4,
        "normalPerCategory": 1,
        "anomalyPerCategory": 2,
        "sampleCount": 12,
        "syntheticImages": False,
        "fakeDetections": False,
    }:
        errors.append("Demo source-selection contract is invalid")

    dataset = manifest.get("dataset", {})
    dataset_without_annotations = {
        key: value for key, value in dataset.items() if key != "annotationFiles"
    }
    if dataset_without_annotations != EXPECTED_DATASET_FIELDS:
        errors.append("Demo dataset provenance or license differs from the pinned source")
    if not COMMIT_PATTERN.fullmatch(str(dataset.get("sourceRevision", ""))):
        errors.append("Demo dataset source revision must be a full commit SHA")

    model_contract = manifest.get("modelObservationContract", {})
    observation_model_id = model_contract.get("modelId")
    observation_model = next(
        (
            model
            for model in model_manifest.get("models", [])
            if model.get("id") == observation_model_id
        ),
        None,
    )
    expected_model_contract = {
        "groundTruth": False,
        "accuracyClaim": False,
        "modelId": observation_model_id,
        "modelSha256": (
            observation_model.get("artifacts", [{}])[0].get("sha256")
            if observation_model
            else None
        ),
        "confidenceThreshold": (
            observation_model.get("backendConfig", {}).get("confidence")
            if observation_model
            else None
        ),
        "nativeClasses": (
            observation_model.get("nativeClasses", []) if observation_model else []
        ),
    }
    if observation_model is None:
        errors.append("Demo observation model is not registered")
    if model_contract != expected_model_contract:
        errors.append("Demo model observation contract is invalid or claims ground truth")

    annotation_entries = dataset.get("annotationFiles")
    if not isinstance(annotation_entries, list) or len(annotation_entries) < 4:
        errors.append("Demo dataset must preserve at least four source annotation CSV files")
        annotation_entries = []
    annotations_by_category: dict[str, tuple[dict[str, Any], dict[str, dict[str, str]]]] = {}
    tracked_annotation_paths: set[PurePosixPath] = set()
    for annotation in annotation_entries:
        category = annotation.get("category") if isinstance(annotation, dict) else None
        relative_value = annotation.get("path") if isinstance(annotation, dict) else None
        if not isinstance(category, str) or not _valid_relative_path(relative_value):
            errors.append("Demo annotation entry has invalid category or path")
            continue
        relative_path = PurePosixPath(relative_value)
        if PROVENANCE_ROOT not in relative_path.parents:
            errors.append(f"Demo annotation is outside provenance directory: {relative_value}")
            continue
        path = REPOSITORY_ROOT / relative_path
        if category in annotations_by_category:
            errors.append(f"Duplicate demo annotation category: {category}")
        tracked_annotation_paths.add(relative_path)
        if not path.is_file():
            errors.append(f"Demo annotation CSV is missing: {relative_value}")
            continue
        payload = path.read_bytes()
        if b"\r\n" in payload or hashlib.sha256(payload).hexdigest() != annotation.get(
            "sha256"
        ):
            errors.append(f"Demo annotation CSV hash/LF mismatch: {relative_value}")
        if (
            annotation.get("sourceArchivePath") != f"{category}/image_anno.csv"
            or SHA256_PATTERN.fullmatch(str(annotation.get("sourceSha256", ""))) is None
            or annotation.get("normalization")
            != "UTF-8 with LF line endings; CSV values unchanged"
        ):
            errors.append(f"Demo annotation provenance is invalid: {relative_value}")
        try:
            annotations_by_category[category] = (annotation, _read_annotation_rows(path))
        except (OSError, UnicodeDecodeError, csv.Error, ValueError) as error:
            errors.append(f"Demo annotation CSV is invalid: {relative_value}: {error}")

    files = manifest.get("files")
    if not isinstance(files, list) or len(files) < 10:
        errors.append("Demo dataset must contain at least ten files")
        return errors
    if selection.get("sampleCount") != len(files):
        errors.append("Demo source-selection sample count differs from the manifest")
    identifiers = [item.get("id") for item in files if isinstance(item, dict)]
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if len(set(identifiers)) != len(files) or None in identifiers:
        errors.append("Demo sample IDs must be present and unique")
    if len(set(paths)) != len(files) or None in paths:
        errors.append("Demo sample paths must be present and unique")

    tracked_paths: set[PurePosixPath] = set()
    label_counts: Counter[str] = Counter()
    category_labels: dict[str, Counter[str]] = {}
    source_defect_labels: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            errors.append("Demo file entry must be an object")
            continue
        identifier = item.get("id", "<unknown>")
        if "source" in item or "expectedNativeClass" in item or "expectedNativeTypes" in item:
            errors.append(f"Legacy prediction/ground-truth fields remain: {identifier}")
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

        ground_truth = item.get("sourceGroundTruth")
        if not isinstance(ground_truth, dict):
            errors.append(f"Demo sample is missing sourceGroundTruth: {identifier}")
            continue
        category = ground_truth.get("category")
        source_label = ground_truth.get("label")
        if ground_truth.get("datasetId") != "visa" or source_label not in {"normal", "anomaly"}:
            errors.append(f"Demo source ground truth is invalid: {identifier}")
            continue
        label_counts[source_label] += 1
        category_labels.setdefault(category, Counter())[source_label] += 1
        image_match = IMAGE_ARCHIVE_PATTERN.fullmatch(
            str(ground_truth.get("imageArchivePath", ""))
        )
        if (
            image_match is None
            or image_match.group("category") != category
            or image_match.group("label").casefold() != source_label
        ):
            errors.append(f"Demo source image path contradicts ground truth: {identifier}")
        annotation_pair = annotations_by_category.get(category)
        annotation = ground_truth.get("annotation", {})
        if annotation_pair is None:
            errors.append(f"Demo source category has no annotation CSV: {identifier}")
        else:
            annotation_entry, annotation_rows = annotation_pair
            source_row = annotation_rows.get(ground_truth.get("imageArchivePath"))
            if source_row is None:
                errors.append(f"Demo source image is absent from annotation CSV: {identifier}")
            else:
                actual_labels = _defect_labels(source_row["label"])
                if ground_truth.get("defectLabels") != actual_labels:
                    errors.append(f"Demo source defect labels differ from CSV: {identifier}")
                expected_source_label = "normal" if not actual_labels else "anomaly"
                if source_label != expected_source_label:
                    errors.append(f"Demo source label differs from annotation CSV: {identifier}")
                if ground_truth.get("maskArchivePath") != (source_row["mask"].strip() or None):
                    errors.append(f"Demo source mask path differs from annotation CSV: {identifier}")
                source_defect_labels.update(actual_labels)
                expected_row_reference = {
                    "image": source_row["image"].strip(),
                    "label": "normal" if not actual_labels else ",".join(actual_labels),
                    "mask": source_row["mask"].strip(),
                }
                if annotation.get("row") != expected_row_reference:
                    errors.append(f"Demo embedded annotation row differs from CSV: {identifier}")
            expected_annotation = {**annotation_entry}
            for field, value in expected_annotation.items():
                if annotation.get(field) != value:
                    errors.append(f"Demo annotation reference differs from dataset entry: {identifier}")
                    break
            if not isinstance(annotation.get("row"), dict):
                errors.append(f"Demo annotation row reference is invalid: {identifier}")
        defect_labels = ground_truth.get("defectLabels")
        mask_path = ground_truth.get("maskArchivePath")
        if source_label == "normal" and (defect_labels != [] or mask_path is not None):
            errors.append(f"Normal source sample must not claim defects or a mask: {identifier}")
        if source_label == "anomaly" and (
            not isinstance(defect_labels, list)
            or not defect_labels
            or MASK_ARCHIVE_PATTERN.fullmatch(str(mask_path or "")) is None
        ):
            errors.append(f"Anomaly source sample must have labels and mask provenance: {identifier}")
        _validate_model_observation(
            item,
            model_contract=model_contract,
            dimensions=dimensions,
            errors=errors,
        )

    if label_counts["normal"] < 3 or label_counts["anomaly"] < 3:
        errors.append("Demo dataset must contain several normal and anomaly source samples")
    if len(category_labels) < 4:
        errors.append("Demo dataset must contain at least four source categories")
    if len(source_defect_labels) < 4:
        errors.append("Demo dataset must contain at least four source defect labels")
    if set(annotations_by_category) != set(category_labels):
        errors.append("Demo annotation categories do not match selected source categories")
    for category, counts in category_labels.items():
        if counts["normal"] < 1 or counts["anomaly"] < 2:
            errors.append(f"Demo source category does not meet normal/anomaly quotas: {category}")
    actual_paths = {
        PurePosixPath(path.relative_to(REPOSITORY_ROOT).as_posix())
        for path in (REPOSITORY_ROOT / DEMO_ROOT).iterdir()
        if path.is_file()
    }
    if tracked_paths != actual_paths:
        errors.append("Demo directory files do not match the manifest exactly")
    actual_annotation_paths = {
        PurePosixPath(path.relative_to(REPOSITORY_ROOT).as_posix())
        for path in (REPOSITORY_ROOT / PROVENANCE_ROOT).iterdir()
        if path.is_file()
    }
    if tracked_annotation_paths != actual_annotation_paths:
        errors.append("Demo provenance files do not match the manifest exactly")
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
    labels = Counter(
        item["sourceGroundTruth"]["label"] for item in manifest["files"]
    )
    categories = {
        item["sourceGroundTruth"]["category"] for item in manifest["files"]
    }
    source_cases = {
        label
        for item in manifest["files"]
        for label in item["sourceGroundTruth"]["defectLabels"]
    }
    print(
        f"[OK] Validated {len(manifest['files'])} licensed samples: "
        f"{labels['normal']} normal, {labels['anomaly']} anomaly, "
        f"{len(categories)} categories, {len(source_cases)} source defect labels."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
