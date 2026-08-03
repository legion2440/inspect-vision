# Audit evidence matrix

Statuses describe the repository today: `PASS` has executable evidence,
`PARTIAL` has only part of the required end-to-end path, and `PLANNED` has no
implementation claim.

| Audit item | Status | Implementation or plan | Evidence |
| --- | --- | --- | --- |
| Repository structure | PARTIAL | Frontend, model registry, and detection core exist; API/storage remain planned | `.venv/Scripts/python.exe scripts/validate_structure.py` |
| Comprehensive root README | PARTIAL | Current state and commands documented; backend setup awaits implementation | `README.md` |
| Full application starts without errors | PLANNED | Frontend builds; backend is absent | `npm --prefix frontend run build` |
| Model paths in environment | PASS | Selected local path, ignored weights, manifest hashes, and integrity validation | `.env.example`, `backend/models/model-manifest.json`, model probe evidence |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details | Production build and browser smoke |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` | Browser upload smoke with local JPG |
| Canvas bounding boxes | PASS | Original-image viewer with rescaled Canvas | Details/upload browser smoke observed one Canvas |
| Defect list fields | PASS | Type, confidence, and coordinates | Frontend implementation and build |
| History date/type filters | PARTIAL | Frontend sends canonical filters; real backend is planned | Mock browser filter smoke returned two scratch rows |
| `POST /api/inspect` | PLANNED | Contract fixed; endpoint absent | `docs/api-contract.md` |
| OpenCV preprocessing | PARTIAL | Letterbox, normalization, and bbox restore utilities are tested; grayscale/CLAHE service is deferred | Detection unit tests; `docs/env-model-contract.md` |
| History GET/DELETE/clear | PLANNED | Contract fixed; endpoints absent | `docs/api-contract.md` |
| Required error messages | PLANNED | Exact HTTP mapping fixed; backend absent | `docs/api-contract.md` |
| Real YOLO/CNN inference | PASS | Two registered Ultralytics checkpoints execute through the normalized core | `docs/evidence/models/detection-core-acceptance.json` |
| Accurate boxes/types/confidence | PARTIAL | Native names, finite confidence, and bounded original-image boxes are verified; benchmark accuracy is not | Core acceptance evidence and unit tests |
| Annotated backend image | PARTIAL | Dual-image frontend contract implemented; backend absent | Frontend build plus API contract |
| Persisted timestamped records | PLANNED | SQLite/media design fixed; implementation absent | `ARCHITECTURE.md` |
| Code quality and separation | PARTIAL | Detection/API/storage boundaries plus real Python and JavaScript import checks exist | `.venv/Scripts/python.exe scripts/validate.py` |
| Live detection bonus | PARTIAL | Actual dimensions and sequential frame client implemented; endpoint absent | Browser/build checks; backend runtime pending |
| Severity bonus | PARTIAL | Backend-authoritative contract plus client fallback; backend absent | Frontend utility tests |
| CSV export bonus | PARTIAL | Real endpoint integration plus mock fallback; endpoint absent | Frontend utility tests; server runtime pending |

README statements alone are not runtime evidence. Update a row to `PASS` only
when the complete real path has repeatable evidence tied to a source commit.
