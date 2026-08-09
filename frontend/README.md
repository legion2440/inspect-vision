# Inspect-Vision — frontend

React 18 + Vite + TanStack Router. Styling uses the Industry design-system tokens
from `src/styles/industry.css`, application composition in `src/styles/app.css`,
and focused operator-control refinements in `src/styles/ui-controls.css`.

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
| `/samples` | Twelve tracked local VisA demo images with explicit model selection |
| `/history` | Date/type/text filters and CSV export |
| `/details/:id` | Persisted record and defect breakdown |

## Model and category controls

`GET /api/models` is the UI source of truth. The currently exposed operator list
contains Bayes-PFL general plus steel and concrete specialists. The rejected
legacy general YOLO is not shown.

When a selected model declares `requiresProductName: true`, `ModelSelector`
shows an editable combobox rather than a native `datalist`. Clicking the control
opens all curated suggestions, typing filters them, keyboard arrows/Enter/Escape
are supported, and a custom zero-shot value remains valid subject to server
validation. The same aligned control is shared by Dashboard, Inspect, and
Samples.

Model selection and category selection are independent. Choosing `Steel surface`
or `Concrete surface` does not switch models automatically; this allows an
operator to compare the general Bayes localizer with a manually selected
specialist on the same input.

The Samples page is backed by the same twelve VisA images tracked in
`backend/samples/demo/`: Candle, Capsules, Cashew, and Chewing gum, with one
normal and two anomalous source examples per category. A card supplies its own
product/category context before inspection but keeps the current model. Source
labels are dataset ground truth, not model predictions. Images are loaded from
the local backend by manifest ID, so browsing the catalog has no network
dependency.

## Backend contract used by the client

| Method | Path | Client use |
| --- | --- | --- |
| GET | `/api/models` | model capabilities, category examples, default/installed state |
| GET | `/api/samples` | tracked local demo metadata |
| GET | `/api/samples/{id}/image` | local demo image by manifest ID |
| POST | `/api/inspect` | multipart image inference |
| POST | `/api/stream` | multipart JPEG live-frame inference |
| GET | `/api/history?from&to&type&q` | history |
| GET | `/api/history/{id}` | detail |
| DELETE | `/api/history/{id}` | delete |
| POST | `/api/history/clear` | clear |
| GET | `/api/export?from&to&type&q` | server CSV |

The Inspect viewer labels original image dimensions separately from model input.
Bayes shows `stretch 518² · CLIP normalization`; steel shows its enhanced
profile and concrete uses standard-color letterbox preprocessing. Bayes native
output is `anomaly`; history filter choices are derived from classes of currently
exposed models rather than hard-coded retired classes.

## Structure

```text
src/
├── components/   uploader, viewer, overlay, defect list, model selector, live stream
├── routes/       dashboard, inspect, samples, history, details
├── hooks/        inspection and live inference hooks
├── context/      shared inspection/model/product state
├── utils/        API client, validation, quality fallback, CSV, formatting
├── mocks/        standalone API-compatible responses
└── styles/       Industry design system and app/operator composition
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
