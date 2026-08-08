# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates
one validated lazy `DetectionRuntimeManager`, one `InspectionStorage`, and one
shared inference lock. Factories remain injectable so HTTP tests exercise route
and storage boundaries without loading model weights.

Implemented routes:

- `POST /api/inspect`: bounded multipart read, content decode, selected-model
  inference, annotation encoding, persistence, and detail response;
- `GET /api/models`: exposed registry metadata, installed/default state,
  `requiresProductName`, and curated guided-category examples;
- `GET /api/samples` and `GET /api/samples/{id}/image`: pinned MVTec AD showcase
  metadata and manifest-ID-only remote image proxying;
- history list/detail/delete/clear;
- `POST /api/stream`: JPEG-only serialized inference without persistence;
- `GET /api/export`: canonical history filters and UTF-8 CSV projection.

Inspect and stream accept optional `modelId`. Models declaring
`requiresProductName=true` require guided product/category context. Bayes-PFL
context is normalized before inference: `_` is accepted as a space separator,
input is lowercased, length is 2-40 characters, only Latin letters/spaces/
hyphens are accepted, and at most three words are allowed. Invalid guided input
returns HTTP 422.

Model and category selection remain independent. A steel or concrete category
does not automatically route to a specialist. Showcase inspection deliberately
reuses the ordinary `/api/inspect` path with the operator's current model; a
sample supplies its own category context only.

Image decoding and history-filter parsing are shared route utilities so inspect,
stream, history, and export cannot silently diverge. Detection and persistence
logic stay in their owning modules.
