"""Probe registered Ultralytics detection models with pinned remote samples."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
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


def _normalize_names(names: object) -> dict[int, str]:
    if isinstance(names, dict):
        normalized = {int(class_id): str(name) for class_id, name in names.items()}
    elif isinstance(names, (list, tuple)):
        normalized = {class_id: str(name) for class_id, name in enumerate(names)}
    else:
        raise TypeError(f"Unsupported model.names value: {type(names).__name__}")
    if not normalized or sorted(normalized) != list(range(len(normalized))):
        raise ValueError("model.names must define contiguous class IDs starting at zero")
    return normalized


def _prepare_samples(sample_manifest: dict[str, Any], directory: Path) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for sample in sample_manifest["samples"]:
        sample_path = directory / f"{sample['id']}.jpg"
        urllib.request.urlretrieve(sample["url"], sample_path)
        actual_hash = _sha256(sample_path)
        if actual_hash != sample["sha256"]:
            raise ValueError(
                f"Sample hash mismatch for {sample['id']}: "
                f"expected {sample['sha256']}, got {actual_hash}"
            )
        image = cv2.imread(str(sample_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot decode sample: {sample['id']}")
        height, width = image.shape[:2]
        prepared.append(
            {
                "id": sample["id"],
                "url": sample["url"],
                "sha256": actual_hash,
                "expectedClass": sample["expectedClass"],
                "width": width,
                "height": height,
                "image": image,
            }
        )
    return prepared


def _probe_model(
    model_spec: dict[str, Any],
    samples: list[dict[str, Any]],
    *,
    device: str,
    confidence: float,
    iou: float,
) -> dict[str, Any]:
    model_path = REPOSITORY_ROOT / "backend" / "models" / model_spec["filename"]
    if not model_path.is_file():
        raise FileNotFoundError(f"Model weight is missing: {model_path}")
    actual_hash = _sha256(model_path)
    if actual_hash != model_spec["sha256"]:
        raise ValueError(
            f"Model hash mismatch for {model_spec['id']}: "
            f"expected {model_spec['sha256']}, got {actual_hash}"
        )
    if model_path.stat().st_size != model_spec["sizeBytes"]:
        raise ValueError(f"Model size mismatch for {model_spec['id']}")

    started_load = time.perf_counter()
    model = YOLO(str(model_path), task="detect")
    load_ms = (time.perf_counter() - started_load) * 1000.0
    if model.task != "detect":
        raise ValueError(f"Model {model_spec['id']} has task={model.task!r}, expected 'detect'")
    names = _normalize_names(model.names)
    expected_names = {index: name for index, name in enumerate(model_spec["classes"])}
    if names != expected_names:
        raise ValueError(
            f"Class mismatch for {model_spec['id']}: "
            f"manifest={expected_names}, model={names}"
        )

    started_inference = time.perf_counter()
    predictions = model.predict(
        source=[sample["image"] for sample in samples],
        imgsz=model_spec["inputSize"]["width"],
        conf=confidence,
        iou=iou,
        device=device,
        verbose=False,
    )
    inference_ms = (time.perf_counter() - started_inference) * 1000.0

    sample_results: list[dict[str, Any]] = []
    total_detections = 0
    for sample, prediction in zip(samples, predictions, strict=True):
        detections: list[dict[str, Any]] = []
        boxes = prediction.boxes
        if boxes is not None:
            xyxy_values = boxes.xyxy.detach().cpu().numpy()
            confidence_values = boxes.conf.detach().cpu().numpy()
            class_values = boxes.cls.detach().cpu().numpy()
            for xyxy, score, raw_class_id in zip(
                xyxy_values, confidence_values, class_values, strict=True
            ):
                class_id = int(raw_class_id)
                if class_id not in names:
                    raise ValueError(f"Unknown class ID {class_id} from {model_spec['id']}")
                coordinates = [float(value) for value in xyxy]
                if not all(math.isfinite(value) for value in [*coordinates, float(score)]):
                    raise ValueError(f"Non-finite detection from {model_spec['id']}")
                x1, y1, x2, y2 = coordinates
                bbox_in_bounds = (
                    0.0 <= x1 <= x2 <= sample["width"]
                    and 0.0 <= y1 <= y2 <= sample["height"]
                )
                if not bbox_in_bounds:
                    raise ValueError(
                        f"Out-of-bounds bbox from {model_spec['id']} on {sample['id']}: "
                        f"{coordinates} for {sample['width']}x{sample['height']}"
                    )
                detections.append(
                    {
                        "classId": class_id,
                        "className": names[class_id],
                        "confidence": round(float(score), 6),
                        "xyxy": [round(value, 4) for value in coordinates],
                    }
                )
        total_detections += len(detections)
        sample_results.append(
            {
                "sampleId": sample["id"],
                "sourceUrl": sample["url"],
                "sha256": sample["sha256"],
                "dimensions": {"width": sample["width"], "height": sample["height"]},
                "expectedClass": sample["expectedClass"],
                "detections": detections,
            }
        )

    if total_detections == 0:
        raise RuntimeError(f"Model {model_spec['id']} produced no detections")

    return {
        "modelId": model_spec["id"],
        "filename": model_spec["filename"],
        "sha256": actual_hash,
        "task": model.task,
        "classes": [names[index] for index in range(len(names))],
        "device": device,
        "loadMs": round(load_ms, 3),
        "inferenceMs": round(inference_ms, 3),
        "totalDetections": total_detections,
        "samples": sample_results,
    }


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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _load_json(args.manifest)
    sample_manifest = _load_json(args.samples)
    with tempfile.TemporaryDirectory(prefix="inspect-vision-probe-") as temp_directory:
        samples = _prepare_samples(sample_manifest, Path(temp_directory))
        models = [
            _probe_model(
                model_spec,
                samples,
                device=args.device,
                confidence=args.confidence,
                iou=args.iou,
            )
            for model_spec in manifest["models"]
        ]

    evidence = {
        "schemaVersion": 1,
        "sourceCommit": _current_commit(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "packages": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "opencv-python", "torch", "torchvision", "ultralytics")
            },
        },
        "probe": {
            "confidence": args.confidence,
            "iou": args.iou,
            "sampleCount": len(sample_manifest["samples"]),
        },
        "models": models,
    }
    serialized = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8", newline="\n")
        print(f"[OK] Wrote model probe evidence to {args.output}")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
