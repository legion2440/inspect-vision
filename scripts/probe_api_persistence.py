"""Exercise one registered model through FastAPI, SQLite, media, and deletion."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import httpx2
import numpy as np
import uvicorn


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "docs/evidence/api-persistence"
SOURCE_PATHS = (
    "backend/config.py",
    "backend/main.py",
    "backend/models/record.py",
    "backend/routes/dependencies.py",
    "backend/routes/detect.py",
    "backend/routes/history.py",
    "backend/routes/serialization.py",
    "backend/storage/media.py",
    "backend/storage/repository.py",
    "backend/storage/service.py",
    "backend/detection/service.py",
    "backend/detection/runtime.py",
    "backend/utils/model_loader.py",
    "backend/utils/preprocessing.py",
    "requirements-api.txt",
    "scripts/probe_api_persistence.py",
)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
    request = urllib.request.Request(url, headers={"User-Agent": "inspect-vision-api-probe"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _decode_data_url(value: str, expected_media_type: str) -> bytes:
    prefix = f"data:{expected_media_type};base64,"
    if not value.startswith(prefix):
        raise ValueError(f"data URL does not use {expected_media_type}")
    return base64.b64decode(value[len(prefix) :], validate=True)


@contextmanager
def _serve(application: object) -> Iterator[str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        port = int(probe_socket.getsockname()[1])
    configuration = uvicorn.Config(
        application,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(configuration)
    thread = threading.Thread(target=server.run, name="api-evidence-uvicorn", daemon=True)
    thread.start()
    deadline = time.monotonic() + 60.0
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("Uvicorn stopped before application startup completed")
        if time.monotonic() >= deadline:
            raise TimeoutError("Uvicorn application startup timed out")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=60.0)
        if thread.is_alive():
            raise TimeoutError("Uvicorn application shutdown timed out")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=Path,
        default=REPOSITORY_ROOT / "backend/samples/model-probe-samples.json",
    )
    parser.add_argument("--sample-id", default="neu-inclusion-1")
    parser.add_argument("--model", default="neu-defect-yolov8")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.config import Settings
    from backend.main import create_app

    samples = _load_json(args.samples)
    sample_group = next(
        (group for group in samples["models"] if group.get("modelId") == args.model),
        None,
    )
    if sample_group is None:
        raise KeyError(f"No sample group for model ID: {args.model}")
    sample = next(
        (candidate for candidate in sample_group["samples"] if candidate["id"] == args.sample_id),
        None,
    )
    if sample is None:
        raise KeyError(f"Unknown sample ID: {args.sample_id}")
    original_payload = _download(sample["url"])
    original_hash = _sha256_bytes(original_payload)
    if original_hash != sample["sha256"]:
        raise ValueError(
            f"Sample hash mismatch: expected {sample['sha256']}, got {original_hash}"
        )

    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    responses: dict[str, object] = {}
    endpoint_statuses: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="inspect-vision-api-") as temporary_name:
        temporary_root = Path(temporary_name)
        settings = Settings(
            model_device=args.device,
            models_dir=REPOSITORY_ROOT / "backend/models",
            database_path=temporary_root / "inspections.sqlite3",
            media_dir=temporary_root / "media",
        )
        application = create_app(settings)
        sample_filename = Path(
            sample.get("qualificationFile")
            or urllib.parse.urlparse(sample["url"]).path
        ).name
        sample_media_type = (
            "image/png" if Path(sample_filename).suffix.casefold() == ".png" else "image/jpeg"
        )
        with _serve(application) as base_url, httpx2.Client(
            base_url=base_url,
            timeout=120.0,
        ) as client:
            requested_spec = application.state.detection_runtime.registry.get_exposed(
                args.model
            )
            post_response = client.post(
                "/api/inspect",
                data={"modelId": args.model},
                files={"image": (sample_filename, original_payload, sample_media_type)},
            )
            endpoint_statuses.append({"method": "POST", "path": "/api/inspect", "status": post_response.status_code})
            post_response.raise_for_status()
            post_body = post_response.json()
            responses["post-inspect.json"] = post_body
            inspection_id = post_body["inspectionId"]
            if post_body["totalDefects"] < 1:
                raise RuntimeError("Real API probe returned no registered-model defects")
            if post_body["model"] != {
                "id": requested_spec.model_id,
                "displayName": requested_spec.display_name,
            }:
                raise RuntimeError("API model projection does not match the requested model")

            list_response = client.get("/api/history")
            endpoint_statuses.append({"method": "GET", "path": "/api/history", "status": list_response.status_code})
            list_response.raise_for_status()
            list_body = list_response.json()
            responses["get-history.json"] = list_body
            if len(list_body) != 1 or list_body[0]["inspectionId"] != inspection_id:
                raise RuntimeError("History list does not contain the persisted inspection")
            if "imageUrl" in list_body[0] or "originalImageUrl" in list_body[0]:
                raise RuntimeError("History list contains an image payload")

            detail_response = client.get(f"/api/history/{inspection_id}")
            endpoint_statuses.append({"method": "GET", "path": "/api/history/{id}", "status": detail_response.status_code})
            detail_response.raise_for_status()
            detail_body = detail_response.json()
            responses["get-detail.json"] = detail_body
            if detail_body != post_body:
                raise RuntimeError("Persisted detail differs from POST response")

            storage = application.state.storage
            record = storage.get(inspection_id)
            if record is None:
                raise RuntimeError("SQLite record is missing before delete")
            stored_original, stored_annotated = storage.read_media(record)
            if stored_original != original_payload:
                raise RuntimeError("Persisted original is not byte-for-byte identical")
            response_original = _decode_data_url(detail_body["originalImageUrl"], record.media_type)
            response_annotated = _decode_data_url(detail_body["imageUrl"], record.media_type)
            if response_original != stored_original or response_annotated != stored_annotated:
                raise RuntimeError("HTTP detail data URLs differ from persisted media")
            annotated_image = cv2.imdecode(
                np.frombuffer(stored_annotated, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if annotated_image is None:
                raise RuntimeError("Persisted annotation cannot be decoded")
            if annotated_image.shape != (record.image_height, record.image_width, 3):
                raise RuntimeError("Persisted annotation dimensions changed")
            persistence_before_delete = {
                "recordExists": True,
                "databaseFields": {
                    "inspectionId": record.inspection_id,
                    "timestamp": post_body["timestamp"],
                    "fileName": record.filename,
                    "imageWidth": record.image_width,
                    "imageHeight": record.image_height,
                    "totalDefects": record.total_defects,
                    "qualityScore": record.quality_score,
                    "status": record.status,
                    "modelId": record.model_id,
                },
                "original": {
                    "relativePath": record.original_media_path,
                    "sha256": _sha256_bytes(stored_original),
                    "byteExactToSource": stored_original == original_payload,
                },
                "annotated": {
                    "relativePath": record.annotated_media_path,
                    "sha256": _sha256_bytes(stored_annotated),
                    "dimensions": {"width": record.image_width, "height": record.image_height},
                },
            }

            delete_response = client.delete(f"/api/history/{inspection_id}")
            endpoint_statuses.append({"method": "DELETE", "path": "/api/history/{id}", "status": delete_response.status_code})
            delete_response.raise_for_status()
            delete_body = delete_response.json()
            responses["delete-history.json"] = delete_body
            if delete_body != {"inspectionId": inspection_id, "deleted": True}:
                raise RuntimeError("Delete response does not match the API contract")

            after_delete_response = client.get("/api/history")
            endpoint_statuses.append({"method": "GET", "path": "/api/history", "status": after_delete_response.status_code})
            after_delete_response.raise_for_status()
            after_delete_body = after_delete_response.json()
            responses["get-history-after-delete.json"] = after_delete_body
            remaining_media = sorted(
                path.relative_to(storage.media.root).as_posix()
                for path in storage.media.root.rglob("*")
                if path.is_file()
            )
            persistence_after_delete = {
                "recordExists": storage.get(inspection_id) is not None,
                "historyCount": len(after_delete_body),
                "remainingMediaFiles": remaining_media,
            }
            if persistence_after_delete != {
                "recordExists": False,
                "historyCount": 0,
                "remainingMediaFiles": [],
            }:
                raise RuntimeError("Delete left SQLite metadata or media files")

    http_outputs: list[dict[str, str]] = []
    for filename, body in responses.items():
        output_path = output_directory / filename
        _write_json(output_path, body)
        http_outputs.append(
            {
                "path": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256_file(output_path),
            }
        )

    evidence = {
        "schemaVersion": 1,
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceCommit": _current_commit(),
        "sourceBinding": "sourceFiles contains the authoritative SHA-256 of executed source files",
        "sourceFiles": {
            relative_path: _sha256_file(REPOSITORY_ROOT / relative_path)
            for relative_path in SOURCE_PATHS
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "packages": {
                package: importlib.metadata.version(package)
                for package in (
                    "fastapi",
                    "httpx2",
                    "opencv-python",
                    "pydantic",
                    "starlette",
                    "torch",
                    "ultralytics",
                )
            },
            "transport": "Uvicorn loopback HTTP/1.1 with FastAPI lifespan",
        },
        "configuration": {
            "modelId": post_body["model"]["id"],
            "modelDevice": args.device,
            "modelConfidence": application.state.detection_runtime.registry.get(
                post_body["model"]["id"]
            ).confidence,
            "maxUploadBytes": 10485760,
            "database": "temporary SQLite file",
            "media": "temporary application-owned directory",
        },
        "sample": {
            "sampleId": sample["id"],
            "sourceUrl": sample["url"],
            "sourceSha256": original_hash,
        },
        "endpointSequence": endpoint_statuses,
        "httpOutputs": http_outputs,
        "inspection": {
            "inspectionId": post_body["inspectionId"],
            "totalDefects": post_body["totalDefects"],
            "qualityScore": post_body["qualityScore"],
            "status": post_body["status"],
            "model": post_body["model"],
        },
        "persistenceBeforeDelete": persistence_before_delete,
        "persistenceAfterDelete": persistence_after_delete,
        "acceptance": {
            "realRegisteredModelViaDetectionService": True,
            "postAndDetailIncludeDualDataUrls": True,
            "historyListOmitsImagePayloads": True,
            "originalStoredByteForByte": True,
            "annotatedStoredAtOriginalDimensions": True,
            "deleteRemovedMetadataAndMedia": True,
        },
    }
    evidence_path = output_directory / "api-persistence-acceptance.json"
    _write_json(evidence_path, evidence)
    print(f"[OK] Wrote API persistence evidence to {evidence_path}")
    print(
        f"[OK] POST -> list -> detail -> delete returned "
        f"{post_body['totalDefects']} real defect(s) and left no media files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
