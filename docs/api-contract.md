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
  "model": { "name": "neu-defect-yolov8", "version": "1" }
}
```

Contract invariants:

- `imageUrl` is the server-rendered annotated image and Download target.
- `originalImageUrl` is unmodified and is the Canvas viewer source.
- `imageWidth` and `imageHeight` describe both coordinate space and original
  image dimensions.
- `confidence` is finite and between `0` and `1`.
- Boxes are clamped to the image boundary and have positive width and height.
- `totalDefects` equals `defects.length`.
- `status` is `passed` only when `totalDefects` is zero; otherwise it is `failed`.
- `qualityScore` is an integer from `0` to `100` and is authoritative.
- `model.name` is the persisted manifest model ID; `model.version` is the API
  projection version and currently equals `1`.
- `type` preserves one of the selected model's native names: `crazing`,
  `inclusion`, `patches`, `pitted_surface`, `rolled-in_scale`, or `scratches`.

## Endpoints

### `POST /api/inspect`

Accepts `multipart/form-data` with one field named `image`. Supported content is
JPEG or PNG up to 10 MiB. Validation uses decoded content, not only the extension
or client-supplied MIME type.

Returns the full inspection detail and persists metadata plus both image assets.
The original payload is stored byte-for-byte. The annotated image uses the same
detected format (`image/jpeg` or `image/png`) regardless of filename extension or
client-supplied MIME type.

### `GET /api/history`

Returns a JSON array of inspection summaries sorted newest first. Summary records
omit `imageUrl` and `originalImageUrl`.

Optional filters:

- `from`: inclusive UTC date in `YYYY-MM-DD` form.
- `to`: inclusive UTC date in `YYYY-MM-DD` form.
- `type`: exact lowercase defect type; `all` or omission disables it.
- `q`: case-insensitive substring of inspection ID or source filename.

Invalid dates or `from > to` return HTTP 422. The endpoint applies all supplied
filters together.

### `GET /api/history/{id}`

Returns the full inspection detail, including both image fields.

### `DELETE /api/history/{id}`

Deletes metadata and owned media atomically and returns:

```json
{ "inspectionId": "insp_20260803_001", "deleted": true }
```

### `POST /api/history/clear`

Clears all metadata and owned media and returns:

```json
{ "cleared": 12 }
```

### `POST /api/stream`

Accepts one JPEG frame in multipart field `frame`. Only one request at a time is
issued by the frontend. Validation is content-based and rejects PNG or
undecodable payloads even when their filename or MIME type says JPEG. The API
uses the same `DetectionService` instance and inference lock as `/api/inspect`.
The response uses frame pixel coordinates:

```json
{
  "frameWidth": 1280,
  "frameHeight": 720,
  "defects": [],
  "totalDefects": 0,
  "qualityScore": 100,
  "status": "passed"
}
```

Stream frames are not persisted in SQLite or media storage.

### `GET /api/export`

Accepts the same filters as history and returns `text/csv; charset=utf-8` with a
download disposition. Column order is:

```text
inspectionId,timestamp,defectCount,types,qualityScore,status
```

Rows and ordering must match `GET /api/history` for the same filters.
`types` contains unique defect types in first-appearance order separated by
` | `. Output is UTF-8 without a BOM, uses LF line endings and standard CSV
quoting, and returns exactly
`Content-Disposition: attachment; filename="inspection-history.csv"`.

## Error contract

FastAPI errors use `{ "detail": "message" }`.

| Condition | HTTP | Exact detail |
| --- | ---: | --- |
| Undecodable or unsupported image | 415 | `Unsupported file type` |
| More than 10 MiB | 413 | `File size exceeds 10MB limit` |
| Model load or inference failure | 500 | `Detection model error` |
| Unknown inspection ID | 404 | `Inspection not found` |

Internal paths, stack traces, model paths, and original unsafe filenames are not
returned. Filenames are sanitized before any filesystem use.
