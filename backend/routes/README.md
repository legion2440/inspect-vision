# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates
one validated lazy `DetectionRuntimeManager`, one `InspectionStorage`, and one
shared inference lock. Factories remain injectable so HTTP tests exercise route
and storage boundaries without loading model weights.

Implemented routes:

- `POST /api/inspect`: bounded multipart read, content decode, model-selected
  inference, same-format annotation encoding, persistence, and detail response;
- `GET /api/models`: registry metadata, default/installed state, and the
  `requiresProductName` capability without loading checkpoints;
- `GET /api/samples` and `GET /api/samples/{id}/image`: attributed source
  showcase metadata and manifest-ID-only image retrieval;
- `GET /api/history`, `GET /api/history/{id}`, `DELETE /api/history/{id}`, and
  `POST /api/history/clear`: filtered inspection history and media lifecycle;
- `POST /api/stream`: JPEG-only serialized inference without persistence;
- `GET /api/export`: canonical history filters and UTF-8 CSV projection.

Inspect and stream accept optional `modelId`. Models that declare
`requiresProductName=true` additionally require multipart field `productName`;
missing or blank context returns HTTP 422 before inference. Ordinary models do
not require that field.

Image decoding and history-filter parsing are shared route utilities so inspect,
stream, history, and export cannot silently diverge. Detection and persistence
logic stay in their owning modules. Showcase inspection deliberately reuses
`POST /api/inspect`; there is no sample-specific inference route.
