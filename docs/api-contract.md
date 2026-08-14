# API contract

This document is the authoritative frontend/backend boundary. JSON fields use camelCase. Dates are UTC ISO 8601 strings. Bounding boxes use original-image pixels with `(0, 0)` at the top-left.

## Inspection detail

```json
{
  "inspectionId": "insp_20260803_001",
  "timestamp": "2026-08-03T14:30:00Z",
  "fileName": "housing_04.jpg",
  "imageUrl": "data:image/jpeg;base64,...annotated...",
  "originalImageUrl": "data:image/jpeg;base64,...original...",
  "imageWidth": 1920,
  "imageHeight": 1080,
  "defects": [{"type":"scratches","confidence":0.92,"boundingBox":{"x":120,"y":85,"width":45,"height":30}}],
  "totalDefects": 1,
  "qualityScore": 82,
  "status": "failed",
  "model": {"id":"neu-defect-yolov8","displayName":"Steel Surface"}
}
```

Invariants: `imageUrl` is annotated, `originalImageUrl` is the Canvas source, boxes use original-image coordinates, confidence is finite in `[0,1]`, boxes have positive bounded area, `totalDefects == defects.length`, `status` is `passed` only with zero defects, `qualityScore` is authoritative 0-100, and native class names are not semantically remapped.

## Model selection

`modelId` is optional for inspect/stream; omission selects `defaultModelId`. Guided models use multipart `productName`. Bayes-PFL normalizes underscores/spaces/case and requires 2-40 Latin-letter/space/hyphen characters with at most three words. Invalid or missing guided context returns HTTP 422. `productNamePresets` are curated examples, not a whitelist.

## Endpoints

### `POST /api/inspect`
Accepts JPEG/PNG `image` up to 10 MiB plus optional `modelId` and conditional `productName`. Validation uses decoded content. Successful requests persist metadata, original media and annotated media and return the full record.

### `POST /api/stream`
Accepts one JPEG `frame` plus optional model/context, reuses the detection runtime, and does not persist.

### `GET /api/models`
Returns the exposed registry: default `bayespfl-general-v1`, `neu-defect-yolov8`, and `concrete-crack-yolov8`. Uninstalled exposed entries remain visible with their installer command.

### `GET /api/samples`

Returns `notice`, dataset attribution metadata, and the fourteen records from the single local operator/demo corpus. The catalog contains eight MVTec Bayes-PFL examples (Bottle, Capsule, Screw, and Metal nut good/bad pairs), three steel examples, and three concrete/crack examples.

Each sample includes its stable ID, product/category context, source labels, recommended model, filename/media type, and same-origin `imageUrl`. Source labels describe dataset metadata, not model predictions. Opening or inspecting a sample never changes the selected model automatically.

### `GET /api/samples/{id}/image`

Serves the matching committed file from `backend/samples/demo/`. Request input is only the known sample ID; filesystem paths and arbitrary URLs are never accepted. Unknown IDs return HTTP 404. The endpoint has no runtime network dependency.

The same fourteen files are the repository demo images and directly satisfy the `at least 10 demo images` acceptance requirement.

### `GET /api/export`
Uses the same history filters and returns UTF-8 CSV with `inspectionId,timestamp,defectCount,types,qualityScore,status`.

## Error contract

| Condition | HTTP | Detail |
| --- | ---: | --- |
| Unsupported/undecodable image | 415 | `Unsupported file type` |
| More than 10 MiB | 413 | `File size exceeds 10MB limit` |
| Bayes-PFL category missing | 422 | `Product / category is required for Bayes-PFL` |
| Invalid guided category | 422 | Specific validation message |
| Inference failure | 500 | `Detection model error` |
| Unknown model | 404 | `Detection model not found` |
| Exposed model not installed | 409 | Includes exact installer command |
| Unknown inspection | 404 | `Inspection not found` |
| Unknown sample | 404 | `Sample not found` |
| Pinned sample unavailable/changed | 502 | Pinned-source retrieval/integrity message |

Internal paths, stack traces, model paths and unsafe original filenames are not returned.
