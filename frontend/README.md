# Inspect-Vision — frontend

React 18 + Vite + TanStack Router (file-based). Styling comes from the Industry
design system in `src/styles/industry.css`; `src/styles/app.css` composes its
tokens.

## Run

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The default is `VITE_USE_MOCK=false`: browser calls use relative `/api` URLs and
the development server proxies them to `http://localhost:8000`. Set optional
`VITE_API_BASE_URL` only for a cross-origin production backend. Set
`VITE_USE_MOCK=true` explicitly for bundled standalone mock responses.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Dashboard statistics, model-aware quick upload, recent inspections |
| `/inspect` | Image-file and live-stream inspection with Canvas overlay |
| `/samples` | Attributed sample cards inspected with the current global model |
| `/history` | Date/type/text filters and CSV export |
| `/details/:id` | Full persisted record and defect breakdown |

## Backend contract used by the client

| Method | Path | Client use |
| --- | --- | --- |
| GET | `/api/models` | model capabilities, default and installed state |
| GET | `/api/samples` | showcase metadata |
| GET | `/api/samples/{id}/image` | source showcase image |
| POST | `/api/inspect` | multipart image inference |
| POST | `/api/stream` | multipart JPEG live-frame inference |
| GET | `/api/history?from&to&type&q` | history |
| GET | `/api/history/{id}` | detail |
| DELETE | `/api/history/{id}` | delete |
| POST | `/api/history/clear` | clear |
| GET | `/api/export?from&to&type&q` | server CSV |

Both inference endpoints send `modelId`. When the selected `/api/models` entry
has `requiresProductName: true`, the UI also requires and sends multipart
`productName`. Bayes-PFL uses that concrete category in its native prompt path;
ordinary models do not need it.

The default registry model is `bayespfl-general-v1`. Its UI caption reflects
`stretch 518² · CLIP normalization`; steel shows grayscale + CLAHE and ordinary
color YOLO models show their color letterbox profile.

Inspection response shape:

```json
{
  "inspectionId": "insp_20250113_001",
  "timestamp": "2025-01-13T14:30:00Z",
  "imageUrl": "data:image/jpeg;base64,...annotated...",
  "originalImageUrl": "data:image/jpeg;base64,...original...",
  "imageWidth": 1920,
  "imageHeight": 1080,
  "fileName": "housing_04_2b.jpg",
  "defects": [
    {
      "type": "anomaly",
      "confidence": 0.76,
      "boundingBox": { "x": 120, "y": 85, "width": 45, "height": 30 }
    }
  ],
  "totalDefects": 1,
  "qualityScore": 91,
  "status": "failed",
  "model": {
    "id": "bayespfl-general-v1",
    "displayName": "General Manufacturing (Bayes-PFL)"
  }
}
```

`imageUrl` is the backend-rendered annotated image used by Download.
`originalImageUrl` is the unmodified source used by `InspectionViewer` with its
interactive Canvas overlay. The backend `qualityScore` is authoritative and the
UI labels it as Quality Score; higher values mean better quality.

## Structure

```text
src/
├── components/   uploader, viewer, overlay, defect list, model selector, live stream
├── routes/       dashboard, inspect, samples, history, details
├── hooks/        inspection and live inference hooks
├── context/      shared inspection/model/product state
├── utils/        API client, validation, quality fallback, CSV, formatting
├── mocks/        standalone API-compatible responses
└── styles/       Industry design system and app composition
```

## Notes

- Upload guards mirror backend image type and 10 MiB limits.
- `DefectOverlay` draws source-space boxes on Canvas and rescales through
  `ResizeObserver`.
- Live mode uses actual camera dimensions and allows only one frame request at a
  time.
- Changing model or product context aborts in-flight upload/live work and clears
  stale results.
- Dashboard Quick Upload and Samples share the same selected model and product
  context. Sample recommendations are advisory only.
- Uninstalled entries stay visible with their exact
  `python scripts/install_models.py --model <id>` command.
- History defect filters are derived from registry-native class names.
