# Audit evidence matrix

Statuses describe the repository today: `PASS` has executable evidence,
`PARTIAL` has only part of the required end-to-end path, and `PLANNED` has no
implementation claim.

| Audit item | Status | Implementation or plan | Evidence |
| --- | --- | --- | --- |
| Repository structure | PARTIAL | Frontend, detection service, and storage exist; FastAPI remains planned | `.venv/Scripts/python.exe scripts/validate_structure.py` |
| Comprehensive root README | PARTIAL | Current state and commands documented; backend setup awaits implementation | `README.md` |
| Full application starts without errors | PLANNED | Frontend builds; backend is absent | `npm --prefix frontend run build` |
| Model paths in environment | PASS | Selected local path, ignored weights, manifest hashes, and integrity validation | `.env.example`, `backend/models/model-manifest.json`, model probe evidence |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details | Production build and browser smoke |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` | Browser upload smoke with local JPG |
| Canvas bounding boxes | PASS | Original-image viewer with rescaled Canvas | Details/upload browser smoke observed one Canvas |
| Defect list fields | PASS | Type, confidence, and coordinates | Frontend implementation and build |
| History date/type filters | PARTIAL | Frontend sends canonical filters and SQLite applies combined date/type/query filtering; HTTP route remains planned | Frontend and storage unit tests |
| `POST /api/inspect` | PLANNED | Contract fixed; endpoint absent | `docs/api-contract.md` |
| OpenCV preprocessing | PASS | Decode validation, one 640-square letterbox, grayscale, CLAHE, three-channel conversion, and one original-coordinate restore | Detection tests; `docs/evidence/inspection-service/inspection-service-acceptance.json` |
| History GET/DELETE/clear | PARTIAL | Repository/service CRUD and media cleanup exist; endpoints remain planned | `tests/unit/history` |
| Required error messages | PLANNED | Exact HTTP mapping fixed; backend absent | `docs/api-contract.md` |
| Real YOLO/CNN inference | PASS | Two registered Ultralytics checkpoints execute through the normalized core | `docs/evidence/models/detection-core-acceptance.json` |
| Accurate boxes/types/confidence | PARTIAL | Native mapping, finite confidence, and positive bounded original-image boxes are verified; benchmark accuracy is not | Core and inspection-service acceptance evidence |
| Annotated backend image | PARTIAL | DetectionService produces verified original-size annotated BGR copies; API image encoding is planned | Three annotated PNG outputs plus service tests |
| Persisted timestamped records | PARTIAL | SQLite metadata and crash-recoverable original/annotated media lifecycle are tested; HTTP runtime evidence remains planned | `tests/unit/history` |
| Code quality and separation | PARTIAL | Detection/API/storage boundaries, transactional persistence tests, and real Python/JavaScript import checks exist | `.venv/Scripts/python.exe scripts/validate.py` |
| Live detection bonus | PARTIAL | Actual dimensions and sequential frame client implemented; endpoint absent | Browser/build checks; backend runtime pending |
| Severity bonus | PARTIAL | Backend-authoritative quality-v1 is implemented in DetectionService; API delivery is planned | Service evidence plus backend/frontend unit tests |
| CSV export bonus | PARTIAL | Real endpoint integration plus mock fallback; endpoint absent | Frontend utility tests; server runtime pending |

README statements alone are not runtime evidence. Update a row to `PASS` only
when the complete real path has repeatable evidence tied to a source commit.
