# Verification matrix

Statuses describe the repository state represented by committed implementation
and retained runtime records. `PASS` has a complete implementation/check path,
`PARTIAL` still has a documented limitation, and `PLANNED` has no implementation
claim.

| Requirement | Status | Implementation or plan | Check / record |
| --- | --- | --- | --- |
| Repository structure | PASS | Required frontend, FastAPI, detection, storage, model, shared-contract, test, and verification paths are present | `python scripts/validate_structure.py` |
| Comprehensive root README | PASS | Platform-neutral setup, run, model installation, API, structure, and validation are documented | `README.md` |
| Full application starts without errors | PASS | FastAPI composition, frontend build paths, model installation, and the current Bayes-PFL default production-service path are verified locally | `python scripts/validate.py`; `python scripts/probe_models.py --device cpu` |
| Model registry and local paths | PASS | Manifest v3 registers Bayes-PFL default, legacy multiclass YOLO, steel specialist, and concrete specialist with pinned artifacts | manifest/schema/installer tests |
| Selectable models | PASS | `/api/models`, upload, live mode, dashboard, and samples share one model selection; guided models expose `requiresProductName` | API/frontend tests |
| Guided product context | PASS | `productName` is accepted by inspect/stream, required for Bayes-PFL, propagated through frontend state, and included in the runtime cache key | runtime/API/frontend tests |
| Required TanStack routes | PASS | Dashboard, inspect, history, and details are implemented | frontend build |
| Drag/drop and file selection | PASS | `ImageUploader.jsx` implements drop and explicit file selection with client validation | frontend tests/build |
| Canvas bounding boxes | PASS | Viewer renders original pixels with a separate rescaled Canvas overlay | frontend implementation and retained browser observations |
| Defect list fields | PASS | Type, confidence, and coordinates are displayed | frontend implementation/build |
| History date/type filters | PASS | Frontend sends canonical filters and FastAPI applies combined SQLite filtering | API/storage tests |
| `POST /api/inspect` | PASS | Bounded multipart read, content decode, model/context selection, inference call, media/SQLite persistence, and detail response are implemented | API integration tests and retained persistence records |
| OpenCV/model preprocessing | PASS | Ultralytics uses shared letterbox profiles; Bayes-PFL owns 518x518 stretch and CLIP normalization | detection/runtime tests and manifest |
| History GET/DELETE/clear | PASS | List/detail/delete/clear use persisted metadata and owned media cleanup | API/storage tests |
| Required error messages | PASS | Unsupported content, upload limit, model lookup/install failure, guided-context validation, and inference failure map at the HTTP boundary | API integration tests |
| Real model inference | PASS | A local CPU production-service probe qualified all four exposed models, including the current Bayes-PFL default, and retained the generated runtime record | `docs/evidence/models/model-registry-acceptance.json` |
| Accurate boxes/types/confidence | PARTIAL | Native type preservation, finite confidence, positive bounded original-image boxes, and geometry ownership are enforced; benchmark accuracy is not claimed | core/service tests and retained runtime records |
| Annotated backend image | PASS | DetectionService annotates original-size pixels; API stores and returns annotated plus original images separately | service/API persistence checks |
| Persisted timestamped records | PASS | SQLite metadata, relative media paths, detail hydration, deletion, and cleanup are implemented | storage/API tests |
| At least 10 demo images | PASS | Twelve attributed VisA demo images remain tracked with separate source truth and model observations | demo validator and retained records |
| Code quality and separation | PASS | API, detection, storage, frontend, and shared-contract boundaries plus repository-local structure checks are implemented | `python scripts/validate.py` |
| Live detection bonus | PASS | JPEG frames use the selected model/context through `/api/stream` without persistence | API/frontend tests and retained records |
| Quality-score bonus | PASS | Backend-authoritative 0-100 quality score is returned and persisted; UI labels higher values as better quality | service/API/frontend tests |
| CSV export bonus | PASS | Server export reuses canonical history filters and CSV projection | API/storage tests and retained CSV record |

Historical runtime bundles are kept immutable and validated against the source
snapshots they recorded. They are not rewritten to make a retired model appear
current. The current model registry record comes from the completed local CPU
production-service probe and covers all four exposed models.
