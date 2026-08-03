"""Build a source-ground-truth-balanced VisA demo set, then observe the model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
ANNOTATION_PATTERN = re.compile(r"^(?P<category>[^/]+)/image_anno\.csv$")
IMAGE_PATTERN = re.compile(
    r"^(?P<category>[^/]+)/Data/Images/(?P<label>Normal|Anomaly)/"
    r"(?P<filename>[^/]+\.(?:jpe?g|png))$",
    re.IGNORECASE,
)
MAX_SAMPLE_BYTES = 10 * 1024 * 1024
RANGE_BLOCK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceRow:
    category: str
    image_path: str
    label: str
    defect_labels: tuple[str, ...]
    mask_path: str | None


@dataclass(frozen=True, slots=True)
class AnnotationFile:
    category: str
    source_path: str
    source_sha256: str
    normalized_bytes: bytes


@dataclass(frozen=True, slots=True)
class CapturedSample:
    payload: bytes
    media_type: str
    extension: str
    width: int
    height: int


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
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("candidate cannot be decoded as BGR")
    return image, media_type, extension


class HttpRangeReader(io.RawIOBase):
    """Seekable HTTP reader backed by bounded Range requests."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        request = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "inspect-vision-demo-sample-preparer"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            self.length = int(response.headers["Content-Length"])
            self.etag = response.headers.get("ETag", "").strip('"')
            self.last_modified = response.headers.get("Last-Modified", "")
        self.position = 0
        self.cache_start = 0
        self.cache = b""

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.length + offset
        else:
            raise ValueError(f"Unsupported seek mode: {whence}")
        if not 0 <= position <= self.length:
            raise ValueError(f"Seek outside archive: {position}")
        self.position = position
        return position

    def _fill_cache(self) -> None:
        self.cache_start = (self.position // RANGE_BLOCK_BYTES) * RANGE_BLOCK_BYTES
        cache_end = min(self.cache_start + RANGE_BLOCK_BYTES, self.length) - 1
        request = urllib.request.Request(
            self.url,
            headers={
                "User-Agent": "inspect-vision-demo-sample-preparer",
                "Range": f"bytes={self.cache_start}-{cache_end}",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206:
                raise RuntimeError("VisA server did not honor a bounded Range request")
            self.cache = response.read()
        if len(self.cache) != cache_end - self.cache_start + 1:
            raise RuntimeError("Incomplete VisA archive range")

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.length or size == 0:
            return b""
        if size < 0:
            size = self.length - self.position
        remaining = min(size, self.length - self.position)
        chunks: list[bytes] = []
        while remaining:
            cache_end = self.cache_start + len(self.cache)
            if not (self.cache_start <= self.position < cache_end):
                self._fill_cache()
                cache_end = self.cache_start + len(self.cache)
            start = self.position - self.cache_start
            chunk_size = min(remaining, cache_end - self.position)
            chunks.append(self.cache[start : start + chunk_size])
            self.position += chunk_size
            remaining -= chunk_size
        return b"".join(chunks)


def _open_archive(url: str) -> HttpRangeReader:
    return HttpRangeReader(url)


def _normalize_csv(payload: bytes) -> bytes:
    text = payload.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _parse_source_rows(category: str, source_path: str, payload: bytes) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with io.StringIO(payload.decode("utf-8-sig"), newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != ["image", "label", "mask"]:
            raise ValueError(f"Unexpected VisA annotation columns in {source_path}")
        for row in reader:
            image_path = row["image"].strip()
            raw_label = row["label"].strip()
            is_normal = raw_label.casefold() == "normal"
            rows.append(
                SourceRow(
                    category=category,
                    image_path=image_path,
                    label="normal" if is_normal else "anomaly",
                    defect_labels=()
                    if is_normal
                    else tuple(
                        value.strip() for value in raw_label.split(",") if value.strip()
                    ),
                    mask_path=row["mask"].strip() or None,
                )
            )
    return rows


def _select_source_rows(
    rows: list[SourceRow],
    *,
    normal_count: int,
    anomaly_count: int,
) -> list[SourceRow]:
    normal_rows = sorted(
        (row for row in rows if row.label == "normal"),
        key=lambda row: row.image_path,
    )
    anomaly_rows = sorted(
        (row for row in rows if row.label == "anomaly"),
        key=lambda row: row.image_path,
    )
    selected_anomalies: list[SourceRow] = []
    seen_cases: set[tuple[str, ...]] = set()
    for row in anomaly_rows:
        case = tuple(label.casefold() for label in row.defect_labels)
        if case in seen_cases:
            continue
        selected_anomalies.append(row)
        seen_cases.add(case)
        if len(selected_anomalies) == anomaly_count:
            break
    if len(normal_rows) < normal_count or len(selected_anomalies) < anomaly_count:
        raise ValueError("VisA category does not satisfy the source-ground-truth quota")
    return [*normal_rows[:normal_count], *selected_anomalies]


def _sample_id(row: SourceRow) -> str:
    stem = Path(row.image_path).stem.lower()
    return f"visa-{row.category.lower()}-{row.label}-{stem}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/demo",
    )
    parser.add_argument(
        "--provenance-directory",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/provenance",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/demo-samples.json",
    )
    parser.add_argument("--category-count", type=int, default=4)
    parser.add_argument("--normal-per-category", type=int, default=1)
    parser.add_argument("--anomaly-per-category", type=int, default=2)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    expected_count = args.category_count * (
        args.normal_per_category + args.anomaly_per_category
    )
    if (
        args.category_count < 4
        or args.normal_per_category < 1
        or args.anomaly_per_category < 2
        or expected_count < 10
    ):
        raise ValueError("Demo quotas require >=4 categories, normal and anomaly, and >=10 files")

    selected_rows: dict[str, SourceRow] = {}
    category_order: list[str] = []
    annotations: dict[str, AnnotationFile] = {}
    captured: dict[str, CapturedSample] = {}
    with _open_archive(args.archive_url) as response:
        archive_etag = response.etag
        archive_last_modified = response.last_modified
        with tarfile.open(fileobj=response, mode="r:") as archive:
            for member in archive:
                annotation_match = ANNOTATION_PATTERN.fullmatch(member.name)
                if annotation_match and len(category_order) < args.category_count:
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise RuntimeError(f"Cannot read annotation file: {member.name}")
                    payload = extracted.read()
                    category = annotation_match.group("category")
                    rows = _parse_source_rows(category, member.name, payload)
                    chosen = _select_source_rows(
                        rows,
                        normal_count=args.normal_per_category,
                        anomaly_count=args.anomaly_per_category,
                    )
                    category_order.append(category)
                    annotations[category] = AnnotationFile(
                        category=category,
                        source_path=member.name,
                        source_sha256=_sha256_bytes(payload),
                        normalized_bytes=_normalize_csv(payload),
                    )
                    selected_rows.update({row.image_path: row for row in chosen})
                    labels = sorted(
                        {label for row in chosen for label in row.defect_labels},
                        key=str.casefold,
                    )
                    print(
                        f"[SOURCE] {category}: {args.normal_per_category} normal, "
                        f"{args.anomaly_per_category} anomaly; cases={', '.join(labels)}",
                        flush=True,
                    )
                    continue

                image_match = IMAGE_PATTERN.fullmatch(member.name)
                if not member.isfile() or image_match is None or member.name not in selected_rows:
                    continue
                if member.size <= 0 or member.size > MAX_SAMPLE_BYTES:
                    raise ValueError(f"Selected sample has invalid size: {member.name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"Cannot read selected image: {member.name}")
                payload = extracted.read()
                if len(payload) != member.size:
                    raise RuntimeError(f"Incomplete archive member: {member.name}")
                image, media_type, extension = _decode_source(payload)
                captured[member.name] = CapturedSample(
                    payload=payload,
                    media_type=media_type,
                    extension=extension,
                    width=int(image.shape[1]),
                    height=int(image.shape[0]),
                )
                if len(captured) == expected_count:
                    break

    if len(category_order) != args.category_count or len(captured) != expected_count:
        missing = sorted(set(selected_rows) - set(captured))
        raise RuntimeError(
            f"Captured {len(captured)}/{expected_count} selected files; missing={missing}"
        )
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from backend.detection.service import DetectionService
    from backend.utils.model_loader import create_detector, get_model_spec

    model_spec = get_model_spec()
    detector = create_detector(device=args.device, confidence=0.25)
    detector.load()
    service = DetectionService(detector)

    output_directory = args.output_directory.resolve()
    provenance_directory = args.provenance_directory.resolve()
    for directory in (output_directory, provenance_directory):
        if directory == REPOSITORY_ROOT or REPOSITORY_ROOT not in directory.parents:
            raise ValueError(f"Refusing to write outside a repository subdirectory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

    annotation_entries: dict[str, dict[str, Any]] = {}
    for category in category_order:
        annotation = annotations[category]
        tracked_path = provenance_directory / f"{category}-image_anno.csv"
        tracked_path.write_bytes(annotation.normalized_bytes)
        annotation_entries[category] = {
            "category": category,
            "path": tracked_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_bytes(annotation.normalized_bytes),
            "sourceArchivePath": annotation.source_path,
            "sourceSha256": annotation.source_sha256,
            "normalization": "UTF-8 with LF line endings; CSV values unchanged",
        }

    files: list[dict[str, Any]] = []
    expected_image_names: set[str] = set()
    for category in category_order:
        category_rows = [
            row for row in selected_rows.values() if row.category == category
        ]
        for row in category_rows:
            sample = captured[row.image_path]
            identifier = _sample_id(row)
            output_name = f"{identifier}.{sample.extension}"
            expected_image_names.add(output_name)
            output_path = output_directory / output_name
            output_path.write_bytes(sample.payload)
            image = _decode_source(sample.payload)[0]
            result = service.inspect(image)
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
            annotation = annotation_entries[category]
            files.append(
                {
                    "id": identifier,
                    "path": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "sha256": _sha256_bytes(sample.payload),
                    "byteSize": len(sample.payload),
                    "dimensions": {"width": sample.width, "height": sample.height},
                    "mediaType": sample.media_type,
                    "modified": False,
                    "sourceGroundTruth": {
                        "datasetId": "visa",
                        "category": category,
                        "label": row.label,
                        "defectLabels": list(row.defect_labels),
                        "imageArchivePath": row.image_path,
                        "maskArchivePath": row.mask_path,
                        "annotation": {
                            **annotation,
                            "row": {
                                "image": row.image_path,
                                "label": "normal"
                                if row.label == "normal"
                                else ",".join(row.defect_labels),
                                "mask": row.mask_path or "",
                            },
                        },
                    },
                    "modelObservation": {
                        "modelId": model_spec.model_id,
                        "modelSha256": model_spec.sha256,
                        "confidenceThreshold": 0.25,
                        "observedNativeClasses": list(
                            dict.fromkeys(detection["type"] for detection in detections)
                        ),
                        "detections": detections,
                        "totalDetections": result.total_defects,
                        "qualityScore": result.quality_score,
                        "status": result.status,
                    },
                }
            )

    expected_annotation_names = {
        f"{category}-image_anno.csv" for category in category_order
    }
    for existing in output_directory.iterdir():
        if (
            existing.is_file()
            and existing.suffix.casefold() in {".jpg", ".jpeg", ".png"}
            and existing.name not in expected_image_names
        ):
            existing.unlink()
    for existing in provenance_directory.iterdir():
        if (
            existing.is_file()
            and existing.name.endswith("-image_anno.csv")
            and existing.name not in expected_annotation_names
        ):
            existing.unlink()

    manifest = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "selection": {
            "method": "source-ground-truth quotas applied before model inference",
            "modelIndependent": True,
            "categoryCount": args.category_count,
            "normalPerCategory": args.normal_per_category,
            "anomalyPerCategory": args.anomaly_per_category,
            "sampleCount": expected_count,
            "syntheticImages": False,
            "fakeDetections": False,
        },
        "dataset": {
            "id": "visa",
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
            "annotationFiles": [annotation_entries[category] for category in category_order],
        },
        "modelObservationContract": {
            "groundTruth": False,
            "accuracyClaim": False,
            "modelId": model_spec.model_id,
            "modelSha256": model_spec.sha256,
            "confidenceThreshold": 0.25,
            "nativeClasses": list(model_spec.classes),
        },
        "files": files,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.manifest, manifest)
    print(
        f"[OK] Wrote {len(files)} source-balanced VisA samples across "
        f"{len(category_order)} categories; model output was observed only after selection",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
