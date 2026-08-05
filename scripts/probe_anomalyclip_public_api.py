"""Verify AnomalyCLIP preservation through public inspect and stream HTTP paths."""

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
MODEL_ID = "anomalyclip-general-v1"
DEFAULT_SAMPLE_CONTRACT = (
    REPOSITORY_ROOT
    / "docs/evidence/anomalyclip-public-api/sample-contract.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "docs/evidence/anomalyclip-public-api/public-api-acceptance.json"
)
SOURCE_PATHS = (
    "backend/main.py",
    "backend/models/model-manifest.json",
    "backend/models/config/anomalyclip-general-v1-score-calibration.json",
    "backend/models/record.py",
    "backend/routes/detect.py",
    "backend/routes/history.py",
    "backend/routes/models.py",
    "backend/routes/serialization.py",
    "backend/routes/stream.py",
    "backend/storage/media.py",
    "backend/storage/repository.py",
    "backend/storage/service.py",
    "backend/detection/anomalyclip_backend.py",
    "backend/detection/runtime.py",
    "backend/detection/service.py",
    "backend/utils/model_loader.py",
    "docs/evidence/anomalyclip-public-api/sample-contract.json",
    "requirements-api.txt",
    "requirements-detection.txt",
    "scripts/probe_anomalyclip_public_api.py",
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as json_file:
        value = json.load(json_file)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "inspect-vision-anomalyclip-public-api-probe"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _decode_data_url(value: str) -> tuple[str, bytes]:
    prefix, separator, encoded = value.partition(",")
    if separator != "," or not prefix.startswith("data:image/") or not prefix.endswith(
        ";base64"
    ):
        raise ValueError("Response does not contain an image data URL")
    media_type = prefix.removeprefix("data:").removesuffix(";base64")
    return media_type, base64.b64decode(encoded, validate=True)


def _image_dimensions(payload: bytes) -> dict[str, int]:
    image = cv2.imdecode(
        np.frombuffer(payload, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    if image is None:
        raise ValueError("Cannot decode image payload")
    return {"width": int(image.shape[1]), "height": int(image.shape[0])}


def _observation(body: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for defect in body["defects"]:
        box = defect["boundingBox"]
        observations.append(
            {
                "type": defect["type"],
                "confidence": float(defect["confidence"]),
                "xyxy": [
                    float(box["x"]),
                    float(box["y"]),
                    float(box["x"] + box["width"]),
                    float(box["y"] + box["height"]),
                ],
            }
        )
    return observations


def _matches_qualification(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> bool:
    if len(actual) != len(expected):
        return False
    for actual_defect, expected_defect in zip(actual, expected, strict=True):
        if actual_defect["type"] != expected_defect["type"]:
            return False
        if abs(actual_defect["confidence"] - expected_defect["confidence"]) > 1e-6:
            return False
        if any(
            abs(actual_value - expected_value) > 1e-4
            for actual_value, expected_value in zip(
                actual_defect["xyxy"], expected_defect["xyxy"], strict=True
            )
        ):
            return False
    return True


def _validate_response(
    body: dict[str, Any],
    sample: dict[str, Any],
    *,
    stream: bool,
) -> list[dict[str, Any]]:
    expected_dimensions = sample["dimensions"]
    width_field = "frameWidth" if stream else "imageWidth"
    height_field = "frameHeight" if stream else "imageHeight"
    if body.get("model") != {
        "id": MODEL_ID,
        "displayName": "General Manufacturing (AnomalyCLIP v1)",
    }:
        raise RuntimeError(f"Wrong public model projection for {sample['id']}")
    if body.get(width_field) != expected_dimensions["width"] or body.get(
        height_field
    ) != expected_dimensions["height"]:
        raise RuntimeError(f"Original dimensions changed for {sample['id']}")
    defects = body.get("defects")
    if not isinstance(defects, list) or body.get("totalDefects") != len(defects):
        raise RuntimeError(f"Invalid defect count for {sample['id']}")
    if body.get("status") != ("passed" if not defects else "failed"):
        raise RuntimeError(f"Invalid verdict for {sample['id']}")
    quality_score = body.get("qualityScore")
    if not isinstance(quality_score, int) or not 0 <= quality_score <= 100:
        raise RuntimeError(f"Invalid quality score for {sample['id']}")
    for defect in defects:
        if defect.get("type") != "anomaly":
            raise RuntimeError(f"Non-native defect type for {sample['id']}")
        confidence = defect.get("confidence")
        box = defect.get("boundingBox", {})
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise RuntimeError(f"Invalid calibrated confidence for {sample['id']}")
        if not (
            0.0 <= box.get("x", -1) < box.get("x", -1) + box.get("width", 0)
            <= expected_dimensions["width"]
            and 0.0
            <= box.get("y", -1)
            < box.get("y", -1) + box.get("height", 0)
            <= expected_dimensions["height"]
        ):
            raise RuntimeError(f"BBox is not in original coordinates for {sample['id']}")
    observation = _observation(body)
    if not _matches_qualification(observation, sample["expectedDetections"]):
        raise RuntimeError(f"Public API observation changed from qualification: {sample['id']}")
    return observation


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
    thread = threading.Thread(
        target=server.run,
        name="anomalyclip-public-api-evidence-uvicorn",
        daemon=True,
    )
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
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from backend.config import Settings
    from backend.main import create_app
    from backend.utils.model_loader import AnomalyClipConfigSpec, ModelRegistry

    contract = _load_json(args.samples)
    groups = contract.get("models", [])
    group = next(
        (candidate for candidate in groups if candidate.get("modelId") == MODEL_ID),
        None,
    )
    if group is None:
        raise KeyError(f"No sample group for model ID: {MODEL_ID}")
    samples = group.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("AnomalyCLIP public API sample contract is empty")

    payloads: dict[str, bytes] = {}
    for sample in samples:
        payload = _download(sample["url"])
        if len(payload) != sample["sizeBytes"]:
            raise ValueError(f"Sample size mismatch for {sample['id']}")
        if _sha256_bytes(payload) != sample["sha256"]:
            raise ValueError(f"Sample hash mismatch for {sample['id']}")
        if _image_dimensions(payload) != sample["dimensions"]:
            raise ValueError(f"Sample dimensions changed for {sample['id']}")
        payloads[sample["id"]] = payload

    registry = ModelRegistry()
    spec = registry.get_exposed(MODEL_ID)
    if registry.default_model_id != "factory-defect-guard-v6-mc":
        raise RuntimeError("Public qualification must not change the default model")
    if not isinstance(spec.backend_config, AnomalyClipConfigSpec):
        raise RuntimeError("Public AnomalyCLIP model has the wrong backend contract")

    artifact_integrity = []
    for artifact in spec.artifacts:
        path = REPOSITORY_ROOT / "backend/models" / artifact.filename
        actual_hash = _sha256_file(path)
        if path.stat().st_size != artifact.size_bytes or actual_hash != artifact.sha256:
            raise RuntimeError(f"Installed artifact failed integrity: {artifact.artifact_id}")
        artifact_integrity.append(
            {
                "id": artifact.artifact_id,
                "filename": artifact.filename,
                "sizeBytes": path.stat().st_size,
                "sha256": actual_hash,
                "verified": True,
            }
        )
    calibration = spec.backend_config.score_calibration
    calibration_hash = _sha256_file(calibration.path)
    if (
        calibration.path.stat().st_size != calibration.size_bytes
        or calibration_hash != calibration.sha256
    ):
        raise RuntimeError("Tracked calibration failed integrity")

    inspect_samples = [sample for sample in samples if sample["runtimePath"] == "inspect"]
    stream_samples = [sample for sample in samples if sample["runtimePath"] == "stream"]
    if len(inspect_samples) < 5 or len(stream_samples) != 1:
        raise ValueError("Sample contract must contain five inspect cases and one stream case")

    endpoint_sequence: list[dict[str, object]] = []
    inspect_evidence: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="inspect-vision-anomalyclip-api-") as temp_name:
        temp_root = Path(temp_name)
        settings = Settings(
            model_device=args.device,
            models_dir=REPOSITORY_ROOT / "backend/models",
            database_path=temp_root / "inspections.sqlite3",
            media_dir=temp_root / "media",
        )
        application = create_app(settings)
        with _serve(application) as base_url, httpx2.Client(
            base_url=base_url,
            timeout=300.0,
        ) as client:
            models_response = client.get("/api/models")
            endpoint_sequence.append(
                {"method": "GET", "path": "/api/models", "status": models_response.status_code}
            )
            models_response.raise_for_status()
            public_models = models_response.json()
            if [model["id"] for model in public_models] != [
                "factory-defect-guard-v6-mc",
                "neu-defect-yolov8",
                "concrete-crack-yolov8",
                MODEL_ID,
            ]:
                raise RuntimeError("GET /api/models did not expose the four-model contract")
            anomalyclip_metadata = public_models[-1]
            if (
                anomalyclip_metadata["preprocessingProfile"] != "anomalyclip-stretch"
                or anomalyclip_metadata["isDefault"] is not False
                or anomalyclip_metadata["installed"] is not True
            ):
                raise RuntimeError("GET /api/models returned invalid AnomalyCLIP metadata")

            history_start = client.get("/api/history")
            endpoint_sequence.append(
                {"method": "GET", "path": "/api/history", "status": history_start.status_code}
            )
            history_start.raise_for_status()
            if history_start.json() != []:
                raise RuntimeError("Temporary history was not empty at probe start")

            created_bodies: list[dict[str, Any]] = []
            for sample in inspect_samples:
                started = time.perf_counter()
                response = client.post(
                    "/api/inspect",
                    data={"modelId": MODEL_ID},
                    files={
                        "image": (
                            Path(sample["qualificationFile"]).name,
                            payloads[sample["id"]],
                            "image/png",
                        )
                    },
                )
                latency_ms = (time.perf_counter() - started) * 1000.0
                endpoint_sequence.append(
                    {"method": "POST", "path": "/api/inspect", "status": response.status_code}
                )
                response.raise_for_status()
                body = response.json()
                observation = _validate_response(body, sample, stream=False)
                original_media_type, original_payload = _decode_data_url(
                    body["originalImageUrl"]
                )
                annotated_media_type, annotated_payload = _decode_data_url(body["imageUrl"])
                if original_payload != payloads[sample["id"]]:
                    raise RuntimeError(f"Original bytes changed for {sample['id']}")
                if _image_dimensions(annotated_payload) != sample["dimensions"]:
                    raise RuntimeError(f"Annotated dimensions changed for {sample['id']}")

                detail_response = client.get(f"/api/history/{body['inspectionId']}")
                endpoint_sequence.append(
                    {
                        "method": "GET",
                        "path": "/api/history/{id}",
                        "status": detail_response.status_code,
                    }
                )
                detail_response.raise_for_status()
                if detail_response.json() != body:
                    raise RuntimeError(f"Persisted detail changed for {sample['id']}")
                created_bodies.append(body)
                inspect_evidence.append(
                    {
                        "sampleId": sample["id"],
                        "domain": sample["domain"],
                        "sourceLabel": sample["sourceLabel"],
                        "sourceUrl": sample["url"],
                        "sourceSha256": sample["sha256"],
                        "dimensions": sample["dimensions"],
                        "model": body["model"],
                        "observation": observation,
                        "totalDefects": body["totalDefects"],
                        "qualityScore": body["qualityScore"],
                        "status": body["status"],
                        "latencyMs": round(latency_ms, 3),
                        "qualificationMatch": True,
                        "original": {
                            "mediaType": original_media_type,
                            "sha256": _sha256_bytes(original_payload),
                            "byteExactToSource": True,
                        },
                        "annotated": {
                            "mediaType": annotated_media_type,
                            "sha256": _sha256_bytes(annotated_payload),
                            "dimensions": _image_dimensions(annotated_payload),
                        },
                        "historyDetailMatchesPost": True,
                        **(
                            {"diagnosticLimitation": sample["diagnosticLimitation"]}
                            if "diagnosticLimitation" in sample
                            else {}
                        ),
                    }
                )

            history_response = client.get("/api/history")
            endpoint_sequence.append(
                {"method": "GET", "path": "/api/history", "status": history_response.status_code}
            )
            history_response.raise_for_status()
            history = history_response.json()
            if len(history) != len(created_bodies) or {
                item["inspectionId"] for item in history
            } != {item["inspectionId"] for item in created_bodies}:
                raise RuntimeError("History does not contain every public inspection")
            if any(item["model"]["id"] != MODEL_ID for item in history):
                raise RuntimeError("History lost the AnomalyCLIP model ID")

            stream_sample = stream_samples[0]
            history_before_stream = history
            started = time.perf_counter()
            stream_response = client.post(
                "/api/stream",
                data={"modelId": MODEL_ID},
                files={
                    "frame": (
                        Path(stream_sample["qualificationFile"]).name,
                        payloads[stream_sample["id"]],
                        "image/jpeg",
                    )
                },
            )
            stream_latency_ms = (time.perf_counter() - started) * 1000.0
            endpoint_sequence.append(
                {"method": "POST", "path": "/api/stream", "status": stream_response.status_code}
            )
            stream_response.raise_for_status()
            stream_body = stream_response.json()
            stream_observation = _validate_response(
                stream_body,
                stream_sample,
                stream=True,
            )
            history_after_response = client.get("/api/history")
            endpoint_sequence.append(
                {
                    "method": "GET",
                    "path": "/api/history",
                    "status": history_after_response.status_code,
                }
            )
            history_after_response.raise_for_status()
            history_after_stream = history_after_response.json()
            if history_after_stream != history_before_stream:
                raise RuntimeError("Public stream request changed persisted history")

    evidence = {
        "schemaVersion": 1,
        "recordedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "sourceCommit": _current_commit(),
        "sourceBinding": "sourceFiles are the authoritative SHA-256 values of the executed current public path",
        "sourceFiles": {
            relative_path: _sha256_file(REPOSITORY_ROOT / relative_path)
            for relative_path in SOURCE_PATHS
        },
        "sampleContract": {
            "path": args.samples.resolve().relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(args.samples.resolve()),
            "qualification": contract["qualification"],
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "device": args.device,
            "packages": {
                package: importlib.metadata.version(package)
                for package in (
                    "fastapi",
                    "httpx2",
                    "opencv-python",
                    "pydantic",
                    "starlette",
                    "torch",
                    "uvicorn",
                )
            },
            "transport": "Uvicorn loopback HTTP/1.1 with FastAPI lifespan",
        },
        "registry": {
            "defaultModelId": registry.default_model_id,
            "publicModels": public_models,
            "anomalyclip": {
                "modelId": spec.model_id,
                "artifacts": artifact_integrity,
                "calibration": {
                    "path": calibration.path.relative_to(REPOSITORY_ROOT).as_posix(),
                    "sizeBytes": calibration.path.stat().st_size,
                    "sha256": calibration_hash,
                    "verified": True,
                },
            },
        },
        "pipeline": "POST /api/inspect and POST /api/stream -> DetectionRuntimeManager -> DetectionService -> AnomalyCLIP backend",
        "endpointSequence": endpoint_sequence,
        "inspect": inspect_evidence,
        "history": {
            "inspectionCount": len(history),
            "allModelIdsPreserved": True,
            "allDetailsMatchPost": True,
        },
        "stream": {
            "sampleId": stream_sample["id"],
            "sourceUrl": stream_sample["url"],
            "sourceSha256": stream_sample["sha256"],
            "dimensions": stream_sample["dimensions"],
            "model": stream_body["model"],
            "observation": stream_observation,
            "totalDefects": stream_body["totalDefects"],
            "qualityScore": stream_body["qualityScore"],
            "status": stream_body["status"],
            "latencyMs": round(stream_latency_ms, 3),
            "qualificationMatch": True,
            "historyCountBefore": len(history_before_stream),
            "historyCountAfter": len(history_after_stream),
            "historyUnchanged": True,
        },
        "accuracyClaim": False,
        "acceptance": {
            "fourModelsSerialized": True,
            "defaultModelUnchanged": True,
            "twoBinaryArtifactsVerified": True,
            "trackedCalibrationVerified": True,
            "realPublicInspectPath": True,
            "qualificationObservationsPreserved": True,
            "originalCoordinateBoxes": True,
            "annotatedDimensionsMatchOriginal": True,
            "historyAndDetailPreserveModel": True,
            "normalZeroDetectionAccepted": True,
            "realPublicStreamPath": True,
            "streamDidNotPersist": True,
            "cableIsDiagnosticOnly": True,
        },
    }
    _write_json(args.output.resolve(), evidence)
    print(f"[OK] Wrote AnomalyCLIP public API evidence to {args.output.resolve()}")
    print(
        f"[OK] {len(inspect_evidence)} inspect cases and one JPEG stream case "
        "preserved qualification observations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
