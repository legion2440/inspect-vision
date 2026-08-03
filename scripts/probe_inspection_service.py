"""Run the selected model through DetectionService and record acceptance evidence."""

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
    "backend/detection/annotation.py",
    "backend/detection/base.py",
    "backend/detection/dto.py",
    "backend/detection/quality.py",
    "backend/detection/service.py",
    "backend/detection/ultralytics_backend.py",
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
    request = urllib.request.Request(url, headers={"User-Agent": "inspect-vision-probe"})
    with urllib.request.urlopen(request, timeout=30) as response:
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
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.confidence != 0.25:
        raise ValueError("Inspection-service acceptance must run at production confidence 0.25")
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.detection.quality import (
        QUALITY_CLASS_WEIGHTS,
        QUALITY_SCORE_VERSION,
    )
    from backend.detection.service import DetectionService, PRIMARY_CLASS_MAPPING
    from backend.utils.model_loader import create_detector, get_model_spec
    from backend.utils.preprocessing import (
        InspectionPreprocessingConfig,
        decode_image,
    )

    manifest = _load_json(args.manifest)
    sample_manifest = _load_json(args.samples)
    selected_model_id = manifest["selectedModelId"]
    model_spec = get_model_spec(selected_model_id, manifest_path=args.manifest)
    detector = create_detector(
        selected_model_id,
        manifest_path=args.manifest,
        device=args.device,
        confidence=args.confidence,
        iou=args.iou,
    )
    detector.load()
    preprocessing = InspectionPreprocessingConfig(
        input_size=640,
        clahe_clip_limit=2.0,
        clahe_tile_grid_size=(8, 8),
    )
    service = DetectionService(detector, preprocessing=preprocessing)
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    sample_results: list[dict[str, Any]] = []
    total_detections = 0
    for sample in sample_manifest["samples"]:
        payload = _download(sample["url"])
        actual_sample_hash = _sha256_bytes(payload)
        if actual_sample_hash != sample["sha256"]:
            raise ValueError(
                f"Sample hash mismatch for {sample['id']}: "
                f"expected {sample['sha256']}, got {actual_sample_hash}"
            )
        original = decode_image(payload)
        original_snapshot = original.copy()
        result = service.inspect(original)
        if not (original == original_snapshot).all():
            raise RuntimeError(f"Service mutated original image: {sample['id']}")
        if result.annotated_image.shape != original.shape:
            raise RuntimeError(f"Annotated dimensions changed: {sample['id']}")
        output_name = f"{sample['id']}-annotated.png"
        output_path = output_directory / output_name
        if not cv2.imwrite(str(output_path), result.annotated_image):
            raise RuntimeError(f"Could not write annotated evidence: {output_path}")
        persisted = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
        if persisted is None or persisted.shape != original.shape:
            raise RuntimeError(f"Could not verify annotated evidence: {output_path}")

        defects = []
        for defect in result.defects:
            box = defect.bounding_box
            if box.width <= 0.0 or box.height <= 0.0:
                raise RuntimeError(f"Non-positive bbox from service: {sample['id']}")
            if box.x + box.width > result.image_width or box.y + box.height > result.image_height:
                raise RuntimeError(f"Out-of-bounds service bbox: {sample['id']}")
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
                "sourceSha256": actual_sample_hash,
                "expectedClass": sample["expectedClass"],
                "originalDimensions": {
                    "width": result.image_width,
                    "height": result.image_height,
                },
                "modelInputDimensions": {"width": 640, "height": 640, "channels": 3},
                "defects": defects,
                "totalDefects": result.total_defects,
                "qualityScore": result.quality_score,
                "status": result.status,
                "modelId": result.model_id,
                "annotatedOutput": {
                    "path": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "sha256": _sha256_file(output_path),
                    "dimensions": {
                        "width": persisted.shape[1],
                        "height": persisted.shape[0],
                    },
                },
            }
        )

    if total_detections == 0:
        raise RuntimeError("Selected model produced no detections through DetectionService")

    source_files = {
        relative_path: _sha256_file(REPOSITORY_ROOT / relative_path)
        for relative_path in SOURCE_PATHS
    }
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
                for package in ("numpy", "opencv-python", "torch", "torchvision", "ultralytics")
            },
        },
        "pipeline": {
            "path": [
                "decode_image(bytes)->BGR",
                "letterbox(640x640)",
                "grayscale",
                "CLAHE(clipLimit=2.0,tileGridSize=8x8)",
                "grayscale_to_bgr(3-channel)",
                "selected YOLO inference(confidence=0.25)",
                "adapter clamp/drop zero-area",
                "restore_boxes(original coordinates, once)",
                "identity service class mapping",
                "quality-v1(original bbox area ratio)",
                "annotation(original-size BGR copy)",
            ],
            "modelInput": {"width": 640, "height": 640, "channels": 3, "dtype": "uint8"},
            "clahe": {"clipLimit": 2.0, "tileGridSize": [8, 8]},
            "confidence": args.confidence,
            "iou": args.iou,
            "coordinateRestoreCount": 1,
        },
        "quality": {
            "version": QUALITY_SCORE_VERSION,
            "formula": "clamp(round(100 - sum(classWeight * confidence * (10 + 90 * originalBboxAreaRatio))), 0, 100)",
            "classWeights": QUALITY_CLASS_WEIGHTS,
            "heuristic": True,
        },
        "model": {
            "modelId": model_spec.model_id,
            "filename": model_spec.filename,
            "sha256": model_spec.sha256,
            "classes": list(model_spec.classes),
            "serviceClassMapping": PRIMARY_CLASS_MAPPING,
            "device": args.device,
        },
        "sampleCount": len(sample_results),
        "totalDetections": total_detections,
        "samples": sample_results,
    }
    evidence_path = output_directory / "inspection-service-acceptance.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[OK] Wrote inspection-service evidence to {evidence_path}")
    print(f"[OK] Selected model returned {total_detections} detections at confidence 0.25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
