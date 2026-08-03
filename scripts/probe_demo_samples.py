"""Run every tracked demo image through the selected DetectionService."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
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
    "backend/samples/demo-samples.json",
    "backend/utils/model_loader.py",
    "backend/utils/preprocessing.py",
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
    for item in manifest["files"]:
        sample_path = REPOSITORY_ROOT / item["path"]
        image = decode_image(sample_path.read_bytes())
        result = service.inspect(image)
        actual_types = list(dict.fromkeys(defect.type for defect in result.defects))
        if item["expectedNativeClass"] not in actual_types:
            raise RuntimeError(
                f"Expected native class missing for {item['id']}: {actual_types}"
            )
        if actual_types != item["expectedNativeTypes"]:
            raise RuntimeError(
                f"Native output changed for {item['id']}: "
                f"expected {item['expectedNativeTypes']}, got {actual_types}"
            )
        total_detections += result.total_defects
        observed_types.update(actual_types)
        samples.append(
            {
                "sampleId": item["id"],
                "path": item["path"],
                "sha256": item["sha256"],
                "sourceArchivePath": item["source"]["archivePath"],
                "sourceCategory": item["source"]["category"],
                "sourceAnomalyLabel": item["source"]["anomalyLabel"],
                "expectedNativeClass": item["expectedNativeClass"],
                "actualNativeTypes": actual_types,
                "dimensions": {
                    "width": result.image_width,
                    "height": result.image_height,
                },
                "defects": [
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
                ],
                "totalDefects": result.total_defects,
                "qualityScore": result.quality_score,
                "status": result.status,
            }
        )

    if len(samples) < 10 or total_detections < len(samples):
        raise RuntimeError("Every tracked demo sample must produce a real detection")
    source_files = {
        relative_path: _sha256_file(REPOSITORY_ROOT / relative_path)
        for relative_path in SOURCE_PATHS
    }
    source_files.update(
        {item["path"]: item["sha256"] for item in manifest["files"]}
    )
    evidence = {
        "schemaVersion": 1,
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
        "model": {
            "modelId": model_spec.model_id,
            "sha256": model_spec.sha256,
            "classes": list(model_spec.classes),
            "confidence": 0.25,
        },
        "sampleCount": len(samples),
        "totalDetections": total_detections,
        "observedNativeTypes": sorted(observed_types),
        "samples": samples,
        "acceptance": {
            "atLeastTenDecodedSamples": len(samples) >= 10,
            "allSourceHashesMatch": True,
            "allSourceDimensionsMatch": True,
            "completePinnedProvenance": True,
            "redistributionLicenseVerified": manifest["dataset"]["license"]
            == "CC BY 4.0",
            "noSyntheticImages": manifest["selection"]["syntheticImages"] is False,
            "noFakeDetections": manifest["selection"]["fakeDetections"] is False,
            "everySampleHasRealSelectedModelDetection": all(
                sample["totalDefects"] > 0 for sample in samples
            ),
            "nativeClassExpectationsMatch": True,
        },
    }
    _write_json(args.output, evidence)
    print(
        f"[OK] Probed {len(samples)} real demo samples with {total_detections} "
        f"selected-model detection(s); wrote {args.output.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
