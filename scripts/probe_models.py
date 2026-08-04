"""Qualify every registered model through the production DetectionService path."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2


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


def _source_hashes() -> dict[str, str]:
    paths = [
        REPOSITORY_ROOT / "backend/models/model-manifest.json",
        REPOSITORY_ROOT / "backend/samples/model-probe-samples.json",
        *sorted((REPOSITORY_ROOT / "backend/detection").glob("*.py")),
        REPOSITORY_ROOT / "backend/utils/model_loader.py",
        REPOSITORY_ROOT / "backend/utils/preprocessing.py",
        REPOSITORY_ROOT / "scripts/probe_models.py",
    ]
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix(): _sha256(path)
        for path in paths
        if path.is_file()
    }


def _download_samples(group: dict[str, Any], directory: Path) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for sample in group["samples"]:
        suffix = Path(urllib.parse.urlparse(sample["url"]).path).suffix or ".img"
        path = directory / f"{sample['id']}{suffix}"
        request = urllib.request.Request(
            sample["url"], headers={"User-Agent": "Inspect-Vision/1.0"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
        digest = _sha256(path)
        if digest != sample["sha256"]:
            raise ValueError(f"Sample hash mismatch for {sample['id']}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot decode sample: {sample['id']}")
        prepared.append({**sample, "image": image})
    return prepared


def _probe_group(
    runtime: Any,
    group: dict[str, Any],
) -> dict[str, Any]:
    spec = runtime.registry.get(group["modelId"])
    with tempfile.TemporaryDirectory(prefix=f"inspect-vision-{spec.model_id}-") as directory:
        samples = _download_samples(group, Path(directory))
        started = time.perf_counter()
        results = [runtime.inspect(sample["image"], spec.model_id) for sample in samples]
        elapsed_ms = (time.perf_counter() - started) * 1000.0

    total_detections = sum(result.total_defects for result in results)
    if total_detections < 1:
        raise RuntimeError(f"Model {spec.model_id} produced no detections through production service")

    sample_results: list[dict[str, Any]] = []
    for sample, result in zip(samples, results, strict=True):
        defects = []
        for defect in result.defects:
            class_id = spec.native_classes.index(defect.type)
            box = defect.bounding_box
            defects.append(
                {
                    "classId": class_id,
                    "className": defect.type,
                    "confidence": round(defect.confidence, 6),
                    "xyxy": [
                        round(box.x, 4),
                        round(box.y, 4),
                        round(box.x + box.width, 4),
                        round(box.y + box.height, 4),
                    ],
                }
            )
        sample_results.append(
            {
                "sampleId": sample["id"],
                "sourceUrl": sample["url"],
                "sourceLabel": sample["sourceLabel"],
                "sha256": sample["sha256"],
                "dimensions": {
                    "width": result.image_width,
                    "height": result.image_height,
                },
                "detections": defects,
                "qualityScore": result.quality_score,
                "status": result.status,
                "annotationDimensionsMatchOriginal": result.annotated_image.shape[:2]
                == (result.image_height, result.image_width),
            }
        )

    return {
        "modelId": spec.model_id,
        "displayName": spec.display_name,
        "role": spec.role,
        "domain": spec.domain,
        "qualificationDomain": group["qualificationDomain"],
        "filename": spec.filename,
        "sha256": spec.sha256,
        "task": spec.task,
        "classes": list(spec.native_classes),
        "confidence": spec.confidence,
        "iou": spec.iou,
        "preprocessingProfile": spec.preprocessing.profile_id,
        "quality": {
            "defaultWeight": spec.quality_default_weight,
            "classWeights": spec.class_weights,
        },
        "inferenceMs": round(elapsed_ms, 3),
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
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "docs/evidence/models/model-registry-acceptance.json",
    )
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from backend.detection.runtime import DetectionRuntimeManager
    from backend.utils.model_loader import ModelRegistry

    registry = ModelRegistry(args.manifest)
    sample_manifest = _load_json(args.samples)
    groups = sample_manifest.get("models")
    if not isinstance(groups, list):
        raise ValueError("Probe sample manifest must contain a models array")
    if {group.get("modelId") for group in groups} != {
        spec.model_id for spec in registry.models
    }:
        raise ValueError("Probe sample groups must match registered model IDs")

    runtime = DetectionRuntimeManager(
        registry,
        models_directory=args.manifest.resolve().parent,
        device=args.device,
    )
    models = [_probe_group(runtime, group) for group in groups]
    evidence = {
        "schemaVersion": 2,
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceCommit": _current_commit(),
        "sourceFiles": _source_hashes(),
        "runtime": {
            "python": platform.python_version(),
            "ultralytics": importlib.metadata.version("ultralytics"),
            "opencv": cv2.__version__,
            "device": args.device,
        },
        "defaultModelId": registry.default_model_id,
        "accuracyClaim": False,
        "pipeline": "DetectionRuntimeManager -> DetectionService",
        "models": models,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[OK] Qualified {len(models)} registered models through production service: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
