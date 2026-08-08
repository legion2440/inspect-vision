# Environment and model contract

Runtime configuration is read from environment variables. `.env.example` is the
tracked template; `.env`, model weights, databases, installed third-party runtime
files, and media are ignored.

The backend targets Python 3.13.5. `requirements-detection.txt` pins the
PyTorch/Ultralytics/OpenCV runtime; `requirements-api.txt` extends it with
FastAPI, Pydantic Settings, multipart handling, Uvicorn, and HTTP-test packages.

## Environment variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `INSPECT_VISION_HOST` | no | FastAPI bind host; defaults to loopback |
| `INSPECT_VISION_PORT` | no | FastAPI port |
| `INSPECT_VISION_CORS_ORIGINS` | yes | Comma-separated exact frontend origins |
| `INSPECT_VISION_MAX_UPLOAD_BYTES` | yes | Positive upload limit capped at 10485760 bytes |
| `INSPECT_VISION_MODELS_DIR` | yes | Directory containing untracked model artifacts |
| `INSPECT_VISION_MODEL_DEVICE` | yes | Exactly `auto`, `cpu`, `cuda`, or `cuda:N` |
| `INSPECT_VISION_DATABASE_PATH` | yes | SQLite database path |
| `INSPECT_VISION_MEDIA_DIR` | yes | Original and annotated image directory |

Per-model thresholds, input size, preprocessing, native classes, prompt settings,
and quality weights are intentionally absent from environment configuration.
Their source of truth is `backend/models/model-manifest.json`.

Frontend configuration remains in `frontend/.env.example`. Real relative `/api`
mode is the default; mock mode is explicit.

## Registry and lifecycle

The schema-validated v3 manifest contains one exposed `defaultModelId`, named
Ultralytics preprocessing profiles, and public models. Each model records:

- ID, display name, role, domain, and description;
- `backend: ultralytics | anomalyclip | bayespfl` and exposure status;
- pinned artifacts with source/revision, license scope, byte size, and SHA-256;
- square input size and model-native classes;
- backend-specific preprocessing/inference/postprocessing settings;
- neutral quality default plus optional native-class weights.

The current default is `bayespfl-general-v1`. It is category-guided and therefore
requires `productName` for inference. `neu-defect-yolov8` is the steel specialist
and `concrete-crack-yolov8` is the concrete/structural crack specialist. The
legacy multiclass `factory-defect-guard-v6-mc` remains available for its existing
coverage-oriented sample path. Native class names are authoritative and are not
translated into invented defect semantics.

FastAPI lifespan validates the registry and creates one
`DetectionRuntimeManager`; it does not eagerly load a checkpoint. On first use,
the manager resolves `modelId`, validates all local artifacts/runtime sources,
creates the matching `DetectionService`, and caches it. Guided models are cached
by `(model ID, normalized productName)` so one request cannot change another
prompt context. A shared inference lock serializes upload and live model calls.

Unknown or hidden IDs return HTTP 404. Missing or invalid registered artifacts
return HTTP 409 with the corresponding installer command. A guided request
without `productName` returns HTTP 422. Actual inference exceptions return HTTP
500 with detail `Detection model error`. Request handling never downloads a
model and never falls back to mock or heuristic detections.

Install artifacts atomically:

```bash
# default Bayes-PFL model, CLIP backbone, checkpoint, and pinned runtime source
.venv/Scripts/python.exe scripts/install_models.py

# one registered model
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# every exposed model
.venv/Scripts/python.exe scripts/install_models.py --all
```

Bayes-PFL does not require a separate Git checkout. The installer downloads the
minimal inference source set from pinned upstream revision
`8f155a07e734913e021c33c469f16a1f75c60e5d` and verifies each source against its
exact Git blob ID. The files stay untracked under
`backend/detection/third_party/bayespfl/runtime/`. Model binaries remain governed
by size and SHA-256 checks.

## Preprocessing and coordinates

`decode_image(bytes)` validates JPEG/PNG content and returns non-empty
`uint8 H x W x 3` BGR. Ultralytics models use service-owned geometry:

1. Preserve original dimensions and pixels.
2. Letterbox once to the model square input.
3. Apply the referenced profile.
4. Run the registered Ultralytics detector.
5. Restore valid boxes exactly once to original-image pixels.
6. Validate native classes, calculate quality, and annotate original pixels.

Profiles:

- `standard-color`: keep letterboxed BGR channels unchanged.
- `steel-enhanced`: grayscale + CLAHE after letterbox, repeated back to BGR.

Bayes-PFL uses backend-owned geometry and receives the original BGR image. It
owns RGB conversion, bicubic stretch to `518×518`, OpenAI CLIP normalization,
features `6/12/18/24`, 10 flows, prompt context length 5, 3 prompt samples, prompt
state length 5, 10 stochastic samples, seed 333, and Gaussian sigma `8`.

Application postprocessing for Bayes-PFL is fixed at:

```text
mapThreshold = 0.72
minComponentAreaRatio = 0.0005
bboxPaddingRatio = 0.25
```

Connected components are restored with independent x/y scaling to original
coordinates. The 25% padding changes only the returned display box around a
retained component; it does not alter the anomaly map or threshold decision.
The upstream benchmark does not publish a single deployment threshold, so the
fixed threshold is an application policy rather than an upstream metric claim.

Bayes-PFL emits only native type `anomaly`. Component confidence is the mean
anomaly score inside the retained threshold component; it is not a semantic
class probability.

## Quality score

The backend quality score is authoritative:

```text
bboxAreaRatio = originalBBoxArea / (originalImageWidth * originalImageHeight)
penalty = sum(classWeight * confidence * (10 + 90 * bboxAreaRatio))
qualityScore = clamp(round(100 - penalty), 0, 100)
```

Each model declares a positive default weight and optional native-class
overrides. Clean images score 100. This is an application heuristic, not
calibrated metrology or a safety measurement.

## Persistence

SQLite stores the actual model ID with every inspection. History list/detail
returns `model: { id, displayName }`; CSV columns remain unchanged. Product prompt
context is request-time inference input and is not currently persisted. Stream
responses include the model projection but are never stored.
