# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates one validated lazy `DetectionRuntimeManager`, one `InspectionStorage`, and one shared inference lock. Factories remain injectable so HTTP tests can exercise route/storage behavior without loading model weights.

Implemented routes:

- `POST /api/inspect`: bounded upload validation, selected-model inference, annotation and persistence;
- `GET /api/models`: exposed registry metadata and guided-category capabilities;
- `GET /api/samples` and `GET /api/samples/{id}/image`: the 14-item operator showcase from `sample_catalog.py` and pinned image delivery by catalog ID;
- history list/detail/delete/clear;
- `POST /api/stream`: JPEG inference without persistence;
- `GET /api/export`: canonical filtered CSV.

Bayes-PFL `productName` context is normalized and validated before inference. Model and category selection remain independent. A sample may supply its category context but never auto-selects another model. Sample inspection reuses the ordinary `/api/inspect` path.

The twelve VisA files under `backend/samples/demo/` are separate demo/evidence assets and are not served as the operator sample catalog.

Image decoding and history-filter parsing remain shared route utilities so inspect, stream, history and export cannot silently diverge. Detection and persistence logic stay in their owning modules.
