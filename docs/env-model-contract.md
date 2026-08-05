# Environment and model contract

Runtime configuration is read from environment variables. `.env.example` is the
tracked template; `.env`, model weights, databases, and media are ignored.

The backend uses Python 3.13.5. `requirements-detection.txt` contains the pinned
Ultralytics/OpenCV CPU runtime and validation dependencies;
`requirements-api.txt` extends it with FastAPI, Pydantic Settings, multipart,
Uvicorn, and HTTP-test dependencies.

## Environment variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `INSPECT_VISION_HOST` | no | FastAPI bind host; defaults to loopback |
| `INSPECT_VISION_PORT` | no | FastAPI port |
| `INSPECT_VISION_CORS_ORIGINS` | yes | Comma-separated exact frontend origins |
| `INSPECT_VISION_MAX_UPLOAD_BYTES` | yes | Positive upload limit capped at 10485760 bytes |
| `INSPECT_VISION_MODELS_DIR` | yes | Directory containing untracked registered checkpoints |
| `INSPECT_VISION_MODEL_DEVICE` | yes | Exactly `auto`, `cpu`, `cuda`, or `cuda:N` |
| `INSPECT_VISION_DATABASE_PATH` | yes | SQLite database path |
| `INSPECT_VISION_MEDIA_DIR` | yes | Original and annotated image directory |

Per-model confidence, IoU, input size, preprocessing, classes, and quality
weights are intentionally absent from environment configuration. Their single
source of truth is `backend/models/model-manifest.json`.

Frontend configuration remains in `frontend/.env.example`. Real relative `/api`
mode is the default; mock mode must be enabled explicitly.

## Registry and lifecycle

The schema-validated v3 manifest contains one exposed `defaultModelId`, named
Ultralytics preprocessing profiles, and registered public or hidden models.
Each model records:

- ID, display name, role, domain, and cautious description;
- `backend: ultralytics | anomalyclip` and `exposed`;
- one or more pinned artifacts with URL/revision, literal license scope, byte
  size, and SHA-256;
- square input size, model-native classes, backend-specific configuration,
  neutral quality default, and optional class-specific quality weights.

The current default is `factory-defect-guard-v6-mc`. Specialists are
`neu-defect-yolov8` for steel surfaces and `concrete-crack-yolov8` for concrete
and structural cracks. Public `anomalyclip-general-v1` provides broad anomaly
localization with the generic native class `anomaly`; it does not classify
subtypes and does not replace the default. Native model names are authoritative
and are never translated into invented defect semantics.

FastAPI lifespan validates the manifest and creates one
`DetectionRuntimeManager`; it does not load a checkpoint. On first use the
manager resolves the optional request `modelId`, verifies the local size/hash,
loads and validates task/classes, creates the matching `DetectionService`, and
caches successful services. A shared application inference lock serializes both
upload and live inference across all cached models.

Unknown or hidden IDs return HTTP 404 at public inspect/stream boundaries. A
public registered model with missing or invalid artifacts returns HTTP 409 with
its `scripts/install_models.py --model <id>` command.
Actual inference exceptions remain HTTP 500 with exact detail
`Detection model error`. Request handling never downloads a model and never
falls back to mock or heuristic detections.

Install checkpoints atomically:

```bash
# default only
.venv/Scripts/python.exe scripts/install_models.py

# one registered model
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# every exposed model, including AnomalyCLIP and both of its artifacts
.venv/Scripts/python.exe scripts/install_models.py --all
```

## Preprocessing and coordinates

`decode_image(bytes)` validates JPEG/PNG content and returns a non-empty
`uint8 H x W x 3` BGR image. `DetectionService` accepts only this decoded array.
Ultralytics models use the service-owned geometry path:

1. Preserve original dimensions and pixels.
2. Letterbox once to the model's square input using its manifest padding color.
3. Apply the referenced preprocessing profile.
4. Pass the already-square three-channel uint8 image to Ultralytics.
5. Clamp/drop invalid adapter boxes and restore valid boxes exactly once to
   original-image pixels.
6. Validate native classes, calculate quality, and annotate a copy of the
   original BGR image.

Profiles:

- `standard-color`: keep the letterboxed BGR channels unchanged. Used by the
  broad and concrete models.
- `steel-enhanced`: letterbox, convert to grayscale, apply
  `CLAHE(clipLimit=2.0, tileGridSize=(8, 8))`, then repeat the adjusted channel
  to BGR. Used by the steel specialist.

Ultralytics still performs tensor conversion and normalization, but receives an
already-sized square so there is no second geometric letterbox. API image
encoding remains outside detection; original bytes stay unchanged and the
annotation is encoded in the detected source format.

The public AnomalyCLIP backend declares backend-owned geometry. It receives the
original BGR image and owns the frozen 518×518 stretch, CLIP normalization,
feature layers `6/12/18/24`, DPAM layer `20`, Gaussian sigma `4`, threshold
`0.10`, ellipse `3×3` open/close, minimum-area ratio `0.0005`, merge distance
`6`, connected components, and separate x/y coordinate restoration. The service
therefore performs neither letterbox nor a second restore. Component confidence
is the tracked empirical percentile against 131 clean-reference component
means; it is not a class probability.

## Quality score

The backend `quality-v1` score is authoritative and is calculated after box
restoration:

```text
bboxAreaRatio = originalBBoxArea / (originalImageWidth * originalImageHeight)
penalty = sum(classWeight * confidence * (10 + 90 * bboxAreaRatio))
qualityScore = clamp(round(100 - penalty), 0, 100)
```

Each model declares `quality.defaultWeight`, currently the explicit neutral
value `1.0`, plus optional positive overrides for its own native classes. The
steel model retains its six established weights; concrete uses `crack = 1.35`;
the broad model currently uses neutral weights. Clean images score 100. This is
an application heuristic, not calibrated metrology or a safety measurement.

## Persistence

SQLite stores the actual model ID with every inspection and accepts all
registered IDs without schema changes. History list/detail returns
`model: { id, displayName }`; CSV columns remain unchanged. Stream responses
contain the same model projection but are never persisted.
