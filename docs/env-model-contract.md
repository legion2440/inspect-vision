# Environment and model contract

Runtime configuration is read from environment variables. `.env.example` is the
tracked template; `.env`, model weights, databases, and media are ignored.

The backend runtime uses Python 3.13.5. The reproducible baseline dependency
profile is `requirements-detection.txt` and intentionally excludes FastAPI,
Streamlit, supervision, tracking, and video runtimes.

## Variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `INSPECT_VISION_HOST` | no | FastAPI bind host; defaults to loopback |
| `INSPECT_VISION_PORT` | no | FastAPI port |
| `INSPECT_VISION_CORS_ORIGINS` | yes | Comma-separated exact frontend origins |
| `INSPECT_VISION_MAX_UPLOAD_BYTES` | yes | Upload limit; canonical value is 10485760 |
| `INSPECT_VISION_MODEL_KIND` | yes | Registered adapter kind; currently `ultralytics` |
| `INSPECT_VISION_MODEL_PATH` | yes | Repository-relative or deployment-local model path |
| `INSPECT_VISION_MODEL_INPUT_SIZE` | yes | Square model input size, initially 640 |
| `INSPECT_VISION_MODEL_CONFIDENCE` | yes | Inclusive detection threshold from 0 to 1 |
| `INSPECT_VISION_MODEL_DEVICE` | yes | Exactly `auto`, `cpu`, `cuda`, or `cuda:N` |
| `INSPECT_VISION_DATABASE_PATH` | yes | SQLite database path |
| `INSPECT_VISION_MEDIA_DIR` | yes | Original and annotated image directory |

Frontend configuration remains in `frontend/.env.example`. Its default is real
API mode and it must not be changed back to implicit mock mode.

## Model lifecycle

- `backend/models/model-manifest.json` is the tracked model registry. The selected
  model, immutable source revision, MIT license metadata, SHA-256, byte size,
  input size, task, and checkpoint-native classes are recorded there.
- Verify the local weight byte size and SHA-256 before constructing the adapter.
- Load one model instance during future FastAPI lifespan startup or through one
  concurrency-safe lazy loader.
- Validate kind, readable path, class names, input size, and supported device.
- Do not download weights during request handling.
- Do not silently replace a missing or failing model with random, heuristic, or
  mock detections. `/api/inspect` and `/api/stream` return `Detection model error`.
- Serialize inference when the selected runtime/model is not thread-safe.
- Record model ID and manifest hash on every future persisted inspection.
- Large weights remain untracked.

## Preprocessing and coordinates

The current detection core accepts `uint8 H × W × 3` BGR arrays. For Ultralytics
`.pt` inference it passes the original array to the library without an additional
letterbox; Ultralytics returns boxes in original-image coordinates.

The next inspection-service milestone will make OpenCV own the required stages:

1. Decode JPEG/PNG and reject invalid content.
2. Preserve the original width and height.
3. Produce grayscale and contrast-adjusted representations for the configured
   pipeline.
4. Resize or letterbox to model input dimensions and normalize as required.
5. Run inference.
6. Map boxes back to original-image pixels and clamp them to bounds.
7. Draw annotations on a copy of the original BGR image.
8. Encode original and annotated images for the API contract.

The adapter boundary returns normalized detections independent of YOLO library
objects. API routes never parse raw model tensors.

## Quality score

The backend score is authoritative and uses defect count, configured class
weights, confidence, and box area divided by `imageWidth * imageHeight`. The
formula and weights must be unit-tested and versioned. Clean images score 100;
the result is clamped to the inclusive 0–100 range.

## Storage

SQLite stores metadata and relative media paths, not base64 bodies. Media writes,
metadata commits, deletion, and clearing must leave no orphaned files after a
successful operation. History list queries never load image bytes.
