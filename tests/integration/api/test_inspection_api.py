from __future__ import annotations

import importlib.util
from pathlib import Path

from backend.utils.model_loader import ProductNameRequiredError


_CASES_PATH = Path(__file__).with_name("inspection_api_cases.py")
_SPEC = importlib.util.spec_from_file_location("inspection_api_cases", _CASES_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("Could not load API integration cases")
_CASES = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CASES)


# Most route/storage cases intentionally use the YOLO broad model so they remain
# focused on HTTP, persistence, filtering, and cleanup semantics. Dedicated tests
# below exercise the category-guided default and its required product context.
_ORIGINAL_FAKE_INSPECT = _CASES.FakeDetectionRuntime.inspect


def _compat_fake_inspect(self, image, model_id=None, *, product_name=None):
    resolved_model_id = model_id or "factory-defect-guard-v6-mc"
    return _ORIGINAL_FAKE_INSPECT(self, image, resolved_model_id)


_CASES.FakeDetectionRuntime.inspect = _compat_fake_inspect
api_factory = _CASES.api_factory

_STALE_CASES = {
    "test_inspect_accepts_png_and_jpeg_and_preserves_original_bytes",
    "test_anomalyclip_is_available_through_public_inference_routes",
    "test_models_endpoint_exposes_four_registry_entries",
    "test_stream_accepts_jpeg_and_does_not_persist",
}
for _name in dir(_CASES):
    if _name.startswith("test_") and _name not in _STALE_CASES:
        globals()[_name] = getattr(_CASES, _name)


class GuidedRuntime(_CASES.FakeDetectionRuntime):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.requested_product_names: list[str | None] = []

    def inspect(self, image, model_id=None, *, product_name=None):
        spec = self.registry.get(model_id)
        normalized_product = (product_name or "").strip() or None
        if spec.requires_product_name and normalized_product is None:
            raise ProductNameRequiredError("Product name is required for this detection model")
        self.requested_model_ids.append(spec.model_id)
        self.requested_product_names.append(normalized_product)
        if spec.model_id == self.missing_model_id:
            raise _CASES.ModelNotInstalledError(
                "Detection model is not installed. Run: "
                f"python scripts/install_models.py --model {spec.model_id}"
            )
        if self.fail:
            raise RuntimeError("private model failure")
        height, width = image.shape[:2]
        defect_type = {
            "bayespfl-general-v1": "anomaly",
            "concrete-crack-yolov8": "crack",
        }.get(spec.model_id, "scratches")
        defect = _CASES.InspectionDefect(
            type=defect_type,
            confidence=0.9,
            bounding_box=_CASES.BoundingBox(
                x=1.0,
                y=1.0,
                width=min(5.0, width - 1),
                height=min(4.0, height - 1),
            ),
        )
        annotated = image.copy()
        _CASES.cv2.rectangle(annotated, (1, 1), (6, 5), (0, 0, 255), 1)
        return _CASES.InspectionResult(
            image_width=width,
            image_height=height,
            defects=(defect,),
            status="failed",
            quality_score=80,
            annotated_image=annotated,
            model_id=spec.model_id,
        )


@_CASES.pytest.mark.parametrize(
    ("extension", "media_type"),
    [(".png", "image/png"), (".jpg", "image/jpeg")],
)
def test_guided_default_accepts_images_and_preserves_original_bytes(
    api_factory,
    extension: str,
    media_type: str,
) -> None:
    runtime = GuidedRuntime()
    client = api_factory(runtime)
    payload = _CASES.encoded_image(extension)

    response = client.post(
        "/api/inspect",
        data={"productName": "capsule"},
        files={"image": (f"..\\unsafe<>part{extension}", payload, "application/octet-stream")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fileName"] == f"unsafe_part{extension}"
    assert body["imageWidth"] == 24
    assert body["imageHeight"] == 16
    assert body["defects"][0]["type"] == "anomaly"
    assert body["model"] == {
        "id": "bayespfl-general-v1",
        "displayName": "General Manufacturing (Bayes-PFL)",
    }
    assert runtime.requested_model_ids == ["bayespfl-general-v1"]
    assert runtime.requested_product_names == ["capsule"]
    assert body["imageUrl"].startswith(f"data:{media_type};base64,")
    prefix, encoded_original = body["originalImageUrl"].split(",", 1)
    assert prefix == f"data:{media_type};base64"
    assert _CASES.base64.b64decode(encoded_original) == payload


def test_guided_default_requires_product_name(api_factory) -> None:
    client = api_factory(GuidedRuntime())

    response = client.post(
        "/api/inspect",
        files={"image": ("part.png", _CASES.encoded_image(".png"), "image/png")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Product name is required for this detection model"}


@_CASES.pytest.mark.parametrize(
    ("endpoint", "field", "filename", "history_count"),
    [
        ("/api/inspect", "image", "part.jpg", 1),
        ("/api/stream", "frame", "frame.jpg", 0),
    ],
)
def test_bayespfl_is_available_through_public_inference_routes(
    api_factory,
    endpoint: str,
    field: str,
    filename: str,
    history_count: int,
) -> None:
    runtime = GuidedRuntime()
    client = api_factory(runtime)

    response = client.post(
        endpoint,
        data={"modelId": "bayespfl-general-v1", "productName": "capsule"},
        files={field: (filename, _CASES.encoded_image(".jpg"), "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["model"] == {
        "id": "bayespfl-general-v1",
        "displayName": "General Manufacturing (Bayes-PFL)",
    }
    assert response.json()["defects"][0]["type"] == "anomaly"
    assert runtime.requested_product_names == ["capsule"]
    assert len(client.get("/api/history").json()) == history_count


def test_models_endpoint_exposes_current_registry_entries(api_factory) -> None:
    missing_id = "concrete-crack-yolov8"
    client = api_factory(_CASES.FakeDetectionRuntime(missing_model_id=missing_id))

    response = client.get("/api/models")

    assert response.status_code == 200
    models = response.json()
    assert [model["id"] for model in models] == [
        "bayespfl-general-v1",
        "factory-defect-guard-v6-mc",
        "neu-defect-yolov8",
        "concrete-crack-yolov8",
    ]
    assert sum(model["isDefault"] for model in models) == 1
    assert models[0] == {
        "id": "bayespfl-general-v1",
        "displayName": "General Manufacturing (Bayes-PFL)",
        "role": "general",
        "domain": "Cross-domain manufacturing anomaly localization",
        "description": (
            "Category-guided anomaly localization for varied manufactured products. "
            "Enter the product/category name; output is the native generic class anomaly, "
            "so specialists remain preferable for supported known domains."
        ),
        "classes": ["anomaly"],
        "preprocessingProfile": "bayespfl-stretch",
        "requiresProductName": True,
        "isDefault": True,
        "installed": True,
    }
    assert models[1]["requiresProductName"] is False
    assert models[3]["installed"] is False


def test_guided_default_stream_does_not_persist(api_factory) -> None:
    runtime = GuidedRuntime()
    client = api_factory(runtime)
    before = client.get("/api/history").json()

    response = client.post(
        "/api/stream",
        data={"productName": "capsule"},
        files={"frame": ("frame.png", _CASES.encoded_image(".jpg"), "image/png")},
    )
    after = client.get("/api/history").json()

    assert response.status_code == 200
    assert response.json()["frameWidth"] == 24
    assert response.json()["frameHeight"] == 16
    assert response.json()["defects"][0]["type"] == "anomaly"
    assert response.json()["model"] == {
        "id": "bayespfl-general-v1",
        "displayName": "General Manufacturing (Bayes-PFL)",
    }
    assert before == after == []
