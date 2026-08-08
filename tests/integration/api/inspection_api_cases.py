from __future__ import annotations

import base64
import csv
import hashlib
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.detection.dto import BoundingBox, InspectionDefect, InspectionResult
from backend.detection.runtime import RegisteredModel
from backend.main import build_storage, create_app
from backend.utils.model_loader import ModelNotInstalledError, ModelRegistry


def encoded_image(extension: str, *, width: int = 24, height: int = 16) -> bytes:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 1] = 140
    image[2:8, 3:10, 2] = 255
    encoded, buffer = cv2.imencode(extension, image)
    assert encoded
    return buffer.tobytes()


class FakeDetectionRuntime:
    def __init__(
        self,
        *,
        fail: bool = False,
        delay: float = 0.0,
        missing_model_id: str | None = None,
    ) -> None:
        self.fail = fail
        self.delay = delay
        self.missing_model_id = missing_model_id
        self.registry = ModelRegistry()
        self.requested_model_ids: list[str] = []
        self._guard = threading.Lock()
        self.active = 0
        self.max_active = 0

    def registered_models(
        self,
        *,
        exposed_only: bool = False,
    ) -> tuple[RegisteredModel, ...]:
        specs = self.registry.exposed_models if exposed_only else self.registry.models
        return tuple(
            RegisteredModel(
                spec=spec,
                is_default=self.registry.is_default(spec.model_id),
                installed=spec.model_id != self.missing_model_id,
            )
            for spec in specs
        )

    def inspect(self, image: np.ndarray, model_id: str | None = None) -> InspectionResult:
        spec = self.registry.get(model_id)
        self.requested_model_ids.append(spec.model_id)
        if spec.model_id == self.missing_model_id:
            raise ModelNotInstalledError(
                f"Detection model is not installed. Run: python scripts/install_models.py --model {spec.model_id}"
            )
        with self._guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.fail:
                raise RuntimeError("private model failure")
            height, width = image.shape[:2]
            box = BoundingBox(x=1.0, y=1.0, width=min(5.0, width - 1), height=min(4.0, height - 1))
            defect_type = {
                "concrete-crack-yolov8": "crack",
                "anomalyclip-general-v1": "anomaly",
            }.get(spec.model_id, "scratches")
            defect = InspectionDefect(
                type=defect_type,
                confidence=0.9,
                bounding_box=box,
            )
            annotated = image.copy()
            cv2.rectangle(annotated, (1, 1), (6, 5), (0, 0, 255), 1)
            return InspectionResult(
                image_width=width,
                image_height=height,
                defects=(defect,),
                status="failed",
                quality_score=80,
                annotated_image=annotated,
                model_id=spec.model_id,
            )
        finally:
            with self._guard:
                self.active -= 1


