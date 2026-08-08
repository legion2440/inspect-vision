# Environment and model contract

Runtime configuration is read from environment variables. `.env.example` is the
tracked template; `.env`, model weights, databases, installed third-party runtime
files, and media are ignored.

The backend targets Python 3.13.5. Model thresholds, preprocessing, native
classes, prompt settings, and quality weights are manifest-owned rather than
environment-owned.

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

## Registry and selection lifecycle

`backend/models/model-manifest.json` v3 records detector artifacts and runtime
configuration. `backend/detection/model-selection.json` records deployment
selection decisions and the Bayes-PFL cross-dataset protocol.

Current exposed models:

- `bayespfl-general-v1` — default general anomaly localizer;
- `neu-defect-yolov8` — steel specialist;
- `concrete-crack-yolov8` — concrete/structural crack specialist.

`factory-defect-guard-v6-mc` remains registered for historical reproducibility
but is rejected as the current general model and therefore `exposed: false`.
Validation prevents that rejected/visible state from drifting back.

The Bayes checkpoint relationship is intentionally:

```text
train_visa.pth
auxiliary training domain = VisA
qualification/showcase domain = MVTec AD
protocol = held-out cross-dataset zero-shot
```

FastAPI lifespan validates the registry and creates one lazy
`DetectionRuntimeManager`; no checkpoint is eagerly loaded. On first use the
manager validates artifacts/runtime sources, creates the matching service, and
caches it. Guided Bayes services are cached by `(model ID, normalized category)`.

Bayes category input is normalized to lowercase, `_` becomes a space, and input
must be 2-40 characters using Latin letters/spaces/hyphens with at most three
words. Invalid guided context returns HTTP 422 for inspect and stream. Unknown or
hidden model IDs return HTTP 404. Missing/invalid exposed artifacts return HTTP
409 with the corresponding installer command. Inference failures map to HTTP
500 without leaking internal paths.

## Installation

```bash
# default Bayes-PFL + CLIP + pinned runtime source
.venv/Scripts/python.exe scripts/install_models.py

# one lightweight specialist
.venv/Scripts/python.exe scripts/install_models.py --model neu-defect-yolov8

# all exposed models
.venv/Scripts/python.exe scripts/install_models.py --all
```

Artifacts are installed atomically and verified by byte size and SHA-256. The
minimal Bayes-PFL runtime source set is fetched from pinned revision
`8f155a07e734913e021c33c469f16a1f75c60e5d` and verified against exact Git blob
IDs. A failed model-artifact download prints manual source, destination, expected
size, SHA-256, and retry information.

## Preprocessing and coordinates

Ultralytics specialists use service-owned geometry: one square letterbox, model
profile preprocessing, inference, and one restore to original-image pixels.

Bayes-PFL uses backend-owned geometry: RGB conversion, bicubic `518x518` stretch,
CLIP normalization, features `6/12/18/24`, 10 flows, prompt context length 5,
three prompt samples, prompt state length 5, ten stochastic samples, seed 333,
and Gaussian sigma `8`.

Application Bayes postprocessing remains:

```text
mapThreshold = 0.72
minComponentAreaRatio = 0.0005
bboxPaddingRatio = 0.25
```

Those are adapter settings, not an upstream accuracy claim. Bayes native type is
`anomaly`; specialist outputs preserve their own checkpoint-native semantic
classes.

## Persistence

SQLite stores the actual model ID with every inspection. History list/detail
returns `model: { id, displayName }`; historical records remain readable even if
a model later becomes hidden. Product/category context is request-time inference
input and is not currently persisted. Stream responses are never stored.
