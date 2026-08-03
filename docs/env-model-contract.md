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
| `INSPECT_VISION_CLAHE_CLIP_LIMIT` | yes | CLAHE clip limit; fixed baseline is `2.0` |
| `INSPECT_VISION_CLAHE_TILE_GRID_SIZE` | yes | Square CLAHE tile grid edge; fixed baseline is `8`, meaning `8 × 8` |
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

`decode_image(bytes)` decodes future HTTP-boundary JPEG/PNG payloads into a
validated, non-empty `uint8 H × W × 3` BGR array. `DetectionService` itself
accepts only that already-decoded array and applies the fixed production path:

1. Preserve original width, height, and pixels.
2. Letterbox once to `640 × 640` with padding value `(114, 114, 114)`.
3. Convert the padded BGR image to one grayscale channel.
4. Apply CLAHE with `clipLimit=2.0` and `tileGridSize=(8, 8)`.
5. Convert the adjusted grayscale image back to three identical BGR channels.
6. Pass exactly `uint8 640 × 640 × 3` to the selected Ultralytics adapter at
   production confidence `0.25`.
7. Let Ultralytics perform tensor conversion and normalization. Its internal
   640-square geometry step is a no-op for this already-sized input.
8. Clamp/drop invalid adapter boxes and restore valid boxes exactly once from the
   640-square coordinate space to original-image pixels.
9. Map native classes through the explicit selected-model identity mapping.
10. Draw annotations on a copy of the original BGR image.

Image encoding remains outside the detection service and belongs to the future
API/media boundary.

The adapter boundary returns normalized detections independent of YOLO library
objects. API routes never parse raw model tensors.

## Quality score

The backend score is authoritative. `quality-v1` is an explicitly heuristic,
versioned score calculated only after coordinate restoration:

```text
bboxAreaRatio = originalBBoxArea / (originalImageWidth * originalImageHeight)
penalty = sum(classWeight * confidence * (10 + 90 * bboxAreaRatio))
qualityScore = clamp(round(100 - penalty), 0, 100)
```

`round` means nearest-integer rounding with half values rounded upward, matching
the browser fallback.

| Native/service type | Weight |
| --- | ---: |
| `crazing` | 1.25 |
| `inclusion` | 1.10 |
| `patches` | 0.90 |
| `pitted_surface` | 1.00 |
| `rolled-in_scale` | 1.20 |
| `scratches` | 0.85 |

Each detection contributes a count baseline through the constant `10`, then
confidence and original-image area scale its penalty. Clean images score 100;
the result is an integer clamped to the inclusive 0–100 range. This heuristic is
authoritative for application behavior but is not a calibrated safety or
metrology measurement.

## Storage

SQLite stores metadata and relative media paths, not base64 bodies. Media writes,
metadata commits, deletion, and clearing must leave no orphaned files after a
successful operation. History list queries never load image bytes.
