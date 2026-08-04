"""Validate the offline sample showcase, provenance, model links, and assets."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import cv2


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "backend/samples/showcase-samples.json"
MODEL_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
SHOWCASE_DIRECTORY = REPOSITORY_ROOT / "backend/samples/showcase"
PROVENANCE_DIRECTORY = REPOSITORY_ROOT / "backend/samples/provenance/showcase"
DEFECTDET_EXCERPT_PATH = PROVENANCE_DIRECTORY / "defectdet-selected-coco.json"
HU_EXCERPT_PATH = PROVENANCE_DIRECTORY / "hu-selected-metadata.json"
MAX_SAMPLE_BYTES = 10 * 1024 * 1024
FORBIDDEN_PREDICTION_KEYS = {
    "boundingbox",
    "confidence",
    "detections",
    "modelobservation",
    "prediction",
    "predictions",
    "qualityscore",
}
DEFECTDET_CATEGORY_LABELS = {
    "MP": "missing pad",
    "OC": "open circuit",
    "SC": "short circuit",
    "SP": "spur",
    "SPC": "spurious copper",
}
EXPECTED_SOURCE_METADATA = {
    "defectdet-v1": "backend/samples/provenance/showcase/defectdet-selected-coco.json",
    "gkn-blade-v1": "folder labels in the pinned source archive",
    "hu-infrastructure-cracks-v1": "backend/samples/provenance/showcase/hu-selected-metadata.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _prediction_paths(value: object, path: str = "manifest") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key.casefold() in FORBIDDEN_PREDICTION_KEYS:
                matches.append(child_path)
            matches.extend(_prediction_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_prediction_paths(child, f"{path}[{index}]"))
    return matches


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _defectdet_source_records(errors: list[str]) -> dict[int, dict[str, Any]]:
    excerpt = _load_json(DEFECTDET_EXCERPT_PATH)
    if (
        excerpt.get("excerptSchemaVersion") != 1
        or excerpt.get("datasetId") != "defectdet-v1"
        or excerpt.get("datasetVersion") != "1"
        or excerpt.get("datasetDoi") != "10.17632/t9d9zs3bmb.1"
        or excerpt.get("categoryLabels") != DEFECTDET_CATEGORY_LABELS
        or excerpt.get("sourceArchive")
        != {
            "filename": "DefectDet.zip",
            "sizeBytes": 1680025801,
            "sha256": "250fc8f60e8ee40ae20bfcb00ff2b16366b395fe2fc9aac29e79a10793080b31",
            "member": "DefectDet/annotation/defect_annotations.json",
            "memberSha256": "9dff4fa102d29514633daf6014334cab7f7102bd97d5befca9b996b293656168",
        }
    ):
        errors.append("DefectDet source excerpt provenance does not match the pinned release")

    category_codes: dict[int, str] = {}
    for category in excerpt.get("categories", []):
        if isinstance(category, dict):
            category_codes[category.get("id")] = category.get("name")
    if category_codes != {1: "MP", 2: "OC", 3: "SC", 4: "SP", 5: "SPC"}:
        errors.append("DefectDet source excerpt categories differ from the source COCO metadata")

    labels_by_image: dict[int, list[str]] = {}
    for annotation in excerpt.get("annotations", []):
        if not isinstance(annotation, dict):
            continue
        image_id = annotation.get("image_id")
        category_code = category_codes.get(annotation.get("category_id"))
        label = DEFECTDET_CATEGORY_LABELS.get(category_code)
        if not isinstance(image_id, int) or label is None:
            errors.append("DefectDet source excerpt contains an unknown image/category reference")
            continue
        labels_by_image.setdefault(image_id, []).append(label)

    records: dict[int, dict[str, Any]] = {}
    for image in excerpt.get("images", []):
        if not isinstance(image, dict) or not isinstance(image.get("id"), int):
            errors.append("DefectDet source excerpt contains an invalid image record")
            continue
        image_id = image["id"]
        extra = image.get("extra")
        original_name = extra.get("name") if isinstance(extra, dict) else None
        records[image_id] = {
            "sourceFile": f"DefectDet/images/{image.get('file_name')}",
            "sourceOriginalName": original_name,
            "sourceWidth": image.get("width"),
            "sourceHeight": image.get("height"),
            "sourceLabels": _deduplicate(labels_by_image.get(image_id, [])),
        }
    return records


def _hu_source_records(errors: list[str]) -> dict[str, dict[str, Any]]:
    excerpt = _load_json(HU_EXCERPT_PATH)
    if (
        excerpt.get("excerptSchemaVersion") != 1
        or excerpt.get("datasetId") != "hu-infrastructure-cracks-v1"
        or excerpt.get("datasetVersion") != "1"
        or excerpt.get("datasetDoi") != "10.5281/zenodo.20829348"
        or excerpt.get("sourceFile")
        != {
            "filename": "metadata.json",
            "sizeBytes": 33857,
            "md5": "ab26c24bcc0af5996937bd32303bfaa2",
            "sha256": "a4578be877e981bd5c42546ae1e6457fe8600504b7c417edaa9d580724991bea",
        }
    ):
        errors.append("HU source excerpt provenance does not match the pinned release")

    records: dict[str, dict[str, Any]] = {}
    for crack in excerpt.get("cracks", []):
        if not isinstance(crack, dict) or not isinstance(crack.get("crack_id"), str):
            errors.append("HU source excerpt contains an invalid crack record")
            continue
        records[crack["crack_id"]] = {
            "sourceLabels": [crack.get("structure"), crack.get("type"), crack.get("severity")]
        }
    return records


def _gkn_source_record(sample: dict[str, Any]) -> dict[str, Any] | None:
    source_file = sample.get("sourceFile")
    if not isinstance(source_file, str):
        return None
    parts = PurePosixPath(source_file).parts
    try:
        data_index = parts.index("Data_GKN")
    except ValueError:
        return None
    if len(parts) != data_index + 3:
        return None
    return {
        "sourceOriginalName": parts[-1],
        "sourceLabels": [parts[-2]],
    }


def _validate_source_record(
    sample: dict[str, Any],
    defectdet_records: dict[int, dict[str, Any]],
    hu_records: dict[str, dict[str, Any]],
) -> str | None:
    dataset_id = sample.get("datasetId")
    if dataset_id == "defectdet-v1":
        expected = defectdet_records.get(sample.get("sourceRecordId"))
    elif dataset_id == "hu-infrastructure-cracks-v1":
        expected = hu_records.get(sample.get("sourceRecordId"))
    elif dataset_id == "gkn-blade-v1":
        expected = _gkn_source_record(sample)
    else:
        return "does not have a supported source-metadata strategy"
    if expected is None:
        return "does not resolve to a tracked source record"
    for field, expected_value in expected.items():
        if sample.get(field) != expected_value:
            return f"{field} differs from source metadata: expected={expected_value!r}"
    return None


def validate_showcase_samples() -> list[str]:
    errors: list[str] = []
    manifest = _load_json(MANIFEST_PATH)
    model_manifest = _load_json(MODEL_MANIFEST_PATH)
    defectdet_records = _defectdet_source_records(errors)
    hu_records = _hu_source_records(errors)

    if manifest.get("schemaVersion") != 1:
        errors.append("Showcase manifest must use schemaVersion 1")
    quota = manifest.get("samplesPerModel")
    if not isinstance(quota, int) or isinstance(quota, bool) or quota < 1:
        errors.append("Showcase samplesPerModel must be a positive integer")
        quota = 0
    if manifest.get("notice") != "Source labels describe dataset metadata, not model predictions.":
        errors.append("Showcase source-label notice is missing or changed")
    for prediction_path in _prediction_paths(manifest):
        errors.append(f"Showcase manifest contains precomputed prediction data: {prediction_path}")

    registered_model_ids = {
        model.get("id")
        for model in model_manifest.get("models", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    }
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        errors.append("Showcase datasets must be a non-empty array")
        datasets = []
    dataset_ids = [dataset.get("id") for dataset in datasets if isinstance(dataset, dict)]
    if len(dataset_ids) != len(datasets) or len(set(dataset_ids)) != len(dataset_ids):
        errors.append("Showcase dataset IDs must be present and unique")
    datasets_by_id: dict[str, dict[str, Any]] = {}
    for dataset in datasets:
        if not isinstance(dataset, dict) or not isinstance(dataset.get("id"), str):
            continue
        dataset_id = dataset["id"]
        datasets_by_id[dataset_id] = dataset
        license_data = dataset.get("license")
        vocabulary = dataset.get("sourceLabelVocabulary")
        if (
            not dataset.get("name")
            or not dataset.get("version")
            or not dataset.get("doi")
            or not _is_https_url(dataset.get("sourceUrl"))
            or not isinstance(dataset.get("authors"), list)
            or not dataset["authors"]
            or not isinstance(dataset.get("attribution"), str)
            or not dataset["attribution"].strip()
            or not isinstance(license_data, dict)
            or license_data.get("name") != "CC BY 4.0"
            or not _is_https_url(license_data.get("url"))
            or not isinstance(vocabulary, list)
            or not vocabulary
            or len(set(vocabulary)) != len(vocabulary)
        ):
            errors.append(f"Showcase dataset provenance is incomplete: {dataset_id}")
        if dataset.get("sourceMetadataExcerpt") != EXPECTED_SOURCE_METADATA.get(dataset_id):
            errors.append(f"Showcase dataset source-metadata strategy is not pinned: {dataset_id}")
        if dataset_id == "hu-infrastructure-cracks-v1" and (
            dataset.get("authors")
            != [
                "Yousef Almashakbeh",
                "Razan Al-Majali",
                "Radwan Alelaimat",
                "Israa Hayarat",
                "Dirar Momani",
            ]
            or dataset.get("attribution")
            != (
                "Almashakbeh, Y., Hayarat, I., Momani, D., & Alelaimat, R. (2026). "
                "HU Infrastructure Cracks Dataset. The Hashemite University, Jordan. "
                "https://hu-infrastructure-cracks.org. CC BY 4.0."
            )
        ):
            errors.append("HU attribution does not match the primary project sources")

    samples = manifest.get("samples")
    if not isinstance(samples, list):
        errors.append("Showcase samples must be an array")
        return errors
    expected_count = quota * len(registered_model_ids)
    if len(samples) != expected_count:
        errors.append(
            f"Showcase must contain exactly {quota} samples for each registered model "
            f"({expected_count} total)"
        )

    identifiers = [sample.get("id") for sample in samples if isinstance(sample, dict)]
    filenames = [sample.get("filename") for sample in samples if isinstance(sample, dict)]
    if len(identifiers) != len(samples) or len(set(identifiers)) != len(identifiers):
        errors.append("Showcase sample IDs must be present and unique")
    if len(filenames) != len(samples) or len(set(filenames)) != len(filenames):
        errors.append("Showcase filenames must be present and unique")

    model_counts: Counter[str] = Counter()
    tracked_files: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            errors.append("Showcase sample entry must be an object")
            continue
        identifier = sample.get("id", "<unknown>")
        model_id = sample.get("recommendedModelId")
        dataset = datasets_by_id.get(sample.get("datasetId"))
        filename = sample.get("filename")
        labels = sample.get("sourceLabels")
        if model_id not in registered_model_ids:
            errors.append(f"Showcase sample links an unknown model: {identifier}")
        else:
            model_counts[model_id] += 1
        if dataset is None:
            errors.append(f"Showcase sample links an unknown dataset: {identifier}")
        elif (
            not isinstance(labels, list)
            or not labels
            or any(label not in dataset["sourceLabelVocabulary"] for label in labels)
        ):
            errors.append(f"Showcase source labels are not from the pinned vocabulary: {identifier}")
        source_record_error = _validate_source_record(sample, defectdet_records, hu_records)
        if source_record_error:
            errors.append(f"Showcase source metadata mismatch for {identifier}: {source_record_error}")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not sample.get("domain")
            or not sample.get("sourceFile")
            or not sample.get("sourceOriginalName")
            or sample.get("mediaType") not in {"image/jpeg", "image/png"}
        ):
            errors.append(f"Showcase sample metadata is incomplete: {identifier}")
            continue

        transform = sample.get("assetTransform")
        if transform is not None and transform != "downscaled":
            errors.append(f"Showcase sample has an unsupported asset transform: {identifier}")
        if transform == "downscaled" and (
            not isinstance(sample.get("sourceWidth"), int)
            or not isinstance(sample.get("sourceHeight"), int)
            or sample["sourceWidth"] <= sample.get("width", 0)
            or sample["sourceHeight"] <= sample.get("height", 0)
        ):
            errors.append(f"Showcase downscale metadata is invalid: {identifier}")

        tracked_files.add(filename)
        path = SHOWCASE_DIRECTORY / filename
        if not path.is_file():
            errors.append(f"Showcase image is missing: {filename}")
            continue
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != sample.get("sha256"):
            errors.append(f"Showcase image hash mismatch: {filename}")
        if len(payload) != sample.get("sizeBytes"):
            errors.append(f"Showcase image size mismatch: {filename}")
        if len(payload) > MAX_SAMPLE_BYTES:
            errors.append(f"Showcase image exceeds the inspect upload limit: {filename}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            errors.append(f"Showcase image cannot be decoded: {filename}")
            continue
        height, width = image.shape[:2]
        if width != sample.get("width") or height != sample.get("height"):
            errors.append(f"Showcase image dimensions mismatch: {filename}")

    expected_model_counts = {model_id: quota for model_id in registered_model_ids}
    if dict(model_counts) != expected_model_counts:
        errors.append(
            f"Showcase model quotas differ: expected={expected_model_counts}, "
            f"actual={dict(model_counts)}"
        )
    on_disk = {path.name for path in SHOWCASE_DIRECTORY.iterdir() if path.is_file()}
    if on_disk != tracked_files:
        errors.append(
            f"Showcase tracked files differ: missing={sorted(tracked_files - on_disk)}, "
            f"untracked={sorted(on_disk - tracked_files)}"
        )
    return errors


def main() -> int:
    errors = validate_showcase_samples()
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        print(f"[FAIL] Showcase validation found {len(errors)} issue(s).", file=sys.stderr)
        return 1
    print("[OK] Showcase labels match tracked source metadata; provenance, hashes, and images are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
