"""Validate the pinned MVTec AD showcase catalog and model links."""

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
EXPECTED_REVISION = "e88b7bd615ad582b0a7e8238066a9fb293a072b4"
EXPECTED_PRODUCTS = {"Bottle", "Capsule", "Screw", "Metal nut"}


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


def validate_showcase_samples() -> list[str]:
    errors: list[str] = []
    manifest = _load_json(MANIFEST_PATH)
    model_manifest = _load_json(MODEL_MANIFEST_PATH)
    selection = _load_json(SELECTION_PATH)

    if manifest.get("schemaVersion") != 2:
        errors.append("Showcase manifest must use schemaVersion 2")
    if manifest.get("notice") != "Source labels describe MVTec AD dataset metadata, not model predictions.":
        errors.append("Showcase source-label notice is missing or changed")

    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or len(datasets) != 1:
        errors.append("Showcase must use exactly one pinned MVTec AD dataset source")
        datasets = []
    if datasets:
        dataset = datasets[0]
        license_data = dataset.get("license", {})
        if (
            dataset.get("id") != "mvtec-ad"
            or dataset.get("name") != "MVTec Anomaly Detection Dataset"
            or dataset.get("sourceRevision") != EXPECTED_REVISION
            or not _https(dataset.get("sourceUrl"))
            or not _https(dataset.get("mirrorUrl"))
            or license_data.get("name") != "CC BY-NC-SA 4.0"
            or not _https(license_data.get("url"))
            or not isinstance(dataset.get("attribution"), str)
            or not dataset["attribution"].strip()
        ):
            errors.append("MVTec AD showcase provenance is incomplete or changed")

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
    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) != 8:
        errors.append("Showcase must contain exactly eight MVTec good/bad samples")
        samples = []

    identifiers: set[str] = set()
    product_counts: Counter[str] = Counter()
    condition_counts: Counter[tuple[str, str]] = Counter()
    for sample in samples:
        if not isinstance(sample, dict):
            errors.append("Showcase sample entries must be objects")
            continue
        identifier = sample.get("id")
        product = sample.get("productName")
        condition = sample.get("condition")
        source_path = sample.get("sourcePath")
        asset_url = sample.get("assetUrl")
        labels = sample.get("sourceLabels")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            errors.append("Showcase sample IDs must be present and unique")
        else:
            identifiers.add(identifier)
        if product not in EXPECTED_PRODUCTS:
            errors.append(f"Unexpected showcase product/category: {product!r}")
            continue
        product_counts[product] += 1
        condition_counts[(product, str(condition))] += 1
        if sample.get("domain") != product:
            errors.append(f"Showcase domain/product mismatch: {identifier}")
        if sample.get("recommendedModelId") != "bayespfl-general-v1":
            errors.append(f"Showcase recommendation must remain Bayes-PFL: {identifier}")
        if sample.get("recommendedModelId") not in exposed:
            errors.append(f"Showcase references a hidden model: {identifier}")
        if product not in local_presets:
            errors.append(f"Showcase product is not a locally checked preset: {product}")
        if condition not in {"good", "bad"}:
            errors.append(f"Showcase condition must be good/bad: {identifier}")
        if not isinstance(labels, list) or not labels or not all(isinstance(label, str) for label in labels):
            errors.append(f"Showcase source labels are invalid: {identifier}")
        if not isinstance(source_path, str) or not source_path.startswith("MVTec-AD/"):
            errors.append(f"Showcase source path is invalid: {identifier}")
        expected_prefix = (
            "https://huggingface.co/datasets/jiang-cc/MMAD/resolve/"
            f"{EXPECTED_REVISION}/"
        )
        if not isinstance(asset_url, str) or not asset_url.startswith(expected_prefix):
            errors.append(f"Showcase asset URL is not pinned: {identifier}")
        elif source_path and not asset_url.endswith(source_path):
            errors.append(f"Showcase asset URL/source path mismatch: {identifier}")
        if sample.get("datasetId") != "mvtec-ad" or sample.get("mediaType") != "image/png":
            errors.append(f"Showcase dataset/media metadata is invalid: {identifier}")

    if set(product_counts) != EXPECTED_PRODUCTS or any(product_counts[p] != 2 for p in EXPECTED_PRODUCTS):
        errors.append("Showcase must contain two samples for each target product")
    for product in EXPECTED_PRODUCTS:
        if condition_counts[(product, "good")] != 1 or condition_counts[(product, "bad")] != 1:
            errors.append(f"Showcase must contain one good and one bad sample for {product}")
    if "pcb" in json.dumps(manifest).casefold():
        errors.append("PCB content must not return to the current operator showcase")
    return errors


def main() -> int:
    errors = validate_showcase_samples()
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[OK] MVTec AD showcase catalog and model links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
