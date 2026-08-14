# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates one validated lazy `DetectionRuntimeManager`, one `InspectionStorage`, and one shared inference lock. Factories remain injectable so HTTP tests can exercise route/storage behavior without loading model weights.

Implemented routes include inspect, models, the local sample catalog, history, stream, and CSV export.

`GET /api/samples` exposes the fourteen records defined by `sample_catalog.py`. `GET /api/samples/{id}/image` serves the corresponding committed file from `backend/samples/demo/`. These are the same fourteen images used as the project demo set; there is no second sample corpus and no runtime network fetch.

Bayes-PFL `productName` context is normalized and validated before inference. Model and category selection remain independent. A sample may supply its category context but never auto-selects another model. Sample inspection reuses the ordinary `/api/inspect` path.

Image decoding and history-filter parsing remain shared route utilities so inspect, stream, history and export cannot silently diverge. Detection and persistence logic stay in their owning modules.
