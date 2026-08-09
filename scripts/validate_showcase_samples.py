"""Validate the operator showcase catalog, provenance, and model links."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "backend/samples/showcase-samples.json"
MODEL_MANIFEST_PATH = REPOSITORY_ROOT / "backend/models/model-manifest.json"
SELECTION_PATH = REPOSITORY_ROOT / "backend/detection/model-selection.json"
MVTEC_REVISION = "e88b7bd615ad582b0a7e8238066a9fb293a072b4"
HISTORICAL_SHOWCASE_COMMIT = "f82fe4645ada00d5b01a16b9a05b2ea36795cce2"
BAYES_MODEL_ID = "bayespfl-general-v1"
EXPECTED_PRODUCTS = {"Bottle", "Capsule", "Screw", "Metal nut"}
EXPECTED_DATASETS = {
    "mvtec-ad",
    "gkn-blade-v1",
    "plos-neu-steel-figure-v1",
    "hu-infrastructure-cracks-v1",
}
EXPECTED_SPECIALIST_IDS = {
    "steel-good-img4685": "neu-defect-yolov8",
    "steel-inclusion-plos-fig3b": "neu-defect-yolov8",
    "steel-scratch-img2113": "neu-defect-yolov8",
    "concrete-cr01-transverse": "concrete-crack-yolov8",
    "concrete-cr26-longitudinal": "concrete-crack-yolov8",
    "concrete-cr43-diagonal": "concrete-crack-yolov8",
}
VERIFIED_SCREW_GOOD_ID = "mvtec-screw-good-001"
VERIFIED_SCREW_GOOD_PATH = "MVTec-AD/screw/test/good/001.png"
VERIFIED_SCREW_GOOD_SHA256 = "983a27fcea10ce8eafeebac3db0899e5fb6ad84338a6cabc5746ee96d2865daa"
VERIFIED_SCREW_GOOD_SIZE = 393132


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _validate_mvtec_dataset(dataset: dict[str, Any], errors: list[str]) -> None:
    license_data = dataset.get("license", {})
    if (
        dataset.get("name") != "MVTec Anomaly Detection Dataset"
        or dataset.get("sourceRevision") != MVTEC_REVISION
        or not _https(dataset.get("sourceUrl"))
        or not _https(dataset.get("mirrorUrl"))
        or license_data.get("name") != "CC BY-NC-SA 4.0"
        or not _https(license_data.get("url"))
        or not isinstance(dataset.get("attribution"), str)
        or not dataset["attribution"].strip()
    ):
        errors.append("MVTec AD showcase provenance is incomplete or changed")


def _validate_specialist_dataset(dataset: dict[str, Any], errors: list[str]) -> None:
    identifier = dataset.get("id")
    license_data = dataset.get("license", {})
    if (
        identifier not in EXPECTED_DATASETS - {"mvtec-ad"}
        or not _https(dataset.get("sourceUrl"))
        or license_data.get("name") != "CC BY 4.0"
        or not _https(license_data.get("url"))
        or not isinstance(dataset.get("attribution"), str)
        or not dataset["attribution"].strip()
    ):
        errors.append(f"Specialist showcase provenance is incomplete or changed: {identifier}")


def validate_showcase_samples() -> list[str]:
    errors: list[str] = []
    manifest = _load_json(MANIFEST_PATH)
    model_manifest = _load_json(MODEL_MANIFEST_PATH)
    selection = _load_json(SELECTION_PATH)

    if manifest.get("schemaVersion") != 3:
        errors.append("Showcase manifest must use schemaVersion 3")
    if manifest.get("notice") != "Source labels describe dataset metadata, not model predictions.":
        errors.append("Showcase source-label notice is missing or changed")

    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        errors.append("Showcase datasets must be an array")
        datasets = []
    dataset_ids = {
        dataset.get("id") for dataset in datasets if isinstance(dataset, dict)
    }
    if dataset_ids != EXPECTED_DATASETS or len(datasets) != len(EXPECTED_DATASETS):
        errors.append("Showcase must contain the MVTec, steel, and concrete provenance sources")
    for dataset in datasets:
        if not isinstance(dataset, dict):
            errors.append("Showcase dataset entries must be objects")
            continue
        if dataset.get("id") == "mvtec-ad":
            _validate_mvtec_dataset(dataset, errors)
        else:
            _validate_specialist_dataset(dataset, errors)

    exposed = {
        model.get("id")
        for model in model_manifest.get("models", [])
        if isinstance(model, dict) and model.get("exposed") is True
    }
    local_presets = {
        item.get("value")
        for item in selection.get("productNamePresets", [])
        if isinstance(item, dict) and item.get("evidence") == "local"
    }
    comparison_presets = {
        item.get("value")
        for item in selection.get("productNamePresets", [])
        if isinstance(item, dict) and item.get("evidence") == "comparison"
    }

    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) != 14:
        errors.append("Showcase must contain eight Bayes examples and six specialist examples")
        samples = []

    identifiers: set[str] = set()
    bayes_products: Counter[str] = Counter()
    bayes_conditions: Counter[tuple[str, str]] = Counter()
    specialist_ids: dict[str, str] = {}
    screw_good: dict[str, Any] | None = None
    mvtec_prefix = (
        "https://huggingface.co/datasets/jiang-cc/MMAD/resolve/"
        f"{MVTEC_REVISION}/"
    )
    historical_prefix = (
        "https://raw.githubusercontent.com/legion2440/inspect-vision/"
        f"{HISTORICAL_SHOWCASE_COMMIT}/backend/samples/showcase/"
    )

    for sample in samples:
        if not isinstance(sample, dict):
            errors.append("Showcase sample entries must be objects")
            continue
        identifier = sample.get("id")
        model_id = sample.get("recommendedModelId")
        labels = sample.get("sourceLabels")
        asset_url = sample.get("assetUrl")
        dataset_id = sample.get("datasetId")
        product = sample.get("productName")
        condition = sample.get("condition")

        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            errors.append("Showcase sample IDs must be present and unique")
            continue
        identifiers.add(identifier)
        if model_id not in exposed:
            errors.append(f"Showcase references a hidden or unknown model: {identifier}")
        if dataset_id not in EXPECTED_DATASETS:
            errors.append(f"Showcase references an unknown dataset: {identifier}")
        if condition not in {"good", "bad"}:
            errors.append(f"Showcase condition must be good/bad: {identifier}")
        if not isinstance(labels, list) or not labels or not all(isinstance(label, str) for label in labels):
            errors.append(f"Showcase source labels are invalid: {identifier}")
        if not isinstance(asset_url, str) or not _https(asset_url):
            errors.append(f"Showcase asset URL is invalid: {identifier}")
            continue

        if model_id == BAYES_MODEL_ID:
            source_path = sample.get("sourcePath")
            if product not in EXPECTED_PRODUCTS:
                errors.append(f"Unexpected Bayes showcase product/category: {product!r}")
                continue
            bayes_products[product] += 1
            bayes_conditions[(product, str(condition))] += 1
            if sample.get("domain") != product:
                errors.append(f"Bayes showcase domain/product mismatch: {identifier}")
            if product not in local_presets:
                errors.append(f"Bayes showcase product is not a locally checked preset: {product}")
            if dataset_id != "mvtec-ad" or sample.get("mediaType") != "image/png":
                errors.append(f"Bayes showcase dataset/media metadata is invalid: {identifier}")
            if not isinstance(source_path, str) or not source_path.startswith("MVTec-AD/"):
                errors.append(f"Bayes showcase source path is invalid: {identifier}")
            if not asset_url.startswith(mvtec_prefix):
                errors.append(f"Bayes showcase asset URL is not pinned: {identifier}")
            elif isinstance(source_path, str) and not asset_url.endswith(source_path):
                errors.append(f"Bayes showcase asset URL/source path mismatch: {identifier}")
            if product == "Screw" and condition == "good":
                screw_good = sample
        elif identifier in EXPECTED_SPECIALIST_IDS:
            specialist_ids[identifier] = str(model_id)
            expected_model = EXPECTED_SPECIALIST_IDS[identifier]
            if model_id != expected_model:
                errors.append(f"Specialist recommendation changed: {identifier}")
            expected_product = "Steel surface" if expected_model == "neu-defect-yolov8" else "Concrete surface"
            if product != expected_product or product not in comparison_presets:
                errors.append(f"Specialist comparison category changed: {identifier}")
            if sample.get("historicalAssetCommit") != HISTORICAL_SHOWCASE_COMMIT:
                errors.append(f"Specialist historical asset binding changed: {identifier}")
            if not asset_url.startswith(historical_prefix):
                errors.append(f"Specialist showcase asset URL is not history-pinned: {identifier}")
            if not isinstance(sample.get("sha256"), str) or len(sample["sha256"]) != 64:
                errors.append(f"Specialist showcase hash is missing: {identifier}")
            if not isinstance(sample.get("sizeBytes"), int) or sample["sizeBytes"] <= 0:
                errors.append(f"Specialist showcase size is missing: {identifier}")
        else:
            errors.append(f"Unexpected specialist showcase sample: {identifier}")

    if set(bayes_products) != EXPECTED_PRODUCTS or any(bayes_products[p] != 2 for p in EXPECTED_PRODUCTS):
        errors.append("Bayes showcase must contain two samples for each target product")
    for product in EXPECTED_PRODUCTS:
        if bayes_conditions[(product, "good")] != 1 or bayes_conditions[(product, "bad")] != 1:
            errors.append(f"Bayes showcase must contain one good and one bad sample for {product}")
    if specialist_ids != EXPECTED_SPECIALIST_IDS:
        errors.append("Specialist showcase sample set is incomplete or changed")

    if not screw_good:
        errors.append("Verified Screw good showcase sample is missing")
    elif (
        screw_good.get("id") != VERIFIED_SCREW_GOOD_ID
        or screw_good.get("sourcePath") != VERIFIED_SCREW_GOOD_PATH
        or screw_good.get("sha256") != VERIFIED_SCREW_GOOD_SHA256
        or screw_good.get("sizeBytes") != VERIFIED_SCREW_GOOD_SIZE
        or screw_good.get("width") != 1024
        or screw_good.get("height") != 1024
    ):
        errors.append("Verified Screw good showcase binding is incomplete or changed")

    serialized = json.dumps(manifest).casefold()
    if "mvtec-screw-good-000" in identifiers or "screw/test/good/000.png" in serialized:
        errors.append("The rejected Screw good/000 showcase case must not return")
    if "factory-defect-guard-v6-mc" in serialized or "pcb" in serialized:
        errors.append("Rejected PCB/general-YOLO content must not return to the operator showcase")
    return errors


def main() -> int:
    errors = validate_showcase_samples()
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[OK] Operator showcase catalog and model links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
