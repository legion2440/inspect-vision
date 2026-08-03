# Audit evidence matrix

Statuses describe the repository today: `PASS` has executable evidence,
`PARTIAL` has only part of the required end-to-end path, and `PLANNED` has no
implementation claim.

| Audit item | Status | Implementation or plan | Evidence |
| --- | --- | --- | --- |
| Repository structure | PARTIAL | Frontend and architecture scaffold exist; backend files are planned | `python scripts/validate_structure.py` |
| Comprehensive root README | PARTIAL | Current state and commands documented; backend setup awaits implementation | `README.md` |
| Full application starts without errors | PLANNED | Frontend builds; backend is absent | `npm --prefix frontend run build` |
| Model paths in environment | PARTIAL | Contract and template exist; model is absent | `.env.example`, `docs/env-model-contract.md` |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details | Production build and browser smoke |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` | Browser upload smoke with local JPG |
| Canvas bounding boxes | PASS | Original-image viewer with rescaled Canvas | Details/upload browser smoke observed one Canvas |
| Defect list fields | PASS | Type, confidence, and coordinates | Frontend implementation and build |
| History date/type filters | PARTIAL | Frontend sends canonical filters; real backend is planned | Mock browser filter smoke returned two scratch rows |
| `POST /api/inspect` | PLANNED | Contract fixed; endpoint absent | `docs/api-contract.md` |
| OpenCV preprocessing | PLANNED | Pipeline contract fixed; implementation absent | `docs/env-model-contract.md` |
| History GET/DELETE/clear | PLANNED | Contract fixed; endpoints absent | `docs/api-contract.md` |
| Required error messages | PLANNED | Exact HTTP mapping fixed; backend absent | `docs/api-contract.md` |
| Real YOLO/CNN inference | PLANNED | Adapter and provenance rules fixed; model unselected | `docs/env-model-contract.md` |
| Accurate boxes/types/confidence | PLANNED | Requires selected model and labeled validation set | No runtime evidence yet |
| Annotated backend image | PARTIAL | Dual-image frontend contract implemented; backend absent | Frontend build plus API contract |
| Persisted timestamped records | PLANNED | SQLite/media design fixed; implementation absent | `ARCHITECTURE.md` |
| Code quality and separation | PARTIAL | Boundaries, validators, frontend modules, and contracts exist | `make validate` |
| Live detection bonus | PARTIAL | Actual dimensions and sequential frame client implemented; endpoint absent | Browser/build checks; backend runtime pending |
| Severity bonus | PARTIAL | Backend-authoritative contract plus client fallback; backend absent | Frontend utility tests |
| CSV export bonus | PARTIAL | Real endpoint integration plus mock fallback; endpoint absent | Frontend utility tests; server runtime pending |

README statements alone are not runtime evidence. Update a row to `PASS` only
when the complete real path has repeatable evidence tied to a source commit.
