# Audit evidence matrix

Statuses describe the repository today: `PASS` has executable evidence,
`PARTIAL` has only part of the required end-to-end path, and `PLANNED` has no
implementation claim.

| Audit item | Status | Implementation or plan | Evidence |
| --- | --- | --- | --- |
| Repository structure | PASS | Required frontend, FastAPI, detection, storage, model, shared contract, test, and evidence paths exist | `.venv/Scripts/python.exe scripts/validate_structure.py` |
| Comprehensive root README | PASS | Setup, run, validation, evidence, model, and known-deferred scope are documented | `README.md` |
| Full application starts without errors | PASS | Uvicorn lifespan loads the real selected model; frontend production build passes | API persistence evidence; `npm --prefix frontend run build` |
| Model paths in environment | PASS | Selected local path, ignored weights, manifest hashes, and integrity validation | `.env.example`, `backend/models/model-manifest.json`, model probe evidence |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details | Production build and browser smoke |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` | Browser upload smoke with local JPG |
| Canvas bounding boxes | PASS | Original-image viewer with rescaled Canvas | Details/upload browser smoke observed one Canvas |
| Defect list fields | PASS | Type, confidence, and coordinates | Frontend implementation and build |
| History date/type filters | PASS | Frontend sends canonical filters and FastAPI applies combined SQLite date/type/query filtering | Frontend, storage, and API tests |
| `POST /api/inspect` | PASS | Exact bounded multipart read, content decode, selected service inference, media/SQLite persistence, and detail response | Saved loopback POST JSON and API tests |
| OpenCV preprocessing | PASS | Decode validation, one 640-square letterbox, grayscale, CLAHE, three-channel conversion, and one original-coordinate restore | Detection tests; `docs/evidence/inspection-service/inspection-service-acceptance.json` |
| History GET/DELETE/clear | PASS | List/detail/delete/clear use persisted metadata and owned media cleanup | Saved list/detail/delete JSON; API/storage tests |
| Required error messages | PASS | Unsupported content, >10 MiB, model failure, and missing ID map exactly | API integration tests |
| Real YOLO/CNN inference | PASS | Two registered Ultralytics checkpoints execute through the normalized core | `docs/evidence/models/detection-core-acceptance.json` |
| Accurate boxes/types/confidence | PARTIAL | Native mapping, finite confidence, and positive bounded original-image boxes are verified; benchmark accuracy is not | Core and inspection-service acceptance evidence |
| Annotated backend image | PASS | DetectionService annotation is encoded in source format, persisted, and returned as `imageUrl`; original remains separate | Service outputs plus API persistence evidence |
| Persisted timestamped records | PASS | SQLite record, relative media paths, byte-exact original, annotated dimensions, reopen, and cleanup are verified | API persistence evidence; storage/API tests |
| At least 10 demo images | PASS | Twelve unmodified VisA images include 4 normal and 8 anomaly samples, 4 product categories, 10 source defect labels, tracked annotation CSVs, CC BY 4.0 provenance, and separate model observations | Demo manifest validator and `docs/evidence/demo-samples/demo-samples-acceptance.json` |
| Code quality and separation | PASS | Pydantic contract, API/detection/storage boundaries, dependency injection, failure tests, and real import checks exist | `.venv/Scripts/python.exe scripts/validate.py` |
| Live detection bonus | PASS | Content-verified JPEG frames use the selected service and shared inference lock without persistence | Saved loopback stream/history snapshots; API concurrency and failure tests |
| Severity bonus | PASS | Backend-authoritative quality-v1 is persisted and delivered through POST/history/detail | Service and API evidence plus backend/frontend tests |
| CSV export bonus | PASS | Server export reuses all canonical history filters, newest-first query semantics, exact columns, escaping, and download headers | Saved filtered history/CSV parity evidence; unit/integration tests |

README statements alone are not runtime evidence. Update a row to `PASS` only
when the complete real path has repeatable evidence tied to a source commit.