@pytest.fixture
def api_factory(tmp_path: Path):
    clients: list[TestClient] = []

    def factory(runtime: FakeDetectionRuntime | None = None) -> TestClient:
        settings = Settings(
            database_path=tmp_path / f"db-{len(clients)}.sqlite3",
            media_dir=tmp_path / f"media-{len(clients)}",
        )
        fake = runtime or FakeDetectionRuntime()
        app = create_app(
            settings,
            detection_runtime_factory=lambda _settings: fake,
            storage_factory=build_storage,
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory

    for client in reversed(clients):
        client.__exit__(None, None, None)


@pytest.mark.parametrize(
    ("extension", "media_type"),
    [(".png", "image/png"), (".jpg", "image/jpeg")],
)
def test_inspect_accepts_png_and_jpeg_and_preserves_original_bytes(
    api_factory,
    extension: str,
    media_type: str,
) -> None:
    client = api_factory()
    payload = encoded_image(extension)

    response = client.post(
        "/api/inspect",
        files={"image": (f"..\\unsafe<>part{extension}", payload, "application/octet-stream")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fileName"] == f"unsafe_part{extension}"
    assert body["imageWidth"] == 24
    assert body["imageHeight"] == 16
    assert body["totalDefects"] == len(body["defects"]) == 1
    assert body["status"] == "failed"
    assert body["qualityScore"] == 80
    assert body["model"] == {
        "id": "factory-defect-guard-v6-mc",
        "displayName": "General Manufacturing",
    }
    assert body["imageUrl"].startswith(f"data:{media_type};base64,")
    prefix, encoded_original = body["originalImageUrl"].split(",", 1)
    assert prefix == f"data:{media_type};base64"
    assert base64.b64decode(encoded_original) == payload


def test_content_is_authoritative_over_extension_and_client_mime(api_factory) -> None:
    client = api_factory()
    payload = encoded_image(".png")

    response = client.post(
        "/api/inspect",
        files={"image": ("part.gif", payload, "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fileName"] == "part.gif"
    assert body["originalImageUrl"].startswith("data:image/png;base64,")


def test_undecodable_spoofed_jpeg_returns_exact_error(api_factory) -> None:
    client = api_factory()

    response = client.post(
        "/api/inspect",
        files={"image": ("fake.jpg", b"\xff\xd8not-an-image", "image/jpeg")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported file type"}


def test_non_image_returns_exact_error(api_factory) -> None:
    client = api_factory()

    response = client.post(
        "/api/inspect",
        files={"image": ("fake.png", b"plain text", "image/png")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported file type"}


def test_exact_10_mib_is_accepted_and_one_byte_over_is_rejected(api_factory) -> None:
    client = api_factory()
    small_png = encoded_image(".png")
    limit = 10 * 1024 * 1024
    exact = small_png + b"\x00" * (limit - len(small_png))

    accepted = client.post(
        "/api/inspect",
        files={"image": ("exact.png", exact, "image/png")},
    )
    rejected = client.post(
        "/api/inspect",
        files={"image": ("large.png", exact + b"\x00", "image/png")},
    )

    assert accepted.status_code == 200, accepted.text
    assert rejected.status_code == 413
    assert rejected.json() == {"detail": "File size exceeds 10MB limit"}


def test_model_failure_is_mapped_without_leaking_exception(api_factory) -> None:
    client = api_factory(FakeDetectionRuntime(fail=True))

    response = client.post(
        "/api/inspect",
        files={"image": ("part.png", encoded_image(".png"), "image/png")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Detection model error"}
    assert "private" not in response.text


def test_inspect_propagates_selected_model_and_persists_it(api_factory) -> None:
    runtime = FakeDetectionRuntime()
    client = api_factory(runtime)

    response = client.post(
        "/api/inspect",
        data={"modelId": "concrete-crack-yolov8"},
        files={"image": ("wall.png", encoded_image(".png"), "image/png")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"] == {
        "id": "concrete-crack-yolov8",
        "displayName": "Concrete & Structural Cracks",
    }
    assert body["defects"][0]["type"] == "crack"
    assert runtime.requested_model_ids == ["concrete-crack-yolov8"]
    history = client.get("/api/history").json()
    assert history[0]["model"] == body["model"]


def test_model_lookup_and_installation_errors_are_distinct(api_factory) -> None:
    missing_id = "concrete-crack-yolov8"
    client = api_factory(FakeDetectionRuntime(missing_model_id=missing_id))

    unknown = client.post(
        "/api/inspect",
        data={"modelId": "unknown"},
        files={"image": ("part.png", encoded_image(".png"), "image/png")},
    )
    missing = client.post(
        "/api/inspect",
        data={"modelId": missing_id},
        files={"image": ("wall.png", encoded_image(".png"), "image/png")},
    )

    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Detection model not found"}
    assert missing.status_code == 409
    assert f"install_models.py --model {missing_id}" in missing.json()["detail"]


@pytest.mark.parametrize(
    ("endpoint", "field", "filename", "history_count"),
    [
        ("/api/inspect", "image", "part.jpg", 1),
        ("/api/stream", "frame", "frame.jpg", 0),
    ],
)
def test_anomalyclip_is_available_through_public_inference_routes(
    api_factory,
    endpoint: str,
    field: str,
    filename: str,
    history_count: int,
) -> None:
    class ExposureAwareRuntime(FakeDetectionRuntime):
        def inspect(
            self,
            image: np.ndarray,
            model_id: str | None = None,
        ) -> InspectionResult:
            self.registry.get_exposed(model_id)
            return super().inspect(image, model_id)

    client = api_factory(ExposureAwareRuntime())

    response = client.post(
        endpoint,
        data={"modelId": "anomalyclip-general-v1"},
        files={field: (filename, encoded_image(".jpg"), "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["model"] == {
        "id": "anomalyclip-general-v1",
        "displayName": "General Manufacturing (AnomalyCLIP v1)",
    }
    assert response.json()["defects"][0]["type"] == "anomaly"
    assert len(client.get("/api/history").json()) == history_count


def test_models_endpoint_exposes_four_registry_entries(api_factory) -> None:
    missing_id = "concrete-crack-yolov8"
    client = api_factory(FakeDetectionRuntime(missing_model_id=missing_id))

    response = client.get("/api/models")

    assert response.status_code == 200
    models = response.json()
    assert [model["id"] for model in models] == [
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
        "anomalyclip-general-v1",
    ]
    assert sum(model["isDefault"] for model in models) == 1
    assert models[0]["installed"] is True
    assert models[2]["installed"] is False
    assert models[3] == {
        "id": "anomalyclip-general-v1",
        "displayName": "General Manufacturing (AnomalyCLIP v1)",
        "role": "general",
        "domain": "Cross-domain manufacturing anomaly localization",
        "description": (
            "Broad anomaly localization with generic anomaly output and no subtype "
            "classification; specialist models are preferred for known domains."
        ),
        "classes": ["anomaly"],
        "preprocessingProfile": "anomalyclip-stretch",
        "isDefault": False,
        "installed": True,
    }


def test_samples_endpoint_exposes_manifest_metadata_without_image_payloads(api_factory) -> None:
    client = api_factory()

    response = client.get("/api/samples")

    assert response.status_code == 200
    body = response.json()
    assert body["notice"] == "Source labels describe dataset metadata, not model predictions."
    assert len(body["datasets"]) >= 3
    assert len(body["samples"]) == 9
    assert "base64" not in response.text.casefold()
    registered_ids = {model["id"] for model in client.get("/api/models").json()}
    recommended_ids = [sample["recommendedModelId"] for sample in body["samples"]]
    assert set(recommended_ids).issubset(registered_ids)
    assert set(recommended_ids) == {
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
    }
    assert all(recommended_ids.count(model_id) == 3 for model_id in set(recommended_ids))
    assert all(sample["imageUrl"].endswith("/image") for sample in body["samples"])


def test_sample_image_is_served_by_manifest_id_with_matching_hash(api_factory) -> None:
    client = api_factory()
    sample = client.get("/api/samples").json()["samples"][0]

    response = client.get(sample["imageUrl"])

    assert response.status_code == 200
    assert response.headers["content-type"] == sample["mediaType"]
    assert hashlib.sha256(response.content).hexdigest() == sample["sha256"]


def test_unknown_sample_id_returns_404_without_path_lookup(api_factory) -> None:
    client = api_factory()

    response = client.get("/api/samples/unknown-sample/image")
    traversal = client.get("/api/samples/..%2Fmodel-manifest.json/image")

    assert response.status_code == 404
    assert response.json() == {"detail": "Sample not found"}
    assert traversal.status_code == 404


def test_stream_accepts_jpeg_and_does_not_persist(api_factory) -> None:
    client = api_factory()
    before = client.get("/api/history").json()

    response = client.post(
        "/api/stream",
        files={"frame": ("frame.png", encoded_image(".jpg"), "image/png")},
    )
    after = client.get("/api/history").json()

    assert response.status_code == 200
    assert response.json() == {
        "frameWidth": 24,
        "frameHeight": 16,
        "defects": [
            {
                "type": "scratches",
                "confidence": 0.9,
                "boundingBox": {"x": 1.0, "y": 1.0, "width": 5.0, "height": 4.0},
            }
        ],
        "totalDefects": 1,
        "qualityScore": 80,
        "status": "failed",
        "model": {
            "id": "factory-defect-guard-v6-mc",
            "displayName": "General Manufacturing",
        },
    }
    assert before == after == []


def test_stream_rejects_png_content(api_factory) -> None:
    client = api_factory()

    response = client.post(
        "/api/stream",
        files={"frame": ("frame.jpg", encoded_image(".png"), "image/jpeg")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported file type"}


def test_stream_propagates_selected_model_without_persistence(api_factory) -> None:
    runtime = FakeDetectionRuntime()
    client = api_factory(runtime)

    response = client.post(
        "/api/stream",
        data={"modelId": "concrete-crack-yolov8"},
        files={"frame": ("frame.jpg", encoded_image(".jpg"), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["model"] == {
        "id": "concrete-crack-yolov8",
        "displayName": "Concrete & Structural Cracks",
    }
    assert response.json()["defects"][0]["type"] == "crack"
    assert client.get("/api/history").json() == []


def test_stream_maps_model_failure(api_factory) -> None:
    client = api_factory(FakeDetectionRuntime(fail=True))

    response = client.post(
        "/api/stream",
        files={"frame": ("frame.jpg", encoded_image(".jpg"), "image/jpeg")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Detection model error"}


def test_history_list_omits_images_and_detail_hydrates_them(api_factory) -> None:
    client = api_factory()
    created = client.post(
        "/api/inspect",
        files={"image": ("Line-A.png", encoded_image(".png"), "image/png")},
    ).json()

    history = client.get("/api/history?type=scratches&q=line-a")
    detail = client.get(f"/api/history/{created['inspectionId']}")

    assert history.status_code == 200
    assert len(history.json()) == 1
    assert "imageUrl" not in history.json()[0]
    assert "originalImageUrl" not in history.json()[0]
    assert detail.status_code == 200
    assert detail.json() == created


def test_history_survives_a_model_removed_from_the_registry(api_factory) -> None:
    client = api_factory()
    created = client.post(
        "/api/inspect",
        files={"image": ("legacy.png", encoded_image(".png"), "image/png")},
    ).json()
    retired_model_id = "retired-manufacturing-model"
    repository = client.app.state.storage.repository
    with repository.transaction() as connection:
        connection.execute(
            "UPDATE inspections SET model_id = ? WHERE inspection_id = ?",
            (retired_model_id, created["inspectionId"]),
        )

    history_response = client.get("/api/history")
    detail_response = client.get(f"/api/history/{created['inspectionId']}")

    assert history_response.status_code == 200
    assert detail_response.status_code == 200
    expected_model = {"id": retired_model_id, "displayName": retired_model_id}
    assert history_response.json()[0]["model"] == expected_model
    assert detail_response.json()["model"] == expected_model


def test_history_is_newest_first_and_dates_are_applied(api_factory) -> None:
    client = api_factory()
    first = client.post(
        "/api/inspect",
        files={"image": ("first.png", encoded_image(".png"), "image/png")},
    ).json()
    second = client.post(
        "/api/inspect",
        files={"image": ("second.png", encoded_image(".png"), "image/png")},
    ).json()
    today = first["timestamp"][:10]

    current = client.get(f"/api/history?from={today}&to={today}")
    historical = client.get("/api/history?to=2000-01-01")

    assert [item["inspectionId"] for item in current.json()] == [
        second["inspectionId"],
        first["inspectionId"],
    ]
    assert historical.json() == []


def test_history_date_validation_returns_422(api_factory) -> None:
    client = api_factory()

    invalid = client.get("/api/history?from=not-a-date")
    reversed_range = client.get("/api/history?from=2026-08-04&to=2026-08-03")

    assert invalid.status_code == 422
    assert reversed_range.status_code == 422


def test_export_rows_match_filtered_history_order_and_projection(api_factory) -> None:
    client = api_factory()
    for filename in ("target-first.jpg", "unrelated.jpg", "target-newest.jpg"):
        response = client.post(
            "/api/inspect",
            files={"image": (filename, encoded_image(".jpg"), "image/jpeg")},
        )
        assert response.status_code == 200
    today = client.get("/api/history").json()[0]["timestamp"][:10]
    query = f"from={today}&to={today}&type=scratches&q=target"

    history_response = client.get(f"/api/history?{query}")
    export_response = client.get(f"/api/export?{query}")

    assert history_response.status_code == 200
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        export_response.headers["content-disposition"]
        == 'attachment; filename="inspection-history.csv"'
    )
    history = history_response.json()
    rows = list(csv.DictReader(io.StringIO(export_response.text)))
    assert [row["inspectionId"] for row in rows] == [
        item["inspectionId"] for item in history
    ]
    assert rows == [
        {
            "inspectionId": item["inspectionId"],
            "timestamp": item["timestamp"],
            "defectCount": str(item["totalDefects"]),
            "types": " | ".join(dict.fromkeys(defect["type"] for defect in item["defects"])),
            "qualityScore": str(item["qualityScore"]),
            "status": item["status"],
        }
        for item in history
    ]


def test_export_uses_the_same_filter_validation_as_history(api_factory) -> None:
    client = api_factory()

    invalid_date = client.get("/api/export?from=not-a-date")
    reversed_range = client.get("/api/export?from=2026-08-04&to=2026-08-03")

    assert invalid_date.status_code == 422
    assert reversed_range.status_code == 422


def test_delete_and_clear_remove_records_and_media(api_factory) -> None:
    client = api_factory()
    first = client.post(
        "/api/inspect",
        files={"image": ("a.png", encoded_image(".png"), "image/png")},
    ).json()
    second = client.post(
        "/api/inspect",
        files={"image": ("b.jpg", encoded_image(".jpg"), "image/jpeg")},
    ).json()

    deleted = client.delete(f"/api/history/{first['inspectionId']}")
    missing = client.get(f"/api/history/{first['inspectionId']}")
    cleared = client.post("/api/history/clear")

    assert deleted.json() == {"inspectionId": first["inspectionId"], "deleted": True}
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Inspection not found"}
    assert cleared.json() == {"cleared": 1}
    assert client.get(f"/api/history/{second['inspectionId']}").status_code == 404
    assert list(client.app.state.storage.media.original_directory.iterdir()) == []
    assert list(client.app.state.storage.media.annotated_directory.iterdir()) == []


def test_missing_delete_returns_exact_error(api_factory) -> None:
    client = api_factory()

    response = client.delete("/api/history/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Inspection not found"}


def test_configured_cors_origin_is_allowed(api_factory) -> None:
    client = api_factory()

    response = client.options(
        "/api/history",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_inference_lock_serializes_concurrent_requests(api_factory) -> None:
    runtime = FakeDetectionRuntime(delay=0.05)
    client = api_factory(runtime)

    def request_once(index: int) -> int:
        response = client.post(
            "/api/inspect",
            files={"image": (f"part-{index}.png", encoded_image(".png"), "image/png")},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=3) as executor:
        statuses = list(executor.map(request_once, range(3)))

    assert statuses == [200, 200, 200]
    assert runtime.max_active == 1


def test_stream_and_inspect_share_one_inference_lock(api_factory) -> None:
    runtime = FakeDetectionRuntime(delay=0.05)
    client = api_factory(runtime)

    def inspect_request() -> int:
        return client.post(
            "/api/inspect",
            files={"image": ("part.jpg", encoded_image(".jpg"), "image/jpeg")},
        ).status_code

    def stream_request() -> int:
        return client.post(
            "/api/stream",
            files={"frame": ("frame.jpg", encoded_image(".jpg"), "image/jpeg")},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(inspect_request), executor.submit(stream_request)]
        statuses = [future.result() for future in futures]

    assert statuses == [200, 200]
    assert runtime.max_active == 1


def test_persisted_detail_survives_application_reopen(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "reopen.sqlite3",
        media_dir=tmp_path / "reopen-media",
    )

    def make_client() -> TestClient:
        app = create_app(
            settings,
            detection_runtime_factory=lambda _settings: FakeDetectionRuntime(),
            storage_factory=build_storage,
        )
        return TestClient(app)

    with make_client() as first_client:
        created = first_client.post(
            "/api/inspect",
            files={"image": ("persistent.png", encoded_image(".png"), "image/png")},
        ).json()

    with make_client() as reopened_client:
        response = reopened_client.get(f"/api/history/{created['inspectionId']}")

    assert response.status_code == 200
    assert response.json() == created
