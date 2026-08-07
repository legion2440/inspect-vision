"""Run a pinned Bayes-PFL candidate through the ordinary DetectionService path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from backend.detection.bayespfl_backend import (
    BAYESPFL_SOURCE_COMMIT,
    OPENAI_CLIP_SHA256,
    BayesPflBackend,
    BayesPflConfig,
    sha256_file,
)
from backend.detection.device import select_device
from backend.detection.service import DetectionService


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKBONE = REPOSITORY_ROOT / "backend/models/ViT-L-14-336px.pt"
DEFAULT_CHECKPOINT = REPOSITORY_ROOT / "backend/models/bayespfl-train-visa.pth"
DEFAULT_OUTPUT = REPOSITORY_ROOT / ".cache/bayespfl-candidate"


def _case(value: str) -> tuple[str, Path]:
    product, separator, raw_path = value.partition("=")
    if not separator or not product.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("--case must use PRODUCT=IMAGE")
    return product.strip(), Path(raw_path.strip()).expanduser().resolve()


def _heatmap_overlay(image: np.ndarray, anomaly_map: np.ndarray) -> np.ndarray:
    resized = cv2.resize(
        anomaly_map,
        (image.shape[1], image.shape[0]),
        interpolation=cv2.INTER_LINEAR,
    )
    mapped = cv2.applyColorMap(
        np.asarray(np.clip(resized, 0.0, 1.0) * 255.0, dtype=np.uint8),
        cv2.COLORMAP_JET,
    )
    return cv2.addWeighted(image, 0.55, mapped, 0.45, 0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--case", action="append", type=_case, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--sigma", type=float, default=8.0)
    parser.add_argument("--min-area-ratio", type=float, default=0.0005)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    checkpoint = args.checkpoint.expanduser().resolve()
    backbone = args.backbone.expanduser().resolve()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    if not checkpoint.is_file():
        raise FileNotFoundError(f"Bayes-PFL checkpoint is missing: {checkpoint}")
    checkpoint_sha = sha256_file(checkpoint)
    checkpoint_size = checkpoint.stat().st_size
    print(f"Bayes-PFL checkpoint: {checkpoint.name}")
    print(f"sizeBytes={checkpoint_size}")
    print(f"sha256={checkpoint_sha}")

    config = BayesPflConfig(
        map_threshold=args.threshold,
        gaussian_sigma=args.sigma,
        min_component_area_ratio=args.min_area_ratio,
    )
    first_product = args.case[0][0]
    detector = BayesPflBackend(
        source_dir=args.source_dir,
        backbone_path=backbone,
        checkpoint_path=checkpoint,
        product_name=first_product,
        device=select_device(args.device),
        config=config,
    )
    service = DetectionService(
        detector,
        preprocessing=None,
        native_classes=("anomaly",),
        quality_default_weight=1.0,
    )

    records: list[dict[str, object]] = []
    for index, (product, image_path) in enumerate(args.case, start=1):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not decode image: {image_path}")
        detector.set_product_name(product)
        result = service.inspect(image)
        anomaly_map = detector.last_anomaly_map
        if anomaly_map is None:
            raise RuntimeError("Bayes-PFL did not expose its last anomaly map")

        stem = f"{index:02d}-{image_path.stem}"
        annotated_path = output / f"{stem}-annotated.png"
        heatmap_path = output / f"{stem}-heatmap.png"
        cv2.imwrite(str(annotated_path), result.annotated_image)
        cv2.imwrite(str(heatmap_path), _heatmap_overlay(image, anomaly_map))

        record = result.to_dict()
        record.update(
            {
                "productName": product,
                "inputPath": str(image_path),
                "inputSha256": sha256_file(image_path),
                "annotatedPath": str(annotated_path),
                "heatmapPath": str(heatmap_path),
                "anomalyMapMin": float(anomaly_map.min()),
                "anomalyMapMax": float(anomaly_map.max()),
                "anomalyMapMean": float(anomaly_map.mean()),
            }
        )
        records.append(record)
        print(
            f"{product}: {image_path.name} -> {result.total_defects} region(s), "
            f"quality={result.quality_score}"
        )

    summary = {
        "candidate": "Bayes-PFL",
        "sourceCommit": BAYESPFL_SOURCE_COMMIT,
        "backboneSha256": OPENAI_CLIP_SHA256,
        "checkpoint": {
            "filename": checkpoint.name,
            "sizeBytes": checkpoint_size,
            "sha256": checkpoint_sha,
        },
        "config": {
            "imageSize": config.image_size,
            "featuresList": list(config.features_list),
            "numFlows": config.num_flows,
            "promptContextLen": config.prompt_context_len,
            "promptNum": config.prompt_num,
            "promptStateLen": config.prompt_state_len,
            "sampleNum": config.sample_num,
            "seed": config.seed,
            "gaussianSigma": config.gaussian_sigma,
            "mapThreshold": config.map_threshold,
            "minComponentAreaRatio": config.min_component_area_ratio,
        },
        "postprocessingNote": (
            "Gaussian sigma follows the upstream test path. The fixed threshold and "
            "connected-component bbox conversion are candidate adapter settings; the "
            "upstream benchmark derives its visualization threshold from target ground truth."
        ),
        "cases": records,
    }
    result_path = output / "result.json"
    result_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Result: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
