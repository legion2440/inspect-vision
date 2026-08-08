# Inspect-Vision — frontend

React 18 + Vite + TanStack Router. Styling uses the Industry design-system tokens
from `src/styles/industry.css` and application composition in `src/styles/app.css`.

## Run

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The default is `VITE_USE_MOCK=false`: relative `/api` requests are proxied to
`http://localhost:8000`. Mock mode is explicit.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Dashboard statistics, model-aware quick upload, recent inspections |
| `/inspect` | Image-file/live-stream inspection with centered mode selector and Canvas overlay |
| `/samples` | Four MVTec AD good/bad pairs inspected with the current model |
| `/history` | Date/type/text filters and CSV export |
| `/details/:id` | Persisted record and defect breakdown |

## Model and category controls

`GET /api/models` is the UI source of truth. The currently exposed operator list
contains Bayes-PFL general plus steel and concrete specialists. The rejected
legacy general YOLO is not shown.

When a selected model declares `requiresProductName: true`, `ModelSelector`
shows a datalist-style combobox. Curated suggestions come from the API and are
labeled by evidence source, while arbitrary custom zero-shot values are still
allowed subject to server validation.

Model selection and category selection are independent. Choosing `Steel surface`
or `Concrete surface` does not switch models automatically; this allows an
operator to compare the general Bayes localizer with a manually selected
specialist on the same input.

A Samples card sets its own product/category context before inspection but keeps
the current model. The current showcase is Bottle, Capsule, Screw, and Metal nut,
each with one GOOD and one BAD MVTec AD source.

## Backend contract used by the client

| Method | Path | Client use |
| --- | --- | --- |
| GET | `/api/models` | model capabilities, category examples, default/installed state |
| GET | `/api/samples` | pinned MVTec showcase metadata |
| GET | `/api/samples/{id}/image` | same-origin proxy for pinned source image |
| POST | `/api/inspect` | multipart image inference |
| POST | `/api/stream` | multipart JPEG live-frame inference |
| GET | `/api/history?from&to&type&q` | history |
| GET | `/api/history/{id}` | detail |
| DELETE | `/api/history/{id}` | delete |
| POST | `/api/history/clear` | clear |
| GET | `/api/export?from&to&type&q` | server CSV |

The Bayes UI caption reflects `stretch 518² · CLIP normalization`; steel shows
its enhanced profile and concrete uses standard-color letterbox preprocessing.
Bayes native output is `anomaly`; history filter choices are derived from classes
of currently exposed models rather than hard-coded retired classes.

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
- Live mode permits only one frame request at a time.
- Changing model or product context aborts in-flight work and clears stale
  results.
- Dashboard Quick Upload, Inspect, and Samples share the same selected model and
  product context.
- Uninstalled exposed entries show their exact installer command.
