"""Record annotated service evidence for one registered model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "docs/evidence/inspection-service"
SOURCE_PATHS = (
    "backend/models/model-manifest.json",
    "backend/samples/model-probe-samples.json",
    "backend/detection/annotation.py",
    "backend/detection/dto.py",
    "backend/detection/quality.py",
    "backend/detection/runtime.py",
    "backend/detection/service.py",
    "backend/utils/model_loader.py",
    "backend/utils/preprocessing.py",
    "scripts/probe_inspection_service.py",
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Inspect-Vision/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "backend/models/model-manifest.json",
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/model-probe-samples.json",
    )
    parser.add_argument("--model", default="neu-defect-yolov8")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from backend.detection.quality import QUALITY_SCORE_VERSION
    from backend.detection.runtime import DetectionRuntimeManager
    from backend.utils.model_loader import ModelRegistry
    from backend.utils.preprocessing import decode_image

    registry = ModelRegistry(args.manifest)
    spec = registry.get(args.model)
    sample_manifest = _load_json(args.samples)
    group = next(
        (item for item in sample_manifest["models"] if item.get("modelId") == spec.model_id),
        None,
    )
    if group is None:
        raise ValueError(f"No probe samples registered for {spec.model_id}")

    runtime = DetectionRuntimeManager(
        registry,
        models_directory=args.manifest.resolve().parent,
        device=args.device,
    )
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    sample_results: list[dict[str, Any]] = []
    total_detections = 0
    for sample in group["samples"]:
        payload = _download(sample["url"])
        digest = _sha256_bytes(payload)
        if digest != sample["sha256"]:
            raise ValueError(f"Sample hash mismatch for {sample['id']}")
        original = decode_image(payload)
        snapshot = original.copy()
        result = runtime.inspect(original, spec.model_id)
        if not (original == snapshot).all():
            raise RuntimeError(f"Service mutated original image: {sample['id']}")
        output_path = output_directory / f"{sample['id']}-annotated.png"
        if not cv2.imwrite(str(output_path), result.annotated_image):
            raise RuntimeError(f"Could not write annotated evidence: {output_path}")

        defects = []
        for defect in result.defects:
            box = defect.bounding_box
            defects.append(
                {
                    "type": defect.type,
                    "confidence": round(defect.confidence, 6),
                    "boundingBox": {
                        "x": round(box.x, 4),
                        "y": round(box.y, 4),
                        "width": round(box.width, 4),
                        "height": round(box.height, 4),
                    },
                }
            )
        total_detections += result.total_defects
        sample_results.append(
            {
                "sampleId": sample["id"],
                "sourceUrl": sample["url"],
                "sourceSha256": digest,
                "sourceLabel": sample["sourceLabel"],
                "originalDimensions": {
                    "width": result.image_width,
                    "height": result.image_height,
                },
                "defects": defects,
                "totalDefects": result.total_defects,
                "qualityScore": result.quality_score,
                "status": result.status,
                "modelId": result.model_id,
                "annotatedOutput": {
                    "path": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "sha256": _sha256_file(output_path),
                    "dimensions": {
                        "width": result.annotated_image.shape[1],
                        "height": result.annotated_image.shape[0],
                    },
                },
            }
        )
    if total_detections < 1:
        raise RuntimeError(f"Model {spec.model_id} produced no service detections")

    evidence = {
        "schemaVersion": 2,
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceCommit": _current_commit(),
        "sourceFiles": {
            path: _sha256_file(REPOSITORY_ROOT / path) for path in SOURCE_PATHS
        },
        "runtime": {
            "python": platform.python_version(),
            "ultralytics": importlib.metadata.version("ultralytics"),
            "device": args.device,
        },
        "pipeline": {
            "preprocessingProfile": spec.preprocessing.profile_id,
            "confidence": spec.confidence,
            "iou": spec.iou,
            "coordinateRestoreCount": 1,
            "modelInput": {
                "width": spec.image_size,
                "height": spec.image_size,
                "channels": 3,
                "dtype": "uint8",
            },
        },
        "quality": {
            "version": QUALITY_SCORE_VERSION,
            "defaultWeight": spec.quality_default_weight,
            "classWeights": spec.class_weights,
            "heuristic": True,
        },
        "model": {
            "modelId": spec.model_id,
            "filename": spec.filename,
            "sha256": spec.sha256,
            "classes": list(spec.native_classes),
        },
        "sampleCount": len(sample_results),
        "totalDetections": total_detections,
        "accuracyClaim": False,
        "samples": sample_results,
    }
    evidence_path = output_directory / "inspection-service-acceptance.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[OK] Wrote {spec.model_id} service evidence to {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
