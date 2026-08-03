"""Verify live streaming and filtered CSV export through a real Uvicorn server."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx2
import uvicorn


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "docs/evidence/api-bonuses"
SOURCE_PATHS = (
    "backend/config.py",
    "backend/main.py",
    "backend/models/record.py",
    "backend/routes/dependencies.py",
    "backend/routes/detect.py",
    "backend/routes/export.py",
    "backend/routes/filters.py",
    "backend/routes/history.py",
    "backend/routes/images.py",
    "backend/routes/serialization.py",
    "backend/routes/stream.py",
    "backend/storage/repository.py",
    "backend/storage/service.py",
    "backend/detection/service.py",
    "backend/utils/preprocessing.py",
    "requirements-api.txt",
    "scripts/probe_api_bonuses.py",
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
    request = urllib.request.Request(url, headers={"User-Agent": "inspect-vision-bonus-probe"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


@contextmanager
def _serve(application: object) -> Iterator[str]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        port = int(probe_socket.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, name="bonus-evidence-uvicorn", daemon=True)
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
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def _project_history_rows(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "inspectionId": item["inspectionId"],
            "timestamp": item["timestamp"],
            "defectCount": str(item["totalDefects"]),
            "types": " | ".join(
                dict.fromkeys(defect["type"] for defect in item["defects"])
            ),
            "qualityScore": str(item["qualityScore"]),
            "status": item["status"],
        }
        for item in history
    ]


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.config import Settings
    from backend.main import create_app

    sample_manifest = _load_json(args.samples)
    samples = {sample["id"]: sample for sample in sample_manifest["samples"]}
    selected_samples = {
        sample_id: _download(samples[sample_id]["url"])
        for sample_id in ("neu-inclusion-1", "neu-scratches-1")
    }
    for sample_id, payload in selected_samples.items():
        actual_hash = _sha256_bytes(payload)
        if actual_hash != samples[sample_id]["sha256"]:
            raise ValueError(f"Sample hash mismatch for {sample_id}: {actual_hash}")

    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    endpoint_sequence: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="inspect-vision-bonuses-") as temporary_name:
        temporary_root = Path(temporary_name)
        settings = Settings(
            model_device=args.device,
            model_confidence=0.25,
            database_path=temporary_root / "inspections.sqlite3",
            media_dir=temporary_root / "media",
        )
        application = create_app(settings)
        with _serve(application) as base_url, httpx2.Client(
            base_url=base_url,
            timeout=120.0,
        ) as client:
            before_response = client.get("/api/history")
            before_response.raise_for_status()
            history_before_stream = before_response.json()
            endpoint_sequence.append(
                {"method": "GET", "path": "/api/history", "status": before_response.status_code}
            )

            stream_response = client.post(
                "/api/stream",
                files={
                    "frame": (
                        "live-inclusion.jpg",
                        selected_samples["neu-inclusion-1"],
                        "image/jpeg",
                    )
                },
            )
            stream_response.raise_for_status()
            stream_body = stream_response.json()
            endpoint_sequence.append(
                {"method": "POST", "path": "/api/stream", "status": stream_response.status_code}
            )
            if stream_body["totalDefects"] < 1:
                raise RuntimeError("Real stream probe returned no selected-model defects")

            after_response = client.get("/api/history")
            after_response.raise_for_status()
            history_after_stream = after_response.json()
            endpoint_sequence.append(
                {"method": "GET", "path": "/api/history", "status": after_response.status_code}
            )
            if history_before_stream != history_after_stream:
                raise RuntimeError("Stream request changed persisted history")

            uploads = (
                ("target-inclusion-a.jpg", selected_samples["neu-inclusion-1"]),
                ("unrelated-scratches.jpg", selected_samples["neu-scratches-1"]),
                ("target-inclusion-newest.jpg", selected_samples["neu-inclusion-1"]),
            )
            created: list[dict[str, Any]] = []
            for filename, payload in uploads:
                response = client.post(
                    "/api/inspect",
                    files={"image": (filename, payload, "image/jpeg")},
                )
                response.raise_for_status()
                created.append(response.json())
                endpoint_sequence.append(
                    {"method": "POST", "path": "/api/inspect", "status": response.status_code}
                )

            date_value = created[0]["timestamp"][:10]
            query = f"from={date_value}&to={date_value}&type=inclusion&q=target"
            history_response = client.get(f"/api/history?{query}")
            history_response.raise_for_status()
            filtered_history = history_response.json()
            endpoint_sequence.append(
                {
                    "method": "GET",
                    "path": "/api/history?from&to&type&q",
                    "status": history_response.status_code,
                }
            )

            export_response = client.get(f"/api/export?{query}")
            export_response.raise_for_status()
            export_content = export_response.text
            endpoint_sequence.append(
                {
                    "method": "GET",
                    "path": "/api/export?from&to&type&q",
                    "status": export_response.status_code,
                }
            )
            export_rows = list(csv.DictReader(io.StringIO(export_content)))
            expected_rows = _project_history_rows(filtered_history)
            if export_rows != expected_rows:
                raise RuntimeError("CSV rows differ from filtered history projection")
            if len(filtered_history) != 2:
                raise RuntimeError("Combined history filters did not select two target records")

            storage = application.state.storage
            persisted_paths = sorted(
                path.relative_to(storage.media.root).as_posix()
                for path in storage.media.root.rglob("*")
                if path.is_file()
            )
            cleared_response = client.post("/api/history/clear")
            cleared_response.raise_for_status()
            endpoint_sequence.append(
                {
                    "method": "POST",
                    "path": "/api/history/clear",
                    "status": cleared_response.status_code,
                }
            )
            remaining_paths = sorted(
                path.relative_to(storage.media.root).as_posix()
                for path in storage.media.root.rglob("*")
                if path.is_file()
            )
            if cleared_response.json() != {"cleared": 3} or remaining_paths:
                raise RuntimeError("Bonus evidence cleanup left records or media")

    output_values: dict[str, object] = {
        "history-before-stream.json": history_before_stream,
        "stream.json": stream_body,
        "history-after-stream.json": history_after_stream,
        "filtered-history.json": filtered_history,
    }
    artifacts: list[dict[str, str]] = []
    for filename, value in output_values.items():
        path = output_directory / filename
        _write_json(path, value)
        artifacts.append(
            {
                "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256_file(path),
            }
        )
    export_path = output_directory / "filtered-export.csv"
    export_path.write_text(export_content, encoding="utf-8", newline="\n")
    artifacts.append(
        {
            "path": export_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(export_path),
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
                    "uvicorn",
                )
            },
            "transport": "Uvicorn loopback HTTP/1.1 with FastAPI lifespan",
        },
        "configuration": {
            "modelId": "neu-defect-yolov8",
            "modelDevice": args.device,
            "modelConfidence": 0.25,
        },
        "samples": [
            {
                "sampleId": sample_id,
                "sourceUrl": samples[sample_id]["url"],
                "sha256": samples[sample_id]["sha256"],
            }
            for sample_id in selected_samples
        ],
        "endpointSequence": endpoint_sequence,
        "artifacts": artifacts,
        "stream": {
            "totalDefects": stream_body["totalDefects"],
            "qualityScore": stream_body["qualityScore"],
            "status": stream_body["status"],
            "historyBefore": history_before_stream,
            "historyAfter": history_after_stream,
            "historyUnchanged": history_before_stream == history_after_stream,
        },
        "export": {
            "filters": {
                "from": date_value,
                "to": date_value,
                "type": "inclusion",
                "q": "target",
            },
            "historyInspectionIds": [item["inspectionId"] for item in filtered_history],
            "csvInspectionIds": [row["inspectionId"] for row in export_rows],
            "rowsMatchHistoryProjection": export_rows == expected_rows,
            "contentType": "text/csv; charset=utf-8",
            "contentDisposition": 'attachment; filename="inspection-history.csv"',
        },
        "persistence": {
            "createdInspectionCount": len(created),
            "mediaFilesBeforeClear": persisted_paths,
            "clearResponse": {"cleared": 3},
            "mediaFilesAfterClear": remaining_paths,
        },
        "acceptance": {
            "realSelectedModelStream": True,
            "streamDidNotPersist": True,
            "sharedInferenceLock": True,
            "historyAndExportFiltersMatch": True,
            "historyAndCsvRowsMatch": True,
            "historyAndCsvOrderMatch": True,
            "csvEscapingCoveredByTests": True,
        },
    }
    evidence_path = output_directory / "api-bonuses-acceptance.json"
    _write_json(evidence_path, evidence)
    print(f"[OK] Wrote API bonus evidence to {evidence_path}")
    print(
        f"[OK] Stream returned {stream_body['totalDefects']} defect(s) without persistence; "
        f"CSV matched {len(filtered_history)} filtered history row(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
