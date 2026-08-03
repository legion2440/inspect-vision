"""Reproduce model observations for the source-balanced tracked demo dataset."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT / "docs/evidence/demo-samples/demo-samples-acceptance.json"
)
SOURCE_PATHS = (
    "backend/detection/annotation.py",
    "backend/detection/quality.py",
    "backend/detection/service.py",
    "backend/models/model-manifest.json",
    "backend/samples/VISA-NOTICE.md",
    "backend/samples/demo-samples.json",
    "backend/utils/model_loader.py",
    "backend/utils/preprocessing.py",
    "scripts/prepare_demo_samples.py",
    "scripts/probe_demo_samples.py",
    "scripts/validate_demo_samples.py",
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as binary_file:
        for chunk in iter(lambda: binary_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_commit() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/demo-samples.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def _observation(result: Any, *, model_id: str, model_sha256: str) -> dict[str, Any]:
    detections = [
        {
            "type": defect.type,
            "confidence": round(defect.confidence, 6),
            "boundingBox": {
                "x": round(defect.bounding_box.x, 4),
                "y": round(defect.bounding_box.y, 4),
                "width": round(defect.bounding_box.width, 4),
                "height": round(defect.bounding_box.height, 4),
            },
        }
        for defect in result.defects
    ]
    return {
        "modelId": model_id,
        "modelSha256": model_sha256,
        "confidenceThreshold": 0.25,
        "observedNativeClasses": list(
            dict.fromkeys(detection["type"] for detection in detections)
        ),
        "detections": detections,
        "totalDetections": result.total_defects,
        "qualityScore": result.quality_score,
        "status": result.status,
    }


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.detection.service import DetectionService
    from backend.utils.model_loader import create_detector, get_model_spec
    from backend.utils.preprocessing import decode_image
    from scripts.validate_demo_samples import validate_demo_samples

    validation_errors = validate_demo_samples()
    if validation_errors:
        raise ValueError("Demo manifest validation failed: " + "; ".join(validation_errors))

    manifest = _load_json(args.manifest)
    model_spec = get_model_spec()
    detector = create_detector(device=args.device, confidence=0.25)
    detector.load()
    service = DetectionService(detector)
    samples: list[dict[str, Any]] = []
    total_detections = 0
    observed_types: set[str] = set()
    ground_truth_split: Counter[str] = Counter()
    source_categories: set[str] = set()
    source_defect_labels: set[str] = set()
    for item in manifest["files"]:
        sample_path = REPOSITORY_ROOT / item["path"]
        image = decode_image(sample_path.read_bytes())
        result = service.inspect(image)
        actual_observation = _observation(
            result,
            model_id=model_spec.model_id,
            model_sha256=model_spec.sha256,
        )
        if actual_observation != item["modelObservation"]:
            raise RuntimeError(f"Tracked model observation changed for {item['id']}")
        ground_truth = item["sourceGroundTruth"]
        ground_truth_split[ground_truth["label"]] += 1
        source_categories.add(ground_truth["category"])
        source_defect_labels.update(ground_truth["defectLabels"])
        total_detections += actual_observation["totalDetections"]
        observed_types.update(actual_observation["observedNativeClasses"])
        samples.append(
            {
                "sampleId": item["id"],
                "path": item["path"],
                "sha256": item["sha256"],
                "dimensions": item["dimensions"],
                "sourceGroundTruth": ground_truth,
                "modelObservation": actual_observation,
            }
        )

    normal_samples = [
        sample
        for sample in samples
        if sample["sourceGroundTruth"]["label"] == "normal"
    ]
    anomaly_samples = [
        sample
        for sample in samples
        if sample["sourceGroundTruth"]["label"] == "anomaly"
    ]
    source_files = {
        relative_path: _sha256_file(REPOSITORY_ROOT / relative_path)
        for relative_path in SOURCE_PATHS
    }
    source_files.update(
        {item["path"]: item["sha256"] for item in manifest["files"]}
    )
    source_files.update(
        {
            annotation["path"]: annotation["sha256"]
            for annotation in manifest["dataset"]["annotationFiles"]
        }
    )
    summary = {
        "sampleCount": len(samples),
        "groundTruthSplit": {
            "normal": ground_truth_split["normal"],
            "anomaly": ground_truth_split["anomaly"],
        },
        "sourceCategories": sorted(source_categories),
        "sourceCategoryCount": len(source_categories),
        "sourceDefectLabels": sorted(source_defect_labels, key=str.casefold),
        "sourceDefectLabelCount": len(source_defect_labels),
        "observedNativeClasses": sorted(observed_types),
        "totalModelDetections": total_detections,
        "zeroDetectionSampleCount": sum(
            sample["modelObservation"]["totalDetections"] == 0 for sample in samples
        ),
        "normalModelOutcomes": {
            "sampleCount": len(normal_samples),
            "zeroDetections": sum(
                sample["modelObservation"]["totalDetections"] == 0
                for sample in normal_samples
            ),
            "falsePositiveSamples": sum(
                sample["modelObservation"]["totalDetections"] > 0
                for sample in normal_samples
            ),
        },
        "anomalyModelOutcomes": {
            "sampleCount": len(anomaly_samples),
            "zeroDetections": sum(
                sample["modelObservation"]["totalDetections"] == 0
                for sample in anomaly_samples
            ),
            "samplesWithDetections": sum(
                sample["modelObservation"]["totalDetections"] > 0
                for sample in anomaly_samples
            ),
        },
    }
    evidence = {
        "schemaVersion": 2,
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceCommit": _current_commit(),
        "sourceBinding": "sourceFiles contains the authoritative SHA-256 of executed source files",
        "sourceFiles": source_files,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "packages": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "opencv-python", "torch", "ultralytics")
            },
        },
        "dataset": manifest["dataset"],
        "modelObservationContract": manifest["modelObservationContract"],
        "accuracyClaim": False,
        "summary": summary,
        "samples": samples,
        "acceptance": {
            "atLeastTenDecodedSamples": len(samples) >= 10,
            "severalNormalSamples": ground_truth_split["normal"] >= 3,
            "severalAnomalySamples": ground_truth_split["anomaly"] >= 3,
            "sourceCategoryDiversity": len(source_categories) >= 4,
            "sourceDefectCaseDiversity": len(source_defect_labels) >= 4,
            "selectionIndependentOfModel": manifest["selection"]["modelIndependent"]
            is True,
            "groundTruthSeparatedFromModelObservation": True,
            "allSourceHashesAndAnnotationsMatch": True,
            "redistributionLicenseVerified": manifest["dataset"]["license"]
            == "CC BY 4.0",
            "noSyntheticImages": manifest["selection"]["syntheticImages"] is False,
            "noFakeDetections": manifest["selection"]["fakeDetections"] is False,
            "allModelObservationsReproduced": True,
            "noAccuracyClaim": True,
        },
    }
    _write_json(args.output, evidence)
    print(
        f"[OK] Probed {len(samples)} samples: {ground_truth_split['normal']} normal, "
        f"{ground_truth_split['anomaly']} anomaly, {len(source_categories)} categories, "
        f"{total_detections} observed model detection(s); no accuracy claim",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
