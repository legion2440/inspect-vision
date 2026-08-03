"""Select real VisA anomalies with selected-model detections and preserve their bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

import cv2
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_URL = (
    "https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar"
)
DATASET_REPOSITORY = "https://github.com/amazon-science/spot-diff"
DATASET_REVISION = "2a692ab575001cbde74d402d897a7286086c6199"
DATASET_LICENSE_URL = (
    "https://raw.githubusercontent.com/amazon-science/spot-diff/"
    f"{DATASET_REVISION}/LICENSE-DATASET"
)
ANOMALY_PATTERN = re.compile(
    r"^(?P<category>[^/]+)/Data/Images/Anomaly/"
    r"(?P<filename>[^/]+\.(?:jpe?g|png))$",
    re.IGNORECASE,
)
MAX_SAMPLE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SelectedSample:
    identifier: str
    output_name: str
    source_path: str
    source_category: str
    payload: bytes
    media_type: str
    width: int
    height: int
    expected_native_class: str
    expected_native_types: tuple[str, ...]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _decode_source(payload: bytes) -> tuple[np.ndarray, str, str]:
    if payload.startswith(b"\xff\xd8"):
        media_type, extension = "image/jpeg", "jpg"
    elif payload.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type, extension = "image/png", "png"
    else:
        raise ValueError("candidate is not JPEG or PNG")
    encoded = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("candidate cannot be decoded as BGR")
    return image, media_type, extension


def _open_archive(url: str) -> BinaryIO:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "inspect-vision-demo-sample-preparer"},
    )
    return urllib.request.urlopen(request, timeout=120)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/demo",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/demo-samples.json",
    )
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.count < 10:
        raise ValueError("The tracked demo dataset requires at least ten samples")
    if args.max_candidates < args.count:
        raise ValueError("max-candidates must be at least count")
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.detection.service import DetectionService
    from backend.utils.model_loader import create_detector, get_model_spec

    model_spec = get_model_spec()
    detector = create_detector(device=args.device, confidence=0.25)
    detector.load()
    service = DetectionService(detector)

    selected: list[SelectedSample] = []
    candidate_count = 0
    with _open_archive(args.archive_url) as response:
        archive_etag = response.headers.get("ETag", "").strip('"')
        archive_last_modified = response.headers.get("Last-Modified", "")
        with tarfile.open(fileobj=response, mode="r|") as archive:
            for member in archive:
                match = ANOMALY_PATTERN.fullmatch(member.name)
                if not member.isfile() or match is None:
                    continue
                candidate_count += 1
                if candidate_count > args.max_candidates:
                    break
                if member.size <= 0 or member.size > MAX_SAMPLE_BYTES:
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                payload = extracted.read()
                if len(payload) != member.size:
                    raise RuntimeError(f"Incomplete archive member: {member.name}")
                try:
                    image, media_type, extension = _decode_source(payload)
                except ValueError:
                    continue
                result = service.inspect(image)
                if not result.defects:
                    continue
                observed_types = tuple(dict.fromkeys(defect.type for defect in result.defects))
                dominant = max(result.defects, key=lambda defect: defect.confidence).type
                category = match.group("category")
                source_stem = Path(match.group("filename")).stem
                identifier = f"visa-{category.lower()}-{source_stem.lower()}"
                selected.append(
                    SelectedSample(
                        identifier=identifier,
                        output_name=f"{identifier}.{extension}",
                        source_path=member.name,
                        source_category=category,
                        payload=payload,
                        media_type=media_type,
                        width=int(image.shape[1]),
                        height=int(image.shape[0]),
                        expected_native_class=dominant,
                        expected_native_types=observed_types,
                    )
                )
                print(
                    f"[SELECT] {member.name}: {len(result.defects)} defect(s), "
                    f"native={', '.join(observed_types)}",
                    flush=True,
                )
                if len(selected) == args.count:
                    break

    if len(selected) != args.count:
        raise RuntimeError(
            f"Found only {len(selected)} usable samples in {candidate_count} candidates"
        )

    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    for sample in selected:
        (output_directory / sample.output_name).write_bytes(sample.payload)

    files: list[dict[str, Any]] = []
    for sample in selected:
        output_path = output_directory / sample.output_name
        files.append(
            {
                "id": sample.identifier,
                "path": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256_bytes(sample.payload),
                "byteSize": len(sample.payload),
                "dimensions": {"width": sample.width, "height": sample.height},
                "mediaType": sample.media_type,
                "modified": False,
                "source": {
                    "dataset": "Visual Anomaly (VisA)",
                    "archiveUrl": args.archive_url,
                    "archivePath": sample.source_path,
                    "category": sample.source_category,
                    "anomalyLabel": "anomaly",
                    "license": "CC BY 4.0",
                    "licenseUrl": DATASET_LICENSE_URL,
                },
                "expectedNativeClass": sample.expected_native_class,
                "expectedNativeTypes": list(sample.expected_native_types),
            }
        )

    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "selection": {
            "method": "unmodified VisA anomaly images with nonzero selected-model output",
            "modelId": model_spec.model_id,
            "confidence": 0.25,
            "syntheticImages": False,
            "fakeDetections": False,
        },
        "dataset": {
            "name": "Visual Anomaly (VisA)",
            "authors": [
                "Yang Zou",
                "Jongheon Jeong",
                "Latha Pemula",
                "Dongqing Zhang",
                "Onkar Dabeer",
            ],
            "repositoryUrl": DATASET_REPOSITORY,
            "sourceRevision": DATASET_REVISION,
            "archiveUrl": args.archive_url,
            "archiveEtag": archive_etag,
            "archiveLastModified": archive_last_modified,
            "license": "CC BY 4.0",
            "licenseUrl": DATASET_LICENSE_URL,
            "citation": "SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation, ECCV 2022",
        },
        "files": files,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.manifest, manifest)
    print(
        f"[OK] Preserved {len(files)} unmodified CC BY 4.0 samples and wrote "
        f"{args.manifest.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
