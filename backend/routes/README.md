# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates
one selected `DetectionService`, one `InspectionStorage`, and one inference lock.
Factories are injectable so HTTP tests exercise the real route/storage boundary
without loading model weights.

Implemented routes:

- `POST /api/inspect`: bounded multipart read, content decode, serialized
  inference, same-format annotation encoding, persistence, and detail response;
- `GET /api/history`: combined server-side date/type/query filters;
- `GET /api/history/{id}`: persisted detail with dual data URLs;
- `DELETE /api/history/{id}` and `POST /api/history/clear`: metadata plus media
  cleanup;
- `POST /api/stream`: JPEG-only content validation and serialized selected-model
  inference without metadata or media persistence;
- `GET /api/export`: canonical history filters, newest-first ordering, and
  UTF-8 CSV projection.

Image decoding and history-filter parsing are shared route utilities so inspect,
stream, history, and export cannot silently diverge. Detection and persistence
logic stay in their owning modules.
