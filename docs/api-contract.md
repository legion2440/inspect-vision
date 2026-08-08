# API contract

This document is the authoritative frontend/backend boundary. JSON fields use
camelCase. Dates are UTC ISO 8601 strings. Bounding boxes use original-image
pixels with `(0, 0)` at the top-left.

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
  "defects": [
    {
      "type": "scratches",
      "confidence": 0.92,
      "boundingBox": { "x": 120, "y": 85, "width": 45, "height": 30 }
    }
  ],
  "totalDefects": 1,
  "qualityScore": 82,
  "status": "failed",
  "model": { "id": "neu-defect-yolov8", "displayName": "Steel Surface" }
}
```

Contract invariants:

- `imageUrl` is the server-rendered annotated image and Download target.
- `originalImageUrl` is unmodified and is the Canvas viewer source.
- `imageWidth` and `imageHeight` define the original-image coordinate space.
- `confidence` is finite and between `0` and `1`.
- Boxes are clamped to the image boundary and have positive width and height.
- `totalDefects` equals `defects.length`.
- `status` is `passed` only when `totalDefects` is zero.
- `qualityScore` is an authoritative integer from `0` to `100`; higher is better.
- `model.id` is the persisted manifest model ID and `model.displayName` is its
  operator-facing label.
- Historical records remain readable after a model is removed; the persisted ID
  becomes the display fallback.
- `type` preserves the checkpoint-native class name without semantic remapping.

## Model selection fields

`modelId` is optional for inspect and stream requests. Omission selects the
registry `defaultModelId`.

`productName` is a multipart text field used only by category-guided models. The
model registry advertises this requirement with `requiresProductName`. For
`bayespfl-general-v1`, `productName` must be a concrete category such as
`metal_nut`, `capsule`, or `bottle`; it is passed to the native Bayes-PFL prompt
path. Specialist and ordinary Ultralytics models ignore this field.

## Endpoints

### `POST /api/inspect`

Accepts `multipart/form-data` with required field `image`, optional `modelId`, and
conditional `productName`. Supported content is JPEG or PNG up to 10 MiB.
Validation uses decoded content, not only the extension or supplied MIME type.

For a model whose registry entry has `requiresProductName: true`, missing or
blank `productName` returns HTTP 422. Successful requests return the full detail
record and persist metadata plus original and annotated media.

### `GET /api/history`

Returns inspection summaries newest first. Summaries omit `imageUrl` and
`originalImageUrl`.

Optional filters are `from` and `to` inclusive UTC dates in `YYYY-MM-DD`, exact
lowercase `type`, and case-insensitive substring `q` over inspection ID or source
filename. Invalid dates or `from > to` return HTTP 422. Filters combine with AND
semantics.

### `GET /api/history/{id}`

Returns the full inspection detail including both image fields.

### `DELETE /api/history/{id}`

Deletes metadata and owned media and returns:

```json
{ "inspectionId": "insp_20260803_001", "deleted": true }
```

### `POST /api/history/clear`

Clears all metadata and owned media and returns:

```json
{ "cleared": 12 }
```

### `POST /api/stream`

Accepts one JPEG frame in multipart field `frame`, optional `modelId`, and the
same conditional `productName` used by inspect. Validation rejects PNG and
undecodable payloads. The endpoint uses the same detection runtime and inference
lock as `/api/inspect`; frames are not persisted.

```json
{
  "frameWidth": 1280,
  "frameHeight": 720,
  "defects": [],
  "totalDefects": 0,
  "qualityScore": 100,
  "status": "passed",
  "model": {
    "id": "bayespfl-general-v1",
    "displayName": "General Manufacturing (Bayes-PFL)"
  }
}
```

### `GET /api/models`

Returns the exposed validated registry projection without loading checkpoints:

```json
[
  {
    "id": "bayespfl-general-v1",
    "displayName": "General Manufacturing (Bayes-PFL)",
    "role": "general",
    "domain": "Cross-domain manufacturing anomaly localization",
    "description": "Category-guided anomaly localization for varied manufactured products...",
    "classes": ["anomaly"],
    "preprocessingProfile": "bayespfl-stretch",
    "requiresProductName": true,
    "isDefault": true,
    "installed": true
  }
]
```

`installed` means every required local model artifact and runtime source passes
its pinned integrity checks. Uninstalled models remain visible so the UI can show
the exact installer command.

The current exposed set is Bayes-PFL general, legacy multiclass general YOLO,
steel surface specialist, and concrete/structural crack specialist. Bayes-PFL
emits only the native generic class `anomaly`; the specialists provide native
semantic defect classes for their supported domains.

### `GET /api/samples`

Returns the offline showcase manifest as `notice`, `datasets`, and `samples`.
Each sample contains source metadata and an image URL but no precomputed model
output. Source labels are dataset metadata, not model predictions.

The recommended model is advisory. The frontend never changes the operator's
selection automatically; `Inspect sample` sends the source image through normal
`POST /api/inspect` with the current model and, when required, current product
category.

### `GET /api/samples/{id}/image`

Returns the local JPEG or PNG for a manifest sample ID. Filesystem paths are
never accepted as request input. Unknown IDs return HTTP 404.

### `GET /api/export`

Accepts the same history filters and returns `text/csv; charset=utf-8` with
newest-first rows. Column order is:

```text
inspectionId,timestamp,defectCount,types,qualityScore,status
```

`types` contains unique defect types in first-appearance order separated by
` | `. Output is UTF-8 without BOM, LF line endings, standard CSV quoting, and
`Content-Disposition: attachment; filename="inspection-history.csv"`.

## Error contract

FastAPI errors use `{ "detail": "message" }`.

| Condition | HTTP | Detail |
| --- | ---: | --- |
| Undecodable or unsupported image | 415 | `Unsupported file type` |
| More than 10 MiB | 413 | `File size exceeds 10MB limit` |
| Guided model missing `productName` | 422 | `Product name is required for this detection model` |
| Model inference failure after successful load | 500 | `Detection model error` |
| Unknown `modelId` | 404 | `Detection model not found` |
| Registered model missing or invalid | 409 | Message includes `python scripts/install_models.py --model <id>` |
| Unknown inspection ID | 404 | `Inspection not found` |
| Unknown showcase sample ID | 404 | `Sample not found` |

Internal paths, stack traces, model paths, and original unsafe filenames are not
returned. Filenames are sanitized before filesystem use.
